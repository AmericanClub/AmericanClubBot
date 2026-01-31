"""
Authentication Routes - Login, Signup, Logout, User Management
"""
from fastapi import APIRouter, HTTPException, status, Request, Depends, BackgroundTasks
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, EmailStr
import uuid

from auth import (
    UserCreate, UserLogin, UserResponse, TokenResponse,
    InviteCodeCreate, InviteCodeResponse, CreditAdjustment,
    verify_password, get_password_hash, create_access_token,
    generate_invite_code, get_client_ip, get_device_info,
    get_current_user, get_current_admin, get_current_active_user
)

from security import (
    check_rate_limit, record_login_attempt, 
    generate_captcha, verify_captcha, get_rate_limit_info,
    get_client_ip as security_get_client_ip
)

from security_advanced import (
    get_security_logs, get_security_stats, log_security_event,
    scan_for_attacks, sanitize_dict, validate_password_strength
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
admin_router = APIRouter(prefix="/admin", tags=["Admin"])
security_router = APIRouter(prefix="/security", tags=["Security"])


# Additional Pydantic models for admin user edit
class UserEditRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    new_password: Optional[str] = None


# Pydantic model for creating new admin
class AdminCreateRequest(BaseModel):
    name: str
    email: EmailStr
    password: str


# Pydantic model for login with CAPTCHA
class LoginWithCaptcha(BaseModel):
    email: EmailStr
    password: str
    captcha_id: str
    captcha_answer: int
    hp_field: Optional[str] = None  # Honeypot field - should always be empty


# ==================
# Security Endpoints
# ==================

@auth_router.get("/captcha")
async def get_captcha():
    """Generate a new CAPTCHA challenge"""
    captcha_id, question, _ = generate_captcha()
    return {
        "captcha_id": captcha_id,
        "question": question
    }


@auth_router.get("/rate-limit-status")
async def get_rate_limit_status(request: Request):
    """Get current rate limit status for the client IP"""
    ip = security_get_client_ip(request)
    return get_rate_limit_info(ip)


# ==================
# Auth Routes
# ==================

@auth_router.post("/signup", response_model=TokenResponse)
async def signup(user_data: UserCreate, request: Request):
    """Register new user with invite code"""
    from server import db
    
    # Validate invite code
    invite_code = await db.invite_codes.find_one({
        "code": user_data.invite_code.upper(),
        "is_used": False
    }, {"_id": 0})
    
    if not invite_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or already used invite code"
        )
    
    # Check if email already exists
    existing_user = await db.users.find_one({"email": user_data.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create user
    user_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    # Create session
    token, session_id = create_access_token(
        data={"sub": user_id},
        role="user"
    )
    
    client_ip = get_client_ip(request)
    device_info = get_device_info(request)
    
    new_user = {
        "id": user_id,
        "email": user_data.email.lower(),
        "password": get_password_hash(user_data.password),
        "name": user_data.name,
        "role": "user",
        "credits": invite_code["credits"],
        "total_credits_used": 0,
        "is_active": True,
        "invite_code_used": invite_code["code"],
        "active_session": {
            "session_id": session_id,
            "ip": client_ip,
            "device": device_info,
            "login_at": now
        },
        "created_at": now,
        "last_login": now
    }
    
    await db.users.insert_one(new_user)
    
    # Mark invite code as used
    await db.invite_codes.update_one(
        {"code": invite_code["code"]},
        {"$set": {
            "is_used": True,
            "used_by": user_id,
            "used_by_email": user_data.email.lower(),
            "used_by_name": user_data.name,
            "used_at": now
        }}
    )
    
    # Add credit transaction log
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "signup_bonus",
        "amount": invite_code["credits"],
        "balance_after": invite_code["credits"],
        "reason": f"Signup bonus from invite code: {invite_code['code']}",
        "created_at": now
    })
    
    return TokenResponse(
        access_token=token,
        user=UserResponse(
            id=user_id,
            email=new_user["email"],
            name=new_user["name"],
            role=new_user["role"],
            credits=new_user["credits"],
            is_active=new_user["is_active"],
            created_at=new_user["created_at"],
            last_login=new_user["last_login"]
        )
    )


@auth_router.post("/login")
async def login(user_data: LoginWithCaptcha, request: Request):
    """Login user with CAPTCHA verification - invalidates previous sessions (single device)"""
    from server import db
    
    ip = security_get_client_ip(request)
    
    # Check honeypot field - if filled, it's a bot
    if user_data.hp_field:
        # Silently reject bots - don't give them useful feedback
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check rate limit first
    is_allowed, blocked_seconds = check_rate_limit(ip)
    if not is_allowed:
        log_security_event(
            event_type="rate_limit_exceeded",
            ip=ip,
            details={"email": user_data.email, "blocked_seconds": blocked_seconds},
            severity="high"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please try again in {blocked_seconds} seconds."
        )
    
    # Verify CAPTCHA
    if not verify_captcha(user_data.captcha_id, user_data.captcha_answer):
        record_login_attempt(ip, success=False)
        log_security_event(
            event_type="captcha_failed",
            ip=ip,
            details={"email": user_data.email},
            severity="low"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired security check answer"
        )
    
    # Find user
    user = await db.users.find_one({"email": user_data.email.lower()}, {"_id": 0})
    
    if not user:
        record_login_attempt(ip, success=False)
        log_security_event(
            event_type="login_failed_unknown_user",
            ip=ip,
            details={"email": user_data.email},
            severity="medium"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Verify password
    if not verify_password(user_data.password, user["password"]):
        record_login_attempt(ip, success=False)
        log_security_event(
            event_type="login_failed_wrong_password",
            ip=ip,
            details={"email": user_data.email, "user_id": user["id"]},
            user_id=user["id"],
            severity="medium"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if active
    if not user.get("is_active", False):
        log_security_event(
            event_type="login_blocked_disabled_account",
            ip=ip,
            details={"email": user_data.email, "user_id": user["id"]},
            user_id=user["id"],
            severity="medium"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Successful login - reset rate limit
    record_login_attempt(ip, success=True)
    
    # Log successful login
    log_security_event(
        event_type="login_success",
        ip=ip,
        details={"email": user_data.email, "role": user["role"]},
        user_id=user["id"],
        severity="low"
    )
    
    # Create new session (this invalidates any previous session)
    token, session_id = create_access_token(
        data={"sub": user["id"]},
        role=user["role"]
    )
    
    client_ip = get_client_ip(request)
    device_info = get_device_info(request)
    now = datetime.now(timezone.utc).isoformat()
    
    # Update user with new session
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "active_session": {
                "session_id": session_id,
                "ip": client_ip,
                "device": device_info,
                "login_at": now
            },
            "last_login": now
        }}
    )
    
    # Build user response with is_super_admin for admins
    user_response = {
        "id": user["id"],
        "email": user["email"],
        "name": user["name"],
        "role": user["role"],
        "credits": user.get("credits", 0),
        "is_active": user["is_active"],
        "created_at": user["created_at"],
        "last_login": now
    }
    
    # Add is_super_admin for admin users
    if user.get("role") == "admin":
        user_response["is_super_admin"] = user.get("is_super_admin", False)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user_response
    }


@auth_router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """Logout current user - invalidate session"""
    from server import db
    
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"active_session": {}}}
    )
    
    return {"message": "Logged out successfully"}


@auth_router.get("/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    """Get current user info"""
    response_data = {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "role": current_user["role"],
        "credits": current_user.get("credits", 0),
        "is_active": current_user["is_active"],
        "created_at": current_user["created_at"],
        "last_login": current_user.get("last_login")
    }
    # Add is_super_admin to response if user is admin
    if current_user.get("role") == "admin":
        response_data["is_super_admin"] = current_user.get("is_super_admin", False)
    return response_data


@auth_router.put("/change-password")
async def change_password(
    old_password: str,
    new_password: str,
    current_user: dict = Depends(get_current_user)
):
    """Change user password"""
    from server import db
    
    if not verify_password(old_password, current_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password": get_password_hash(new_password)}}
    )
    
    return {"message": "Password changed successfully"}


# ==================
# Admin Routes - User Management
# ==================

@admin_router.get("/users")
async def get_all_users(current_admin: dict = Depends(get_current_admin)):
    """Get all users (admin only)"""
    from server import db
    
    users = await db.users.find({}, {"_id": 0, "password": 0}).to_list(1000)
    
    # Add is_super_admin info for the requesting admin
    return {
        "users": users, 
        "total": len(users),
        "current_admin_is_super": current_admin.get("is_super_admin", False)
    }


@admin_router.get("/users/{user_id}")
async def get_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """Get specific user details"""
    from server import db
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get user's call history count
    call_count = await db.call_logs.count_documents({"user_id": user_id})
    user["total_calls"] = call_count
    
    return user


@admin_router.put("/users/{user_id}/toggle-active")
async def toggle_user_active(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """Enable/disable user account"""
    from server import db
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Cannot toggle your own account
    if user_id == current_admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot disable your own account")
    
    # For admin accounts: only super admin can toggle, and cannot toggle other super admins
    if user["role"] == "admin":
        if not current_admin.get("is_super_admin"):
            raise HTTPException(status_code=403, detail="Only Super Admin can disable other admins")
        if user.get("is_super_admin"):
            raise HTTPException(status_code=403, detail="Cannot disable Super Admin account")
    
    new_status = not user.get("is_active", True)
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"is_active": new_status}}
    )
    
    # If disabling, invalidate session
    if not new_status:
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"active_session": {}}}
        )
    
    return {"message": f"User {'enabled' if new_status else 'disabled'}", "is_active": new_status}


@admin_router.put("/users/{user_id}/edit")
async def edit_user(
    user_id: str,
    edit_data: UserEditRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Edit user details (name, email, password) - Admin only"""
    from server import db
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_data = {}
    changes = []
    
    # Update name if provided
    if edit_data.name and edit_data.name != user.get("name"):
        update_data["name"] = edit_data.name
        changes.append(f"name changed to '{edit_data.name}'")
    
    # Update email if provided
    if edit_data.email and edit_data.email.lower() != user.get("email"):
        # Check if email already exists
        existing = await db.users.find_one({"email": edit_data.email.lower(), "id": {"$ne": user_id}})
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use by another user")
        update_data["email"] = edit_data.email.lower()
        changes.append(f"email changed to '{edit_data.email.lower()}'")
    
    # Update password if provided
    if edit_data.new_password:
        update_data["password"] = get_password_hash(edit_data.new_password)
        changes.append("password changed")
        # Invalidate user session when password changes
        update_data["active_session"] = {}
    
    if not update_data:
        return {"message": "No changes made", "changes": []}
    
    # Perform update
    await db.users.update_one(
        {"id": user_id},
        {"$set": update_data}
    )
    
    return {
        "message": "User updated successfully",
        "changes": changes,
        "session_invalidated": "password" in str(changes)
    }


@admin_router.post("/users/{user_id}/credits")
async def adjust_user_credits(
    user_id: str,
    adjustment: CreditAdjustment,
    current_admin: dict = Depends(get_current_admin)
):
    """Add or deduct credits from user"""
    from server import db
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    current_credits = user.get("credits", 0)
    new_credits = current_credits + adjustment.amount
    
    if new_credits < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot deduct {abs(adjustment.amount)} credits. User only has {current_credits}"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    
    # Update user credits
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"credits": new_credits}}
    )
    
    # Add transaction log
    await db.credit_transactions.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "admin_adjustment",
        "amount": adjustment.amount,
        "balance_after": new_credits,
        "reason": adjustment.reason,
        "adjusted_by": current_admin["id"],
        "created_at": now
    })
    
    return {
        "message": f"Credits adjusted by {adjustment.amount}",
        "previous_credits": current_credits,
        "new_credits": new_credits
    }


@admin_router.get("/users/{user_id}/transactions")
async def get_user_transactions(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """Get user's credit transaction history"""
    from server import db
    
    transactions = await db.credit_transactions.find(
        {"user_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    
    return {"transactions": transactions}


@admin_router.delete("/users/{user_id}")
async def delete_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """Delete a user (admin cannot delete themselves or super admin)"""
    from server import db
    
    # Check if trying to delete self
    if user_id == current_admin["id"]:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    
    # Check if user exists
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if target is super admin - only super admin can delete other admins
    if user.get("role") == "admin":
        # If target is super admin, no one can delete
        if user.get("is_super_admin"):
            raise HTTPException(status_code=403, detail="Cannot delete Super Admin")
        
        # Only super admin can delete other admins
        if not current_admin.get("is_super_admin"):
            raise HTTPException(status_code=403, detail="Only Super Admin can delete other admins")
    
    # Delete user
    await db.users.delete_one({"id": user_id})
    
    # Also delete user's credit transactions
    await db.credit_transactions.delete_many({"user_id": user_id})
    
    return {"message": f"User {user['email']} deleted successfully"}


@admin_router.post("/create-admin")
async def create_admin(
    admin_data: AdminCreateRequest,
    current_admin: dict = Depends(get_current_admin)
):
    """Create a new admin user (only super admin can do this)"""
    from server import db
    
    # Only super admin can create new admins
    if not current_admin.get("is_super_admin"):
        raise HTTPException(
            status_code=403, 
            detail="Only Super Admin can create new admins"
        )
    
    # Check if email already exists
    existing_user = await db.users.find_one({"email": admin_data.email.lower()})
    if existing_user:
        raise HTTPException(
            status_code=400, 
            detail="Email already registered"
        )
    
    # Create new admin
    admin_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    
    new_admin = {
        "id": admin_id,
        "email": admin_data.email.lower(),
        "name": admin_data.name,
        "password": get_password_hash(admin_data.password),
        "role": "admin",
        "is_super_admin": False,  # New admins are not super admin
        "credits": 999999,  # Admins have unlimited credits
        "is_active": True,
        "created_at": now,
        "active_session": {}
    }
    
    await db.users.insert_one(new_admin)
    
    return {
        "message": f"Admin {admin_data.name} created successfully",
        "admin_id": admin_id,
        "email": admin_data.email.lower()
    }


# ==================
# Admin Routes - Invite Codes
# ==================

@admin_router.post("/invite-codes", response_model=InviteCodeResponse)
async def create_invite_code(
    code_data: InviteCodeCreate,
    current_admin: dict = Depends(get_current_admin)
):
    """Create new invite code"""
    from server import db
    
    code = code_data.code.upper() if code_data.code else generate_invite_code()
    
    # Check if code already exists
    existing = await db.invite_codes.find_one({"code": code})
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Invite code already exists"
        )
    
    now = datetime.now(timezone.utc).isoformat()
    
    new_code = {
        "id": str(uuid.uuid4()),
        "code": code,
        "credits": code_data.credits,
        "is_used": False,
        "used_by": None,
        "used_by_email": None,
        "used_by_name": None,
        "used_at": None,
        "notes": code_data.notes,
        "created_by": current_admin["id"],
        "created_by_name": current_admin["name"],
        "created_at": now
    }
    
    await db.invite_codes.insert_one(new_code)
    
    return InviteCodeResponse(
        id=new_code["id"],
        code=new_code["code"],
        credits=new_code["credits"],
        is_used=new_code["is_used"],
        notes=new_code["notes"],
        created_at=new_code["created_at"],
        created_by=current_admin["name"]
    )


@admin_router.post("/invite-codes/bulk")
async def create_bulk_invite_codes(
    count: int,
    credits: int,
    prefix: Optional[str] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Create multiple invite codes at once"""
    from server import db
    
    if count > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 codes at once")
    
    now = datetime.now(timezone.utc).isoformat()
    codes_created = []
    
    for _ in range(count):
        code = generate_invite_code()
        if prefix:
            code = f"{prefix.upper()}-{code.split('-')[1]}"
        
        new_code = {
            "id": str(uuid.uuid4()),
            "code": code,
            "credits": credits,
            "is_used": False,
            "used_by": None,
            "used_by_email": None,
            "used_by_name": None,
            "used_at": None,
            "notes": f"Bulk generated ({count} codes)",
            "created_by": current_admin["id"],
            "created_by_name": current_admin["name"],
            "created_at": now
        }
        
        await db.invite_codes.insert_one(new_code)
        codes_created.append(code)
    
    return {"message": f"Created {count} invite codes", "codes": codes_created}


@admin_router.get("/invite-codes")
async def get_all_invite_codes(
    used: Optional[bool] = None,
    current_admin: dict = Depends(get_current_admin)
):
    """Get all invite codes"""
    from server import db
    
    query = {}
    if used is not None:
        query["is_used"] = used
    
    codes = await db.invite_codes.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    
    stats = {
        "total": len(codes),
        "used": sum(1 for c in codes if c["is_used"]),
        "unused": sum(1 for c in codes if not c["is_used"])
    }
    
    return {"codes": codes, "stats": stats}


@admin_router.delete("/invite-codes/{code_id}")
async def delete_invite_code(code_id: str, current_admin: dict = Depends(get_current_admin)):
    """Delete invite code - allowed if unused OR if the user who used it no longer exists"""
    from server import db
    
    code = await db.invite_codes.find_one({"id": code_id}, {"_id": 0})
    if not code:
        raise HTTPException(status_code=404, detail="Invite code not found")
    
    # If code is used, check if the user still exists
    if code["is_used"] and code.get("used_by"):
        user_exists = await db.users.find_one({"id": code["used_by"]})
        if user_exists:
            raise HTTPException(
                status_code=400, 
                detail="Cannot delete: invite code was used by an existing user"
            )
    
    await db.invite_codes.delete_one({"id": code_id})
    
    return {"message": "Invite code deleted"}


# ==================
# Admin Routes - Dashboard Stats
# ==================

@admin_router.get("/dashboard/stats")
async def get_dashboard_stats(current_admin: dict = Depends(get_current_admin)):
    """Get admin dashboard statistics"""
    from server import db
    
    total_users = await db.users.count_documents({"role": "user"})
    active_users = await db.users.count_documents({"role": "user", "is_active": True})
    total_calls = await db.call_logs.count_documents({})
    total_credits_used = 0
    
    # Aggregate total credits used
    pipeline = [
        {"$match": {"type": "call_deduction"}},
        {"$group": {"_id": None, "total": {"$sum": {"$abs": "$amount"}}}}
    ]
    result = await db.credit_transactions.aggregate(pipeline).to_list(1)
    if result:
        total_credits_used = result[0].get("total", 0)
    
    # Invite code stats
    total_codes = await db.invite_codes.count_documents({})
    used_codes = await db.invite_codes.count_documents({"is_used": True})
    
    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "inactive": total_users - active_users
        },
        "calls": {
            "total": total_calls
        },
        "credits": {
            "total_used": total_credits_used
        },
        "invite_codes": {
            "total": total_codes,
            "used": used_codes,
            "unused": total_codes - used_codes
        }
    }



# ==================
# Security Routes (Super Admin Only)
# ==================

async def get_super_admin(current_admin: dict = Depends(get_current_admin)):
    """Dependency to ensure user is super admin"""
    if not current_admin.get("is_super_admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super Admin access required"
        )
    return current_admin


@security_router.get("/logs")
async def get_security_logs_endpoint(
    limit: int = 100,
    severity: Optional[str] = None,
    event_type: Optional[str] = None,
    current_admin: dict = Depends(get_super_admin)
):
    """Get security event logs (Super Admin only)"""
    logs = get_security_logs(limit=limit, severity=severity, event_type=event_type)
    return {"logs": logs, "count": len(logs)}


@security_router.delete("/logs")
async def clear_security_logs_endpoint(current_admin: dict = Depends(get_super_admin)):
    """Clear all security logs (Super Admin only)"""
    from security_advanced import security_logs
    cleared_count = len(security_logs)
    security_logs.clear()
    
    # Log the clear action itself
    log_security_event(
        event_type="security_logs_cleared",
        ip="system",
        details={"cleared_by": current_admin["email"], "cleared_count": cleared_count},
        user_id=current_admin["id"],
        severity="medium"
    )
    
    return {"message": f"Cleared {cleared_count} security logs"}


@security_router.get("/stats")
async def get_security_stats_endpoint(current_admin: dict = Depends(get_super_admin)):
    """Get security statistics (Super Admin only)"""
    stats = get_security_stats()
    return stats


@security_router.get("/check-password")
async def check_password_strength_endpoint(password: str):
    """Check password strength (public endpoint for signup validation)"""
    result = validate_password_strength(password)
    return result


@security_router.post("/test-input")
async def test_input_security(
    request: Request,
    current_admin: dict = Depends(get_super_admin)
):
    """Test input for potential security issues (Super Admin only - for testing)"""
    try:
        body = await request.json()
    except:
        body = {}
    
    # Scan for attacks
    findings = scan_for_attacks(body)
    
    # Sanitize
    sanitized = sanitize_dict(body)
    
    return {
        "original": body,
        "sanitized": sanitized,
        "findings": findings,
        "is_safe": len(findings) == 0
    }
