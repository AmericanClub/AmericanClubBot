"""
Provider Management Routes - Manage API credentials for voice providers
"""
from fastapi import APIRouter, HTTPException, Depends
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field
import uuid
import os

from auth import get_current_admin

provider_router = APIRouter(prefix="/admin/providers", tags=["Providers"])


# ==================
# Pydantic Models
# ==================

class PhoneNumber(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    number: str
    label: str = "Main"
    is_active: bool = True


class PhoneNumberUpdate(BaseModel):
    number: Optional[str] = None
    label: Optional[str] = None
    is_active: Optional[bool] = None


class SignalWireConfig(BaseModel):
    project_id: str
    auth_token: str
    space_url: str
    phone_numbers: List[PhoneNumber] = []


class InfobipConfig(BaseModel):
    api_key: str
    base_url: str = "api.infobip.com"
    app_id: Optional[str] = None
    phone_numbers: List[PhoneNumber] = []


class ProviderUpdate(BaseModel):
    is_enabled: bool = True
    signalwire: Optional[SignalWireConfig] = None
    infobip: Optional[InfobipConfig] = None


# ==================
# Routes
# ==================

@provider_router.get("")
async def get_providers(current_admin: dict = Depends(get_current_admin)):
    """Get all provider configurations"""
    from server import db
    
    providers = await db.providers.find({}, {"_id": 0}).to_list(10)
    
    # If no providers exist, return defaults
    if not providers:
        return {
            "providers": [
                {
                    "id": "signalwire",
                    "name": "SignalWire",
                    "is_enabled": False,
                    "is_configured": False,
                    "phone_numbers": []
                },
                {
                    "id": "infobip",
                    "name": "Infobip", 
                    "is_enabled": False,
                    "is_configured": False,
                    "phone_numbers": []
                }
            ]
        }
    
    # Mask sensitive data
    for p in providers:
        if p.get("credentials"):
            creds = p["credentials"]
            if creds.get("auth_token"):
                creds["auth_token"] = "***" + creds["auth_token"][-4:] if len(creds.get("auth_token", "")) > 4 else "****"
            if creds.get("api_key"):
                creds["api_key"] = "***" + creds["api_key"][-4:] if len(creds.get("api_key", "")) > 4 else "****"
    
    return {"providers": providers}


@provider_router.get("/{provider_id}")
async def get_provider(provider_id: str, current_admin: dict = Depends(get_current_admin)):
    """Get specific provider configuration"""
    from server import db
    
    provider = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    
    if not provider:
        return {
            "id": provider_id,
            "name": provider_id.title(),
            "is_enabled": False,
            "is_configured": False,
            "credentials": {},
            "phone_numbers": []
        }
    
    # Mask sensitive data
    if provider.get("credentials"):
        creds = provider["credentials"]
        if creds.get("auth_token"):
            creds["auth_token_masked"] = "***" + creds["auth_token"][-4:] if len(creds.get("auth_token", "")) > 4 else "****"
            del creds["auth_token"]
        if creds.get("api_key"):
            creds["api_key_masked"] = "***" + creds["api_key"][-4:] if len(creds.get("api_key", "")) > 4 else "****"
            del creds["api_key"]
    
    return provider


@provider_router.put("/signalwire")
async def update_signalwire(
    config: SignalWireConfig,
    is_enabled: bool = True,
    current_admin: dict = Depends(get_current_admin)
):
    """Update SignalWire provider configuration"""
    from server import db
    
    now = datetime.now(timezone.utc).isoformat()
    
    provider_data = {
        "id": "signalwire",
        "name": "SignalWire",
        "is_enabled": is_enabled,
        "is_configured": True,
        "credentials": {
            "project_id": config.project_id,
            "auth_token": config.auth_token,
            "space_url": config.space_url
        },
        "phone_numbers": [pn.dict() for pn in config.phone_numbers],
        "updated_by": current_admin["id"],
        "updated_at": now
    }
    
    await db.providers.update_one(
        {"id": "signalwire"},
        {"$set": provider_data},
        upsert=True
    )
    
    # Update environment variables in memory for immediate use
    os.environ["SIGNALWIRE_PROJECT_ID"] = config.project_id
    os.environ["SIGNALWIRE_AUTH_TOKEN"] = config.auth_token
    os.environ["SIGNALWIRE_SPACE_URL"] = config.space_url
    if config.phone_numbers:
        os.environ["SIGNALWIRE_FROM_NUMBER"] = config.phone_numbers[0].number
    
    return {
        "message": "SignalWire configuration updated",
        "is_enabled": is_enabled,
        "phone_numbers_count": len(config.phone_numbers)
    }


@provider_router.put("/infobip")
async def update_infobip(
    config: InfobipConfig,
    is_enabled: bool = True,
    current_admin: dict = Depends(get_current_admin)
):
    """Update Infobip provider configuration"""
    from server import db
    
    now = datetime.now(timezone.utc).isoformat()
    
    provider_data = {
        "id": "infobip",
        "name": "Infobip",
        "is_enabled": is_enabled,
        "is_configured": True,
        "credentials": {
            "api_key": config.api_key,
            "base_url": config.base_url,
            "app_id": config.app_id
        },
        "phone_numbers": [pn.dict() for pn in config.phone_numbers],
        "updated_by": current_admin["id"],
        "updated_at": now
    }
    
    await db.providers.update_one(
        {"id": "infobip"},
        {"$set": provider_data},
        upsert=True
    )
    
    # Update environment variables in memory
    os.environ["INFOBIP_API_KEY"] = config.api_key
    os.environ["INFOBIP_BASE_URL"] = config.base_url
    if config.app_id:
        os.environ["INFOBIP_APP_ID"] = config.app_id
    if config.phone_numbers:
        os.environ["INFOBIP_FROM_NUMBER"] = config.phone_numbers[0].number
    
    return {
        "message": "Infobip configuration updated",
        "is_enabled": is_enabled,
        "phone_numbers_count": len(config.phone_numbers)
    }


@provider_router.get("/{provider_id}/phone-numbers")
async def get_phone_numbers(
    provider_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all phone numbers for a provider"""
    from server import db
    
    provider = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    
    if not provider:
        return {"phone_numbers": []}
    
    return {"phone_numbers": provider.get("phone_numbers", [])}


@provider_router.post("/{provider_id}/phone-numbers")
async def add_phone_number(
    provider_id: str,
    phone: PhoneNumber,
    current_admin: dict = Depends(get_current_admin)
):
    """Add phone number to provider"""
    from server import db
    
    # Check if provider exists, if not create it
    provider = await db.providers.find_one({"id": provider_id})
    
    if not provider:
        # Create provider with the new phone number
        await db.providers.insert_one({
            "id": provider_id,
            "name": provider_id.title(),
            "is_enabled": False,
            "is_configured": False,
            "credentials": {},
            "phone_numbers": [phone.model_dump()]
        })
        return {"message": "Provider created with phone number", "number": phone.number, "id": phone.id}
    
    # Add to existing provider
    result = await db.providers.update_one(
        {"id": provider_id},
        {"$push": {"phone_numbers": phone.model_dump()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to add phone number")
    
    return {"message": "Phone number added", "number": phone.number, "id": phone.id}


@provider_router.put("/{provider_id}/phone-numbers/{phone_id}")
async def update_phone_number(
    provider_id: str,
    phone_id: str,
    phone_update: PhoneNumberUpdate,
    current_admin: dict = Depends(get_current_admin)
):
    """Update a phone number"""
    from server import db
    
    # Build update query
    update_fields = {}
    if phone_update.number is not None:
        update_fields["phone_numbers.$.number"] = phone_update.number
    if phone_update.label is not None:
        update_fields["phone_numbers.$.label"] = phone_update.label
    if phone_update.is_active is not None:
        update_fields["phone_numbers.$.is_active"] = phone_update.is_active
    
    if not update_fields:
        return {"message": "No fields to update"}
    
    result = await db.providers.update_one(
        {"id": provider_id, "phone_numbers.id": phone_id},
        {"$set": update_fields}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Phone number not found")
    
    return {"message": "Phone number updated"}


@provider_router.delete("/{provider_id}/phone-numbers/{phone_id}")
async def remove_phone_number(
    provider_id: str,
    phone_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Remove phone number from provider"""
    from server import db
    
    result = await db.providers.update_one(
        {"id": provider_id},
        {"$pull": {"phone_numbers": {"id": phone_id}}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="Provider or phone number not found")
    
    return {"message": "Phone number removed"}


@provider_router.put("/{provider_id}/toggle")
async def toggle_provider(
    provider_id: str,
    current_admin: dict = Depends(get_current_admin)
):
    """Enable/disable provider"""
    from server import db
    
    provider = await db.providers.find_one({"id": provider_id}, {"_id": 0})
    
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    
    new_status = not provider.get("is_enabled", False)
    
    await db.providers.update_one(
        {"id": provider_id},
        {"$set": {"is_enabled": new_status}}
    )
    
    return {"message": f"Provider {'enabled' if new_status else 'disabled'}", "is_enabled": new_status}


# Helper function to get provider credentials from DB
async def get_provider_credentials(provider_id: str) -> dict:
    """Get provider credentials from database"""
    from server import db
    
    provider = await db.providers.find_one(
        {"id": provider_id, "is_enabled": True, "is_configured": True},
        {"_id": 0}
    )
    
    if not provider:
        return None
    
    return {
        "credentials": provider.get("credentials", {}),
        "phone_numbers": provider.get("phone_numbers", [])
    }


# User endpoint to get available phone numbers
user_provider_router = APIRouter(prefix="/user/providers", tags=["User Providers"])


@user_provider_router.get("/phone-numbers")
async def get_available_phone_numbers(provider: str = None):
    """Get available phone numbers for users to select as Caller ID"""
    from server import db
    
    query = {}
    if provider:
        query["id"] = provider
    
    providers = await db.providers.find(query, {"_id": 0}).to_list(10)
    
    result = []
    for p in providers:
        phone_numbers = p.get("phone_numbers", [])
        for pn in phone_numbers:
            if pn.get("is_active", True):
                result.append({
                    "provider_id": p["id"],
                    "provider_name": p.get("name", p["id"].title()),
                    "number": pn.get("number"),
                    "label": pn.get("label", "Main"),
                    "id": pn.get("id")
                })
    
    return {"phone_numbers": result}
