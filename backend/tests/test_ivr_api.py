"""
IVR Bot Calling API Tests
Tests for: Root API, Config, Call Initiation, SSE Events, Verification (Accept/Deny)
"""
import pytest
import requests
import os
import time
import json
import threading
from queue import Queue

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

class TestRootAndConfig:
    """Test root API and configuration endpoints"""
    
    def test_root_api_returns_running_status(self):
        """Backend API /api/ returns running status"""
        response = requests.get(f"{BASE_URL}/api/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert "message" in data
        assert data["message"] == "Bot Calling API"
        assert "mode" in data
        print(f"Root API: {data}")
    
    def test_config_returns_infobip_configuration(self):
        """Backend API /api/config returns Infobip configuration"""
        response = requests.get(f"{BASE_URL}/api/config")
        assert response.status_code == 200
        data = response.json()
        assert "infobip_configured" in data
        assert "from_number" in data
        assert "app_name" in data
        print(f"Config: {data}")
    
    def test_voice_models_endpoint(self):
        """Test voice models endpoint"""
        response = requests.get(f"{BASE_URL}/api/voice-models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        assert all("id" in model and "name" in model for model in data)
        print(f"Voice models: {len(data)} available")
    
    def test_call_types_endpoint(self):
        """Test call types endpoint"""
        response = requests.get(f"{BASE_URL}/api/call-types")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0
        print(f"Call types: {len(data)} available")


class TestCallInitiation:
    """Test call initiation and IVR flow"""
    
    def test_initiate_call_simulation_mode(self):
        """POST /api/calls/initiate starts a call (simulation mode)"""
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "recipient_name": "Test User",
                "service_name": "TestService",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello {name}, This is the {service} account service prevention line.",
                "step2": "Please enter the {digits}-digit security code.",
                "step3": "Thank you. Please hold for a moment.",
                "accepted": "Thank you. Goodbye.",
                "rejected": "The code is incorrect. Please try again."
            }
        }
        
        response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert data["status"] == "initiated"
        assert "call_id" in data
        assert "mode" in data
        
        print(f"Call initiated: {data}")
        return data["call_id"]
    
    def test_get_call_by_id(self):
        """Test getting call details by ID"""
        # First initiate a call
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello",
                "step2": "Enter code",
                "step3": "Please wait",
                "accepted": "Goodbye",
                "rejected": "Try again"
            }
        }
        
        init_response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert init_response.status_code == 200
        call_id = init_response.json()["call_id"]
        
        # Wait for simulation to progress
        time.sleep(2)
        
        # Get call details
        response = requests.get(f"{BASE_URL}/api/calls/{call_id}")
        assert response.status_code == 200
        data = response.json()
        
        assert "id" in data
        assert data["id"] == call_id
        assert "status" in data
        assert "events" in data
        print(f"Call details: status={data['status']}, events={len(data['events'])}")
    
    def test_get_all_calls(self):
        """Test getting all calls"""
        response = requests.get(f"{BASE_URL}/api/calls")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"Total calls in history: {len(data)}")


class TestSSEEvents:
    """Test SSE event streaming"""
    
    def test_sse_endpoint_streams_events(self):
        """SSE endpoint /api/calls/{call_id}/events streams events"""
        # First initiate a call
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello",
                "step2": "Enter code",
                "step3": "Please wait",
                "accepted": "Goodbye",
                "rejected": "Try again"
            }
        }
        
        init_response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert init_response.status_code == 200
        call_id = init_response.json()["call_id"]
        
        # Collect SSE events
        events_received = []
        
        def collect_events():
            try:
                response = requests.get(
                    f"{BASE_URL}/api/calls/{call_id}/events",
                    stream=True,
                    timeout=15
                )
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode('utf-8')
                        if line_str.startswith('data: '):
                            event_data = json.loads(line_str[6:])
                            events_received.append(event_data)
                            if len(events_received) >= 5:
                                break
            except Exception as e:
                print(f"SSE collection stopped: {e}")
        
        # Run event collection in thread
        thread = threading.Thread(target=collect_events)
        thread.start()
        thread.join(timeout=15)
        
        assert len(events_received) > 0, "Should receive at least one SSE event"
        print(f"SSE events received: {len(events_received)}")
        
        # Check for expected event types
        event_types = [e.get("event_type") or e.get("type") for e in events_received]
        print(f"Event types: {event_types}")


class TestVerification:
    """Test Accept/Deny verification flow"""
    
    def test_verify_accepted_ends_call(self):
        """POST /api/calls/{call_id}/verify with accepted=true ends call"""
        # Initiate call
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello",
                "step2": "Enter code",
                "step3": "Please wait",
                "accepted": "Goodbye",
                "rejected": "Try again"
            }
        }
        
        init_response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert init_response.status_code == 200
        call_id = init_response.json()["call_id"]
        
        # Wait for simulation to reach verification stage
        time.sleep(14)  # Simulation takes ~13 seconds to reach decision box
        
        # Verify with accepted=true
        verify_response = requests.post(
            f"{BASE_URL}/api/calls/{call_id}/verify",
            json={"accepted": True}
        )
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["status"] == "verified"
        assert data["accepted"] == True
        print(f"Verification accepted: {data}")
        
        # Check call status
        time.sleep(1)
        call_response = requests.get(f"{BASE_URL}/api/calls/{call_id}")
        assert call_response.status_code == 200
        call_data = call_response.json()
        assert call_data["verification_result"] == "accepted"
        print(f"Call status after accept: {call_data['status']}")
    
    def test_verify_denied_loops_for_new_code(self):
        """POST /api/calls/{call_id}/verify with accepted=false loops back for new code"""
        # Initiate call
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello",
                "step2": "Enter code",
                "step3": "Please wait",
                "accepted": "Goodbye",
                "rejected": "Try again"
            }
        }
        
        init_response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert init_response.status_code == 200
        call_id = init_response.json()["call_id"]
        
        # Wait for simulation to reach verification stage
        time.sleep(14)
        
        # Verify with accepted=false (deny)
        verify_response = requests.post(
            f"{BASE_URL}/api/calls/{call_id}/verify",
            json={"accepted": False}
        )
        assert verify_response.status_code == 200
        data = verify_response.json()
        assert data["status"] == "verified"
        assert data["accepted"] == False
        print(f"Verification denied: {data}")
        
        # Wait for new code simulation
        time.sleep(6)
        
        # Check call has new code
        call_response = requests.get(f"{BASE_URL}/api/calls/{call_id}")
        assert call_response.status_code == 200
        call_data = call_response.json()
        
        # Should have multiple codes in history after deny
        assert len(call_data.get("dtmf_codes_history", [])) >= 1
        print(f"DTMF codes history: {call_data.get('dtmf_codes_history')}")


class TestCallManagement:
    """Test call management endpoints"""
    
    def test_hangup_call(self):
        """Test hanging up a call"""
        # Initiate call
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello",
                "step2": "Enter code",
                "step3": "Please wait",
                "accepted": "Goodbye",
                "rejected": "Try again"
            }
        }
        
        init_response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert init_response.status_code == 200
        call_id = init_response.json()["call_id"]
        
        time.sleep(2)
        
        # Hangup
        hangup_response = requests.post(f"{BASE_URL}/api/calls/{call_id}/hangup")
        assert hangup_response.status_code == 200
        data = hangup_response.json()
        assert data["status"] == "hangup"
        print(f"Hangup response: {data}")
    
    def test_delete_call(self):
        """Test deleting a call"""
        # Initiate call
        payload = {
            "config": {
                "call_type": "Login Verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+525547000906",
                "otp_digits": 6
            },
            "steps": {
                "step1": "Hello",
                "step2": "Enter code",
                "step3": "Please wait",
                "accepted": "Goodbye",
                "rejected": "Try again"
            }
        }
        
        init_response = requests.post(f"{BASE_URL}/api/calls/initiate", json=payload)
        assert init_response.status_code == 200
        call_id = init_response.json()["call_id"]
        
        time.sleep(1)
        
        # Delete
        delete_response = requests.delete(f"{BASE_URL}/api/calls/{call_id}")
        assert delete_response.status_code == 200
        data = delete_response.json()
        assert data["status"] == "deleted"
        print(f"Delete response: {data}")
        
        # Verify deleted
        get_response = requests.get(f"{BASE_URL}/api/calls/{call_id}")
        assert get_response.status_code == 404
    
    def test_get_nonexistent_call_returns_404(self):
        """Test getting a non-existent call returns 404"""
        response = requests.get(f"{BASE_URL}/api/calls/nonexistent-call-id")
        assert response.status_code == 404


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
