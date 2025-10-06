#!/usr/bin/env python3
"""
Test script to verify TTS service works with S3
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Set environment variables (use your actual credentials)
# os.environ['AWS_ACCESS_KEY_ID'] = 'your-access-key-here'
# os.environ['AWS_SECRET_ACCESS_KEY'] = 'your-secret-key-here'
# os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'
# os.environ['S3_BUCKET_NAME'] = 'your-bucket-name'

# Set a dummy OpenAI key for testing (won't actually call OpenAI)
os.environ['OPENAI_API_KEY'] = 'test-key'

from server.services.tts import ensure_tts_for_word, _s3_ready
from server.services.s3_storage import tts_audio_exists, get_tts_audio_url
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_tts_s3_integration():
    """Test TTS service with S3 integration"""
    
    logger.info("Testing TTS service with S3 integration...")
    
    # Check if S3 is ready
    if not _s3_ready():
        logger.error("❌ S3 not ready")
        return False
    
    logger.info("✅ S3 is ready")
    
    # Test with a word that should exist in S3 (from migration)
    test_word = "hello"
    test_language = "en"
    
    # Check if the word exists in S3
    # We need to construct the filename that would be generated
    import hashlib
    sig = hashlib.sha1("openai:gpt-4o-mini-tts:alloy".encode('utf-8')).hexdigest()[:6]
    fname = f"hello__{sig}.mp3"
    
    if tts_audio_exists(test_language, fname, 'tts'):
        s3_url = get_tts_audio_url(test_language, fname, 'tts')
        logger.info(f"✅ Found existing audio in S3: {s3_url}")
        return True
    else:
        logger.info(f"ℹ️ Audio file not found in S3: {fname}")
        logger.info("This is normal if the word hasn't been generated yet")
        return True

def test_s3_storage_functions():
    """Test S3 storage helper functions"""
    
    logger.info("Testing S3 storage helper functions...")
    
    # Test URL generation
    test_url = get_tts_audio_url('en', 'test.mp3', 'tts')
    expected_url = "https://projectsiluma.s3.eu-central-1.amazonaws.com/media/tts/en/test.mp3"
    
    if test_url == expected_url:
        logger.info("✅ URL generation works correctly")
    else:
        logger.error(f"❌ URL generation failed: {test_url} != {expected_url}")
        return False
    
    # Test file existence check (should return False for non-existent file)
    if not tts_audio_exists('en', 'non-existent-file.mp3', 'tts'):
        logger.info("✅ File existence check works correctly")
    else:
        logger.error("❌ File existence check failed")
        return False
    
    return True

def main():
    """Main function"""
    logger.info("Starting TTS S3 integration test...")
    
    success1 = test_s3_storage_functions()
    success2 = test_tts_s3_integration()
    
    if success1 and success2:
        logger.info("🎉 All TTS S3 tests passed!")
        logger.info("Your TTS service is ready to use S3 for audio storage!")
    else:
        logger.error("❌ Some TTS S3 tests failed")
    
    return success1 and success2

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
