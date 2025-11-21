#!/usr/bin/env python3
"""
Separate HTTP service for word duplicate cleanup.

This service runs independently and provides an HTTP endpoint
that can be triggered by the main application.
"""

import os
import sys
from flask import Flask, request, jsonify
from flask_cors import CORS

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cleanup_word_duplicates import run_cleanup

app = Flask(__name__)
CORS(app)  # Allow requests from main app

# Log startup information
print("=" * 60)
print("🧹 Word Duplicate Cleanup Service")
print("=" * 60)
print(f"📋 Service: {os.getenv('RAILWAY_SERVICE_NAME', 'cleanup_service')}")
print(f"🌐 Private Domain: {os.getenv('RAILWAY_PRIVATE_DOMAIN', 'N/A')}")
print(f"🔗 Database: {'PostgreSQL' if os.getenv('DATABASE_URL') else 'Not configured'}")
print("=" * 60)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'service': 'cleanup-service'})


@app.route('/cleanup', methods=['POST'])
def cleanup():
    """
    Trigger cleanup process.
    Accepts optional 'dry_run' parameter in JSON body.
    """
    try:
        data = request.get_json(force=True) or {}
        dry_run = data.get('dry_run', False)
        
        print(f"🔄 Cleanup requested (dry_run={dry_run})")
        
        stats = run_cleanup(dry_run=dry_run)
        
        return jsonify({
            'success': True,
            'stats': stats
        })
        
    except Exception as e:
        print(f"❌ Error in cleanup endpoint: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


if __name__ == '__main__':
    # Railway uses PORT environment variable automatically
    # Fallback to CLEANUP_SERVICE_PORT or default 5001
    port = int(os.getenv('PORT') or os.getenv('CLEANUP_SERVICE_PORT', 5001))
    host = os.getenv('HOST') or os.getenv('CLEANUP_SERVICE_HOST', '0.0.0.0')
    
    print(f"🚀 Starting cleanup service on {host}:{port}")
    print(f"📋 Service name: {os.getenv('RAILWAY_SERVICE_NAME', 'cleanup_service')}")
    print(f"🌐 Private domain: {os.getenv('RAILWAY_PRIVATE_DOMAIN', 'N/A')}")
    
    app.run(host=host, port=port, debug=False)

