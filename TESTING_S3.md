# S3 Integration Testing Guide

This guide explains how to test the S3 integration for audio storage.

## Prerequisites

1. **AWS Credentials**: Set up your AWS credentials as environment variables
2. **S3 Bucket**: Create an S3 bucket for audio storage
3. **OpenAI API Key**: For testing real audio generation

## Environment Variables

Create a `.env` file or set these environment variables:

```bash
# AWS S3 Configuration
AWS_ACCESS_KEY_ID=your-access-key-here
AWS_SECRET_ACCESS_KEY=your-secret-key-here
AWS_DEFAULT_REGION=eu-central-1
S3_BUCKET_NAME=your-bucket-name

# OpenAI Configuration (for real audio generation)
OPENAI_API_KEY=your-openai-key-here
```

## Test Files

### 1. `simple_s3_test.py`
Basic S3 connection test - uploads, downloads, and deletes a test file.

### 2. `test_s3_connection.py`
Comprehensive S3 connection test with detailed logging.

### 3. `test_tts_s3.py`
Tests TTS service integration with S3 (without actual audio generation).

### 4. `test_complete_audio_flow.py`
Tests the complete audio flow including URL generation and file existence checking.

### 5. `test_real_audio_generation.py`
Tests real audio generation with OpenAI TTS and S3 upload.

### 6. `migrate_audio_to_s3.py`
Migration script to upload existing local audio files to S3.

## Running Tests

### Basic S3 Test
```bash
python simple_s3_test.py
```

### Complete Test Suite
```bash
python test_complete_audio_flow.py
```

### Real Audio Generation (requires OpenAI key)
```bash
python test_real_audio_generation.py
```

### Migrate Existing Files
```bash
python migrate_audio_to_s3.py
```

## Security Notes

- **Never commit AWS credentials to Git**
- Use environment variables or `.env` files
- The test files use placeholder values for security
- Replace with your actual credentials before testing

## Expected Results

All tests should pass and show:
- ✅ S3 connection successful
- ✅ Audio URL generation working
- ✅ File upload/download working
- ✅ Browser-ready URLs generated

## Troubleshooting

1. **S3 Connection Failed**: Check AWS credentials and bucket permissions
2. **Upload Failed**: Verify S3 bucket exists and IAM user has write permissions
3. **Audio Generation Failed**: Check OpenAI API key and quota
4. **URL Not Working**: Verify bucket is public or has proper CORS configuration
