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

class CallMessages(BaseModel):
    greetings: str
    prompt: str
    retry: str
    end_message: str
    
class CallSteps(BaseModel):
    step1: Optional[str] = None
    step2: Optional[str] = None
    step3: Optional[str] = None
    accepted: Optional[str] = None
    rejected: Optional[str] = None

class CallRequest(BaseModel):
    config: CallConfig
    messages: CallMessages
    steps: Optional[CallSteps] = None

class CallLog(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    config: CallConfig
    messages: CallMessages
    steps: Optional[CallSteps] = None
    status: str = "PENDING"
    infobip_call_id: Optional[str] = None
    infobip_message_id: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_seconds: int = 0
    error_message: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    events: List[Dict] = Field(default_factory=list)

class CallEvent(BaseModel):
    timestamp: str
    event_type: str
    details: str
    call_id: str

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

async def add_call_event(call_id: str, event_type: str, details: str):
    """Add event to call log and broadcast"""
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "details": details,
        "call_id": call_id
    }
    
    # Update database
    await db.call_logs.update_one(
        {"id": call_id},
        {"$push": {"events": event}}
    )
    
    # Broadcast to SSE
    await broadcast_event(call_id, event)
    
    return event

# Voice name mapping for Infobip (using available voices)
VOICE_MAP = {
    "hera": {"name": "Joanna", "language": "en", "gender": "female"},
    "aria": {"name": "Kendra", "language": "en", "gender": "female"},
    "apollo": {"name": "Matthew", "language": "en", "gender": "male"},
    "zeus": {"name": "Joey", "language": "en", "gender": "male"},
}

async def send_voice_message_infobip(call_id: str, config: CallConfig, messages: CallMessages):
    """Send voice message using Infobip Voice Message API"""
    try:
        client = await get_http_client()
        
        # Get voice settings
        voice_id = config.voice_model.split()[0].lower() if config.voice_model else "hera"
        voice_settings = VOICE_MAP.get(voice_id, VOICE_MAP["hera"])
        
        # Prepare the full message
        full_message = f"{messages.greetings} {messages.prompt}"
        
        # Clean phone numbers
        from_num = config.from_number.replace("+", "").replace(" ", "").replace("-", "")
        to_num = config.recipient_number.replace("+", "").replace(" ", "").replace("-", "")
        
        # Infobip Voice Message API payload (advanced endpoint)
        payload = {
            "messages": [
                {
                    "from": from_num,
                    "destinations": [
                        {
                            "to": to_num
                        }
                    ],
                    "text": full_message,
                    "language": voice_settings["language"],
                    "voice": {
                        "name": voice_settings["name"],
                        "gender": voice_settings["gender"]
                    }
                }
            ]
        }
        
        logger.info(f"Sending voice message to Infobip: {json.dumps(payload)}")
        
        # Send request to Infobip Voice Message API (advanced endpoint)
        response = await client.post("/tts/3/advanced", json=payload)
        
        logger.info(f"Infobip response status: {response.status_code}")
        logger.info(f"Infobip response: {response.text}")
        
        if response.status_code in [200, 201, 202]:
            result = response.json()
            
            # Extract message details
            if result.get("messages") and len(result["messages"]) > 0:
                msg = result["messages"][0]
                message_id = msg.get("messageId")
                status_name = msg.get("status", {}).get("name", "PENDING")
                status_desc = msg.get("status", {}).get("description", "")
                
                # Update call log with Infobip message ID
                await db.call_logs.update_one(
                    {"id": call_id},
                    {"$set": {
                        "infobip_message_id": message_id,
                        "status": "CALLING",
                        "started_at": datetime.now(timezone.utc).isoformat()
                    }}
                )
                
                await add_call_event(call_id, "CALL_INITIATED", f"Voice message sent. Message ID: {message_id}")
                await add_call_event(call_id, "INFOBIP_STATUS", f"Status: {status_name} - {status_desc}")
                
                # Start polling for status updates
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
        error_msg = f"Error sending voice message: {str(e)}"
        logger.error(error_msg)
        await add_call_event(call_id, "CALL_FAILED", error_msg)
        await db.call_logs.update_one(
            {"id": call_id},
            {"$set": {"status": "FAILED", "error_message": error_msg}}
        )
        return {"success": False, "error": str(e)}

async def poll_message_status(call_id: str, message_id: str):
    """Poll Infobip for message delivery status"""
    try:
        client = await get_http_client()
        max_polls = 30  # Poll for up to 5 minutes (30 * 10 seconds)
        poll_count = 0
        
        while poll_count < max_polls:
            await asyncio.sleep(10)  # Wait 10 seconds between polls
            poll_count += 1
            
            try:
                # Get message status from Infobip
                response = await client.get(f"/tts/3/reports?messageId={message_id}")
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get("results") and len(result["results"]) > 0:
                        report = result["results"][0]
                        status = report.get("status", {})
                        status_name = status.get("name", "UNKNOWN")
                        status_desc = status.get("description", "")
                        
                        # Map Infobip status to our status
                        status_mapping = {
                            "PENDING_ENROUTE": "CALLING",
                            "PENDING_ACCEPTED": "CALLING",
                            "DELIVERED_TO_OPERATOR": "RINGING",
                            "DELIVERED_TO_HANDSET": "ESTABLISHED",
                            "DELIVERED": "FINISHED",
                            "REJECTED": "FAILED",
                            "UNDELIVERABLE": "FAILED",
                            "EXPIRED": "FAILED",
                        }
                        
                        new_status = status_mapping.get(status_name, "CALLING")
                        
                        # Update status
                        await db.call_logs.update_one(
                            {"id": call_id},
                            {"$set": {"status": new_status}}
                        )
                        
                        await add_call_event(call_id, f"STATUS_{status_name}", status_desc)
                        
                        # Stop polling if call is finished or failed
                        if new_status in ["FINISHED", "FAILED"]:
                            await db.call_logs.update_one(
                                {"id": call_id},
                                {"$set": {"ended_at": datetime.now(timezone.utc).isoformat()}}
                            )
                            await add_call_event(call_id, "CALL_FINISHED", f"Call completed with status: {status_name}")
                            break
                            
            except Exception as poll_error:
                logger.warning(f"Poll error: {poll_error}")
                
        # If we exhausted polls, mark as finished
        if poll_count >= max_polls:
            await db.call_logs.update_one(
                {"id": call_id},
                {"$set": {
                    "status": "FINISHED",
                    "ended_at": datetime.now(timezone.utc).isoformat()
                }}
            )
            await add_call_event(call_id, "CALL_FINISHED", "Status polling completed")
            
    except Exception as e:
        logger.error(f"Error in status polling: {e}")

async def simulate_call_flow(call_id: str, config: CallConfig, messages: CallMessages):
    """Simulate call flow for demo (fallback when Infobip is unavailable)"""
    try:
        # PENDING -> CALLING
        await asyncio.sleep(1)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "CALLING"}})
        await add_call_event(call_id, "CALL_INITIATED", f"[SIMULATION] Calling {config.recipient_number}...")
        
        # CALLING -> RINGING
        await asyncio.sleep(2)
        await db.call_logs.update_one({"id": call_id}, {"$set": {"status": "RINGING"}})
        await add_call_event(call_id, "CALL_RINGING", f"[SIMULATION] Phone is ringing for {config.recipient_name or config.recipient_number}")
        
        # RINGING -> ESTABLISHED
        await asyncio.sleep(3)
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {"status": "ESTABLISHED", "started_at": datetime.now(timezone.utc).isoformat()}}
        )
        await add_call_event(call_id, "CALL_ESTABLISHED", "[SIMULATION] Call connected")
        
        # Playing TTS messages
        await asyncio.sleep(1)
        await add_call_event(call_id, "TTS_PLAYING", f"[SIMULATION] Playing greetings: {messages.greetings[:50]}...")
        
        await asyncio.sleep(3)
        await add_call_event(call_id, "TTS_PLAYING", f"[SIMULATION] Playing prompt: {messages.prompt[:50]}...")
        
        await asyncio.sleep(5)
        await add_call_event(call_id, "DTMF_RECEIVED", "[SIMULATION] User input received: ******")
        
        # ESTABLISHED -> FINISHED
        await asyncio.sleep(2)
        end_time = datetime.now(timezone.utc).isoformat()
        await db.call_logs.update_one(
            {"id": call_id}, 
            {"$set": {"status": "FINISHED", "ended_at": end_time, "duration_seconds": 15}}
        )
        await add_call_event(call_id, "CALL_FINISHED", "[SIMULATION] Call completed. Duration: 15 seconds")
        
    except Exception as e:
        logger.error(f"Error in call simulation: {e}")
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
    """Initiate a new outbound voice call"""
    try:
        # Create call log
        call_log = CallLog(
            config=request.config,
            messages=request.messages,
            steps=request.steps
        )
        
        # Insert to database
        doc = call_log.model_dump()
        await db.call_logs.insert_one(doc)
        
        # Add initial event
        await add_call_event(call_log.id, "CALL_QUEUED", "Call queued for processing")
        
        # Check if Infobip is configured
        if INFOBIP_API_KEY and INFOBIP_BASE_URL:
            # Use real Infobip API
            background_tasks.add_task(
                send_voice_message_infobip, 
                call_log.id, 
                request.config, 
                request.messages
            )
        else:
            # Use simulation
            background_tasks.add_task(
                simulate_call_flow, 
                call_log.id, 
                request.config, 
                request.messages
            )
        
        return {
            "status": "initiated",
            "call_id": call_log.id,
            "message": "Call initiated successfully",
            "using_infobip": bool(INFOBIP_API_KEY and INFOBIP_BASE_URL)
        }
        
    except Exception as e:
        logger.error(f"Error initiating call: {e}")
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
        
        # Update status
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
            # Send connection established
            yield f"data: {json.dumps({'type': 'connected', 'message': 'Connected to event stream'})}\n\n"
            
            # Get existing events from database
            call_log = await db.call_logs.find_one({"id": call_id}, {"_id": 0})
            if call_log and call_log.get("events"):
                for event in call_log["events"]:
                    yield f"data: {json.dumps(event)}\n\n"
            
            # Stream new events
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(event)}\n\n"
                    
                    # Check if call ended
                    if event.get("event_type") in ["CALL_FINISHED", "CALL_FAILED", "CALL_HANGUP"]:
                        break
                except asyncio.TimeoutError:
                    # Send heartbeat
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

@api_router.post("/webhook/call-events")
async def handle_infobip_webhook(request: Request):
    """Webhook endpoint for Infobip call events"""
    try:
        payload = await request.json()
        logger.info(f"Webhook received: {json.dumps(payload)}")
        
        # Handle delivery reports
        if "results" in payload:
            for result in payload["results"]:
                message_id = result.get("messageId")
                status = result.get("status", {})
                status_name = status.get("name", "UNKNOWN")
                
                # Find call by message ID
                call_log = await db.call_logs.find_one({"infobip_message_id": message_id}, {"_id": 0})
                
                if call_log:
                    # Map status
                    status_mapping = {
                        "DELIVERED": "FINISHED",
                        "REJECTED": "FAILED",
                        "UNDELIVERABLE": "FAILED",
                    }
                    
                    new_status = status_mapping.get(status_name)
                    if new_status:
                        await db.call_logs.update_one(
                            {"id": call_log["id"]},
                            {"$set": {"status": new_status}}
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
        {"id": "hera", "name": "Hera (Female, Mature)", "gender": "female", "infobip_voice": "Salli"},
        {"id": "aria", "name": "Aria (Female, Young)", "gender": "female", "infobip_voice": "Kimberly"},
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
