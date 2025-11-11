"""
S3 Storage Service for Audio Files
Handles uploading and serving audio files from AWS S3
"""
import os
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.exceptions import S3UploadFailedError
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class S3AudioStorage:
    def __init__(self):
        self.bucket_name = os.environ.get('S3_BUCKET_NAME', 'siluma-audio-files')
        self.region = os.environ.get('AWS_DEFAULT_REGION', 'eu-central-1')
        
        # Check if S3 credentials are available
        aws_key = os.environ.get('AWS_ACCESS_KEY_ID')
        aws_secret = os.environ.get('AWS_SECRET_ACCESS_KEY')
        
        if not aws_key or not aws_secret:
            logger.warning("AWS credentials not found. S3 integration disabled. Using local file storage.")
            self.s3_client = None
            return
        
        # Initialize S3 client
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=aws_key,
                aws_secret_access_key=aws_secret,
                region_name=self.region
            )
            logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
        except NoCredentialsError:
            logger.error("AWS credentials not found. Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY")
            self.s3_client = None
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None
    
    def upload_audio_bytes(self, audio_bytes: bytes, s3_key: str) -> Optional[str]:
        """
        Upload audio bytes directly to S3 without saving to disk first.
        More efficient than upload_audio_file when you already have bytes in memory.
        
        Args:
            audio_bytes: Audio file bytes
            s3_key: S3 object key (path in bucket)
            
        Returns:
            Public URL of uploaded file or None if failed
        """
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return None
        
        try:
            import io
            # Try uploading with ACL first (for older buckets)
            try:
                audio_file_obj = io.BytesIO(audio_bytes)
                self.s3_client.upload_fileobj(
                    audio_file_obj,
                    self.bucket_name,
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'audio/mpeg',
                        'CacheControl': 'max-age=31536000',  # 1 year cache
                        'ACL': 'public-read'  # Make file publicly accessible
                    }
                )
                logger.info(f"Successfully uploaded {s3_key} to S3 with ACL (from bytes)")
            except (ClientError, S3UploadFailedError) as acl_error:
                # If ACL fails, try without ACL (bucket might use bucket policy instead)
                error_str = str(acl_error)
                if 'AccessControlListNotSupported' in error_str or 'InvalidRequest' in error_str or 'ACL' in error_str:
                    logger.warning(f"ACL not supported for bucket, trying without ACL: {acl_error}")
                    # Create a NEW BytesIO object for retry (the previous one may be closed)
                    audio_file_obj = io.BytesIO(audio_bytes)
                    self.s3_client.upload_fileobj(
                        audio_file_obj,
                        self.bucket_name,
                        s3_key,
                        ExtraArgs={
                            'ContentType': 'audio/mpeg',
                            'ContentDisposition': 'inline',
                            'CacheControl': 'max-age=31536000'  # 1 year cache
                        }
                    )
                    logger.info(f"Successfully uploaded {s3_key} to S3 without ACL (from bytes)")
                else:
                    raise  # Re-raise if it's a different error
            
            # Generate public URL
            public_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"✅ Audio file uploaded from bytes: {s3_key} -> {public_url}")
            return public_url
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"Failed to upload {s3_key} to S3: {error_code} - {error_message}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error uploading {s3_key} to S3: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def upload_audio_file(self, local_file_path: str, s3_key: str) -> Optional[str]:
        """
        Upload audio file to S3 and return public URL
        
        Args:
            local_file_path: Path to local audio file
            s3_key: S3 object key (path in bucket)
            
        Returns:
            Public URL of uploaded file or None if failed
        """
        if not self.s3_client:
            logger.error("S3 client not initialized")
            return None
            
        try:
            # Try uploading with ACL first (for older buckets)
            try:
                self.s3_client.upload_file(
                    local_file_path, 
                    self.bucket_name, 
                    s3_key,
                    ExtraArgs={
                        'ContentType': 'audio/mpeg',
                        'CacheControl': 'max-age=31536000',  # 1 year cache
                        'ACL': 'public-read'  # Make file publicly accessible
                    }
                )
                logger.info(f"Successfully uploaded {s3_key} to S3 with ACL")
            except (ClientError, S3UploadFailedError) as acl_error:
                # If ACL fails, try without ACL (bucket might use bucket policy instead)
                error_str = str(acl_error)
                if 'AccessControlListNotSupported' in error_str or 'InvalidRequest' in error_str or 'ACL' in error_str:
                    logger.warning(f"ACL not supported for bucket, trying without ACL: {acl_error}")
                    self.s3_client.upload_file(
                        local_file_path, 
                        self.bucket_name, 
                        s3_key,
                        ExtraArgs={
                            'ContentType': 'audio/mpeg',
                            'CacheControl': 'max-age=31536000'  # 1 year cache
                        }
                    )
                    logger.info(f"Successfully uploaded {s3_key} to S3 without ACL")
                else:
                    raise  # Re-raise if it's a different error
            
            # Generate public URL
            public_url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
            logger.info(f"✅ Audio file uploaded: {s3_key} -> {public_url}")
            return public_url
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            error_message = e.response.get('Error', {}).get('Message', str(e))
            logger.error(f"❌ Failed to upload {s3_key} to S3: {error_code} - {error_message}")
            return None
        except FileNotFoundError:
            logger.error(f"❌ Local file not found: {local_file_path}")
            return None
        except Exception as e:
            logger.error(f"❌ Unexpected error uploading {s3_key}: {type(e).__name__}: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def file_exists(self, s3_key: str) -> bool:
        """
        Check if file exists in S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if file exists, False otherwise
        """
        if not self.s3_client:
            return False
            
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=s3_key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            logger.error(f"Error checking file existence for {s3_key}: {e}")
            return False
    
    def get_public_url(self, s3_key: str) -> str:
        """
        Get public URL for S3 object
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Public URL
        """
        return f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{s3_key}"
    
    def delete_file(self, s3_key: str) -> bool:
        """
        Delete file from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful, False otherwise
        """
        if not self.s3_client:
            return False
            
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
            logger.info(f"Successfully deleted {s3_key} from S3")
            return True
        except ClientError as e:
            logger.error(f"Failed to delete {s3_key} from S3: {e}")
            return False

# Global instance
s3_storage = S3AudioStorage()

def upload_tts_audio_bytes(audio_bytes: bytes, language: str, filename: str, audio_type: str = 'tts') -> Optional[str]:
    """
    Upload TTS audio bytes directly to S3 without saving to disk first.
    More efficient than upload_tts_audio when you already have bytes in memory.
    
    Args:
        audio_bytes: Audio file bytes
        language: Language code (e.g., 'en', 'de')
        filename: Audio filename
        audio_type: 'tts' for words, 'tts_sentences' for sentences
        
    Returns:
        S3 public URL or None if failed
    """
    s3_key = f"media/{audio_type}/{language}/{filename}"
    return s3_storage.upload_audio_bytes(audio_bytes, s3_key)

def upload_tts_audio(local_file_path: str, language: str, filename: str, audio_type: str = 'tts') -> Optional[str]:
    """
    Upload TTS audio file to S3
    
    Args:
        local_file_path: Path to local audio file
        language: Language code (e.g., 'en', 'de')
        filename: Audio filename
        audio_type: 'tts' for words, 'tts_sentences' for sentences
        
    Returns:
        S3 public URL or None if failed
    """
    s3_key = f"media/{audio_type}/{language}/{filename}"
    return s3_storage.upload_audio_file(local_file_path, s3_key)

def get_tts_audio_url(language: str, filename: str, audio_type: str = 'tts') -> str:
    """
    Get S3 public URL for TTS audio file
    
    Args:
        language: Language code
        filename: Audio filename
        audio_type: 'tts' for words, 'tts_sentences' for sentences
        
    Returns:
        S3 public URL
    """
    s3_key = f"media/{audio_type}/{language}/{filename}"
    return s3_storage.get_public_url(s3_key)

def tts_audio_exists(language: str, filename: str, audio_type: str = 'tts') -> bool:
    """
    Check if TTS audio file exists in S3
    
    Args:
        language: Language code
        filename: Audio filename
        audio_type: 'tts' for words, 'tts_sentences' for sentences
        
    Returns:
        True if file exists in S3
    """
    s3_key = f"media/{audio_type}/{language}/{filename}"
    return s3_storage.file_exists(s3_key)
