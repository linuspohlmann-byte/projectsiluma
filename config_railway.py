"""
Railway-specific configuration for ProjectSiluma
"""

import os

class RailwayConfig:
    """Railway-specific configuration settings"""
    
    # Railway information
    PLATFORM = "Railway"
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'railway-secret-key-change-in-production'
    DEBUG = False
    TESTING = False
    
    # Database settings - default path if Postgres is not available
    DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'polo.db')
    
    @staticmethod
    def ensure_database_config():
        """
        Ensure Railway keeps DATABASE_URL so the app can use PostgreSQL when available.
        Log a helpful message when the variable is missing so fallbacks are explicit.
        """
        import logging
        if not os.environ.get('DATABASE_URL'):
            logging.warning("DATABASE_URL not set on Railway – falling back to local SQLite.")
    
    # File upload settings
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Security settings
    SESSION_COOKIE_SECURE = True  # HTTPS only on Railway
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # CORS settings
    CORS_ORIGINS = ['*']  # Railway allows dynamic origins
    
    # CORS headers for API access
    CORS_HEADERS = ['Content-Type', 'Authorization', 'X-Requested-With']
    CORS_METHODS = ['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS']
    
    # Logging
    LOG_LEVEL = 'INFO'
    
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
    
    # Railway-specific settings
    PORT = int(os.environ.get('PORT', 5000))
    HOST = '0.0.0.0'
    
    # TTS settings for Railway
    TTS_CACHE_ENABLED = True
    TTS_FALLBACK_ENABLED = True  # Enable fallback for missing audio files
    
    # Background sync settings
    SYNC_ENABLED = True
    SYNC_INTERVAL = 300  # 5 minutes
    
    @staticmethod
    def init_app(app):
        """Initialize the app with Railway settings"""
        import os
        import logging
        
        # Ensure database configuration is correct (prefer PostgreSQL when available)
        RailwayConfig.ensure_database_config()
        
        # Create necessary directories
        os.makedirs(RailwayConfig.USER_DATA_FOLDER, exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'data'), exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'media'), exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'media', 'tts'), exist_ok=True)
        os.makedirs(os.path.join(os.path.dirname(__file__), 'media', 'tts_sentences'), exist_ok=True)
        
        # Set up logging for Railway
        logging.basicConfig(
            level=getattr(logging, RailwayConfig.LOG_LEVEL),
            format='%(asctime)s %(levelname)s %(name)s %(message)s'
        )
        
        # Log Railway configuration
        logging.info(f"App configured for Railway platform")
        logging.info(f"Port: {RailwayConfig.PORT}")
        logging.info(f"TTS Cache: {RailwayConfig.TTS_CACHE_ENABLED}")
        logging.info(f"Background Sync: {RailwayConfig.SYNC_ENABLED}")
        logging.info(
            "Database: %s",
            "PostgreSQL" if os.environ.get('DATABASE_URL') else "SQLite (fallback)"
        )
