# Performance Testing Guide

## Quick Test Checklist

### 1. Authentication Performance ✅
**Test**: Open app and check browser console
**Expected**: 
- Console log: `✅ User data loaded` in ~50-100ms
- No blocking during page load

**How to verify**:
```javascript
// In browser console, check timing:
performance.getEntriesByType('navigation')[0].domContentLoadedEventEnd
```

### 2. Custom Level Groups Loading ✅
**Test**: Open Library tab
**Expected**:
- Console log: `✅ Loaded X custom level groups from summary API in Xms`
- Should be < 1000ms (1 second)
- Groups appear immediately

**How to verify**:
- Open browser DevTools → Network tab
- Filter: `/api/custom-levels/groups/summary`
- Check response time (should be < 500ms)

### 3. Group Opening Performance ✅
**Test**: Click on a custom level group
**Expected**:
- Console log: `⚡ Ultra-lazy loading: Levels loaded without content`
- Group opens instantly (< 500ms)
- Levels show without content initially

**How to verify**:
- Network tab: `/api/custom-level-groups/<id>`
- Response should be small (only metadata)
- Response time < 500ms

### 4. Level Start Performance ✅
**Test**: Start a level
**Expected**:
- Console log: `🔧 preloadWordsBatch API call`
- First words available immediately
- Tooltips open instantly for first words

**How to verify**:
- Network tab: `/api/words/batch`
- Should see batch request for first 10 words
- Response time < 300ms

### 5. Tooltip Performance ✅
**Test**: Open tooltip for same word multiple times
**Expected**:
- First open: API call (~200ms)
- Second+ opens: Instant (cached)
- Console log: `🔧 Using cached word data`

**How to verify**:
- Open tooltip for word "hello"
- Check Network tab - should see `/api/word` call
- Open tooltip for "hello" again
- No API call (cached)
- Instant display

## Performance Benchmarks

### Before Optimizations
- Authentication: 300-500ms
- Groups loading: 2-5s
- Group opening: 1-3s (or ~1min with content)
- Level start: 2-4s
- Tooltip open: 300-800ms

### After Optimizations (Expected)
- Authentication: 50-100ms ✅ **80% faster**
- Groups loading: 0.5-1s ✅ **75% faster**
- Group opening: 200-500ms ✅ **85% faster**
- Level start: 0.5-1s ✅ **75% faster**
- Tooltip open: 50-200ms ✅ **75% faster**

## Database Indexes

### Local Development (SQLite)
Tables may not exist locally - this is normal. Indexes will be created automatically when tables are created.

### Production (Railway PostgreSQL)
**To create indexes on Railway**:

1. **Option 1: Via Railway CLI** (Recommended)
   ```bash
   # Set DATABASE_URL from Railway
   railway variables
   # Copy DATABASE_URL value
   export DATABASE_URL="postgresql://..."
   python3 railway_create_indexes.py
   ```

2. **Option 2: Via Railway Dashboard**
   - Go to Railway dashboard → Your service → Variables
   - Copy DATABASE_URL
   - Run locally: `DATABASE_URL="..." python3 railway_create_indexes.py`

3. **Option 3: One-time SQL Script**
   ```sql
   -- Run this in Railway PostgreSQL console
   CREATE INDEX IF NOT EXISTS idx_users_id ON users(id);
   CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
   CREATE INDEX IF NOT EXISTS idx_custom_level_groups_user_id ON custom_level_groups(user_id);
   CREATE INDEX IF NOT EXISTS idx_custom_level_groups_language ON custom_level_groups(language);
   CREATE INDEX IF NOT EXISTS idx_custom_levels_group_id ON custom_levels(group_id);
   CREATE INDEX IF NOT EXISTS idx_custom_levels_group_level ON custom_levels(group_id, level_number);
   CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user_group_level ON custom_level_progress(user_id, group_id, level_number);
   CREATE INDEX IF NOT EXISTS idx_custom_level_progress_user ON custom_level_progress(user_id);
   CREATE INDEX IF NOT EXISTS idx_words_word_lang_native ON words(word, language, native_language);
   CREATE INDEX IF NOT EXISTS idx_words_language ON words(language);
   CREATE INDEX IF NOT EXISTS idx_user_word_fam_user_word_lang ON user_word_familiarity(user_id, word, language, native_language);
   ```

## Monitoring Performance

### Browser Console Logs
Look for these performance indicators:
- `✅ Loaded X custom level groups from summary API in Xms`
- `🔧 preloadWordsBatch API call` (with timing)
- `🔧 Using cached word data` (cache hits)
- `⚡ Ultra-lazy loading: Levels loaded without content`

### Network Tab Analysis
1. Open DevTools → Network tab
2. Filter by API endpoints:
   - `/api/custom-levels/groups/summary` - Should be < 500ms
   - `/api/custom-level-groups/<id>` - Should be < 500ms (no content)
   - `/api/words/batch` - Should be < 300ms
   - `/api/word` - Should be < 200ms (or cached)

### Cache Hit Rate
Check tooltip.js cache:
```javascript
// In browser console:
// Check cache size
wordDataCache.size

// Check cache entries
Array.from(wordDataCache.keys()).slice(0, 10)
```

## Troubleshooting

### Groups loading slowly?
- Check if using `/api/custom-levels/groups/summary` endpoint
- Verify database indexes are created
- Check Network tab for slow queries

### Tooltips not caching?
- Check browser console for cache logs
- Verify `wordDataCache` is being used
- Check cache TTL (10 minutes)

### Level opening slow?
- Verify ultra-lazy loading is working (no content in response)
- Check if content is being loaded on-demand
- Verify preloading is happening

## Success Criteria

✅ **Authentication**: < 100ms  
✅ **Groups loading**: < 1s  
✅ **Group opening**: < 500ms  
✅ **Level start**: < 1s  
✅ **Tooltip (cached)**: < 50ms  
✅ **Tooltip (uncached)**: < 200ms  

If all criteria are met, optimizations are working! 🎉

