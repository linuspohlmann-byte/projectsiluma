#!/usr/bin/env python3
"""
Test script to verify S3 connection and configuration
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("python-dotenv not installed, using system environment variables")

from server.services.s3_storage import s3_storage
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_s3_connection():
    """Test S3 connection and basic operations"""
    
    logger.info("Testing S3 connection...")
    
    # Check if S3 client is initialized
    if not s3_storage.s3_client:
        logger.error("❌ S3 client not initialized")
        return False
    
    logger.info("✅ S3 client initialized")
    
    # Test bucket access
    try:
        response = s3_storage.s3_client.head_bucket(Bucket=s3_storage.bucket_name)
        logger.info(f"✅ Successfully connected to bucket: {s3_storage.bucket_name}")
    except Exception as e:
        logger.error(f"❌ Failed to access bucket {s3_storage.bucket_name}: {e}")
        return False
    
    # Test file upload (small test file)
    test_content = b"Hello S3! This is a test file."
    test_key = "test/connection-test.txt"
    
    try:
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
            temp_file.write(test_content)
            temp_file_path = temp_file.name
        
        # Upload test file
        s3_url = s3_storage.upload_audio_file(temp_file_path, test_key)
        if s3_url:
            logger.info(f"✅ Successfully uploaded test file: {s3_url}")
        else:
            logger.error("❌ Failed to upload test file")
            return False
        
        # Test file existence check
        if s3_storage.file_exists(test_key):
            logger.info("✅ File existence check works")
        else:
            logger.error("❌ File existence check failed")
            return False
        
        # Test file deletion
        if s3_storage.delete_file(test_key):
            logger.info("✅ File deletion works")
        else:
            logger.error("❌ File deletion failed")
            return False
        
        # Clean up temporary file
        os.unlink(temp_file_path)
        
    except Exception as e:
        logger.error(f"❌ Error during S3 operations: {e}")
        return False
    
    logger.info("🎉 All S3 tests passed!")
    return True

def main():
    """Main function"""
    logger.info("Starting S3 connection test...")
    
    # Check environment variables
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"❌ Missing environment variables: {', '.join(missing_vars)}")
        logger.error("Please create a .env file with your AWS credentials")
        return False
    
    logger.info("✅ All required environment variables found")
    
    success = test_s3_connection()
    
    if success:
        logger.info("🎉 S3 connection test completed successfully!")
        logger.info("You can now run the migration script: python migrate_audio_to_s3.py")
    else:
        logger.error("❌ S3 connection test failed")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
