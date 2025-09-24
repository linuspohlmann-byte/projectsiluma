#!/usr/bin/env python3
"""
WSGI entry point for Strato hosting
This file is required for Python hosting on Strato
"""

import os
import sys

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

# Set environment variables for production
os.environ.setdefault('FLASK_ENV', 'production')

try:
    # Import the Flask app
    from app import app
    
    # This is the WSGI application that Strato will use
    application = app
    
    # For local testing
    if __name__ == "__main__":
        app.run(debug=False, host='0.0.0.0', port=5000)
        
except Exception as e:
    # Log the error for debugging
    import logging
    logging.basicConfig(level=logging.DEBUG)
    logging.error(f"Failed to import Flask app: {e}")
    raise
