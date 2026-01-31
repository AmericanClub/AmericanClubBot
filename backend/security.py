"""
Security Module - Rate Limiting & CAPTCHA
"""
import random
import time
from datetime import datetime, timezone
from typing import Dict, Tuple, Optional
from fastapi import HTTPException, Request
from collections import defaultdict
import hashlib

# Rate limiting storage (in production, use Redis)
# Format: {ip: {"attempts": count, "last_attempt": timestamp, "blocked_until": timestamp}}
rate_limit_storage: Dict[str, Dict] = defaultdict(lambda: {"attempts": 0, "last_attempt": 0, "blocked_until": 0})

# CAPTCHA storage (in production, use Redis with TTL)
# Format: {captcha_id: {"answer": int, "created_at": timestamp}}
captcha_storage: Dict[str, Dict] = {}

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # seconds
MAX_ATTEMPTS_PER_WINDOW = 5  # max login attempts per minute
BLOCK_DURATION = 300  # 5 minutes block after exceeding limit


def get_client_ip(request: Request) -> str:
    """Get real client IP address"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check_rate_limit(ip: str) -> Tuple[bool, Optional[int]]:
    """
    Check if IP is rate limited
    Returns: (is_allowed, seconds_until_unblock)
    """
    current_time = time.time()
    data = rate_limit_storage[ip]
    
    # Check if currently blocked
    if data["blocked_until"] > current_time:
        remaining = int(data["blocked_until"] - current_time)
        return False, remaining
    
    # Reset counter if window has passed
    if current_time - data["last_attempt"] > RATE_LIMIT_WINDOW:
        data["attempts"] = 0
    
    return True, None


def record_login_attempt(ip: str, success: bool = False):
    """Record a login attempt"""
    current_time = time.time()
    data = rate_limit_storage[ip]
    
    if success:
        # Reset on successful login
        data["attempts"] = 0
        data["blocked_until"] = 0
    else:
        data["attempts"] += 1
        data["last_attempt"] = current_time
        
        # Block if exceeded limit
        if data["attempts"] >= MAX_ATTEMPTS_PER_WINDOW:
            data["blocked_until"] = current_time + BLOCK_DURATION


def generate_captcha() -> Tuple[str, str, int]:
    """
    Generate a simple math CAPTCHA
    Returns: (captcha_id, question, answer)
    """
    # Clean old CAPTCHAs (older than 5 minutes)
    current_time = time.time()
    expired_ids = [cid for cid, data in captcha_storage.items() 
                   if current_time - data["created_at"] > 300]
    for cid in expired_ids:
        del captcha_storage[cid]
    
    # Generate random math problem
    operations = [
        ("+", lambda a, b: a + b),
        ("-", lambda a, b: a - b),
        ("×", lambda a, b: a * b),
    ]
    
    op_symbol, op_func = random.choice(operations)
    
    if op_symbol == "×":
        # Keep multiplication simple
        num1 = random.randint(2, 9)
        num2 = random.randint(2, 9)
    elif op_symbol == "-":
        # Ensure positive result
        num1 = random.randint(5, 15)
        num2 = random.randint(1, num1 - 1)
    else:
        num1 = random.randint(1, 15)
        num2 = random.randint(1, 15)
    
    answer = op_func(num1, num2)
    question = f"{num1} {op_symbol} {num2} = ?"
    
    # Generate unique ID
    captcha_id = hashlib.md5(f"{time.time()}{random.random()}".encode()).hexdigest()[:16]
    
    # Store CAPTCHA
    captcha_storage[captcha_id] = {
        "answer": answer,
        "created_at": current_time
    }
    
    return captcha_id, question, answer


def verify_captcha(captcha_id: str, user_answer: int) -> bool:
    """
    Verify CAPTCHA answer
    Returns: True if correct, False otherwise
    """
    if captcha_id not in captcha_storage:
        return False
    
    data = captcha_storage[captcha_id]
    
    # Check if expired (5 minutes)
    if time.time() - data["created_at"] > 300:
        del captcha_storage[captcha_id]
        return False
    
    # Verify answer
    is_correct = data["answer"] == user_answer
    
    # Remove CAPTCHA after verification (one-time use)
    del captcha_storage[captcha_id]
    
    return is_correct


def get_rate_limit_info(ip: str) -> Dict:
    """Get rate limit info for an IP"""
    current_time = time.time()
    data = rate_limit_storage[ip]
    
    is_blocked = data["blocked_until"] > current_time
    remaining_time = max(0, int(data["blocked_until"] - current_time)) if is_blocked else 0
    
    return {
        "attempts": data["attempts"],
        "max_attempts": MAX_ATTEMPTS_PER_WINDOW,
        "is_blocked": is_blocked,
        "blocked_seconds_remaining": remaining_time,
        "window_seconds": RATE_LIMIT_WINDOW
    }
