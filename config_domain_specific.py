"""
Domain-specific configuration for 570864742.swh.strato-hosting.eu
"""

import os

class DomainConfig:
    """Domain-specific configuration settings"""
    
    # Domain information
    DOMAIN = "570864742.swh.strato-hosting.eu"
    BASE_URL = f"https://{DOMAIN}"
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'change-this-secret-key-in-production-2024'
    DEBUG = False
    TESTING = False
    
    # Database settings
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'polo.db')
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Security settings
    SESSION_COOKIE_SECURE = True  # HTTPS only
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CORS settings
    CORS_ORIGINS = [BASE_URL]
    
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
    
    # Strato-specific paths
    STRATO_PATH = "/kunden/homepages/57/570864742/htdocs/"
    
    @staticmethod
    def init_app(app):
        """Initialize the app with domain-specific settings"""
        import os
        import logging
        
        # Create necessary directories
        os.makedirs(DomainConfig.USER_DATA_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'media'), exist_ok=True)
        
        # Set up logging
        logging.basicConfig(
            level=getattr(logging, DomainConfig.LOG_LEVEL),
            format='%(asctime)s %(levelname)s %(name)s %(message)s'
        )
        
        # Log domain configuration
        logging.info(f"App configured for domain: {DomainConfig.DOMAIN}")
        logging.info(f"Base URL: {DomainConfig.BASE_URL}")
        logging.info(f"Strato path: {DomainConfig.STRATO_PATH}")
