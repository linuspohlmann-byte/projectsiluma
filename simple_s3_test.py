#!/usr/bin/env python3
"""
Simple S3 connection test
"""
import os
import boto3
from botocore.exceptions import ClientError

# Set environment variables (use your actual credentials)
# os.environ['AWS_ACCESS_KEY_ID'] = 'your-access-key-here'
# os.environ['AWS_SECRET_ACCESS_KEY'] = 'your-secret-key-here'
# os.environ['AWS_DEFAULT_REGION'] = 'eu-central-1'

def test_s3():
    try:
        # Create S3 client
        s3_client = boto3.client('s3')
        bucket_name = 'projectsiluma'
        
        # Test bucket access
        response = s3_client.head_bucket(Bucket=bucket_name)
        print(f"✅ Successfully connected to bucket: {bucket_name}")
        
        # Test upload
        test_content = b"Hello S3! This is a test file."
        test_key = "test/connection-test.txt"
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=test_key,
            Body=test_content,
            ContentType='text/plain'
        )
        print(f"✅ Successfully uploaded test file: {test_key}")
        
        # Test download
        response = s3_client.get_object(Bucket=bucket_name, Key=test_key)
        downloaded_content = response['Body'].read()
        if downloaded_content == test_content:
            print("✅ Successfully downloaded and verified test file")
        else:
            print("❌ Downloaded content doesn't match")
            return False
        
        # Clean up
        s3_client.delete_object(Bucket=bucket_name, Key=test_key)
        print("✅ Successfully deleted test file")
        
        print("🎉 All S3 tests passed!")
        return True
        
    except ClientError as e:
        print(f"❌ AWS Error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    success = test_s3()
    exit(0 if success else 1)
