import hashlib
import secrets
import string
from datetime import datetime, timedelta, UTC
from typing import Optional, Dict, Any

from ..db import (
    create_user, get_user_by_username, get_user_by_email, get_user_by_id,
    update_user_last_login, create_user_session, get_user_by_session,
    delete_user_session, cleanup_expired_sessions
)

# Session configuration
SESSION_DURATION_HOURS = 24 * 7  # 7 days
SESSION_TOKEN_LENGTH = 32

def hash_password(password: str) -> str:
    """Hash a password using SHA-256 with salt"""
    salt = secrets.token_hex(16)
    password_hash = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{password_hash}"

def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password against its hash"""
    try:
        salt, stored_hash = password_hash.split(':', 1)
        password_hash_to_check = hashlib.sha256((password + salt).encode()).hexdigest()
        return password_hash_to_check == stored_hash
    except (ValueError, AttributeError):
        return False

def generate_session_token() -> str:
    """Generate a secure session token"""
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(SESSION_TOKEN_LENGTH))

def create_session(user_id: int) -> str:
    """Create a new session for a user"""
    try:
        # Clean up expired sessions first
        cleanup_expired_sessions()
        
        # Generate session token and expiration
        session_token = generate_session_token()
        expires_at = (datetime.now(UTC) + timedelta(hours=SESSION_DURATION_HOURS)).isoformat()
        
        # Create session in database
        session_id = create_user_session(user_id, session_token, expires_at)
        
        if not session_id:
            raise Exception("Failed to create session in database - session_id is None or 0")
        
        return session_token
    except Exception as e:
        print(f"DEBUG: create_session error: {str(e)} (type: {type(e)})")
        raise Exception(f"Session creation failed: {str(e)}")

def validate_session(session_token: str) -> Optional[Dict[str, Any]]:
    """Validate a session token and return user data if valid"""
    if not session_token:
        return None
    
    user = get_user_by_session(session_token)
    if not user:
        return None
    
    # Update last login if this is a new session validation
    update_user_last_login(user['id'])
    
    return {
        'id': user['id'],
        'username': user['username'],
        'email': user['email'],
        'created_at': user['created_at'],
        'last_login': user['last_login'],
        'settings': user['settings']
    }

def logout_user(session_token: str) -> bool:
    """Logout a user by deleting their session"""
    if not session_token:
        return False
    
    delete_user_session(session_token)
    return True

def register_user(username: str, email: str, password: str) -> Dict[str, Any]:
    """Register a new user"""
    # Validate input
    if not username or len(username.strip()) < 3:
        return {'success': False, 'error': 'Username must be at least 3 characters long'}
    
    if not email or '@' not in email:
        return {'success': False, 'error': 'Valid email address required'}
    
    if not password or len(password) < 6:
        return {'success': False, 'error': 'Password must be at least 6 characters long'}
    
    # Check if username already exists
    if get_user_by_username(username.strip()):
        return {'success': False, 'error': 'Username already exists'}
    
    # Check if email already exists
    if get_user_by_email(email.strip()):
        return {'success': False, 'error': 'Email already exists'}
    
    try:
        # Create user
        password_hash = hash_password(password)
        user_id = create_user(username.strip(), email.strip().lower(), password_hash)
        
        # Create session
        session_token = create_session(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'session_token': session_token,
            'message': 'User registered successfully'
        }
    except Exception as e:
        return {'success': False, 'error': f'Registration failed: {str(e)}'}

def login_user(username_or_email: str, password: str) -> Dict[str, Any]:
    """Login a user with username or email"""
    if not username_or_email or not password:
        return {'success': False, 'error': 'Username/email and password required'}
    
    # Try to find user by username or email
    user = get_user_by_username(username_or_email.strip())
    if not user:
        user = get_user_by_email(username_or_email.strip().lower())
    
    if not user:
        return {'success': False, 'error': 'Invalid username/email or password'}
    
    # Get password hash - handle both dict and Row objects
    if isinstance(user, dict):
        password_hash = user.get('password_hash')
    elif hasattr(user, 'keys'):  # SQLite Row object
        password_hash = user['password_hash']
    else:
        password_hash = getattr(user, 'password_hash', None)
    
    if not password_hash:
        return {'success': False, 'error': 'User data corrupted - no password hash'}
    
    if not verify_password(password, password_hash):
        return {'success': False, 'error': 'Invalid username/email or password'}
    
    try:
        # Create session - handle both dict and Row objects
        if isinstance(user, dict):
            user_id = user.get('id')
        elif hasattr(user, 'keys'):  # SQLite Row object
            user_id = user['id']
        else:
            user_id = getattr(user, 'id', None)
            
        if not user_id:
            return {'success': False, 'error': 'User data corrupted - no user ID'}
            
        session_token = create_session(user_id)
        
        return {
            'success': True,
            'user_id': user_id,
            'session_token': session_token,
            'message': 'Login successful'
        }
    except Exception as e:
        return {'success': False, 'error': f'Login failed: {str(e)}'}

def get_current_user(session_token: str) -> Optional[Dict[str, Any]]:
    """Get current user from session token"""
    return validate_session(session_token)

def require_auth(session_token: str) -> Optional[int]:
    """Require authentication and return user_id, or None if not authenticated"""
    user = validate_session(session_token)
    return user['id'] if user else None
