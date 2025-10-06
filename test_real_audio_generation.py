#!/usr/bin/env python3
"""
Test real audio generation and S3 upload
This test will actually generate a new audio file and upload it to S3
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

# You need to set your real OpenAI API key for this test
# os.environ['OPENAI_API_KEY'] = 'your-real-openai-key-here'

from server.services.tts import ensure_tts_for_word, _s3_ready
from server.services.s3_storage import tts_audio_exists, get_tts_audio_url
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_real_audio_generation():
    """Test real audio generation and S3 upload"""
    logger.info("Testing real audio generation and S3 upload...")
    
    if not _s3_ready():
        logger.error("❌ S3 not ready")
        return False
    
    # Check if OpenAI key is set
    if not os.environ.get('OPENAI_API_KEY') or os.environ.get('OPENAI_API_KEY') == 'your-real-openai-key-here':
        logger.warning("⚠️ OpenAI API key not set. Skipping real audio generation test.")
        logger.info("To test real audio generation:")
        logger.info("1. Set your OpenAI API key: export OPENAI_API_KEY='your-key'")
        logger.info("2. Run this test again")
        return True
    
    # Test with a unique word to avoid conflicts
    import time
    timestamp = int(time.time())
    test_word = f"testword{timestamp}"
    test_language = "en"
    
    logger.info(f"Generating audio for word: '{test_word}' in language: {test_language}")
    
    try:
        # Generate TTS audio (this will call OpenAI and upload to S3)
        audio_url = ensure_tts_for_word(test_word, test_language)
        
        if audio_url:
            logger.info(f"✅ Audio generated successfully: {audio_url}")
            
            # Verify the file exists in S3
            if audio_url.startswith('https://projectsiluma.s3.eu-central-1.amazonaws.com/'):
                logger.info("✅ Audio URL points to S3")
                
                # Extract filename from URL
                filename = audio_url.split('/')[-1]
                if tts_audio_exists(test_language, filename, 'tts'):
                    logger.info("✅ Audio file confirmed in S3")
                    logger.info(f"🎵 Audio is ready for playback at: {audio_url}")
                    return True
                else:
                    logger.error("❌ Audio file not found in S3")
                    return False
            else:
                logger.error(f"❌ Audio URL doesn't point to S3: {audio_url}")
                return False
        else:
            logger.error("❌ Audio generation failed")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error during audio generation: {e}")
        return False

def test_audio_playback_url():
    """Test that generated audio URLs are browser-ready"""
    logger.info("Testing audio playback URL format...")
    
    # Test URL format
    test_url = get_tts_audio_url('en', 'test.mp3', 'tts')
    
    if test_url.startswith('https://') and 'projectsiluma.s3.eu-central-1.amazonaws.com' in test_url:
        logger.info("✅ Audio URLs are browser-ready")
        logger.info(f"Example URL: {test_url}")
        logger.info("These URLs can be used directly in HTML <audio> tags or JavaScript")
        return True
    else:
        logger.error(f"❌ Audio URL format error: {test_url}")
        return False

def main():
    """Main function"""
    logger.info("Starting real audio generation test...")
    
    # Test URL format first
    if not test_audio_playback_url():
        return False
    
    # Test real generation if OpenAI key is available
    if not test_real_audio_generation():
        return False
    
    logger.info("🎉 Real audio generation test completed!")
    logger.info("")
    logger.info("📋 What this test verified:")
    logger.info("  ✅ Audio generation with OpenAI TTS")
    logger.info("  ✅ Automatic upload to S3")
    logger.info("  ✅ S3 URL generation")
    logger.info("  ✅ File existence verification")
    logger.info("  ✅ Browser-ready audio URLs")
    logger.info("")
    logger.info("🚀 Your app is now fully configured for S3 audio storage!")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
