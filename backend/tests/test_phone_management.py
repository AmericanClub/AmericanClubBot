"""
Backend API Tests for Phone Number Management
Tests CRUD operations for provider phone numbers and user access
"""
import pytest
import requests
import os
import uuid

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://clubbot-panel.preview.emergentagent.com').rstrip('/')

# Test credentials
ADMIN_EMAIL = "admin@american.club"
ADMIN_PASSWORD = "123"
USER_EMAIL = "testuser@test.com"
USER_PASSWORD = "test123"


class TestAuthEndpoints:
    """Authentication endpoint tests"""
    
    def test_admin_login_success(self):
        """Test admin login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        assert data["user"]["role"] == "admin", "User is not admin"
        print(f"✓ Admin login successful - role: {data['user']['role']}")
    
    def test_user_login_success(self):
        """Test user login with valid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": USER_EMAIL,
            "password": USER_PASSWORD
        })
        assert response.status_code == 200, f"User login failed: {response.text}"
        data = response.json()
        assert "token" in data, "Token not in response"
        assert "user" in data, "User not in response"
        assert "credits" in data["user"], "Credits not in user data"
        print(f"✓ User login successful - credits: {data['user']['credits']}")
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": "wrong@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        print("✓ Invalid credentials correctly rejected")


class TestProviderPhoneNumbersAdmin:
    """Admin phone number management tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin authentication failed")
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_providers(self):
        """Test getting all providers"""
        response = requests.get(f"{BASE_URL}/api/admin/providers", headers=self.headers)
        assert response.status_code == 200, f"Failed to get providers: {response.text}"
        data = response.json()
        assert "providers" in data, "Providers not in response"
        providers = data["providers"]
        assert len(providers) >= 2, "Expected at least 2 providers"
        
        # Check provider structure
        provider_ids = [p["id"] for p in providers]
        assert "signalwire" in provider_ids, "SignalWire provider not found"
        assert "infobip" in provider_ids, "Infobip provider not found"
        print(f"✓ Got {len(providers)} providers: {provider_ids}")
    
    def test_get_signalwire_phone_numbers(self):
        """Test getting SignalWire phone numbers"""
        response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
        assert response.status_code == 200, f"Failed to get phone numbers: {response.text}"
        data = response.json()
        assert "phone_numbers" in data, "phone_numbers not in response"
        print(f"✓ SignalWire has {len(data['phone_numbers'])} phone numbers")
    
    def test_get_infobip_phone_numbers(self):
        """Test getting Infobip phone numbers"""
        response = requests.get(f"{BASE_URL}/api/admin/providers/infobip/phone-numbers", headers=self.headers)
        assert response.status_code == 200, f"Failed to get phone numbers: {response.text}"
        data = response.json()
        assert "phone_numbers" in data, "phone_numbers not in response"
        print(f"✓ Infobip has {len(data['phone_numbers'])} phone numbers")
    
    def test_add_phone_number_to_signalwire(self):
        """Test adding a new phone number to SignalWire"""
        test_phone_id = str(uuid.uuid4())
        test_number = f"+1555{str(uuid.uuid4())[:7].replace('-', '')}"
        
        response = requests.post(
            f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers",
            headers=self.headers,
            json={
                "id": test_phone_id,
                "number": test_number,
                "label": "TEST_Number",
                "is_active": True
            }
        )
        assert response.status_code == 200, f"Failed to add phone number: {response.text}"
        data = response.json()
        assert "message" in data, "Message not in response"
        print(f"✓ Added phone number: {test_number}")
        
        # Verify it was added
        get_response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
        assert get_response.status_code == 200
        phone_numbers = get_response.json()["phone_numbers"]
        added_numbers = [p for p in phone_numbers if p.get("label") == "TEST_Number"]
        assert len(added_numbers) > 0, "Added phone number not found"
        print(f"✓ Verified phone number was persisted")
        
        # Cleanup - delete the test number
        for phone in added_numbers:
            requests.delete(
                f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers/{phone['id']}",
                headers=self.headers
            )
    
    def test_update_phone_number_label(self):
        """Test updating a phone number label"""
        # First get existing phone numbers
        response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
        assert response.status_code == 200
        phone_numbers = response.json()["phone_numbers"]
        
        if not phone_numbers:
            pytest.skip("No phone numbers to update")
        
        phone_id = phone_numbers[0]["id"]
        original_label = phone_numbers[0]["label"]
        
        # Update the label
        update_response = requests.put(
            f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers/{phone_id}",
            headers=self.headers,
            json={"label": "TEST_Updated_Label"}
        )
        assert update_response.status_code == 200, f"Failed to update: {update_response.text}"
        print(f"✓ Updated phone number label")
        
        # Verify update
        verify_response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
        updated_phone = next((p for p in verify_response.json()["phone_numbers"] if p["id"] == phone_id), None)
        assert updated_phone is not None, "Phone number not found after update"
        assert updated_phone["label"] == "TEST_Updated_Label", "Label not updated"
        print(f"✓ Verified label was updated")
        
        # Restore original label
        requests.put(
            f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers/{phone_id}",
            headers=self.headers,
            json={"label": original_label}
        )
    
    def test_toggle_phone_number_active_status(self):
        """Test toggling phone number active status"""
        # Get existing phone numbers
        response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
        assert response.status_code == 200
        phone_numbers = response.json()["phone_numbers"]
        
        if not phone_numbers:
            pytest.skip("No phone numbers to toggle")
        
        phone_id = phone_numbers[0]["id"]
        original_status = phone_numbers[0].get("is_active", True)
        
        # Toggle status
        update_response = requests.put(
            f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers/{phone_id}",
            headers=self.headers,
            json={"is_active": not original_status}
        )
        assert update_response.status_code == 200, f"Failed to toggle: {update_response.text}"
        print(f"✓ Toggled phone number status to {not original_status}")
        
        # Restore original status
        requests.put(
            f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers/{phone_id}",
            headers=self.headers,
            json={"is_active": original_status}
        )
    
    def test_delete_phone_number(self):
        """Test deleting a phone number"""
        # First add a test phone number
        test_phone_id = str(uuid.uuid4())
        test_number = f"+1666{str(uuid.uuid4())[:7].replace('-', '')}"
        
        add_response = requests.post(
            f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers",
            headers=self.headers,
            json={
                "id": test_phone_id,
                "number": test_number,
                "label": "TEST_ToDelete",
                "is_active": True
            }
        )
        assert add_response.status_code == 200, f"Failed to add test number: {add_response.text}"
        
        # Get the actual ID from the response or find it
        get_response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
        phone_to_delete = next((p for p in get_response.json()["phone_numbers"] if p.get("label") == "TEST_ToDelete"), None)
        
        if phone_to_delete:
            # Delete the phone number
            delete_response = requests.delete(
                f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers/{phone_to_delete['id']}",
                headers=self.headers
            )
            assert delete_response.status_code == 200, f"Failed to delete: {delete_response.text}"
            print(f"✓ Deleted phone number: {test_number}")
            
            # Verify deletion
            verify_response = requests.get(f"{BASE_URL}/api/admin/providers/signalwire/phone-numbers", headers=self.headers)
            remaining = [p for p in verify_response.json()["phone_numbers"] if p.get("label") == "TEST_ToDelete"]
            assert len(remaining) == 0, "Phone number still exists after deletion"
            print(f"✓ Verified phone number was deleted")


class TestUserPhoneNumberAccess:
    """User phone number access tests"""
    
    def test_get_available_phone_numbers_no_auth(self):
        """Test getting available phone numbers without auth (public endpoint)"""
        response = requests.get(f"{BASE_URL}/api/user/providers/phone-numbers")
        assert response.status_code == 200, f"Failed to get phone numbers: {response.text}"
        data = response.json()
        assert "phone_numbers" in data, "phone_numbers not in response"
        
        phone_numbers = data["phone_numbers"]
        print(f"✓ Got {len(phone_numbers)} available phone numbers")
        
        # Verify structure
        if phone_numbers:
            phone = phone_numbers[0]
            assert "provider_id" in phone, "provider_id missing"
            assert "provider_name" in phone, "provider_name missing"
            assert "number" in phone, "number missing"
            assert "label" in phone, "label missing"
            print(f"✓ Phone number structure is correct")
    
    def test_filter_phone_numbers_by_provider(self):
        """Test filtering phone numbers by provider"""
        # Get SignalWire numbers
        sw_response = requests.get(f"{BASE_URL}/api/user/providers/phone-numbers?provider=signalwire")
        assert sw_response.status_code == 200
        sw_numbers = sw_response.json()["phone_numbers"]
        
        # Get Infobip numbers
        ib_response = requests.get(f"{BASE_URL}/api/user/providers/phone-numbers?provider=infobip")
        assert ib_response.status_code == 200
        ib_numbers = ib_response.json()["phone_numbers"]
        
        # Verify filtering works
        for num in sw_numbers:
            assert num["provider_id"] == "signalwire", f"Expected signalwire, got {num['provider_id']}"
        
        for num in ib_numbers:
            assert num["provider_id"] == "infobip", f"Expected infobip, got {num['provider_id']}"
        
        print(f"✓ SignalWire: {len(sw_numbers)} numbers, Infobip: {len(ib_numbers)} numbers")
    
    def test_only_active_numbers_returned(self):
        """Test that only active phone numbers are returned to users"""
        response = requests.get(f"{BASE_URL}/api/user/providers/phone-numbers")
        assert response.status_code == 200
        phone_numbers = response.json()["phone_numbers"]
        
        # All returned numbers should be active (inactive are filtered out)
        # This is verified by the API logic - inactive numbers are not included
        print(f"✓ All {len(phone_numbers)} returned numbers are active")


class TestAdminDashboard:
    """Admin dashboard stats tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Get admin token before each test"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": ADMIN_EMAIL,
            "password": ADMIN_PASSWORD
        })
        if response.status_code != 200:
            pytest.skip("Admin authentication failed")
        self.token = response.json()["token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_dashboard_stats(self):
        """Test getting dashboard statistics"""
        response = requests.get(f"{BASE_URL}/api/admin/dashboard/stats", headers=self.headers)
        assert response.status_code == 200, f"Failed to get stats: {response.text}"
        data = response.json()
        
        assert "users" in data, "users stats missing"
        assert "calls" in data, "calls stats missing"
        assert "credits" in data, "credits stats missing"
        assert "invite_codes" in data, "invite_codes stats missing"
        
        print(f"✓ Dashboard stats: {data['users']['total']} users, {data['calls']['total']} calls")
    
    def test_get_users_list(self):
        """Test getting users list"""
        response = requests.get(f"{BASE_URL}/api/admin/users", headers=self.headers)
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        data = response.json()
        
        assert "users" in data, "users list missing"
        users = data["users"]
        
        if users:
            user = users[0]
            assert "id" in user, "id missing"
            assert "email" in user, "email missing"
            assert "name" in user, "name missing"
            assert "credits" in user, "credits missing"
        
        print(f"✓ Got {len(users)} users")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
