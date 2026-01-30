#!/usr/bin/env python3
"""
Backend API Testing for Bot Calling Application
Tests all API endpoints and call flow simulation
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, Any

class BotCallingAPITester:
    def __init__(self, base_url="https://callgenius-23.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.tests_run = 0
        self.tests_passed = 0
        self.current_call_id = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log test messages with timestamp"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {level}: {message}")
        
    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Dict = None, timeout: int = 10) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}" if not endpoint.startswith('http') else endpoint
        headers = {'Content-Type': 'application/json'}
        
        self.tests_run += 1
        self.log(f"🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers, timeout=timeout)
                
            success = response.status_code == expected_status
            
            if success:
                self.tests_passed += 1
                self.log(f"✅ {name} - Status: {response.status_code}")
                try:
                    return True, response.json()
                except:
                    return True, {}
            else:
                self.log(f"❌ {name} - Expected {expected_status}, got {response.status_code}", "ERROR")
                try:
                    error_detail = response.json()
                    self.log(f"   Error details: {error_detail}", "ERROR")
                except:
                    self.log(f"   Response text: {response.text[:200]}", "ERROR")
                return False, {}
                
        except requests.exceptions.Timeout:
            self.log(f"❌ {name} - Request timeout after {timeout}s", "ERROR")
            return False, {}
        except Exception as e:
            self.log(f"❌ {name} - Error: {str(e)}", "ERROR")
            return False, {}
    
    def test_root_endpoint(self) -> bool:
        """Test the root API endpoint"""
        success, response = self.run_test(
            "Root API Endpoint",
            "GET", 
            "",
            200
        )
        
        if success and response.get("status") == "running":
            self.log("   API is running correctly")
            return True
        elif success:
            self.log(f"   Unexpected response: {response}", "WARN")
            return False
        return False
    
    def test_config_endpoint(self) -> bool:
        """Test the config API endpoint for Infobip configuration"""
        success, response = self.run_test(
            "Config API Endpoint",
            "GET", 
            "config",
            200
        )
        
        if success:
            infobip_configured = response.get("infobip_configured", False)
            from_number = response.get("from_number", "")
            app_name = response.get("app_name", "")
            
            self.log(f"   Infobip configured: {infobip_configured}")
            self.log(f"   From number: {from_number}")
            self.log(f"   App name: {app_name}")
            
            return infobip_configured  # Should return True for proper Infobip config
        return False
    
    def test_voice_models_endpoint(self) -> bool:
        """Test voice models endpoint"""
        success, response = self.run_test(
            "Voice Models Endpoint",
            "GET",
            "voice-models",
            200
        )
        
        if success and isinstance(response, list) and len(response) > 0:
            self.log(f"   Found {len(response)} voice models")
            return True
        return False
    
    def test_call_types_endpoint(self) -> bool:
        """Test call types endpoint"""
        success, response = self.run_test(
            "Call Types Endpoint", 
            "GET",
            "call-types",
            200
        )
        
        if success and isinstance(response, list) and len(response) > 0:
            self.log(f"   Found {len(response)} call types")
            return True
        return False
    
    def test_initiate_call(self) -> str:
        """Test call initiation and return call_id"""
        call_data = {
            "config": {
                "call_type": "login_verification",
                "voice_model": "Hera (Female, Mature)",
                "from_number": "+18085821342",
                "recipient_number": "+14155552671",
                "recipient_name": "Test User",
                "service_name": "TestService",
                "otp_digits": 6
            },
            "messages": {
                "greetings": "Hello Test User, This is the TestService account service prevention line.",
                "prompt": "Please enter the 6-digit security code that we sent to your phone number.",
                "retry": "The verification code you entered is incorrect. Please try again.",
                "end_message": "Thank you for your attention. Goodbye."
            },
            "steps": {
                "step1": "Step 1 message",
                "step2": "Step 2 message", 
                "step3": "Step 3 message",
                "accepted": "Thank you for verification",
                "rejected": "Verification failed"
            }
        }
        
        success, response = self.run_test(
            "Call Initiation",
            "POST",
            "calls/initiate", 
            200,
            call_data
        )
        
        if success and response.get("call_id"):
            call_id = response["call_id"]
            self.current_call_id = call_id
            self.log(f"   Call initiated with ID: {call_id}")
            return call_id
        return None
    
    def test_get_call_details(self, call_id: str) -> bool:
        """Test getting call details"""
        success, response = self.run_test(
            "Get Call Details",
            "GET",
            f"calls/{call_id}",
            200
        )
        
        if success and response.get("id") == call_id:
            self.log(f"   Call status: {response.get('status', 'Unknown')}")
            self.log(f"   Events count: {len(response.get('events', []))}")
            return True
        return False
    
    def test_get_all_calls(self) -> bool:
        """Test getting all calls"""
        success, response = self.run_test(
            "Get All Calls",
            "GET", 
            "calls",
            200
        )
        
        if success and isinstance(response, list):
            self.log(f"   Found {len(response)} total calls")
            return True
        return False
    
    def test_call_flow_simulation(self, call_id: str) -> bool:
        """Test the call flow simulation by waiting and checking status changes"""
        self.log("🔄 Testing call flow simulation...")
        
        # Wait for call to progress through states
        expected_states = ["PENDING", "CALLING", "RINGING", "ESTABLISHED", "FINISHED"]
        max_wait_time = 20  # seconds
        start_time = time.time()
        
        last_status = None
        events_seen = []
        
        while time.time() - start_time < max_wait_time:
            success, response = self.run_test(
                f"Call Status Check",
                "GET",
                f"calls/{call_id}",
                200
            )
            
            if success:
                current_status = response.get("status")
                events = response.get("events", [])
                
                if current_status != last_status:
                    self.log(f"   Status changed: {last_status} -> {current_status}")
                    last_status = current_status
                
                # Track new events
                if len(events) > len(events_seen):
                    new_events = events[len(events_seen):]
                    for event in new_events:
                        self.log(f"   Event: {event.get('event_type')} - {event.get('details')}")
                    events_seen = events
                
                # Check if call finished
                if current_status in ["FINISHED", "FAILED"]:
                    self.log(f"✅ Call flow completed with status: {current_status}")
                    self.log(f"   Total events: {len(events_seen)}")
                    return True
            
            time.sleep(1)
        
        self.log("❌ Call flow did not complete within expected time", "ERROR")
        return False
    
    def test_hangup_call(self, call_id: str) -> bool:
        """Test hanging up an active call"""
        success, response = self.run_test(
            "Hangup Call",
            "POST",
            f"calls/{call_id}/hangup",
            200
        )
        
        if success and response.get("status") == "hangup":
            self.log(f"   Call {call_id} hung up successfully")
            return True
        return False
    
    def test_hangup_nonexistent_call(self) -> bool:
        """Test hanging up a non-existent call (should fail)"""
        fake_call_id = "non-existent-call-id"
        success, response = self.run_test(
            "Hangup Non-existent Call",
            "POST", 
            f"calls/{fake_call_id}/hangup",
            404
        )
        
        if success:
            self.log("   Correctly returned 404 for non-existent call")
            return True
        return False
    
    def test_sse_connection(self, call_id: str) -> bool:
        """Test SSE connection (basic connectivity test)"""
        self.log("🔍 Testing SSE Connection...")
        
        try:
            import sseclient
            url = f"{self.api_url}/calls/{call_id}/events"
            
            # Try to connect to SSE endpoint
            response = requests.get(url, stream=True, timeout=5)
            
            if response.status_code == 200:
                self.log("✅ SSE endpoint is accessible")
                return True
            else:
                self.log(f"❌ SSE endpoint returned {response.status_code}", "ERROR")
                return False
                
        except ImportError:
            # SSE client not available, just test the endpoint accessibility
            try:
                response = requests.get(f"{self.api_url}/calls/{call_id}/events", timeout=5)
                if response.status_code == 200:
                    self.log("✅ SSE endpoint is accessible (basic test)")
                    return True
                else:
                    self.log(f"❌ SSE endpoint returned {response.status_code}", "ERROR")
                    return False
            except Exception as e:
                self.log(f"❌ SSE endpoint test failed: {str(e)}", "ERROR")
                return False
        except Exception as e:
            self.log(f"❌ SSE connection test failed: {str(e)}", "ERROR")
            return False
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all backend tests"""
        self.log("🚀 Starting Bot Calling API Tests")
        self.log(f"   Base URL: {self.base_url}")
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": self.base_url,
            "tests": {},
            "summary": {}
        }
        
        # Test basic endpoints
        results["tests"]["root_endpoint"] = self.test_root_endpoint()
        results["tests"]["config_endpoint"] = self.test_config_endpoint()
        results["tests"]["voice_models"] = self.test_voice_models_endpoint()
        results["tests"]["call_types"] = self.test_call_types_endpoint()
        results["tests"]["get_all_calls"] = self.test_get_all_calls()
        
        # Test call initiation
        call_id = self.test_initiate_call()
        results["tests"]["call_initiation"] = call_id is not None
        
        if call_id:
            # Test call-related endpoints
            results["tests"]["get_call_details"] = self.test_get_call_details(call_id)
            results["tests"]["sse_connection"] = self.test_sse_connection(call_id)
            results["tests"]["call_flow_simulation"] = self.test_call_flow_simulation(call_id)
        else:
            self.log("❌ Skipping call-dependent tests due to initiation failure", "ERROR")
            results["tests"]["get_call_details"] = False
            results["tests"]["sse_connection"] = False
            results["tests"]["call_flow_simulation"] = False
        
        # Test error cases
        results["tests"]["hangup_nonexistent"] = self.test_hangup_nonexistent_call()
        
        # Summary
        results["summary"] = {
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": self.tests_run - self.tests_passed,
            "success_rate": round((self.tests_passed / self.tests_run) * 100, 1) if self.tests_run > 0 else 0,
            "current_call_id": self.current_call_id
        }
        
        self.log("📊 Test Summary:")
        self.log(f"   Total Tests: {results['summary']['total_tests']}")
        self.log(f"   Passed: {results['summary']['passed_tests']}")
        self.log(f"   Failed: {results['summary']['failed_tests']}")
        self.log(f"   Success Rate: {results['summary']['success_rate']}%")
        
        return results

def main():
    """Main test execution"""
    tester = BotCallingAPITester()
    results = tester.run_all_tests()
    
    # Return appropriate exit code
    if results["summary"]["success_rate"] >= 80:
        print("\n🎉 Backend tests completed successfully!")
        return 0
    else:
        print(f"\n⚠️  Backend tests completed with {results['summary']['success_rate']}% success rate")
        return 1

if __name__ == "__main__":
    sys.exit(main())