"""
Middleware for automatic user authentication and context injection
"""
from functools import wraps
from flask import request, g, jsonify
from server.services.auth import get_current_user

def require_auth(optional=False):
    """
    Decorator for API endpoints that need user authentication.
    
    Args:
        optional (bool): If True, user authentication is optional. 
                        If False, returns 401 if not authenticated.
    
    Returns:
        Decorated function with user context in g.current_user
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Extract session token from Authorization header
            auth_header = request.headers.get('Authorization', '')
            session_token = auth_header.replace('Bearer ', '') if auth_header.startswith('Bearer ') else None
            
            # Get current user
            user = None
            if session_token:
                try:
                    user = get_current_user(session_token)
                except Exception as e:
                    print(f"Auth error: {e}")
                    if not optional:
                        return jsonify({'success': False, 'error': 'Invalid session'}), 401
            
            # Store user in Flask's g object for access in route handlers
            g.current_user = user
            g.user_id = user['id'] if user else None
            g.session_token = session_token
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def inject_user_context(f):
    """
    Decorator that injects user context into API responses.
    Automatically adds user_id and user_progress to response data.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Call the original function
        response = f(*args, **kwargs)
        
        # If response is a JSON response, add user context
        if hasattr(response, 'json') and isinstance(response.json, dict):
            data = response.json
            if data.get('success', False):
                # Add user context to successful responses
                data['user_id'] = getattr(g, 'user_id', None)
                
                # Add user progress if available
                if hasattr(g, 'user_progress'):
                    data['user_progress'] = g.user_progress
        
        return response
    return decorated_function

def get_user_context():
    """
    Helper function to get current user context from Flask's g object.
    
    Returns:
        dict: User context with user_id, user, and session_token
    """
    return {
        'user_id': getattr(g, 'user_id', None),
        'user': getattr(g, 'current_user', None),
        'session_token': getattr(g, 'session_token', None),
        'is_authenticated': getattr(g, 'user_id', None) is not None
    }
