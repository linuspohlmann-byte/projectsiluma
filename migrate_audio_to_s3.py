#!/usr/bin/env python3
"""
Migration script to upload existing audio files to S3
Run this script to migrate your local audio files to AWS S3
"""
import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from server.services.s3_storage import s3_storage
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate_audio_files():
    """Migrate all local audio files to S3"""
    
    # Check if S3 is configured
    if not s3_storage.s3_client:
        logger.error("S3 not configured. Please set AWS credentials and S3_BUCKET_NAME")
        return False
    
    media_dir = project_root / 'media'
    if not media_dir.exists():
        logger.error("Media directory not found")
        return False
    
    migrated_count = 0
    failed_count = 0
    
    # Migrate TTS word files
    tts_dir = media_dir / 'tts'
    if tts_dir.exists():
        logger.info("Migrating TTS word files...")
        for lang_dir in tts_dir.iterdir():
            if lang_dir.is_dir():
                lang = lang_dir.name
                logger.info(f"Processing language: {lang}")
                
                for audio_file in lang_dir.glob('*.mp3'):
                    s3_key = f"media/tts/{lang}/{audio_file.name}"
                    
                    # Check if file already exists in S3
                    if s3_storage.file_exists(s3_key):
                        logger.info(f"File already exists in S3: {s3_key}")
                        continue
                    
                    # Upload to S3
                    s3_url = s3_storage.upload_audio_file(str(audio_file), s3_key)
                    if s3_url:
                        logger.info(f"Migrated: {audio_file.name} -> {s3_url}")
                        migrated_count += 1
                    else:
                        logger.error(f"Failed to migrate: {audio_file.name}")
                        failed_count += 1
    
    # Migrate TTS sentence files
    tts_sentences_dir = media_dir / 'tts_sentences'
    if tts_sentences_dir.exists():
        logger.info("Migrating TTS sentence files...")
        for lang_dir in tts_sentences_dir.iterdir():
            if lang_dir.is_dir():
                lang = lang_dir.name
                logger.info(f"Processing language: {lang}")
                
                for audio_file in lang_dir.glob('*.mp3'):
                    s3_key = f"media/tts_sentences/{lang}/{audio_file.name}"
                    
                    # Check if file already exists in S3
                    if s3_storage.file_exists(s3_key):
                        logger.info(f"File already exists in S3: {s3_key}")
                        continue
                    
                    # Upload to S3
                    s3_url = s3_storage.upload_audio_file(str(audio_file), s3_key)
                    if s3_url:
                        logger.info(f"Migrated: {audio_file.name} -> {s3_url}")
                        migrated_count += 1
                    else:
                        logger.error(f"Failed to migrate: {audio_file.name}")
                        failed_count += 1
    
    logger.info(f"Migration completed: {migrated_count} files migrated, {failed_count} failed")
    return failed_count == 0

def main():
    """Main function"""
    logger.info("Starting audio file migration to S3...")
    
    # Check environment variables
    required_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'S3_BUCKET_NAME']
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    
    if missing_vars:
        logger.error(f"Missing environment variables: {', '.join(missing_vars)}")
        logger.error("Please set these variables in your .env file or environment")
        return False
    
    success = migrate_audio_files()
    
    if success:
        logger.info("✅ Migration completed successfully!")
    else:
        logger.error("❌ Migration completed with errors")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
