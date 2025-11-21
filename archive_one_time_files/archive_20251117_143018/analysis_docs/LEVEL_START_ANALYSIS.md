# Level Start Event Analysis

This document provides a comprehensive analysis of all events that occur when starting a level, including all caching mechanisms designed to provide a seamless experience without wait times.

## Overview

When a user starts a level, the system performs extensive preloading and caching to ensure instant playback of audio, immediate display of word data, and smooth task progression. This analysis covers both **standard levels** and **custom levels**.

---

## Entry Points

### Standard Levels
- **Function**: `startLevel(lvl)` in `static/js/ui/lesson.js:2412`
- **Trigger**: User clicks on a level button
- **Alternative**: `startLevelWithTopic(lvl, topic, reuse)` - allows topic override

### Custom Levels
- **Function**: `startLevelWithTopic(lvl, topic, reuse)` in `static/js/ui/lesson.js:2735`
- **Trigger**: User clicks on a custom level
- **Two paths**:
  1. Pre-loaded data: `RUN._customLevelData` exists
  2. API-based: `RUN._customGroupId` and `RUN._customLevelNumber` set

---

## Event Flow: Standard Level Start

### Phase 1: Initialization & Validation

1. **Level Lock Check** (lines 2620-2646)
   - Checks if previous level was completed with ≥60% score
   - Uses cached level data from `dataset.bulkData` on level elements
   - Shows locked message if requirement not met

2. **RUN State Initialization** (lines 2649-2652)
   ```javascript
   RUN.target = $('#target-lang')?.value || 'en';
   RUN.native = localStorage.getItem('siluma_native') || 'de';
   RUN.level = Number(lvl) || 1;
   RUN.mcCorrect = 0; RUN.mcTotal = 0;
   ```

3. **UI Preparation** (lines 2653-2658)
   - Switch to 'lesson' tab
   - Unlock audio context (browser autoplay policy)
   - Prime sentence audio (preload silent audio for instant playback)
   - Hide alphabet and practice cards

4. **Topic Selection** (lines 2660-2668)
   - Uses override topic if set (`RUN._overrideTopic`)
   - Falls back to level-specific default topics
   - Includes CEFR level if set

5. **API Request: Start Level** (lines 2674-2683)
   - **Endpoint**: `POST /api/level/start`
   - **Payload**: `{ level, target_lang, native_lang, topic, cefr, prompt, reuse }`
   - **Response**: `{ success, run_id, items }`
   - **Caching**: None at this stage (fresh data from backend)

### Phase 2: Task Queue Building

6. **Build Task Queue** (line 2686, function at 736-809)
   - Processes `RUN.items` to create task queue
   - Extracts multiple choice (MC) and sentence building (SB) tasks
   - Shuffles and limits to 15 tasks
   - Initializes progress dots UI

### Phase 3: First Task Preloading (CRITICAL - Blocks UI)

7. **Preload First Task Completely** (lines 2690-2701)
   - **Function**: `preloadTaskData(firstTaskIndex, progressCallback)`
   - **Purpose**: Ensure first task is 100% ready before showing
   - **Progress Updates**: Shows loader with status messages

   **Sub-steps of preloadTaskData** (lines 268-328):

   a. **Step 1: Load Word Data** (line 298)
      - **Function**: `preloadWordsBatch(words, lang, nativeLang)`
      - **Cache Check**: `WORDS_CACHE` Map (key: `lang + '|' + word`)
      - **API**: `POST /api/words/batch` (only for missing words)
      - **Cache Update**: All fetched words stored in `WORDS_CACHE`
      - **Tooltip Sync**: Updates tooltip cache via `window.setCachedWordData()`

   b. **Step 2: Enrich Words** (line 305)
      - **Function**: `batchEnrichWords(words, lang, nativeLang, sentenceContext, sentenceNative)`
      - **Cache Check**: Checks if words have translation + (lemma OR pos)
      - **API**: `POST /api/word/enrich_batch` (batch size: 10 words)
      - **Cache Update**: Enriched data merged into `WORDS_CACHE`
      - **Purpose**: Adds audio_url, IPA, examples, synonyms, collocations

   c. **Step 3: Preload Word Audio** (line 310)
      - **Function**: `preloadWordsAudio(words, lang)`
      - **Cache Check**: `audioPreloadCache` Map (key: audio URL)
      - **Process**:
        1. Extract audio URLs from `WORDS_CACHE`
        2. Create Audio elements with `preload='auto'`
        3. Wait for `canplaythrough` event
        4. Store Audio objects in `audioPreloadCache`
      - **Purpose**: Instant word audio playback on click

   d. **Step 4: Preload Sentence Audio** (lines 314-321)
      - **Function**: `prewarmSentenceTTS(sentenceText)`
      - **Cache Check**: `sentenceAudioCache` Map (key: `lang:${text.trim()}`)
      - **API**: `POST /api/sentence/tts` (if not cached)
      - **Cache Update**: Stores audio URL in `sentenceAudioCache`
      - **Preload**: Creates Audio element and preloads for instant replay

8. **Hide Loader & Render First Task** (lines 2703-2707)
   - Loader hidden after preloading complete
   - **Function**: `renderCurrent()` - displays first task
   - **What renderCurrent() Does** (lines 1480-1856):
     - Updates progress indicators
     - Renders sentence with word spans (clickable for tooltips)
     - For MC tasks: Creates gap, renders options with click handlers
     - For SB tasks: Creates sentence building interface
     - Binds replay button (uses preloaded sentence audio)
     - Highlights words by familiarity (uses `familiarityCache`)
     - Word clicks use cached audio (`audioPreloadCache`)
     - All word data from `WORDS_CACHE` (no API calls during render)

### Phase 4: Background Preloading (Non-Blocking)

9. **Background Preload Next Tasks** (lines 2709-2728)
   - **Trigger**: `setTimeout(..., 100)` - starts 100ms after first task shown
   - **Target**: Next 2-3 tasks ahead
   - **Process**: Same `preloadTaskData()` function, but:
     - No progress callback (silent)
     - Non-blocking (fire-and-forget)
     - Errors logged but don't affect UI

---

## Event Flow: Custom Level Start (Pre-loaded Data)

### Path A: Pre-loaded Data (lines 2415-2491)

1. **Check for Pre-loaded Data** (line 2415)
   - `RUN._customLevelData` contains full level items
   - No API call needed

2. **RUN State Setup** (lines 2419-2426)
   - Same as standard level
   - Uses `RUN._customLevelData` directly

3. **UI Preparation** (lines 2428-2436)
   - Same as standard level

4. **Build Task Queue** (line 2440)
   - Same as standard level

5. **Preload First Task** (lines 2444-2455)
   - Same preloading process as standard level

6. **Background Preload** (lines 2466-2485)
   - Same background preloading as standard level

### Path B: API-Based Custom Level (lines 2495-2615)

1. **API Request: Start Custom Level** (lines 2525-2535)
   - **Endpoint**: `POST /api/custom-levels/{groupId}/{levelNumber}/start`
   - **Backend Processing** (app.py:3821-3880):
     - Checks for lazy loading flag
     - Triggers word enrichment if needed
     - Returns `{ success, run_id, items }`

2. **Remaining Steps**: Same as Path A (steps 2-6)

---

## Caching Mechanisms

### 1. Word Data Cache (`WORDS_CACHE`)
- **Type**: `Map<string, object>`
- **Key Format**: `lang + '|' + word`
- **Location**: `static/js/ui/lesson.js:14`
- **Storage**: In-memory (browser session)
- **Contents**:
  - `word`, `language`, `native_language`
  - `translation`, `lemma`, `pos`
  - `ipa`, `example`, `synonyms`, `collocations`
  - `audio_url`, `familiarity`
- **Lifetime**: Until page refresh
- **Update Points**:
  - `preloadWordsBatch()` - batch API response
  - `batchEnrichWords()` - enrichment API response
  - `cachePut()` - individual word updates

### 2. Audio Preload Cache (`audioPreloadCache`)
- **Type**: `Map<string, Audio | 'loading' | null>`
- **Key Format**: Audio URL (trimmed)
- **Location**: `static/js/ui/lesson.js:1085`
- **Storage**: In-memory (browser session)
- **Contents**: Preloaded Audio elements ready for instant playback
- **States**:
  - `'loading'`: Currently preloading
  - `Audio object`: Ready to play
  - `null`: Preload failed
- **Lifetime**: Until page refresh
- **Update Points**:
  - `preloadAudio()` - when audio loads successfully
  - `preloadWordsAudio()` - batch preloading

### 3. Sentence Audio Cache (`sentenceAudioCache`)
- **Type**: `Map<string, string>`
- **Key Format**: `lang:${text.trim()}`
- **Location**: `static/js/ui/lesson.js:934`
- **Storage**: In-memory (browser session)
- **Contents**: Audio URLs for sentence TTS
- **Lifetime**: Until page refresh
- **Update Points**:
  - `prewarmSentenceTTS()` - when TTS API returns URL
  - `speakSentenceOnce()` - on-demand TTS generation

### 4. Familiarity Cache (`familiarityCache`)
- **Type**: `Map<string, number>`
- **Key Format**: `lang:${word.toLowerCase()}`
- **Location**: `static/js/ui/lesson.js:1308`
- **Storage**: In-memory (browser session)
- **Contents**: Word familiarity values (0-5)
- **Lifetime**: Until page refresh
- **Update Points**:
  - `getCachedFamiliarity()` - on fetch
  - `updateFamiliarityOptimistic()` - optimistic updates
  - Batch familiarity updates after task completion

### 5. Level State Cache (DOM-based)
- **Type**: `dataset.bulkData` on level elements
- **Location**: `static/js/ui/levels.js`
- **Storage**: DOM attributes (persists until page refresh)
- **Contents**: Level status, score, progress data
- **Update Points**:
  - `applyLevelStates()` - bulk API response
  - Level completion

### 6. Tooltip Cache (Global)
- **Type**: Managed by `window.setCachedWordData()`
- **Location**: `static/js/ui/tooltip.js` (referenced)
- **Storage**: In-memory (browser session)
- **Contents**: Word data for tooltip display
- **Sync**: Updated via `cachePut()` in lesson.js

### 7. Practice Word Cache
- **Type**: `WordDataCache` class
- **Location**: `static/js/ui/practice.js:34-59`
- **Storage**: In-memory with expiration (10 minutes)
- **Contents**: Word data for practice mode
- **Max Size**: Configurable (default: 100 entries)

---

## API Endpoints Called During Level Start

### Standard Level
1. **POST /api/level/start**
   - **When**: Initial level start
   - **Purpose**: Get level items and run_id
   - **Caching**: None (fresh data)

2. **POST /api/words/batch**
   - **When**: During `preloadTaskData()` - Step 1
   - **Purpose**: Fetch word data (translation, lemma, pos, etc.)
   - **Caching**: Results stored in `WORDS_CACHE`
   - **Conditional**: Only called for words not in cache

3. **POST /api/word/enrich_batch**
   - **When**: During `preloadTaskData()` - Step 2
   - **Purpose**: Enrich words with audio_url, IPA, examples
   - **Caching**: Results merged into `WORDS_CACHE`
   - **Conditional**: Only called for words missing enrichment data

4. **POST /api/sentence/tts**
   - **When**: During `preloadTaskData()` - Step 4
   - **Purpose**: Generate sentence audio URL
   - **Caching**: URL stored in `sentenceAudioCache`
   - **Conditional**: Only called if not in cache

### Custom Level
1. **POST /api/custom-levels/{groupId}/{levelNumber}/start**
   - **When**: Initial custom level start (if not pre-loaded)
   - **Purpose**: Get custom level items and run_id
   - **Backend**: May trigger lazy word enrichment

2. **POST /api/custom-levels/{groupId}/{levelNumber}/enrich_batch**
   - **When**: During word enrichment (if custom level context)
   - **Purpose**: Enrich words for custom level
   - **Caching**: Results stored in `WORDS_CACHE`

3. **Same as Standard Level**: Steps 2-4 above

---

## Performance Optimizations

### 1. Sequential Preloading Strategy
- **First Task**: Fully preloaded before UI display (blocking)
- **Next Tasks**: Preloaded in background (non-blocking)
- **Rationale**: User sees first task instantly, subsequent tasks ready when needed

### 2. Cache-First Approach
- All data fetching checks cache first
- API calls only for missing data
- Reduces network requests significantly

### 3. Batch Operations
- Word data: Batch API (`/api/words/batch`)
- Word enrichment: Batch API (`/api/word/enrich_batch`, max 10 words)
- Audio preloading: Parallel batches (configurable size)

### 4. Smart Enrichment
- Only enriches words missing core data (translation OR lemma/pos)
- Checks cache before enrichment API call
- Skips enrichment if already complete

### 5. Audio Preloading
- Audio elements created and preloaded before needed
- `canplaythrough` event ensures readiness
- Failed preloads don't block UI (graceful degradation)

### 6. Optimistic Updates
- Familiarity values updated optimistically
- Batch updates sent to backend after task completion
- Cache updated immediately for responsive UI

---

## Error Handling

### Cache Misses
- Graceful fallback to API calls
- No UI blocking on cache failures

### API Failures
- Enrichment failures: Logged, but don't block level start
- Audio preload failures: Marked as `null` in cache, fallback to on-demand loading
- Sentence TTS failures: Silent failure, replay button may not work

### Network Issues
- Timeout handling (5 seconds for audio preload)
- Retry logic not implemented (would add complexity)

---

## Timing Breakdown (Estimated)

### Standard Level Start
1. **Level Lock Check**: < 1ms (DOM cache)
2. **API: Start Level**: 100-500ms (network dependent)
3. **Build Task Queue**: < 10ms (in-memory)
4. **Preload First Task**:
   - Word data batch: 100-300ms (if cache miss)
   - Word enrichment: 200-500ms (if needed)
   - Audio preload: 500-2000ms (network dependent)
   - Sentence TTS: 300-1000ms (if cache miss)
   - **Total**: 1-4 seconds (first time), < 100ms (cached)
5. **Render First Task**: < 50ms
6. **Background Preload**: Non-blocking, continues in background

**Total User-Visible Time**: 1-4 seconds (first time), < 200ms (cached)

---

## Cache Invalidation

### Word Cache
- **Invalidation**: Manual via `window.invalidateWordsCache(lang)`
- **Trigger**: After level completion, familiarity updates
- **Scope**: Language-specific

### Audio Cache
- **Invalidation**: None (cleared on page refresh)
- **Lifetime**: Browser session

### Sentence Audio Cache
- **Invalidation**: None (cleared on page refresh)
- **Lifetime**: Browser session

### Familiarity Cache
- **Invalidation**: Updated after batch familiarity API calls
- **Lifetime**: Browser session

---

## Recommendations for Optimization

1. **Persistent Cache**: Consider localStorage for word data (with expiration)
2. **Service Worker**: Cache audio files for offline playback
3. **Predictive Preloading**: Preload likely next words based on level content
4. **Compression**: Compress audio files for faster preloading
5. **CDN**: Use CDN for audio files to reduce latency
6. **IndexedDB**: Store larger datasets (audio blobs) in IndexedDB

---

## Summary

The level start process is highly optimized with multiple layers of caching:

1. **Word Data**: Cached in-memory, batch API calls for missing data
2. **Audio**: Preloaded Audio elements for instant playback
3. **Sentence TTS**: URLs cached, audio preloaded
4. **Familiarity**: Cached for optimistic UI updates
5. **Level State**: Cached in DOM for instant lock checks

The system ensures the first task is **completely ready** before display, while subsequent tasks are preloaded in the background. This provides a seamless experience with minimal wait times, especially on repeat visits when caches are warm.

