# Level Loading System Redesign

## Current System Analysis

### Current Flow:
1. **Click "Start Level"**
   - Loads level data from API
   - Shows loading screen briefly
   - Hides loader immediately
   - Renders first task
   - **Then** starts loading words/audio in background (too late!)

2. **Tooltip Opening:**
   - Makes individual `/api/word?word=X&language=Y&native_language=Z` call
   - Each word = 1 API call
   - No batch loading

3. **Task Switching:**
   - No preloading of next task
   - Everything loaded on-demand (slow)

### Problems:
- ❌ Loading screen closes before content is ready
- ❌ Tooltip makes individual API calls (N calls for N words)
- ❌ No preloading of next task
- ❌ Audio loaded after task is shown (delay)
- ❌ Word data loaded after tooltip opens (delay)

---

## Ideal System Design

### Phase 1: Loading Screen (Blocking)
**When:** User clicks "Start Level"

**What to load:**
1. ✅ Level content (sentences/items)
2. ✅ **All words** from first task (batch API)
3. ✅ **All tooltip data** for first task words (batch API)
4. ✅ **First sentence audio** (preload)
5. ✅ **Word audio** for first task (preload)
6. ✅ Task queue building

**Loading Screen shows:**
- Progress indicator
- "Loading level content..."
- "Preparing first task..."
- "Ready!"

**Only hide loader when:**
- ✅ All first task data is loaded
- ✅ Audio is ready
- ✅ Tooltip data is cached

### Phase 2: During First Task (Non-blocking)
**When:** User is working on first task

**What to preload in background:**
1. ✅ **All words** from second task (batch API)
2. ✅ **All tooltip data** for second task words (batch API)
3. ✅ **Second sentence audio** (preload)
4. ✅ **Word audio** for second task (preload)

**Priority:** Low priority, don't interfere with current task

### Phase 3: After Task Submission (Non-blocking)
**When:** User submits answer to current task

**What to preload:**
1. ✅ **All words** from third task (batch API)
2. ✅ **All tooltip data** for third task words (batch API)
3. ✅ **Third sentence audio** (preload)
4. ✅ **Word audio** for third task (preload)

**Pattern:** Always preload next 2-3 tasks ahead

---

## Tooltip System Redesign

### Current: Individual API Calls
```javascript
// BAD: N API calls for N words
for (const word of words) {
  await fetch(`/api/word?word=${word}&language=${lang}&native_language=${nat}`);
}
```

### New: Batch API Call
```javascript
// GOOD: 1 API call for all words
await fetch('/api/words/batch', {
  method: 'POST',
  body: JSON.stringify({
    words: ['word1', 'word2', 'word3', ...],
    language: lang,
    native_language: nat
  })
});
```

### Tooltip Opening Flow:
1. Check cache first (instant if cached)
2. If not cached, use batch API to load all words at once
3. Display tooltip immediately with cached data

---

## Implementation Plan

### Step 1: Create Comprehensive Preload Function
```javascript
async function preloadTaskData(taskIndex) {
  const task = RUN.items[taskIndex];
  if (!task) return;
  
  const words = extractWords(task);
  const lang = RUN.target;
  const nativeLang = RUN.native;
  
  // Parallel loading:
  await Promise.all([
    // 1. Load all word data + tooltip data (batch)
    preloadWordsBatch(words, lang, nativeLang),
    
    // 2. Preload sentence audio
    prewarmSentenceTTS(task.text_target),
    
    // 3. Preload word audio (batch)
    preloadWordsAudio(words, lang),
    
    // 4. Enrich words if needed (batch)
    batchEnrichWords(words, lang, nativeLang, task.text_target, task.text_native_ref)
  ]);
}
```

### Step 2: Update Loading Screen Logic
```javascript
async function startLevel(lvl) {
  showLoader('Loading level...');
  
  // Load level data
  const levelData = await loadLevelData(lvl);
  
  // Build task queue
  buildTaskQueue();
  
  // Preload first task COMPLETELY before showing
  showLoader('Preparing first task...');
  await preloadTaskData(0); // BLOCKING - wait for completion
  
  // Now show the task
  hideLoader();
  renderCurrent();
  
  // Preload next tasks in background (non-blocking)
  setTimeout(() => {
    preloadTaskData(1).catch(() => {});
    preloadTaskData(2).catch(() => {});
  }, 100);
}
```

### Step 3: Update Tooltip to Use Batch API
```javascript
async function openTooltip(anchor, word) {
  // Check cache first
  const cached = getCachedWordData(word, lang, nativeLang);
  if (cached) {
    displayTooltip(cached); // Instant!
    return;
  }
  
  // If not cached, load via batch API
  // But ideally, this should already be preloaded!
  const data = await fetchWordDataBatch([word], lang, nativeLang);
  displayTooltip(data[word]);
}
```

### Step 4: Preload Next Task After Submission
```javascript
async function submitAnswer() {
  // Process current answer...
  
  // Preload next task immediately (non-blocking)
  const nextTaskIndex = RUN.idx + 1;
  if (RUN.items[nextTaskIndex]) {
    preloadTaskData(nextTaskIndex).catch(() => {});
  }
  
  // Advance to next task
  advanceToNextTask();
}
```

---

## Benefits

1. **Instant Tooltip Opening:** All data preloaded during loading screen
2. **Instant Audio:** Audio ready before task is shown
3. **Smooth Task Switching:** Next task already loaded
4. **Fewer API Calls:** Batch API instead of individual calls
5. **Better UX:** Loading screen shows actual progress
6. **No Performance Impact:** Preloading happens in background, doesn't block UI

---

## Backend Requirements

### New/Enhanced Endpoints:
1. ✅ `/api/words/batch` - Already exists, returns word data + familiarity
2. ✅ `/api/word/enrich_batch` - Already exists for enrichment
3. ⚠️ Consider: `/api/words/batch-with-tooltip` - Returns everything needed for tooltip in one call

### Current `/api/words/batch` endpoint:
- Returns: `{ word, translation, ipa, pos, lemma, example, synonyms, collocations, familiarity, ... }`
- ✅ Already includes tooltip data!
- ✅ Already includes familiarity data!

**Conclusion:** Backend is ready! Just need to use it properly.

---

## Migration Strategy

1. **Phase 1:** Implement preload function (non-breaking)
2. **Phase 2:** Update loading screen to wait for preload (breaking change)
3. **Phase 3:** Update tooltip to use batch API (non-breaking, fallback to individual)
4. **Phase 4:** Add next-task preloading (non-breaking)

---

## Performance Targets

- **Level Start:** < 2 seconds (currently ~30 seconds)
- **Tooltip Open:** < 100ms (currently ~3 seconds)
- **Task Switch:** < 500ms (currently ~10 seconds)
- **Audio Play:** Instant (currently ~10 seconds delay)

