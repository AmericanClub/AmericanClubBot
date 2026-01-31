"""
Advanced Security Module
- Security Headers
- Input Validation & Sanitization
- Request Size Limiting
- Suspicious Activity Detection & Logging
- NoSQL Injection Prevention
"""
import re
import time
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
import logging

logger = logging.getLogger(__name__)

# ===================
# Security Configuration
# ===================

MAX_REQUEST_SIZE = 1 * 1024 * 1024  # 1MB max request body
MAX_INPUT_LENGTH = {
    "email": 254,
    "password": 128,
    "name": 100,
    "invite_code": 50,
    "phone": 20,
    "default": 1000
}

# Patterns that indicate potential attacks
SUSPICIOUS_PATTERNS = [
    # NoSQL Injection patterns
    r'\$where',
    r'\$regex',
    r'\$gt',
    r'\$lt',
    r'\$ne',
    r'\$or',
    r'\$and',
    r'\$not',
    r'\$exists',
    r'\$elemMatch',
    r'\$in',
    r'\$nin',
    r'{\s*"\$',
    # SQL Injection patterns (in case of mixed DB)
    r"('\s*OR\s*')",
    r"('\s*AND\s*')",
    r'(;\s*DROP\s+TABLE)',
    r'(;\s*DELETE\s+FROM)',
    r'(UNION\s+SELECT)',
    # XSS patterns
    r'<script[^>]*>',
    r'javascript:',
    r'on\w+\s*=',
    r'<iframe',
    r'<object',
    r'<embed',
    # Path traversal
    r'\.\./\.\.',
    r'\.\.\\\\',
    # Command injection
    r';\s*cat\s+',
    r';\s*ls\s+',
    r'\|\s*cat\s+',
    r'`[^`]+`',
]

# Compiled patterns for efficiency
COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in SUSPICIOUS_PATTERNS]

# In-memory security log storage (in production, use Redis/DB)
security_logs: List[Dict] = []
MAX_SECURITY_LOGS = 1000


# ===================
# Security Headers Middleware
# ===================

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Security Headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy (adjust based on your needs)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        
        # Strict Transport Security (for HTTPS)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response


# ===================
# Request Size Limiter Middleware
# ===================

class RequestSizeLimiterMiddleware(BaseHTTPMiddleware):
    """Limit request body size to prevent DoS attacks"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        
        if content_length:
            content_length = int(content_length)
            if content_length > MAX_REQUEST_SIZE:
                log_security_event(
                    event_type="large_request_blocked",
                    ip=get_client_ip(request),
                    details={"content_length": content_length, "max_allowed": MAX_REQUEST_SIZE}
                )
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"Request too large. Maximum size is {MAX_REQUEST_SIZE // 1024}KB"
                )
        
        return await call_next(request)


# ===================
# Input Sanitization
# ===================

def sanitize_string(value: str, field_name: str = "default") -> str:
    """Sanitize string input"""
    if not isinstance(value, str):
        return value
    
    # Get max length for this field
    max_length = MAX_INPUT_LENGTH.get(field_name, MAX_INPUT_LENGTH["default"])
    
    # Truncate if too long
    value = value[:max_length]
    
    # Remove null bytes
    value = value.replace('\x00', '')
    
    # Remove potential NoSQL operators at the start
    if value.startswith('$'):
        value = value[1:]
    
    return value


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize dictionary input"""
    if not isinstance(data, dict):
        return data
    
    sanitized = {}
    for key, value in data.items():
        # Sanitize key (remove $ prefix which could be NoSQL operator)
        safe_key = key.lstrip('$') if isinstance(key, str) else key
        
        if isinstance(value, str):
            sanitized[safe_key] = sanitize_string(value, safe_key)
        elif isinstance(value, dict):
            sanitized[safe_key] = sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[safe_key] = [sanitize_dict(v) if isinstance(v, dict) else v for v in value]
        else:
            sanitized[safe_key] = value
    
    return sanitized


def detect_injection(value: str) -> bool:
    """Check if string contains potential injection patterns"""
    if not isinstance(value, str):
        return False
    
    for pattern in COMPILED_PATTERNS:
        if pattern.search(value):
            return True
    
    return False


def scan_for_attacks(data: Any, path: str = "") -> List[str]:
    """Recursively scan data for potential attack patterns"""
    findings = []
    
    if isinstance(data, str):
        if detect_injection(data):
            findings.append(f"Suspicious pattern at {path}: {data[:100]}...")
    elif isinstance(data, dict):
        for key, value in data.items():
            # Check if key itself is suspicious
            if isinstance(key, str) and key.startswith('$'):
                findings.append(f"NoSQL operator in key at {path}: {key}")
            findings.extend(scan_for_attacks(value, f"{path}.{key}"))
    elif isinstance(data, list):
        for i, item in enumerate(data):
            findings.extend(scan_for_attacks(item, f"{path}[{i}]"))
    
    return findings


# ===================
# Security Logging
# ===================

def get_client_ip(request: Request) -> str:
    """Get real client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    return request.client.host if request.client else "unknown"


def log_security_event(
    event_type: str,
    ip: str,
    details: Dict[str, Any] = None,
    user_id: str = None,
    severity: str = "medium"
):
    """Log a security event"""
    global security_logs
    
    event = {
        "id": hashlib.md5(f"{time.time()}{ip}{event_type}".encode()).hexdigest()[:16],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "ip": ip,
        "user_id": user_id,
        "severity": severity,
        "details": details or {}
    }
    
    security_logs.append(event)
    
    # Keep only last N logs
    if len(security_logs) > MAX_SECURITY_LOGS:
        security_logs = security_logs[-MAX_SECURITY_LOGS:]
    
    # Log to console for monitoring
    logger.warning(f"SECURITY EVENT [{severity.upper()}]: {event_type} from {ip} - {details}")


def get_security_logs(
    limit: int = 100,
    severity: str = None,
    event_type: str = None
) -> List[Dict]:
    """Get security logs with optional filtering"""
    logs = security_logs.copy()
    
    if severity:
        logs = [l for l in logs if l["severity"] == severity]
    
    if event_type:
        logs = [l for l in logs if l["event_type"] == event_type]
    
    # Return most recent first
    return sorted(logs, key=lambda x: x["timestamp"], reverse=True)[:limit]


def get_security_stats() -> Dict:
    """Get security statistics"""
    now = datetime.now(timezone.utc)
    
    # Count events by type
    event_counts = {}
    severity_counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
    unique_ips = set()
    
    for log in security_logs:
        event_type = log["event_type"]
        event_counts[event_type] = event_counts.get(event_type, 0) + 1
        severity_counts[log["severity"]] = severity_counts.get(log["severity"], 0) + 1
        unique_ips.add(log["ip"])
    
    return {
        "total_events": len(security_logs),
        "unique_ips": len(unique_ips),
        "events_by_type": event_counts,
        "events_by_severity": severity_counts,
        "last_updated": now.isoformat()
    }


# ===================
# Validation Functions
# ===================

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email)) and len(email) <= MAX_INPUT_LENGTH["email"]


def validate_phone(phone: str) -> bool:
    """Validate phone number format"""
    # Remove common separators
    clean = re.sub(r'[\s\-\(\)\.]', '', phone)
    # Check if it's a valid phone number (digits only, optional + prefix)
    pattern = r'^\+?[1-9]\d{6,14}$'
    return bool(re.match(pattern, clean))


def validate_password_strength(password: str) -> Dict[str, Any]:
    """Check password strength"""
    issues = []
    score = 0
    
    if len(password) >= 8:
        score += 1
    else:
        issues.append("Password should be at least 8 characters")
    
    if len(password) >= 12:
        score += 1
    
    if re.search(r'[a-z]', password):
        score += 1
    else:
        issues.append("Password should contain lowercase letters")
    
    if re.search(r'[A-Z]', password):
        score += 1
    else:
        issues.append("Password should contain uppercase letters")
    
    if re.search(r'\d', password):
        score += 1
    else:
        issues.append("Password should contain numbers")
    
    if re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        score += 1
    
    strength = "weak"
    if score >= 5:
        strength = "strong"
    elif score >= 3:
        strength = "medium"
    
    return {
        "score": score,
        "max_score": 6,
        "strength": strength,
        "issues": issues
    }
