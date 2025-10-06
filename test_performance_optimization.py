#!/usr/bin/env python3
"""
Performance test for optimized TTS and Enrich functionality.
Tests the improvements made to reduce 60-second wait times.
"""

import os
import time
import json
from typing import List, Dict

# Set up environment (use actual values from your environment)
# os.environ.setdefault('OPENAI_API_KEY', 'sk-proj-your-key-here')
# os.environ.setdefault('AWS_ACCESS_KEY_ID', 'your-access-key-here')
# os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'your-secret-key-here')
# os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-central-1')
# os.environ.setdefault('S3_BUCKET_NAME', 'projectsiluma')

def test_batch_tts_performance():
    """Test the new batch TTS functionality"""
    print("🧪 Testing Batch TTS Performance...")
    
    try:
        from server.services.tts import ensure_tts_for_words_batch
        
        # Test words
        test_words = ['hello', 'world', 'test', 'performance', 'optimization']
        language = 'en'
        
        print(f"📝 Testing {len(test_words)} words: {test_words}")
        
        start_time = time.time()
        results = ensure_tts_for_words_batch(test_words, language, max_workers=3)
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"⏱️  Batch TTS completed in {duration:.2f} seconds")
        print(f"📊 Results: {len(results)}/{len(test_words)} words processed")
        
        for word, audio_url in results.items():
            print(f"  ✅ {word}: {audio_url[:50]}...")
        
        return duration, len(results)
        
    except Exception as e:
        print(f"❌ Batch TTS test failed: {e}")
        return None, 0

def test_sequential_vs_batch():
    """Compare sequential vs batch processing"""
    print("\n🔄 Comparing Sequential vs Batch Processing...")
    
    try:
        from server.services.tts import ensure_tts_for_word, ensure_tts_for_words_batch
        
        test_words = ['apple', 'banana', 'cherry', 'date', 'elderberry']
        language = 'en'
        
        # Sequential processing
        print("📝 Sequential processing...")
        start_time = time.time()
        sequential_results = {}
        for word in test_words:
            audio_url = ensure_tts_for_word(word, language)
            if audio_url:
                sequential_results[word] = audio_url
        sequential_duration = time.time() - start_time
        
        # Batch processing
        print("📝 Batch processing...")
        start_time = time.time()
        batch_results = ensure_tts_for_words_batch(test_words, language, max_workers=3)
        batch_duration = time.time() - start_time
        
        print(f"⏱️  Sequential: {sequential_duration:.2f}s")
        print(f"⏱️  Batch: {batch_duration:.2f}s")
        print(f"🚀 Speed improvement: {sequential_duration/batch_duration:.1f}x faster")
        
        return {
            'sequential_duration': sequential_duration,
            'batch_duration': batch_duration,
            'improvement': sequential_duration/batch_duration
        }
        
    except Exception as e:
        print(f"❌ Comparison test failed: {e}")
        return None

def test_s3_integration():
    """Test S3 integration performance"""
    print("\n☁️  Testing S3 Integration...")
    
    try:
        from server.services.s3_storage import s3_storage
        
        if s3_storage.s3_client is None:
            print("⚠️  S3 not configured, skipping test")
            return False
        
        # Test S3 operations
        test_file = 'test_performance.mp3'
        test_content = b'fake audio content for testing'
        
        # Upload test
        start_time = time.time()
        success = s3_storage.upload_audio_file(test_content, 'en', test_file, 'tts')
        upload_duration = time.time() - start_time
        
        if success:
            print(f"✅ S3 upload: {upload_duration:.2f}s")
            
            # Existence check test
            start_time = time.time()
            exists = s3_storage.audio_file_exists('en', test_file, 'tts')
            check_duration = time.time() - start_time
            
            print(f"✅ S3 existence check: {check_duration:.2f}s")
            
            # Cleanup
            try:
                s3_storage.s3_client.delete_object(Bucket=s3_storage.bucket_name, Key=f'tts/en/{test_file}')
                print("🧹 Test file cleaned up")
            except:
                pass
            
            return True
        else:
            print("❌ S3 upload failed")
            return False
            
    except Exception as e:
        print(f"❌ S3 test failed: {e}")
        return False

def test_enrich_batch_performance():
    """Test the optimized enrich batch endpoint"""
    print("\n📚 Testing Enrich Batch Performance...")
    
    try:
        from server.services.llm import llm_enrich_words_batch
        
        test_words = ['hello', 'world', 'test']
        language = 'en'
        native_language = 'de'
        
        print(f"📝 Testing enrich for {len(test_words)} words")
        
        start_time = time.time()
        results = llm_enrich_words_batch(test_words, language, native_language, {})
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"⏱️  Enrich batch completed in {duration:.2f} seconds")
        
        enriched_count = len([w for w, data in results.items() if data and data.get('translation')])
        print(f"📊 Enriched: {enriched_count}/{len(test_words)} words")
        
        return duration, enriched_count
        
    except Exception as e:
        print(f"❌ Enrich batch test failed: {e}")
        return None, 0

def main():
    """Run all performance tests"""
    print("🚀 Performance Optimization Tests")
    print("=" * 50)
    
    # Test results
    results = {}
    
    # Test 1: Batch TTS
    duration, count = test_batch_tts_performance()
    results['batch_tts'] = {'duration': duration, 'count': count}
    
    # Test 2: Sequential vs Batch comparison
    comparison = test_sequential_vs_batch()
    results['comparison'] = comparison
    
    # Test 3: S3 integration
    s3_success = test_s3_integration()
    results['s3_integration'] = s3_success
    
    # Test 4: Enrich batch
    enrich_duration, enrich_count = test_enrich_batch_performance()
    results['enrich_batch'] = {'duration': enrich_duration, 'count': enrich_count}
    
    # Summary
    print("\n📊 Performance Test Summary")
    print("=" * 50)
    
    if results['batch_tts']['duration']:
        print(f"✅ Batch TTS: {results['batch_tts']['duration']:.2f}s for {results['batch_tts']['count']} words")
    
    if results['comparison']:
        print(f"✅ Speed improvement: {results['comparison']['improvement']:.1f}x faster with batch processing")
    
    if results['s3_integration']:
        print("✅ S3 integration working")
    else:
        print("⚠️  S3 integration issues")
    
    if results['enrich_batch']['duration']:
        print(f"✅ Enrich batch: {results['enrich_batch']['duration']:.2f}s for {results['enrich_batch']['count']} words")
    
    print("\n🎯 Expected improvements:")
    print("- Batch TTS processing: 3-5x faster")
    print("- S3 integration: Reliable cloud storage")
    print("- Optimized caching: 24-hour cache for audio files")
    print("- Parallel processing: Multiple words simultaneously")

if __name__ == '__main__':
    main()
