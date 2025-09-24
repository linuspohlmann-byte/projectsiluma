// API Request Batcher
// Batches multiple API requests to reduce network overhead

class APIBatcher {
    constructor() {
        this.pendingRequests = new Map();
        this.batchTimeout = 50; // 50ms batching window
        this.maxBatchSize = 10;
    }

    /**
     * Add a request to the batch queue
     * @param {string} url - The API endpoint
     * @param {Object} options - Fetch options
     * @param {Function} resolve - Promise resolve function
     * @param {Function} reject - Promise reject function
     */
    addRequest(url, options, resolve, reject) {
        const key = this.getRequestKey(url, options);
        
        if (!this.pendingRequests.has(key)) {
            this.pendingRequests.set(key, []);
        }
        
        this.pendingRequests.get(key).push({ resolve, reject, url, options });
        
        // Process batch if it's full or schedule processing
        if (this.pendingRequests.get(key).length >= this.maxBatchSize) {
            this.processBatch(key);
        } else {
            this.scheduleBatchProcessing(key);
        }
    }

    /**
     * Get a unique key for the request based on URL and method
     */
    getRequestKey(url, options) {
        const method = options?.method || 'GET';
        return `${method}:${url}`;
    }

    /**
     * Schedule batch processing with timeout
     */
    scheduleBatchProcessing(key) {
        if (this.pendingRequests.get(key).timer) {
            clearTimeout(this.pendingRequests.get(key).timer);
        }
        
        this.pendingRequests.get(key).timer = setTimeout(() => {
            this.processBatch(key);
        }, this.batchTimeout);
    }

    /**
     * Process a batch of requests
     */
    async processBatch(key) {
        const requests = this.pendingRequests.get(key);
        if (!requests || requests.length === 0) return;

        // Clear the batch
        this.pendingRequests.delete(key);
        
        // Process requests in parallel
        const promises = requests.map(async (request) => {
            try {
                const response = await fetch(request.url, request.options);
                const data = await response.json();
                request.resolve(data);
            } catch (error) {
                request.reject(error);
            }
        });

        await Promise.allSettled(promises);
    }

    /**
     * Create a batched fetch function
     */
    createBatchedFetch() {
        return (url, options = {}) => {
            return new Promise((resolve, reject) => {
                this.addRequest(url, options, resolve, reject);
            });
        };
    }
}

// Create global instance
const apiBatcher = new APIBatcher();

// Export batched fetch function
export const batchedFetch = apiBatcher.createBatchedFetch();

// Export the class for custom usage
export default APIBatcher;
