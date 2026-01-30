"""
Authentication Module - JWT, Password Hashing, Session Management
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, EmailStr
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import uuid

# JWT Settings - SECRET_KEY is required in production
SECRET_KEY = os.environ.get("JWT_SECRET_KEY") or os.environ.get("APP_URL", "fallback-dev-key-" + str(uuid.uuid4()))
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES_USER = 60 * 24  # 24 hours for users
ACCESS_TOKEN_EXPIRE_MINUTES_ADMIN = 60 * 24 * 365  # 1 year for admins (effectively never)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security scheme
security = HTTPBearer()


# ==================
# Pydantic Models
# ==================

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    invite_code: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    credits: int
    is_active: bool
    created_at: str
    last_login: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class InviteCodeCreate(BaseModel):
    code: Optional[str] = None  # Auto-generate if not provided
    credits: int = Field(ge=0, description="Credits to assign")
    notes: Optional[str] = None


class InviteCodeResponse(BaseModel):
    id: str
    code: str
    credits: int
    is_used: bool
    used_by_email: Optional[str] = None
    used_by_name: Optional[str] = None
    used_at: Optional[str] = None
    notes: Optional[str] = None
    created_at: str
    created_by: str


class CreditAdjustment(BaseModel):
    amount: int = Field(description="Positive to add, negative to deduct")
    reason: str


# ==================
# Helper Functions
# ==================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """Hash a password"""
    return pwd_context.hash(password)


def create_access_token(data: dict, role: str = "user") -> tuple[str, str]:
    """Create JWT access token with session ID"""
    to_encode = data.copy()
    
    # Set expiry based on role
    if role == "admin":
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_ADMIN)
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES_USER)
    
    # Generate unique session ID for single-device enforcement
    session_id = str(uuid.uuid4())
    
    to_encode.update({
        "exp": expire,
        "session_id": session_id,
        "role": role
    })
    
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt, session_id


def decode_token(token: str) -> dict:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def generate_invite_code() -> str:
    """Generate a random invite code"""
    import random
    import string
    prefix = "INV"
    random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    return f"{prefix}-{random_part}"


def get_client_ip(request: Request) -> str:
    """Get client IP address from request"""
    # Check for forwarded headers (behind proxy/load balancer)
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    return request.client.host if request.client else "unknown"


def get_device_info(request: Request) -> str:
    """Get device/browser info from User-Agent"""
    user_agent = request.headers.get("user-agent", "unknown")
    # Truncate if too long
    return user_agent[:200] if len(user_agent) > 200 else user_agent


# ==================
# Dependency Functions
# ==================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    request: Request = None
):
    """
    Dependency to get current authenticated user
    Also validates single-device session
    """
    from server import db  # Import here to avoid circular import
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Session expired, please login again",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        raise credentials_exception
    
    user_id: str = payload.get("sub")
    session_id: str = payload.get("session_id")
    
    if user_id is None or session_id is None:
        raise credentials_exception
    
    # Get user from database
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    
    if user is None:
        raise credentials_exception
    
    if not user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    
    # Validate session ID (single device enforcement)
    active_session = user.get("active_session", {})
    if active_session.get("session_id") != session_id:
        raise credentials_exception
    
    return user


async def get_current_admin(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure user is admin"""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


async def get_current_active_user(current_user: dict = Depends(get_current_user)):
    """Dependency to ensure user is active"""
    if not current_user.get("is_active", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled"
        )
    return current_user
