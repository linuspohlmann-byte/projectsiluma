/**
 * Performance optimization utilities for audio and enrichment
 */

class PerformanceOptimizer {
    constructor() {
        this.audioCache = new Map();
        this.enrichmentCache = new Map();
        this.preloadQueue = [];
        this.isPreloading = false;
        this.maxConcurrentRequests = 5;
        this.activeRequests = 0;
    }

    /**
     * Preload audio files for better user experience
     */
    async preloadAudio(audioUrls) {
        if (!audioUrls || audioUrls.length === 0) return;
        
        console.log(`🎵 Preloading ${audioUrls.length} audio files...`);
        
        const preloadPromises = audioUrls.map(url => this.preloadSingleAudio(url));
        
        try {
            await Promise.allSettled(preloadPromises);
            console.log('✅ Audio preloading complete');
        } catch (error) {
            console.warn('⚠️ Some audio files failed to preload:', error);
        }
    }

    /**
     * Preload a single audio file
     */
    preloadSingleAudio(url) {
        return new Promise((resolve, reject) => {
            if (this.audioCache.has(url)) {
                resolve();
                return;
            }

            const audio = new Audio();
            audio.preload = 'auto';
            
            audio.addEventListener('canplaythrough', () => {
                this.audioCache.set(url, audio);
                resolve();
            });
            
            audio.addEventListener('error', (e) => {
                console.warn(`Failed to preload audio: ${url}`, e);
                reject(e);
            });
            
            audio.src = url;
        });
    }

    /**
     * Batch enrich words with progress indication
     */
    async batchEnrichWords(words, language, nativeLanguage, sentenceContexts = {}, onProgress = null) {
        if (!words || words.length === 0) return {};

        console.log(`📚 Batch enriching ${words.length} words...`);
        
        const batchSize = 10;
        const results = {};
        let processed = 0;

        for (let i = 0; i < words.length; i += batchSize) {
            const batch = words.slice(i, i + batchSize);
            
            try {
                const batchResults = await this.enrichWordBatch(batch, language, nativeLanguage, sentenceContexts);
                Object.assign(results, batchResults);
                
                processed += batch.length;
                if (onProgress) {
                    onProgress(processed, words.length);
                }
                
                // Small delay to prevent overwhelming the server
                await new Promise(resolve => setTimeout(resolve, 100));
                
            } catch (error) {
                console.error(`Error enriching batch ${i}-${i + batchSize}:`, error);
            }
        }

        console.log(`✅ Batch enrichment complete: ${Object.keys(results).length} words enriched`);
        return results;
    }

    /**
     * Enrich a single batch of words
     */
    async enrichWordBatch(words, language, nativeLanguage, sentenceContexts) {
        const cacheKey = `enrich:${language}:${nativeLanguage}:${words.join(',')}`;
        
        if (this.enrichmentCache.has(cacheKey)) {
            return this.enrichmentCache.get(cacheKey);
        }

        try {
            const response = await fetch('/api/word/enrich_batch', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    words: words,
                    language: language,
                    native_language: nativeLanguage,
                    sentence_contexts: sentenceContexts
                })
            });

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            
            if (data.success) {
                this.enrichmentCache.set(cacheKey, data.results);
                return data.results;
            } else {
                throw new Error(data.error || 'Enrichment failed');
            }
            
        } catch (error) {
            console.error('Batch enrichment error:', error);
            return {};
        }
    }

    /**
     * Batch generate TTS audio
     */
    async batchGenerateTTS(words, language, sentenceContexts = {}, onProgress = null) {
        if (!words || words.length === 0) return {};

        console.log(`🎵 Batch generating TTS for ${words.length} words...`);
        
        const results = {};
        let processed = 0;

        // Process in smaller batches to avoid overwhelming the server
        const batchSize = 5;
        for (let i = 0; i < words.length; i += batchSize) {
            const batch = words.slice(i, i + batchSize);
            
            try {
                const batchResults = await this.generateTTSBatch(batch, language, sentenceContexts);
                Object.assign(results, batchResults);
                
                processed += batch.length;
                if (onProgress) {
                    onProgress(processed, words.length);
                }
                
                // Small delay between batches
                await new Promise(resolve => setTimeout(resolve, 200));
                
            } catch (error) {
                console.error(`Error generating TTS for batch ${i}-${i + batchSize}:`, error);
            }
        }

        console.log(`✅ TTS generation complete: ${Object.keys(results).length} audio files generated`);
        return results;
    }

    /**
     * Generate TTS for a single batch of words
     */
    async generateTTSBatch(words, language, sentenceContexts) {
        const results = {};
        
        // Use Promise.allSettled to handle individual failures gracefully
        const promises = words.map(async (word) => {
            try {
                const response = await fetch('/api/word/tts', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        word: word,
                        language: language,
                        sentence: sentenceContexts[word] || '',
                        instructions: ''
                    })
                });

                if (response.ok) {
                    const data = await response.json();
                    if (data.success && data.audio_url) {
                        results[word] = data.audio_url;
                    }
                }
            } catch (error) {
                console.warn(`Failed to generate TTS for word "${word}":`, error);
            }
        });

        await Promise.allSettled(promises);
        return results;
    }

    /**
     * Show progress indicator
     */
    showProgress(message, current, total) {
        const progress = Math.round((current / total) * 100);
        console.log(`${message}: ${progress}% (${current}/${total})`);
        
        // You can integrate this with your UI progress indicators
        if (window.showProgressIndicator) {
            window.showProgressIndicator(message, progress);
        }
    }

    /**
     * Clear caches
     */
    clearCaches() {
        this.audioCache.clear();
        this.enrichmentCache.clear();
        console.log('🧹 Performance caches cleared');
    }

    /**
     * Get cache statistics
     */
    getCacheStats() {
        return {
            audioCacheSize: this.audioCache.size,
            enrichmentCacheSize: this.enrichmentCache.size
        };
    }
}

// Global instance
window.performanceOptimizer = new PerformanceOptimizer();

// Export for module systems
if (typeof module !== 'undefined' && module.exports) {
    module.exports = PerformanceOptimizer;
}
