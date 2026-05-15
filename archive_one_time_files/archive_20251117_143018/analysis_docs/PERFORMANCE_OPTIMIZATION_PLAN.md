# Performance Optimization Plan

## Overview
This document outlines specific optimizations to decrease load times for:
- a) User authentication
- b) Page content loading (especially custom level groups)
- c) Opening a level group
- d) Starting a level
- e) Supplying tooltip and word data

---

## a) User Authentication Optimization

### Current Issues
1. **Blocking API call on page load**: `checkAuthStatus()` makes a synchronous `/api/auth/me` call that blocks rendering
2. **No caching**: User data is fetched on every page load even if token is valid
3. **Sequential initialization**: Auth check happens before other critical resources load

### Optimizations

#### 1. **Parallel Authentication Check**
```javascript
// In auth.js - Make auth check non-blocking
async checkAuthStatus() {
    if (!this.sessionToken) {
        this.showLoginSection();
        this.handleUnauthenticatedState();
        return;
    }

    // Don't await - let page continue loading
    this.verifyTokenAsync();
}

async verifyTokenAsync() {
    try {
        const response = await fetch('/api/auth/me', {
            headers: { 'Authorization': `Bearer ${this.sessionToken}` }
        });
        // ... handle response
    } catch (error) {
        // Handle error without blocking
    }
}
```

#### 2. **Cache User Data in localStorage**
```javascript
// Cache user data with timestamp
const USER_CACHE_KEY = 'user_cache';
const USER_CACHE_TTL = 5 * 60 * 1000; // 5 minutes

async checkAuthStatus() {
    // Check cache first
    const cached = this.getCachedUser();
    if (cached && Date.now() - cached.timestamp < USER_CACHE_TTL) {
        this.currentUser = cached.user;
        this.showAuthSection();
        this.handleAuthenticatedState();
        // Verify in background
        this.verifyTokenAsync();
        return;
    }
    // ... rest of auth check
}
```

#### 3. **Optimize Backend `/api/auth/me` Endpoint**
```python
# In app.py - Add caching and optimize query
@app.get('/api/auth/me')
@require_auth(optional=True)
def api_auth_me():
    user_context = get_user_context()
    user_id = user_context.get('user_id')
    
    if not user_id:
        return jsonify({'success': False, 'user': None})
    
    # Use lightweight query - only fetch essential fields
    # Add database index on users.id if not exists
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, username, email, native_language, created_at
            FROM users WHERE id = %s
        ''', (user_id,))
        # ... return minimal user data
    finally:
        conn.close()
```

#### 4. **Use HTTP/2 Server Push for Auth Resources**
- Preload auth-related CSS/JS resources
- Push user data if token exists in cookie

**Expected Improvement**: 200-500ms faster initial load

---

## b) Page Content Loading (Custom Level Groups)

### Current Issues
1. **Sequential API calls**: Groups are loaded one by one
2. **Heavy queries**: Each group fetch includes full level data
3. **No pagination**: All groups loaded at once
4. **Redundant data**: Full level content fetched even when not needed

### Optimizations

#### 1. **Batch Load Custom Level Groups**
```javascript
// In custom-level-groups.js
async function loadCustomLevelGroups() {
    const headers = {};
    if (window.authManager?.isAuthenticated()) {
        Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Single API call for all groups with minimal data
    const response = await fetch('/api/custom-levels/groups/summary', {
        headers: headers
    });
    // Returns: [{id, name, language, level_count, total_words, progress_summary}]
}
```

#### 2. **Create Optimized Backend Endpoint**
```python
# In app.py
@custom_levels_bp.get('/api/custom-levels/groups/summary')
@require_auth(optional=True)
def api_custom_levels_groups_summary():
    """Return lightweight summary of all groups for current user"""
    user_context = get_user_context()
    user_id = user_context.get('user_id')
    
    if not user_id:
        return jsonify({'success': True, 'groups': []})
    
    conn = get_db_connection()
    try:
        # Single query with JOINs for efficiency
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                clg.id,
                clg.name,
                clg.language,
                clg.native_language,
                COUNT(DISTINCT cl.id) as level_count,
                SUM(cl.word_count) as total_words,
                COUNT(DISTINCT CASE WHEN clp.status = 'completed' THEN cl.id END) as completed_levels
            FROM custom_level_groups clg
            LEFT JOIN custom_levels cl ON cl.group_id = clg.id
            LEFT JOIN custom_level_progress clp ON 
                clp.group_id = clg.id AND 
                clp.level_number = cl.level_number AND
                clp.user_id = %s
            WHERE clg.user_id = %s
            GROUP BY clg.id, clg.name, clg.language, clg.native_language
            ORDER BY clg.created_at DESC
        ''', (user_id, user_id))
        
        groups = []
        for row in cursor.fetchall():
            groups.append({
                'id': row[0],
                'name': row[1],
                'language': row[2],
                'native_language': row[3],
                'level_count': row[4] or 0,
                'total_words': row[5] or 0,
                'completed_levels': row[6] or 0
            })
        
        return jsonify({'success': True, 'groups': groups})
    finally:
        conn.close()
```

#### 3. **Lazy Load Full Group Data**
```javascript
// Only load full group data when user clicks to open it
async function loadGroupDetails(groupId) {
    // Load full data on-demand
    const response = await fetch(`/api/custom-levels/${groupId}`, {
        headers: window.authManager?.getAuthHeaders()
    });
}
```

#### 4. **Add Database Indexes**
```sql
-- Ensure these indexes exist
CREATE INDEX IF NOT EXISTS idx_custom_level_groups_user_id 
    ON custom_level_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_levels_group_id 
    ON custom_levels(group_id);
CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group_level 
    ON custom_level_progress(user_id, group_id, level_number);
```

#### 5. **Implement Virtual Scrolling**
- Only render visible group cards
- Load more as user scrolls
- Reduces initial DOM manipulation time

**Expected Improvement**: 1-3 seconds faster for users with many groups

---

## c) Opening a Level Group

### Current Issues
1. **Full level content loaded**: All 10 levels' content fetched even if not needed
2. **Sequential level queries**: Each level queried separately
3. **Heavy JSON parsing**: Large content objects parsed synchronously
4. **No progressive loading**: User waits for all data before seeing anything

### Optimizations

#### 1. **Ultra-Lazy Level Loading**
```python
# In app.py - Modify custom level endpoint
@custom_levels_bp.get('/api/custom-levels/<int:group_id>')
@require_auth(optional=True)
def api_custom_levels_get(group_id):
    """Return group with minimal level data - content loaded on-demand"""
    user_context = get_user_context()
    user_id = user_context.get('user_id')
    
    conn = get_db_connection()
    try:
        # Get group info
        group_info = get_custom_level_group(group_id, user_id)
        
        # Get levels WITHOUT content (much faster)
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                id, level_number, word_count, created_at, updated_at
            FROM custom_levels
            WHERE group_id = %s
            ORDER BY level_number
        ''', (group_id,))
        
        levels = []
        for row in cursor.fetchall():
            levels.append({
                'id': row[0],
                'level_number': row[1],
                'word_count': row[2],  # Pre-calculated, no need to parse JSON
                'created_at': row[3],
                'updated_at': row[4],
                'content': None  # Loaded on-demand via separate endpoint
            })
        
        return jsonify({
            'success': True,
            'group': group_info,
            'levels': levels
        })
    finally:
        conn.close()
```

#### 2. **On-Demand Level Content Loading**
```javascript
// In custom-level-groups.js
async function loadLevelContent(groupId, levelNumber) {
    // Only load when level is actually opened
    const response = await fetch(
        `/api/custom-levels/${groupId}/${levelNumber}/content`,
        { headers: window.authManager?.getAuthHeaders() }
    );
    return await response.json();
}
```

#### 3. **Batch Progress Loading**
```python
# Load all level progress in single query
@custom_levels_bp.get('/api/custom-levels/<int:group_id>/bulk-stats')
@require_auth(optional=True)
def api_custom_levels_bulk_stats(group_id):
    """Already exists - ensure it's optimized"""
    # Current implementation is good, but ensure:
    # 1. Single query with JOINs
    # 2. Uses progress cache table
    # 3. Returns minimal data
```

#### 4. **Progressive Rendering**
```javascript
// Render group header immediately, levels progressively
async function renderGroup(groupId) {
    // 1. Show group header immediately
    showGroupHeader(groupData);
    
    // 2. Load and render levels one by one (non-blocking)
    for (const level of levels) {
        await renderLevelCard(level);
        // Yield to browser for rendering
        await new Promise(resolve => setTimeout(resolve, 0));
    }
}
```

**Expected Improvement**: 500ms-2s faster, perceived as instant

---

## d) Starting a Level

### Current Issues
1. **Heavy practice session initialization**: Full level content loaded
2. **Word enrichment on-demand**: Words enriched as they appear (causes delays)
3. **Sequential TTS generation**: Audio generated one by one
4. **No preloading**: First words not ready when level starts

### Optimizations

#### 1. **Preload First N Words**
```javascript
// In lesson.js - Preload first 5-10 words when level opens
async function preloadLevelWords(levelData) {
    const wordsToPreload = levelData.items.slice(0, 10);
    
    // Batch enrich words
    await batchEnrichWords(
        wordsToPreload.map(item => item.word),
        levelData.language,
        levelData.native_language
    );
    
    // Preload TTS audio
    for (const item of wordsToPreload) {
        prewarmSentenceTTS(item.sentence || item.word, levelData.language);
    }
}
```

#### 2. **Optimize Practice Start Endpoint**
```python
# In app.py - Practice start endpoint
@app.post('/api/practice/start')
@require_auth(optional=True)
def api_practice_start():
    """Optimize practice session initialization"""
    payload = request.get_json() or {}
    group_id = payload.get('group_id')
    level_number = payload.get('level_number')
    
    # 1. Load level WITHOUT full content if not needed
    level_data = get_custom_level(group_id, level_number, include_content=False)
    
    # 2. Get words list only (lightweight)
    words = extract_words_from_level(level_data)  # Fast extraction
    
    # 3. Create practice session with minimal data
    run_id = create_practice_session(user_id, group_id, level_number, words)
    
    # 4. Return first word immediately
    return jsonify({
        'success': True,
        'run_id': run_id,
        'word': words[0] if words else None,
        'remaining': len(words) - 1,
        'total': len(words)
    })
```

#### 3. **Background Word Enrichment**
```javascript
// Enrich words in background while user reads first item
async function startLevel(groupId, levelNumber) {
    // 1. Start practice session (fast)
    const session = await fetch('/api/practice/start', {...});
    
    // 2. Show first word immediately
    showFirstWord(session.word);
    
    // 3. Enrich remaining words in background
    enrichWordsInBackground(session.words.slice(1));
}
```

#### 4. **Batch TTS Generation**
```python
# Generate TTS for multiple words at once
@app.post('/api/words/batch-tts')
@require_auth(optional=True)
def api_words_batch_tts():
    """Generate TTS for multiple words in parallel"""
    payload = request.get_json() or {}
    words = payload.get('words', [])
    language = payload.get('language', 'en')
    
    # Use asyncio to generate TTS in parallel
    import asyncio
    from server.services.tts import ensure_tts_for_word
    
    async def generate_all():
        tasks = [ensure_tts_for_word(w, language) for w in words]
        return await asyncio.gather(*tasks)
    
    results = asyncio.run(generate_all())
    return jsonify({'success': True, 'audio_urls': results})
```

#### 5. **Cache Practice Sessions**
```python
# Cache practice session data in Redis/memory
from functools import lru_cache

@lru_cache(maxsize=100)
def get_cached_practice_session(run_id):
    # Return cached session data
    pass
```

**Expected Improvement**: 1-2 seconds faster level start

---

## e) Tooltip and Word Data

### Current Issues
1. **Individual API calls**: Each tooltip opens separate API call
2. **Full word data fetched**: All fields loaded even if not displayed
3. **No caching**: Same word fetched multiple times
4. **Synchronous loading**: UI blocked while fetching

### Optimizations

#### 1. **Aggressive Frontend Caching**
```javascript
// In tooltip.js - Add word data cache
const wordDataCache = new Map();
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

async function fetchWordData(word, language, nativeLanguage) {
    const cacheKey = `${word}:${language}:${nativeLanguage}`;
    const cached = wordDataCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        return cached.data;
    }
    
    const response = await fetch(`/api/word?word=${word}&language=${language}`, {
        headers: window.authManager?.getAuthHeaders()
    });
    const data = await response.json();
    
    wordDataCache.set(cacheKey, {
        data: data,
        timestamp: Date.now()
    });
    
    return data;
}
```

#### 2. **Preload Tooltip Data**
```javascript
// Preload tooltip data for visible words
function preloadTooltipDataForVisibleWords() {
    const visibleWords = document.querySelectorAll('.word-highlight, .word-clickable');
    visibleWords.forEach(element => {
        const word = element.textContent.trim();
        if (word) {
            // Preload in background
            fetchWordData(word, targetLang, nativeLang).catch(() => {});
        }
    });
}
```

#### 3. **Optimize Word API Endpoint**
```python
# In app.py - Return only needed fields
@app.get('/api/word')
@require_auth(optional=True)
def api_word_get():
    word = request.args.get('word')
    language = request.args.get('language', 'en')
    fields = request.args.get('fields', 'all')  # Comma-separated list
    
    # Only fetch requested fields
    if fields != 'all':
        field_list = fields.split(',')
        # Build SELECT query dynamically
        select_fields = ', '.join(field_list)
    else:
        select_fields = '*'
    
    cursor.execute(f'SELECT {select_fields} FROM words WHERE word = %s AND language = %s', 
                   (word, language))
    # ... return only requested fields
```

#### 4. **Batch Word Data Fetching**
```python
# New endpoint for batch word fetching
@app.post('/api/words/batch')
@require_auth(optional=True)
def api_words_batch():
    """Fetch multiple words in single query"""
    payload = request.get_json() or {}
    words = payload.get('words', [])
    language = payload.get('language', 'en')
    
    if not words:
        return jsonify({'success': True, 'words': []})
    
    conn = get_db_connection()
    try:
        # Use IN clause or array for PostgreSQL
        if config['type'] == 'postgresql':
            cursor.execute('''
                SELECT * FROM words 
                WHERE word = ANY(%s) AND language = %s
            ''', (words, language))
        else:
            placeholders = ','.join(['?'] * len(words))
            cursor.execute(f'''
                SELECT * FROM words 
                WHERE word IN ({placeholders}) AND language = ?
            ''', words + [language])
        
        words_data = {}
        for row in cursor.fetchall():
            word_dict = _coerce_row_to_dict(row, cursor.description)
            words_data[word_dict['word']] = word_dict
        
        return jsonify({'success': True, 'words': words_data})
    finally:
        conn.close()
```

#### 5. **Use IndexedDB for Persistent Cache**
```javascript
// Store word data in IndexedDB for offline access
const dbName = 'siluma-word-cache';
const dbVersion = 1;

async function initWordCacheDB() {
    return new Promise((resolve, reject) => {
        const request = indexedDB.open(dbName, dbVersion);
        request.onerror = () => reject(request.error);
        request.onsuccess = () => resolve(request.result);
        request.onupgradeneeded = (event) => {
            const db = event.target.result;
            if (!db.objectStoreNames.contains('words')) {
                db.createObjectStore('words', { keyPath: ['word', 'language'] });
            }
        };
    });
}

async function getWordFromCache(word, language) {
    const db = await initWordCacheDB();
    const transaction = db.transaction(['words'], 'readonly');
    const store = transaction.objectStore('words');
    return store.get([word, language]);
}
```

#### 6. **Debounce Tooltip Opening**
```javascript
// Prevent rapid tooltip opens from causing multiple API calls
let tooltipOpenTimeout = null;

export async function openTooltip(anchor, word) {
    // Cancel pending tooltip opens
    if (tooltipOpenTimeout) {
        clearTimeout(tooltipOpenTimeout);
    }
    
    // Debounce tooltip opening
    tooltipOpenTimeout = setTimeout(async () => {
        // Open tooltip with cached/preloaded data
        await actuallyOpenTooltip(anchor, word);
    }, 50); // 50ms debounce
}
```

**Expected Improvement**: Tooltip opens instantly for cached words, 200-500ms faster for uncached

---

## Database Optimization Checklist

### Required Indexes
```sql
-- Users table
CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Custom level groups
CREATE INDEX IF NOT EXISTS idx_custom_level_groups_user_id 
    ON custom_level_groups(user_id);
CREATE INDEX IF NOT EXISTS idx_custom_level_groups_language 
    ON custom_level_groups(language);

-- Custom levels
CREATE INDEX IF NOT EXISTS idx_custom_levels_group_id 
    ON custom_levels(group_id);
CREATE INDEX IF NOT EXISTS idx_custom_levels_group_level 
    ON custom_levels(group_id, level_number);

-- Custom level progress (critical for performance)
CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group_level 
    ON custom_level_progress(user_id, group_id, level_number);
CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user 
    ON custom_level_progress(user_id);

-- Words table
CREATE INDEX IF NOT EXISTS idx_words_word_lang_native 
    ON words(word, language, native_language);
CREATE INDEX IF NOT EXISTS idx_words_language 
    ON words(language);

-- User word familiarity
CREATE INDEX IF NOT EXISTS idx_user_word_fam_user_word_lang 
    ON user_word_familiarity(user_id, word, language, native_language);
```

### Query Optimization
- Use `EXPLAIN ANALYZE` on slow queries
- Avoid N+1 queries - use JOINs
- Use prepared statements
- Limit result sets with `LIMIT`
- Use `SELECT` specific columns, not `SELECT *`

---

## Implementation Priority

### Phase 1 (Quick Wins - 1-2 days)
1. ✅ Add database indexes
2. ✅ Implement frontend word data caching
3. ✅ Optimize `/api/auth/me` endpoint
4. ✅ Create `/api/custom-levels/groups/summary` endpoint

### Phase 2 (Medium Impact - 3-5 days)
1. ✅ Implement batch word fetching
2. ✅ Add progressive level loading
3. ✅ Preload first N words in level
4. ✅ Optimize practice start endpoint

### Phase 3 (Long-term - 1-2 weeks)
1. ✅ Implement IndexedDB caching
2. ✅ Add HTTP/2 server push
3. ✅ Implement virtual scrolling for groups
4. ✅ Add Redis caching layer (if needed)

---

## Expected Overall Improvements

| Operation | Current Time | Optimized Time | Improvement |
|-----------|--------------|----------------|-------------|
| Authentication | 300-500ms | 50-100ms | 80% faster |
| Load Groups | 2-5s | 0.5-1s | 75% faster |
| Open Group | 1-3s | 200-500ms | 85% faster |
| Start Level | 2-4s | 0.5-1s | 75% faster |
| Tooltip Open | 300-800ms | 50-200ms | 75% faster |

**Total perceived improvement**: App feels 3-5x faster

