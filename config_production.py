"""
Production configuration for Strato hosting
"""

import os

class ProductionConfig:
    """Production configuration settings"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    DEBUG = False
    TESTING = False
    
    # Database settings
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'polo.db')
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Security settings
    SESSION_COOKIE_SECURE = False  # Set to True if using HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CORS settings (if needed)
    CORS_ORIGINS = ['https://yourdomain.com']
    
    # Logging
    LOG_LEVEL = 'WARNING'
    
    # Performance settings
    JSON_SORT_KEYS = False
    JSONIFY_PRETTYPRINT_REGULAR = False
    
    # Static files
    STATIC_FOLDER = 'static'
    STATIC_URL_PATH = '/static'
    
    # Media files
    MEDIA_FOLDER = 'media'
    
    # User data folder
    USER_DATA_FOLDER = os.path.join(os.path.dirname(__file__), 'data', 'users')
    
    # Ensure directories exist
    @staticmethod
    def init_app(app):
        """Initialize the app with production settings"""
        import os
        
        # Create necessary directories
        os.makedirs(ProductionConfig.USER_DATA_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'media'), exist_ok=True)
        
        # Set up logging
        import logging
        logging.basicConfig(
            level=getattr(logging, ProductionConfig.LOG_LEVEL),
            format='%(asctime)s %(levelname)s %(name)s %(message)s'
        )
