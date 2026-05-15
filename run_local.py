#!/usr/bin/env python3
"""
Local development server for ProjectSiluma
"""
import os
import sys

# Set environment variables for local development
os.environ.setdefault('FLASK_ENV', 'development')
os.environ.setdefault('PORT', '5001')
os.environ.setdefault('FORCE_SQLITE', '1')
os.environ.setdefault('SILUMA_QUIET', '1')

# Add the project directory to Python path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)
os.environ.setdefault('PYTHONPATH', project_dir)

# Import and run the Flask app
if __name__ == '__main__':
    try:
        from app import app
        print("🚀 Starting ProjectSiluma local development server...")
        print("📝 Server will be available at: http://localhost:5001")
        print("🔍 Debug mode: ON")
        print("=" * 50)
        
        # Run the app in debug mode
        app.run(debug=True, host='127.0.0.1', port=5001, use_reloader=False)
    except Exception as e:
        print(f"❌ Failed to start Flask app: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


