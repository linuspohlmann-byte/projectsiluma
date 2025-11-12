// Tooltip module: encapsulated state + public API
// Provides: setupTooltipSaveClose(), observeTooltipClose(), openTooltip(), closeTooltip(), playOrGenAudio(), ttSave()
// Also exposes openTooltip/playOrGenAudio/closeTooltip on window for legacy inline callers in index.html

import { api } from '../api.js';

// Local helpers
const $ = (sel) => document.querySelector(sel);

// Helper for language badges (target/native)
function _langBadgeText(kind){
  // kind: 'target' | 'native'
  return kind==='native' ? 'Muttersprache' : 'Zielsprache';
}

// Tooltip state
const TT = { el: null, word: '', anchor: null, isSaving: false };

// Word data cache for performance optimization
const wordDataCache = new Map();
const CACHE_TTL = 10 * 60 * 1000; // 10 minutes

function getCacheKey(word, language, nativeLanguage) {
    return `${word}:${language}:${nativeLanguage}`;
}

function getCachedWordData(word, language, nativeLanguage) {
    const cacheKey = getCacheKey(word, language, nativeLanguage);
    const cached = wordDataCache.get(cacheKey);
    
    if (cached && Date.now() - cached.timestamp < CACHE_TTL) {
        return cached.data;
    }
    
    // Remove expired entry
    if (cached) {
        wordDataCache.delete(cacheKey);
    }
    
    // SYNC: Also check WORDS_CACHE from lesson.js for instant access
    if (typeof window !== 'undefined' && window.cacheGet) {
        const lessonCached = window.cacheGet(word, language);
        if (lessonCached) {
            // Sync to tooltip cache
            setCachedWordData(word, language, nativeLanguage, lessonCached);
            return lessonCached;
        }
    }
    
    return null;
}

function setCachedWordData(word, language, nativeLanguage, data) {
    const cacheKey = getCacheKey(word, language, nativeLanguage);
    wordDataCache.set(cacheKey, {
        data: data,
        timestamp: Date.now()
    });
    
    // Limit cache size to prevent memory issues (keep last 500 entries)
    if (wordDataCache.size > 500) {
        const firstKey = wordDataCache.keys().next().value;
        wordDataCache.delete(firstKey);
    }
}

// Expose cache functions globally for lesson.js access
if (typeof window !== 'undefined') {
    window.setCachedWordData = setCachedWordData;
    window.getCachedWordData = getCachedWordData;
}

// --- Save current tooltip fields ------------------------------------------------
export async function ttSave(){
  // Prevent multiple simultaneous saves
  if (TT.isSaving) {
    console.log('🔧 Save already in progress, skipping...');
    return;
  }
  
  const wordEl = document.getElementById('tt-title');
  const word = (wordEl?.textContent||'').trim();
  if(!word) return;
  
  TT.isSaving = true;
  
  // Use stored context information for reliable identification
  const context = TT.wordContext || {};
  const language = context.language || (document.getElementById('target-lang')?.value||'').trim();
  const native_language = context.native_language || (localStorage.getItem('siluma_native')||'').trim();
  let user_id = context.user_id;
  
  // Fallback: try to get user_id from auth context if not available
  if (!user_id) {
    try {
      // First try to get from global auth state
      if (window.authManager && window.authManager.currentUser) {
        user_id = window.authManager.currentUser.id;
      } else {
        // Fallback: try to decode from session token
        const sessionToken = localStorage.getItem('session_token');
        if (sessionToken) {
          try {
            const userInfo = JSON.parse(atob(sessionToken.split('.')[1]));
            user_id = userInfo.user_id || userInfo.id;
          } catch (e) {
            console.warn('⚠️ Could not decode session token:', e);
          }
        }
      }
    } catch (e) {
      console.warn('⚠️ Could not get user ID:', e);
    }
  }
  
  const familiarity = parseInt(document.getElementById('tt-fam')?.value||'0',10)||0;
  const user_comment = (document.getElementById('tt-user-comment')?.value||'').trim();
  
  // Only save if we have all required context information
  if (!language || !native_language) {
    console.warn('⚠️ Missing language context for tooltip save:', { language, native_language });
    return;
  }
  
  // Warn if user_id is still undefined
  if (!user_id) {
    console.warn('⚠️ User ID is undefined, saving without user context');
  }
  
  // Save familiarity and user comment with full context
  const payload = { 
    word, 
    language, 
    native_language, 
    user_id,
    familiarity, 
    user_comment 
  };
  
  console.log('🔧 Saving tooltip data:', payload);
  try{
    // Add headers for authentication and native language
    const headers = { 'Content-Type': 'application/json' };
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    // Add authentication header if available
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    
    await fetch('/api/word/upsert', {
      method:'POST', headers,
      body: JSON.stringify(payload)
    });
    
    // Invalidate words cache to ensure fresh data is loaded
    try{
      if (typeof window.invalidateWordsCache === 'function') {
        window.invalidateWordsCache(payload.language);
      }
    }catch(_){}
  }catch(_){ /* ignore network errors on close */ }
  finally {
    TT.isSaving = false;
  }
}

// --- Close tooltip -------------------------------------------------------------
export async function closeTooltip(doSave=true){
  const tip = TT.el || document.getElementById('tooltip');
  if(!tip) return;
  
  // Always save when closing tooltip to ensure data persistence
  if(doSave){ 
    console.log('🔧 Closing tooltip, saving data...');
    await ttSave(); 
  }
  
  tip.style.display = 'none';
  TT.word=''; TT.anchor=null; TT.wordContext=null; TT.isSaving=false;
  document.removeEventListener('click', onDocClick, {capture:false});
}

// --- Open tooltip anchored to a word ------------------------------------------
export async function openTooltip(anchor, word){
  // Save current tooltip data before opening new one
  if (TT.word && TT.word !== word) {
    console.log('🔧 Opening new tooltip, saving previous data...');
    await ttSave();
  }
  
  TT.word = word; TT.anchor = anchor;
  TT.el = document.getElementById('tooltip');
  const tip = TT.el;
  if(!tip) return;
  
  // Extract and store all 4 required attributes for reliable identification
  TT.wordContext = {
    word: word,
    language: null,
    native_language: null,
    user_id: null
  };
  
  // 1. Get target language (from current lesson or dropdown)
  TT.wordContext.language = window.RUN?.target || document.getElementById('target-lang')?.value || 'en';
  
  // 2. Get native language (from localStorage or user context)
  TT.wordContext.native_language = localStorage.getItem('siluma_native') || 'en';
  
  // 3. Get user ID (from auth context)
  try {
    // First try to get from global auth state
    if (window.authManager && window.authManager.currentUser) {
      TT.wordContext.user_id = window.authManager.currentUser.id;
    } else {
      // Fallback: try to decode from session token
      const sessionToken = localStorage.getItem('session_token');
      if (sessionToken) {
        try {
          const userInfo = JSON.parse(atob(sessionToken.split('.')[1]));
          TT.wordContext.user_id = userInfo.user_id || userInfo.id;
        } catch (e) {
          console.warn('⚠️ Could not decode session token:', e);
        }
      }
    }
  } catch (e) {
    console.warn('⚠️ Could not get user ID:', e);
  }
  
  console.log('🔧 Tooltip context:', TT.wordContext);
  
  // Extract sentence context from the lesson if available
  TT.sentenceContext = null;
  if (window.RUN && window.RUN.items && window.RUN.items.length > 0) {
    // Find the current sentence that contains this word
    const currentItem = window.RUN.items[window.RUN.idx || 0];
    if (currentItem && currentItem.text_target) {
      TT.sentenceContext = currentItem.text_target;
    }
  }
  const gSelInit = document.getElementById('tt-gender');
  if(gSelInit){
    const lang0 = window.RUN?.target || document.getElementById('target-lang')?.value || 'en';
    gSelInit.innerHTML = genderOptionsForLanguage(lang0).map(([v,l])=>`<option value="${v}">${l}</option>`).join('');
    // Set dynamic badges for field language (no hardcoded names)
    const bIpa = document.getElementById('tt-badge-ipa');
    if(bIpa) bIpa.textContent = _langBadgeText('target');
    const bSyn = document.getElementById('tt-badge-syn');
    if(bSyn) bSyn.textContent = _langBadgeText('target');
    const bExN = document.getElementById('tt-badge-example-native');
    if(bExN) bExN.textContent = _langBadgeText('native');
  }

  // Show and position
  tip.style.display = 'block';
  positionTooltip(anchor);
  // Stop propagation for internal clicks
  tip.addEventListener('click', (ev)=> ev.stopPropagation(), { once:false });
  // Defer outside-click listener so it does not fire for the same click
  setTimeout(()=>{
  if(!document._ttOutsideBound){
    document.addEventListener('click', onDocClick, { capture:false });
    document._ttOutsideBound = true;
  }
}, 0);

  // Title
  const w = String(word||'').trim();
  const titleEl = document.getElementById('tt-title');
  if(titleEl) titleEl.textContent = w || 'Wort';

  // Placeholders
  const tIn = $('#tt-translation'), exIn = $('#tt-example'), exN = $('#tt-example-native');
  if(tIn) tIn.placeholder = 'lade…';
  if(exIn) exIn.placeholder = 'lade…';
  if(exN) exN.placeholder = 'lade…';

  const fill = (js)=>{
    if(!js) return;
    
    // Fill text fields (read-only)
    const translationEl = $('#tt-translation');
    if(translationEl) translationEl.textContent = js.translation || '–';
    
    const ipaEl = $('#tt-ipa');
    if(ipaEl) ipaEl.textContent = js.ipa || '–';
    
    const genderEl = $('#tt-gender');
    if(genderEl) {
      const genderMap = {
        'masc': 'Maskulin',
        'fem': 'Feminin', 
        'neut': 'Neutrum',
        'common': 'Utrum',
        'none': 'Kein Genus'
      };
      genderEl.textContent = genderMap[js.gender] || 'Kein Genus';
    }
    
    const exampleNativeEl = $('#tt-example-native');
    if(exampleNativeEl) exampleNativeEl.textContent = js.example_native || '–';
    
    const synEl = $('#tt-syn');
    if(synEl) synEl.textContent = Array.isArray(js.synonyms) ? js.synonyms.join(', ') : '–';
    
    const posEl = $('#tt-pos');
    if(posEl) {
      const posMap = {
        'NOUN': 'Nomen',
        'VERB': 'Verb',
        'ADJ': 'Adjektiv',
        'ADV': 'Adverb',
        'PRON': 'Pronomen',
        'DET': 'Artikel/Det',
        'PREP': 'Präposition',
        'CONJ': 'Konjunktion',
        'NUM': 'Numerale',
        'PART': 'Partikel',
        'INTJ': 'Interjektion'
      };
      posEl.textContent = posMap[js.pos] || '–';
    }
    
    // Fill editable fields (familiarity and user comment)
    const fam = $('#tt-fam'); 
    if(fam) {
      // Always reset to the value from the data, default to 0 if not available
      fam.value = String(js.familiarity ?? 0);
    }
    
    const userComment = $('#tt-user-comment');
    if(userComment) {
      // Always reset to the value from the data, default to empty string if not available
      userComment.value = js.user_comment || '';
    }
    
    // Audio handling
    const a = $('#tt-audio-el');
    if(a){
      if((js.audio_url||'').trim()){ a.src = js.audio_url; a.style.display='block'; }
      else { a.removeAttribute('src'); a.style.display='none'; }
    }
    
    // Keep hidden elements for compatibility
    if(tIn) tIn.value = js.translation || tIn.value || '';
    if(exIn) exIn.value = js.example || exIn.value || '';
    if(exN) exN.value = js.example_native || exN.value || '';
    const lem = $('#tt-lemma'); if(lem) lem.value = js.lemma || lem.value || '';
    const pos = $('#tt-pos-select'); if(pos) pos.value = (js.pos||'').toUpperCase();
    const ipa = $('#tt-ipa-input'); if(ipa) ipa.value = js.ipa || ipa.value || '';
    const syn = $('#tt-syn-input'); if(syn) syn.value = Array.isArray(js.synonyms) ? js.synonyms.join(', ') : (syn.value||'');
    const col = $('#tt-col'); if(col) col.value = Array.isArray(js.collocations) ? js.collocations.join(', ') : (col.value||'');
    const gSel = $('#tt-gender-select'); if(gSel){
      const allowed = new Set(['masc','fem','neut','common','none']);
      const v = String(js.gender||'none').toLowerCase();
      gSel.value = allowed.has(v) ? v : 'none';
    }
  };

  // Auto-refetch audio if missing
  const a = $('#tt-audio-el');
  if(a && !a._ttBound){
    a.addEventListener('error', ()=>{ a.removeAttribute('src'); playOrGenAudio(); }, {once:false});
    a._ttBound = true;
  }

  function genderOptionsForLanguage(lang){
    const L = String(lang||'en').toLowerCase();
    if(['fr','es','it','pt','ro','ca'].includes(L)) return [['masc',window.t ? window.t('grammar.masculine', 'Maskulin') : 'Maskulin'],['fem',window.t ? window.t('grammar.feminine', 'Feminin') : 'Feminin'],['none',window.t ? window.t('grammar.no_gender', 'Kein Genus') : 'Kein Genus']];
    if(['nl','sv','no','da'].includes(L)) return [['common',window.t ? window.t('grammar.common', 'Utrum') : 'Utrum'],['neut',window.t ? window.t('grammar.neuter', 'Neutrum') : 'Neutrum'],['none',window.t ? window.t('grammar.no_gender', 'Kein Genus') : 'Kein Genus']];
    if(['de','ru','pl','cs','sk','uk','el','ar','tr'].includes(L)) return [['masc',window.t ? window.t('grammar.masculine', 'Maskulin') : 'Maskulin'],['fem',window.t ? window.t('grammar.feminine', 'Feminin') : 'Feminin'],['neut',window.t ? window.t('grammar.neuter', 'Neutrum') : 'Neutrum'],['none',window.t ? window.t('grammar.no_gender', 'Kein Genus') : 'Kein Genus']];
    return [['none',window.t ? window.t('grammar.no_gender', 'Kein Genus') : 'Kein Genus']];
  }

  // Fetch details, enrich if needed
  try{
    const lang = window.RUN?.target || 'en';
    const nat  = window.RUN?.native || 'de';
    
    console.log('🔧 Tooltip opening for word:', w, 'language:', lang);
    
    // CRITICAL: Check cache FIRST before any API calls for instant display
    let js1 = getCachedWordData(w, lang, nat);
    if (js1) {
      console.log('✅ Tooltip: Using cached word data for instant display:', w);
      fill(js1);
      // Audio will be handled by playOrGenAudio if needed
    }
    
    // Check if this is a custom level and try to get word data from custom level context
    if (!js1) {
      if (window.RUN._customGroupId && window.RUN._customLevelNumber) {
        console.log('🔧 Tooltip for custom level word:', w);
        
        // For custom levels, try to get word data from the current item first
        const currentItem = window.RUN.items[window.RUN.idx || 0];
        if (currentItem && currentItem.words) {
          // Look for the word in the current item's words array
          const wordData = currentItem.words.find(word => word === w);
          if (wordData) {
            console.log('🔧 Found word in custom level item:', wordData);
            // Create a basic word object for the tooltip
            js1 = {
              word: w,
              language: lang,
              translation: '', // Will be filled by enrichment
              familiarity: 0,
              pos: '',
              ipa: '',
              example_native: '',
              synonyms: [],
              collocations: [],
              gender: 'none'
            };
          }
        }
      }
      
      // If we don't have word data yet, try to fetch from global database
      if (!js1) {
        console.log('⚠️ Tooltip: Word data not in cache, fetching for:', w);
        
        // NEW: Use batch API endpoint directly (more efficient than individual calls)
        const headers = { 'Content-Type': 'application/json' };
        const sessionToken = localStorage.getItem('session_token');
        if (sessionToken) {
          headers['Authorization'] = `Bearer ${sessionToken}`;
        }
        
        try {
          // Use batch endpoint - even for single word, it's more efficient
          const batchResponse = await fetch('/api/words/batch', {
            method: 'POST',
            headers,
            body: JSON.stringify({
              words: [w],
              language: lang,
              native_language: nat
            })
          });
          
          if (batchResponse.ok) {
            const batchData = await batchResponse.json();
            if (batchData.success && batchData.words && batchData.words[w]) {
              js1 = batchData.words[w];
              console.log('✅ Tooltip: Fetched word data via batch API:', w);
              
              // Cache the word data (sync to both caches)
              if (js1 && js1.word) {
                setCachedWordData(w, lang, nat, js1);
                // Also sync to WORDS_CACHE
                if (window.cachePut) {
                  window.cachePut(js1);
                }
              }
            }
          }
        } catch (e) {
          console.log('⚠️ Batch API failed, falling back to single API:', e);
          
          // Fallback to single word API if batch didn't work
          const r1 = await fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}&native_language=${encodeURIComponent(nat)}`, {
            headers: { 'Authorization': sessionToken ? `Bearer ${sessionToken}` : '' }
          });
          js1 = await r1.json();
          console.log('✅ Tooltip: Fetched word data via single API:', w);
          
          // Cache the word data (sync to both caches)
          if (js1 && js1.word) {
            setCachedWordData(w, lang, nat, js1);
            // Also sync to WORDS_CACHE
            if (window.cachePut) {
              window.cachePut(js1);
            }
          }
        }
      }
    }
    
    // Ensure the word in the data matches the requested word
    if (js1 && js1.word !== w) {
      console.log('⚠️ Word mismatch in tooltip data:', js1.word, 'vs requested:', w);
      js1.word = w; // Fix the word
    }
    
    fill(js1);
    
    const missing = !(js1 && (js1.translation||'').trim());
    if(missing){
      console.log('🔧 Word missing translation, enriching:', w);
      try{
        // Check if we're in a custom level context
        if (window.RUN._customGroupId && window.RUN._customLevelNumber) {
          console.log('🔧 Using custom level batch enrich for tooltip');
          await fetch(`/api/custom-levels/${window.RUN._customGroupId}/${window.RUN._customLevelNumber}/enrich_batch`, {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
              words: [w], // Batch API expects array of words
              language:lang, 
              native_language:nat,
              sentence_context: TT.sentenceContext || '', // Use sentence context if available
              sentence_native: ''
            })
          });
        } else {
          // Use standard enrichment API
          console.log('🔧 Using standard enrich API for:', w);
          await fetch('/api/word/enrich', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({
              word:w, 
              language:lang, 
              native_language:nat,
              sentence_context: TT.sentenceContext || '', // Use sentence context if available
              sentence_native: ''
            })
          });
        }
        
        // Try to fetch the enriched word data
        console.log('🔧 Fetching enriched word data for:', w);
        
        // Add authentication headers for user-specific data
        const headers = {};
        const sessionToken = localStorage.getItem('session_token');
        if (sessionToken) {
          headers['Authorization'] = `Bearer ${sessionToken}`;
        }
        
        const r2 = await fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}&native_language=${encodeURIComponent(nat)}`, {
          headers
        });
        const js2 = await r2.json();
        console.log('🔧 Fetched enriched word data:', js2);
        
        // Ensure the word in the enriched data matches the requested word
        if (js2 && js2.word !== w) {
          console.log('⚠️ Word mismatch in enriched tooltip data:', js2.word, 'vs requested:', w);
          js2.word = w; // Fix the word
        }
        
        fill(js2);
      }catch(e){ 
        console.log('❌ Error enriching word:', e);
      }
    }
  }catch(e){ 
    console.log('❌ Error in tooltip fetch:', e);
  }
}

// --- Outside click handler ----------------------------------------------------

// --- Audio handling -----------------------------------------------------------
export async function playOrGenAudio(word, sentenceContext = null){
  const a = document.getElementById('tt-audio-el');
  const w = (typeof word === 'string' && word.trim()) ? word.trim() : (TT.word || '');
  const lang = (window.RUN && window.RUN.target) ? window.RUN.target : 'en';
  if(!a || !w) return;

  const loadedFor = a.dataset && a.dataset.word ? a.dataset.word : '';
  const sameWord = loadedFor && loadedFor === w;

  if(sameWord && a.src && a.src.trim() !== ''){
    try{ a.pause(); a.currentTime = 0; await a.play(); return; }catch(_){}
  }

  try{
    // First check if we have audio URL in cache (from word enrichment/preloading)
    let audioUrl = null;
    
    // Check tooltip cache first
    const nat = window.RUN?.native || localStorage.getItem('siluma_native') || 'de';
    const cachedTooltip = getCachedWordData(w, lang, nat);
    if (cachedTooltip && cachedTooltip.audio_url && cachedTooltip.audio_url.trim()) {
      audioUrl = cachedTooltip.audio_url.trim();
      console.log('✅ Tooltip audio: Found URL in tooltip cache:', w);
    }
    
    // Also check WORDS_CACHE
    if (!audioUrl && window.cacheGet) {
      const cached = window.cacheGet(w, lang);
      if (cached && cached.audio_url && cached.audio_url.trim()) {
        audioUrl = cached.audio_url.trim();
        console.log('✅ Tooltip audio: Found URL in WORDS_CACHE:', w);
      }
    }
    
    // If no cached URL, fetch from API
    if (!audioUrl) {
      console.log('⚠️ Tooltip audio: No cached URL, fetching from API:', w);
      const payload = { word: w, language: lang };
      if (sentenceContext && sentenceContext.trim()) {
        payload.sentence = sentenceContext.trim();
      }
      
      const r = await fetch('/api/word/tts', {
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify(payload)
      });
      const js = await r.json();
      if(js?.success && js.audio_url){
        audioUrl = js.audio_url;
        // Update cache with audio URL
        if (window.cacheGet) {
          const cached = window.cacheGet(w, lang);
          if (cached) {
            cached.audio_url = audioUrl;
            if (window.cachePut) window.cachePut(cached);
          }
        }
      }
    }
    
    if (audioUrl) {
      // Check if audio is preloaded for instant playback
      if (window.audioPreloadCache && window.audioPreloadCache.has(audioUrl)) {
        const preloaded = window.audioPreloadCache.get(audioUrl);
        if (preloaded && preloaded !== 'loading' && preloaded !== null) {
          // Use preloaded audio element for instant playback
          try {
            preloaded.currentTime = 0;
            await preloaded.play();
            return;
          } catch (e) {
            // Fall through to regular playback if preloaded fails
            if (window.DEBUG) console.warn('Preloaded audio play failed, falling back:', e);
          }
        }
      }
      
      // Regular playback - ensure audio is loaded before playing
      // Create a new audio element to avoid conflicts
      const audioEl = new Audio();
      audioEl.preload = 'auto';
      audioEl.src = audioUrl;
      a.src = audioUrl; // Also set on the tooltip element for compatibility
      a.style.display='block';
      if(a.dataset) a.dataset.word = w;
      
      // Wait for audio to be ready before playing
      try {
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            if (window.DEBUG) console.error('❌ Audio load timeout:', audioUrl);
            reject(new Error('Audio load timeout'));
          }, 5000);
          audioEl.addEventListener('canplaythrough', () => {
            clearTimeout(timeout);
            resolve();
          }, { once: true });
          audioEl.addEventListener('loadeddata', () => {
            clearTimeout(timeout);
            resolve();
          }, { once: true });
          audioEl.addEventListener('error', (e) => {
            clearTimeout(timeout);
            const error = audioEl.error;
            let errorMsg = 'Unknown error';
            if (error) {
              switch(error.code) {
                case error.MEDIA_ERR_ABORTED:
                  errorMsg = 'MEDIA_ERR_ABORTED - User aborted';
                  break;
                case error.MEDIA_ERR_NETWORK:
                  errorMsg = 'MEDIA_ERR_NETWORK - Network error (possibly CORS)';
                  break;
                case error.MEDIA_ERR_DECODE:
                  errorMsg = 'MEDIA_ERR_DECODE - Decode error (corrupted file)';
                  break;
                case error.MEDIA_ERR_SRC_NOT_SUPPORTED:
                  errorMsg = 'MEDIA_ERR_SRC_NOT_SUPPORTED - Format not supported or CORS blocked';
                  break;
                default:
                  errorMsg = `Error code ${error.code}`;
              }
            }
            if (window.DEBUG) console.error('❌ Audio load error:', errorMsg, 'URL:', audioUrl, 'Error details:', error);
            reject(new Error(errorMsg));
          }, { once: true });
        });
        audioEl.currentTime = 0;
        await audioEl.play();
        if (window.DEBUG) console.log('✅ Word audio playing:', audioUrl);
      } catch (e) {
        if (e.name === 'NotAllowedError' || e.name === 'AbortError') {
          if (window.DEBUG) console.log('🔇 Audio play blocked by browser policy, waiting for user interaction');
          // User interaction required - audio will play on next click
          const playOnClick = () => {
            document.removeEventListener('click', playOnClick, true);
            if (audioEl && audioEl.src === audioUrl) {
              audioEl.currentTime = 0;
              audioEl.play().then(() => {
                if (window.DEBUG) console.log('✅ Word audio playing after user interaction');
              }).catch(err => {
                if (window.DEBUG) console.error('❌ Audio play failed after user interaction:', err);
              });
            }
          };
          document.addEventListener('click', playOnClick, { once: true, capture: true });
        } else {
          if (window.DEBUG) console.error('❌ Audio play failed:', e, 'URL:', audioUrl, 'Error name:', e.name, 'Error message:', e.message);
        }
      }
    }
  }catch(_){};
}

// --- Positioning --------------------------------------------------------------
function positionTooltip(anchor){
  const tip = TT.el || document.getElementById('tooltip');
  if(!tip || !anchor || !anchor.getBoundingClientRect) return;
  const r = anchor.getBoundingClientRect();
  const pad = 20;
  
  // Check if we're on mobile (768px or less)
  const isMobile = window.innerWidth <= 768;
  
  // Get shell element to determine the right edge of the content area
  const shell = document.querySelector('.shell');
  const shellRect = shell ? shell.getBoundingClientRect() : null;
  
  // Calculate the right edge of the content area (shell right edge)
  const contentRightEdge = shellRect ? shellRect.right : window.innerWidth;
  
  // Position tooltip in the right margin area, centered vertically
  const w = tip.offsetWidth || 320;
  const h = tip.offsetHeight || 160;
  
  let x, y;
  
  if (isMobile) {
    // On mobile, position tooltip centered horizontally and above/below anchor
    x = (window.innerWidth - w) / 2;
    
    // Try to position above the anchor first
    y = r.top + window.scrollY - h - pad;
    
    // If it doesn't fit above, position below
    if (y < window.scrollY + pad) {
      y = r.bottom + window.scrollY + pad;
    }
    
    // Ensure it stays within viewport
    if (y + h > window.scrollY + window.innerHeight - pad) {
      y = window.scrollY + window.innerHeight - h - pad;
    }
  } else {
    // Desktop: position in right margin area
    // X position: right edge of content + some padding, but ensure it fits in viewport
    x = contentRightEdge + pad;
    if (x + w > window.innerWidth) {
      x = window.innerWidth - w - pad;
    }
    
    // Y position: center vertically relative to the anchor, but keep within viewport
    y = r.top + window.scrollY + (r.height / 2) - (h / 2);
    
    // Ensure tooltip stays within viewport bounds
    if (y < window.scrollY + pad) {
      y = window.scrollY + pad;
    } else if (y + h > window.scrollY + window.innerHeight - pad) {
      y = window.scrollY + window.innerHeight - h - pad;
    }
  }
  
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}

// --- Setup wiring -------------------------------------------------------------
export function setupTooltipSaveClose(){
  const tip = document.getElementById('tooltip');
  TT.el = tip || null;
  const x = document.getElementById('tt-close');
  const saveBtn = document.getElementById('tt-save');

  if(x){ x.onclick = ()=> closeTooltip(true); }
  if(saveBtn){ saveBtn.onclick = ()=>{ ttSave(); }; }

// Close when clicking outside (capturing phase to run before other handlers)
document.addEventListener('click',(ev)=>{
  if(!TT.el || TT.el.style.display==='none') return;
  if(TT.el.contains(ev.target)) return;
  const isWord = ev.target.closest && ev.target.closest('.word');
  if(isWord) return; // Wechsel handled openTooltip
  closeTooltip(true);
  }, true);

  // ESC closes tooltip and saves
  document.addEventListener('keydown', (e)=>{ if(e.key === 'Escape') { closeTooltip(true); } });

  // Tooltip textareas autoresize
  document.querySelectorAll('#tooltip textarea').forEach(ta=>{
    ta.addEventListener('input', ()=>{ ta.style.height='auto'; ta.style.height = (ta.scrollHeight)+"px"; });
  });
}

export function observeTooltipClose(){
  const tip = document.getElementById('tooltip');
  if(!tip) return;
  const isVisible = () => window.getComputedStyle(tip).display !== 'none';
  let wasVisible = isVisible();
  const obs = new MutationObserver(async () => {
    const nowVisible = isVisible();
    if (wasVisible && !nowVisible) { try { await ttSave(); } catch(_) {} }
    wasVisible = nowVisible;
  });
  obs.observe(tip, { attributes:true, attributeFilter:['style'] });
}

export function onDocClick(ev){
  const tip = TT.el || document.getElementById('tooltip');
  if(!tip) return;
  if(tip.contains(ev.target)) return;

  const nextWordEl = ev.target.closest && ev.target.closest('.word');
  if(nextWordEl && nextWordEl.dataset && nextWordEl.dataset.word){
    openTooltip(nextWordEl, nextWordEl.dataset.word);
    ev.stopPropagation();
    return;
  }
  if(ev.target === TT.anchor) return;
  closeTooltip(true);
}

const enrichBtn = document.getElementById('tt-enrich');
const audioBtn  = document.getElementById('tt-audio-btn');
if(enrichBtn){ enrichBtn.onclick = async (e)=>{ e.stopPropagation(); await enrichCurrentTooltip(); }; }
if(audioBtn && !audioBtn._bound){
  audioBtn.addEventListener('click', (e)=>{ e.stopPropagation(); playOrGenAudio(TT.word, TT.sentenceContext); });
  audioBtn._bound = true;
}

async function enrichCurrentTooltip(){
  const w = (document.getElementById('tt-title')?.textContent||'').trim();
  if(!w) return;
  const lang = (document.getElementById('target-lang')?.value||window.RUN?.target||'en');
  const nat  = (localStorage.getItem('siluma_native')||window.RUN?.native||'de');
  
  // Check if word is already enriched
  const cached = cacheGet(w, lang);
  if(cached && cached.translation && cached.pos) {
    console.log('🎯 Word already enriched, skipping tooltip enrichment:', w);
    return;
  }
  
  try{
    // Check if we're in a custom level context
    const isCustomLevel = window.RUN && (window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP);
    
    if (isCustomLevel) {
      // Use custom level batch enrichment API
      const groupId = window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP;
      const levelNumber = window.RUN._customLevelNumber || window.SELECTED_CUSTOM_LEVEL || 1;
      
      await fetch(`/api/custom-levels/${groupId}/${levelNumber}/enrich_batch`, {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          words: [w],
          language:lang,
          native_language:nat,
          sentence_context: '', // No context available in tooltip
          sentence_native: ''
        })
      });
    } else {
      // Use standard enrichment API
      await fetch('/api/word/enrich',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({
        word:w,
        language:lang,
        native_language:nat,
        sentence_context: '', // No context available in tooltip
        sentence_native: ''
      })});
    }
    // Add authentication headers for user-specific data
    const headers = {};
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    
    const js = await (await fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}&native_language=${encodeURIComponent(nat)}`, {
      headers
    })).json();
    const tIn = document.getElementById('tt-translation');
    const exIn = document.getElementById('tt-example');
    const exN  = document.getElementById('tt-example-native');
    if(tIn) tIn.value = js.translation || tIn.value || '';
    if(exIn) exIn.value = js.example || exIn.value || '';
    if(exN) exN.value  = js.example_native || exN.value || '';
    const fam = document.getElementById('tt-fam'); if(fam) fam.value = String(js.familiarity ?? fam.value ?? 0);
    const lem = document.getElementById('tt-lemma'); if(lem) lem.value = js.lemma || lem.value || '';
    const pos = document.getElementById('tt-pos'); if(pos) pos.value = (js.pos||'').toUpperCase();
    const ipa = document.getElementById('tt-ipa'); if(ipa) ipa.value = js.ipa || ipa.value || '';
    const a = document.getElementById('tt-audio-el');
    if(a){ if((js.audio_url||'').trim()){ a.src = js.audio_url; a.style.display='block'; } else { a.removeAttribute('src'); a.style.display='none'; } }
    const syn = document.getElementById('tt-syn'); if(syn) syn.value = Array.isArray(js.synonyms) ? js.synonyms.join(', ') : (syn.value||'');
    const col = document.getElementById('tt-col'); if(col) col.value = Array.isArray(js.collocations) ? js.collocations.join(', ') : (col.value||'');
    const gSel = document.getElementById('tt-gender'); if(gSel){
      const allowed = new Set(['masc','fem','neut','common','none']);
      const v = String(js.gender||'none').toLowerCase();
      gSel.value = allowed.has(v) ? v : 'none';
    }
  }catch(_){}
}

// Expose selected API for legacy inline code in index.html
if(typeof window !== 'undefined'){
  window.openTooltip = openTooltip;
  window.playOrGenAudio = playOrGenAudio;
  window.closeTooltip = closeTooltip;
  window.showWordDetailsPanel = showWordDetailsPanel;
  window.showInstructionPanel = showInstructionPanel;
  window.showLoadingPanel = showLoadingPanel;
}

// ===== Word Details Panel Functions =====

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Show instruction panel when no word is selected
export function showInstructionPanel(taskType, options = {}) {
  const panel = document.getElementById('word-details-panel');
  if (!panel) return;
  
  let instructionText = '';
  let icon = '';
  let hintText = 'Klicke auf ein Wort, um Details zu sehen';
  
  switch (taskType) {
    case 'mc':
      instructionText = window.t ? 
        window.t('instructions.choose_word', 'Wähle das fehlende Wort aus und setze es in die Lücke.') : 
        'Wähle das fehlende Wort aus und setze es in die Lücke.';
      icon = '🎯';
      hintText = 'Klicke auf ein Wort im Satz, um Details zu sehen';
      break;
      
    case 'sb':
      instructionText = window.t ? 
        window.t('instructions.build_sentence', 'Ziehe die Wörter per Drag & Drop in die richtige Reihenfolge. Klicke auf ein Wort für Details.') : 
        'Ziehe die Wörter per Drag & Drop in die richtige Reihenfolge. Klicke auf ein Wort für Details.';
      icon = '🧩';
      hintText = 'Ziehe Wörter per Drag & Drop. Klicke auf ein Wort für Details.';
      break;
      
    case 'translate':
      const nativeName = options.nativeName || 'Deutsch';
      instructionText = window.t ? 
        window.t('instructions.translate_sentence', 'Übersetze den folgenden Satz nach {nativeName}').replace('{nativeName}', nativeName) :
        `Übersetze den folgenden Satz nach ${escapeHtml(nativeName)}.`;
      icon = '🔄';
      hintText = 'Klicke auf ein Wort im Satz, um Übersetzung, Audio und Details zu sehen';
      break;
      
    default:
      instructionText = 'Bereite dich auf die Aufgabe vor...';
      icon = '📚';
      break;
  }
  
  panel.innerHTML = `
    <div class="word-details-instruction">
      <div class="word-details-instruction-icon">${icon}</div>
      <h3 class="word-details-instruction-title">${instructionText}</h3>
      <div class="word-details-instruction-hint">💡 ${hintText}</div>
    </div>
  `;
}

// Show loading state while fetching word details
export function showLoadingPanel(word) {
  const panel = document.getElementById('word-details-panel');
  if (!panel) return;
  
  panel.innerHTML = `
    <div class="word-details-loading">
      <div class="word-details-loading-spinner"></div>
      <div class="word-details-loading-text">Lade Details für "${escapeHtml(word)}"...</div>
    </div>
  `;
}

// Show word details in the panel
export async function showWordDetailsPanel(anchor, word) {
  const panel = document.getElementById('word-details-panel');
  if (!panel) return;
  
  // Show loading state
  showLoadingPanel(word);
  
  // Save current tooltip data before opening new one
  if (TT.word && TT.word !== word) {
    console.log('🔧 Opening new word details, saving previous data...');
    await ttSave();
  }
  
  TT.word = word;
  TT.anchor = anchor;
  
  // Extract and store context
  TT.wordContext = {
    word: word,
    language: window.RUN?.target || document.getElementById('target-lang')?.value || 'en',
    native_language: localStorage.getItem('siluma_native') || 'en',
    user_id: null
  };
  
  // Get user ID
  try {
    if (window.authManager && window.authManager.currentUser) {
      TT.wordContext.user_id = window.authManager.currentUser.id;
    } else {
      const sessionToken = localStorage.getItem('session_token');
      if (sessionToken) {
        try {
          const userInfo = JSON.parse(atob(sessionToken.split('.')[1]));
          TT.wordContext.user_id = userInfo.user_id || userInfo.id;
        } catch (e) {
          console.warn('⚠️ Could not decode session token:', e);
        }
      }
    }
  } catch (e) {
    console.warn('⚠️ Could not get user ID:', e);
  }
  
  // Load word data (use EXACT same logic as openTooltip)
  const w = String(word||'').trim();
  const lang = window.RUN?.target || TT.wordContext.language || 'en';
  const nat = window.RUN?.native || TT.wordContext.native_language || 'de';
  
  console.log('🔧 Word details panel opening for word:', w, 'language:', lang, 'native:', nat);
  
  // CRITICAL: Check cache FIRST before any API calls for instant display (same as openTooltip)
  let js1 = getCachedWordData(w, lang, nat);
  if (js1) {
    console.log('✅ Word details panel: Using cached word data for instant display:', w);
    renderWordDetailsPanel(panel, w, js1);
    // Continue to fetch fresh data in background (like openTooltip does)
  }
  
  // Check if this is a custom level and try to get word data from custom level context
  if (!js1) {
    if (window.RUN._customGroupId && window.RUN._customLevelNumber) {
      console.log('🔧 Word details panel for custom level word:', w);
      
      // For custom levels, try to get word data from the current item first
      const currentItem = window.RUN.items[window.RUN.idx || 0];
      if (currentItem && currentItem.words) {
        // Look for the word in the current item's words array
        const wordData = currentItem.words.find(word => word === w);
        if (wordData) {
          console.log('🔧 Found word in custom level item:', wordData);
          // Create a basic word object for the panel
          js1 = {
            word: w,
            language: lang,
            translation: '', // Will be filled by enrichment
            familiarity: 0,
            pos: '',
            ipa: '',
            example_native: '',
            synonyms: [],
            collocations: [],
            gender: 'none'
          };
        }
      }
    }
  }
  
  // If we don't have word data yet, try to fetch from global database (same as openTooltip)
  if (!js1) {
    console.log('⚠️ Word details panel: Word data not in cache, fetching for:', w);
    
    try {
      // NEW: Use batch API endpoint directly (more efficient than individual calls) - same as openTooltip
      const headers = { 'Content-Type': 'application/json' };
      const sessionToken = localStorage.getItem('session_token');
      if (sessionToken) {
        headers['Authorization'] = `Bearer ${sessionToken}`;
      }
      
      try {
        // Use batch endpoint - even for single word, it's more efficient (same as openTooltip)
        const batchResponse = await fetch('/api/words/batch', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            words: [w],
            language: lang,
            native_language: nat
          })
        });
        
        if (batchResponse.ok) {
          const batchData = await batchResponse.json();
          if (batchData.success && batchData.words && batchData.words[w]) {
            js1 = batchData.words[w];
            console.log('✅ Word details panel: Fetched word data via batch API:', w);
            
            // Cache the word data (sync to both caches)
            if (js1 && js1.word) {
              setCachedWordData(w, lang, nat, js1);
              // Also sync to WORDS_CACHE
              if (window.cachePut) {
                window.cachePut(js1);
              }
            }
            
            renderWordDetailsPanel(panel, w, js1);
            return;
          }
        }
      } catch (e) {
        console.log('⚠️ Batch API failed, falling back to single API:', e);
      }
      
      // Fallback to single word API if batch didn't work (same as openTooltip)
      // IMPORTANT: Include native_language in query parameter, not just header!
      const r1 = await fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}&native_language=${encodeURIComponent(nat)}`, {
        headers: { 'Authorization': sessionToken ? `Bearer ${sessionToken}` : '' }
      });
      
      if (r1.ok) {
        js1 = await r1.json();
        console.log('✅ Word details panel: Fetched word data via single API:', w);
        
        // Cache the word data (sync to both caches)
        if (js1 && js1.word) {
          setCachedWordData(w, lang, nat, js1);
          // Also sync to WORDS_CACHE
          if (window.cachePut) {
            window.cachePut(js1);
          }
        }
        
        renderWordDetailsPanel(panel, w, js1);
        return;
      } else {
        console.error('❌ Word API error:', r1.status, r1.statusText);
      }
    } catch (e) {
      console.error('❌ Error fetching word:', e);
    }
  } else {
    // We have cached data, but fetch fresh data in background (like openTooltip does)
    // This ensures we have the latest data
    setTimeout(async () => {
      try {
        const headers = { 'Content-Type': 'application/json' };
        const sessionToken = localStorage.getItem('session_token');
        if (sessionToken) {
          headers['Authorization'] = `Bearer ${sessionToken}`;
        }
        
        const r1 = await fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}&native_language=${encodeURIComponent(nat)}`, {
          headers: { 'Authorization': sessionToken ? `Bearer ${sessionToken}` : '' }
        });
        
        if (r1.ok) {
          const freshData = await r1.json();
          if (freshData && freshData.word) {
            setCachedWordData(w, lang, nat, freshData);
            if (window.cachePut) {
              window.cachePut(freshData);
            }
            // Update panel with fresh data
            renderWordDetailsPanel(panel, w, freshData);
          }
        }
      } catch (e) {
        console.log('⚠️ Background refresh failed:', e);
      }
    }, 100);
  }
  
  // Fallback: show error with more details
  panel.innerHTML = `
    <div class="word-details-instruction">
      <div class="word-details-instruction-icon">⚠️</div>
      <h3 class="word-details-instruction-title">Wort nicht gefunden</h3>
      <div class="word-details-instruction-text">Details für "${escapeHtml(w)}" konnten nicht geladen werden.</div>
      <div style="margin-top: 12px; font-size: 12px; color: var(--text-secondary);">
        Sprache: ${escapeHtml(lang)}<br>
        Wort: "${escapeHtml(w)}"
      </div>
    </div>
  `;
}

// Render word details in the panel
function renderWordDetailsPanel(panel, word, data) {
  const translation = data.translation || '';
  const ipa = data.ipa || '';
  const gender = data.gender || '';
  const example = data.example || '';
  const exampleNative = data.example_native || '';
  const synonyms = data.synonyms || '';
  const pos = data.pos || '';
  const familiarity = data.familiarity || 0;
  const userComment = data.user_comment || '';
  const audioUrl = data.audio_url || '';
  
  // Format gender display
  const genderMap = {
    'masc': 'Maskulin',
    'fem': 'Feminin', 
    'neut': 'Neutrum',
    'common': 'Utrum',
    'none': 'Kein Genus'
  };
  const genderDisplay = genderMap[gender] || gender || '–';
  
  // Format POS display
  const posMap = {
    'NOUN': 'Nomen',
    'VERB': 'Verb',
    'ADJ': 'Adjektiv',
    'ADV': 'Adverb',
    'PRON': 'Pronomen',
    'DET': 'Artikel/Det',
    'PREP': 'Präposition',
    'CONJ': 'Konjunktion',
    'NUM': 'Numerale',
    'PART': 'Partikel',
    'INTJ': 'Interjektion'
  };
  const posDisplay = posMap[pos] || pos || '–';
  
  // Format synonym list - handle both array and string formats
  let synonymList = '–';
  if (synonyms) {
    if (Array.isArray(synonyms)) {
      // Already an array - join with commas
      const syns = synonyms.map(s => String(s).trim()).filter(Boolean);
      synonymList = syns.length > 0 ? syns.join(', ') : '–';
    } else if (typeof synonyms === 'string') {
      // String format - split by comma
      const syns = synonyms.split(',').map(s => s.trim()).filter(Boolean);
      synonymList = syns.length > 0 ? syns.join(', ') : '–';
    } else {
      // Try to convert to string
      synonymList = String(synonyms).trim() || '–';
    }
  }
  
  // Always show all fields (like old tooltip), even if empty
  panel.innerHTML = `
    <div class="word-details-panel-header">
      <h3 class="word-details-panel-title">${escapeHtml(word)}</h3>
    </div>
    <div class="word-details-panel-content">
      <div class="word-details-field">
        <label class="word-details-field-label">Übersetzung</label>
        <div class="word-details-field-value">${escapeHtml(translation || '–')}</div>
      </div>
      
      <div class="word-details-field">
        <label class="word-details-field-label">Aussprache (IPA)</label>
        <div class="word-details-field-value">${escapeHtml(ipa || '–')}</div>
      </div>
      
      <div class="word-details-field">
        <label class="word-details-field-label">Genus</label>
        <div class="word-details-field-value">${escapeHtml(genderDisplay)}</div>
      </div>
      
      ${example ? `
        <div class="word-details-field">
          <label class="word-details-field-label">Beispielsatz</label>
          <div class="word-details-field-value">${escapeHtml(example)}</div>
        </div>
      ` : ''}
      
      <div class="word-details-field">
        <label class="word-details-field-label">Beispiel-Übersetzung</label>
        <div class="word-details-field-value">${escapeHtml(exampleNative || '–')}</div>
      </div>
      
      <div class="word-details-field">
        <label class="word-details-field-label">Synonyme</label>
        <div class="word-details-field-value">${escapeHtml(synonymList)}</div>
      </div>
      
      <div class="word-details-field">
        <label class="word-details-field-label">Wortart</label>
        <div class="word-details-field-value">${escapeHtml(posDisplay)}</div>
      </div>
      
      <div class="word-details-field">
        <label class="word-details-field-label">Bekanntheit</label>
        <select id="wd-fam" class="word-details-field-value" style="padding: 10px 12px;">
          <option value="0" ${familiarity === 0 ? 'selected' : ''}>Unbekannt</option>
          <option value="1" ${familiarity === 1 ? 'selected' : ''}>Gesehen</option>
          <option value="2" ${familiarity === 2 ? 'selected' : ''}>Lernen</option>
          <option value="3" ${familiarity === 3 ? 'selected' : ''}>Vertraut</option>
          <option value="4" ${familiarity === 4 ? 'selected' : ''}>Stark</option>
          <option value="5" ${familiarity === 5 ? 'selected' : ''}>Auswendig</option>
        </select>
      </div>
      
      ${userComment ? `
        <div class="word-details-field">
          <label class="word-details-field-label">Kommentar</label>
          <div class="word-details-field-value">${escapeHtml(userComment)}</div>
        </div>
      ` : ''}
      
      <div class="word-details-buttons">
        ${audioUrl ? `
          <button class="word-details-btn" onclick="playAudioFromPanel('${escapeHtml(audioUrl)}')">
            🔊 Audio
          </button>
        ` : ''}
        <button class="word-details-btn primary" onclick="saveWordDetailsFromPanel()">
          💾 Speichern
        </button>
      </div>
    </div>
  `;
  
  // Hook up familiarity change handler
  const famSelect = panel.querySelector('#wd-fam');
  if (famSelect) {
    famSelect.addEventListener('change', () => {
      TT.wordContext.familiarity = parseInt(famSelect.value);
    });
  }
}

// Play audio from panel
window.playAudioFromPanel = function(audioUrl) {
  if (audioUrl && audioUrl.trim()) {
    const audio = new Audio(audioUrl);
    audio.play().catch(e => console.error('Audio play failed:', e));
  }
};

// Save word details from panel
window.saveWordDetailsFromPanel = async function() {
  await ttSave();
};