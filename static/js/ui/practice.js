// practice.js — Flashcard practice flow
// Public API: initPractice(), startPracticeForLevel(level, runIdOverride), startPracticeForLatestLevel()
// Exposes legacy globals: window.startPracticeForLevel, window.startPracticeForLatestLevel

import { showTab } from './levels.js';

const $ = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));

// --- Module state ------------------------------------------------------------
let PR = { id:null, curr:'', remaining:0, seen:0, total:0, _next:null, _done:false, _queue:[], _qi:0 };

// Practice statistics
let practiceStats = {
  correct: 0,
  incorrect: 0,
  streak: 0,
  maxStreak: 0,
  startTime: null,
  ratings: [] // Track ratings for undo functionality
};

// Word data cache
class WordDataCache {
  constructor(maxSize = 200) {
    this.cache = new Map();
    this.maxSize = maxSize;
  }
  
  getKey(word, language) {
    return `${word.toLowerCase()}_${language}`;
  }
  
  get(word, language) {
    const key = this.getKey(word, language);
    const item = this.cache.get(key);
    if (!item) return null;
    // Check if expired (10 minutes)
    if (Date.now() - item.timestamp > 600000) {
      this.cache.delete(key);
      return null;
    }
    return item.data;
  }
  
  set(word, language, data) {
    const key = this.getKey(word, language);
    if (this.cache.size >= this.maxSize) {
      // Remove oldest entry
      const firstKey = this.cache.keys().next().value;
      this.cache.delete(firstKey);
    }
    this.cache.set(key, { data, timestamp: Date.now() });
  }
  
  clear() {
    this.cache.clear();
  }
}

const wordCache = new WordDataCache();
const audioCache = new Map(); // Cache audio URLs

// Track current audio operation to prevent race conditions
let currentAudioOperation = null;

const MAX_FAM = 5;
// Cached word data fetcher
async function getWordData(word, language) {
  const lang = language || ($('#target-lang')?.value || '');
  const cached = wordCache.get(word, lang);
  if (cached) return cached;
  
  try {
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    const r = await fetch(`/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(lang)}`, { headers });
    const js = await r.json();
    if (js && js.success !== false) {
      wordCache.set(word, lang, js);
      return js;
    }
  } catch(_) {}
  return null;
}

async function getFamiliarity(word, language){
  const wordData = await getWordData(word, language);
  if (wordData && wordData.familiarity !== undefined) {
    return parseInt(wordData.familiarity || 0, 10) || 0;
  }
  return 0;
}

function isValidForPractice(fam){ return Number(fam||0) < 5; }
async function isMemorized(word, lang){
  try{ const f = await getFamiliarity(word, lang); return !isValidForPractice(f); }
  catch(_){ return false; }
}
async function nextFromQueueSkippingMemorized(){
  const lang = $('#target-lang')?.value||'';
  while (PR._queue && PR._qi < PR._queue.length){
    const cand = String(PR._queue[PR._qi]||'').trim();
    PR._qi++;
    if(!cand) continue;
    if(!(await isMemorized(cand, lang))) return cand;
  }
  return '';
}

async function prebuildPracticeQueue(limit=10){
  // reset
  PR._queue = [];
  PR._qi = 0;

  // Optional lightweight peek endpoint (if backend supports it). Fail silently.
  try{
    const url = `/api/practice/peek?run_id=${encodeURIComponent(PR.id)}&limit=${encodeURIComponent(limit)}`;
    const r = await fetch(url, { method:'GET' });
    if(r.ok){
      const js = await r.json();
      const arr  = Array.isArray(js?.words) ? js.words : Array.isArray(js) ? js : [];
      const uniq = Array.from(new Set(arr.map(w=>String(w||'').trim()).filter(Boolean)));
      // kein Familiarity-Filter im Warm-up
      const out  = uniq.slice(0, limit);
      PR._queue  = out;
      PR._qi     = 0;
      return;
    }
  }catch(_){ /* ignore and fall back */ }

  // Fallback: no prebuilding – we rely on server-driven sequencing after user grades.
  // Keep queue empty so normal flow uses PR.curr from /api/practice/start and subsequent /grade.
  PR._queue = [];
  PR._qi = 0;
}

// --- UI bootstrap ------------------------------------------------------------
function ensurePracticeUI(){
  if(document.getElementById('practice-card')) return;
  if(!document.getElementById('pr-style')){
    const st=document.createElement('style'); st.id='pr-style'; st.textContent=`
      #pr-face{perspective:1200px}
      .pr-flip{position:relative;min-height:420px;border:1px solid var(--border);border-radius:14px;padding:18px;transform-style:preserve-3d;transition:transform .4s ease}
      .pr-flip.flipped{transform:rotateY(180deg)}
      .pr-front,.pr-back{position:absolute; inset:0; backface-visibility:hidden; -webkit-backface-visibility:hidden}
      .pr-front{transform:rotateY(0)}
      .pr-back{transform:rotateY(180deg)}
      .pr-front{display:flex}
      .pr-back{display:none}
      .pr-flip.flipped .pr-front{display:none}
      .pr-flip.flipped .pr-back{display:flex}
      .pr-front{flex-direction:column; align-items:center; justify-content:space-between; padding:14px; color:var(--fg); border-radius:14px}
      .pr-back{color:var(--fg); border-radius:14px}
      .pr-instr{font-size:13px; opacity:.9; text-align:center; color:var(--fg)}
      .pr-center{flex:1 1 auto; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:8px}
      .pr-word{font-size:30px; font-weight:800; letter-spacing:.2px; text-align:center; color:var(--fg)}
      .pr-ipa-row{display:flex;align-items:center;gap:10px;justify-content:center}
      .pr-ipa{color:var(--fg)}
      #practice-card .btn{border:1px solid var(--border)}
      #practice-card .btn:hover{background:var(--accent);border-color:var(--accent);color:white}
      .pr-back{flex-direction:column; align-items:center; justify-content:space-between; padding:14px}
      .pr-back-center{flex:1 1 auto; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; text-align:center}
      .pr-translation{font-size:24px; font-weight:800; color:var(--fg)}
      .pr-example{max-width:640px; color:var(--fg)}
      .pr-fam{font-size:14px; opacity:.9; color:var(--fg)}
      .pr-back-actions{display:flex; gap:10px; justify-content:center; padding-top:12px}
      #pr-audio-btn{cursor:pointer;border:1px solid var(--border);border-radius:24px;padding:8px 14px;display:inline-flex;align-items:center;gap:6px;font-size:18px;min-width:44px;justify-content:center}
      #pr-audio-btn[disabled]{opacity:.5;cursor:not-allowed}
      #pr-audio-btn.playing{animation:pulse 1.5s ease-in-out infinite}
      @keyframes pulse{0%,100%{opacity:1}50%{opacity:0.6}}
      .pr-stat-item{display:inline-flex;align-items:center;gap:4px;padding:4px 8px;background:var(--surface);border-radius:6px;font-weight:600}
      .pr-rating-btn{min-width:100px;padding:12px 20px;font-size:15px;font-weight:600;border-radius:10px;transition:all 0.2s;border:none;color:white;cursor:pointer}
      .pr-rating-btn:hover{transform:translateY(-2px);box-shadow:0 4px 12px rgba(0,0,0,0.2)}
      .pr-rating-btn:active{transform:translateY(0)}
      .pr-rating-btn:disabled{opacity:0.5;cursor:not-allowed;transform:none}
      #pr-bad{background:linear-gradient(135deg,#ef4444,#dc2626);box-shadow:0 2px 8px rgba(239,68,68,0.3)}
      #pr-okay{background:linear-gradient(135deg,#f59e0b,#d97706);box-shadow:0 2px 8px rgba(245,158,11,0.3)}
      #pr-good{background:linear-gradient(135deg,#10b981,#059669);box-shadow:0 2px 8px rgba(16,185,129,0.3)}
      .pr-loading{display:flex;align-items:center;justify-content:center;min-height:200px;color:var(--fg);opacity:0.7}
      .pr-loading::after{content:'';width:24px;height:24px;border:3px solid var(--surface);border-top-color:var(--accent);border-radius:50%;animation:spin 0.8s linear infinite}
      @keyframes spin{to{transform:rotate(360deg)}}
    `; document.head.appendChild(st);
    // Copy base .level-node background/shadow using a probe element to avoid state classes like .done
    (function applyLevelNodeTheme(){
      const probe = document.createElement('div');
      probe.className = 'level-node';
      probe.style.position = 'absolute';
      probe.style.left = '-9999px';
      probe.style.top = '0';
      document.body.appendChild(probe);
      const cs = getComputedStyle(probe);
      // const bg = cs.background; // Not used anymore
      const sh = cs.boxShadow;
      document.body.removeChild(probe);
      let theme = document.getElementById('pr-theme-style');
      if(!theme){ theme = document.createElement('style'); theme.id = 'pr-theme-style'; document.head.appendChild(theme); }
      // Use global card background (same as level overview blocks), keep level-node shadow
      theme.textContent = `.pr-front, .pr-back { background:var(--card); box-shadow:${sh}; }`;
    })();
  }
  const card=document.createElement('div');
  card.id='practice-card'; card.className='card'; card.style.display='none';
  card.innerHTML=`
    <div id="pr-progress" style="margin-bottom:16px">
      <div class="pr-progress-header" style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <div id="pr-progress-text" class="pill" style="font-weight:700"></div>
        <div id="pr-progress-percent" style="font-size:14px;opacity:0.8;color:var(--fg)"></div>
      </div>
      <div class="pr-progress-bar" style="width:100%;height:8px;background:var(--surface);border-radius:4px;overflow:hidden">
        <div id="pr-progress-bar-fill" style="height:100%;background:var(--accent);transition:width 0.3s ease;width:0%"></div>
      </div>
      <div id="pr-stats" style="display:flex;gap:12px;justify-content:center;margin-top:8px;font-size:12px;opacity:0.9"></div>
    </div>
    <div id="practice-inner" style="padding:12px 12px 14px 12px">
      <div id="pr-card" class="pr-flip">
        <div class="pr-front">
          <div class="pr-instr" data-i18n="practice.translate_in_head">Im Kopf übersetzen. Dann bewerten.</div>
          <div class="pr-center">
            <div id="pr-word" class="pr-word"></div>
            <div class="pr-ipa-row">
              <div id="pr-ipa" class="pr-ipa"></div>
              <button id="pr-audio-btn" class="btn" title="Audio abspielen" data-i18n-title="practice.audio_play">🔊</button>
              <audio id="pr-audio-el" preload="auto" style="display:none"></audio>
            </div>
          </div>
          <div class="pr-front-actions">
            <button id="pr-flip-front" class="btn" data-i18n="practice.flip_card">Drehen</button>
          </div>
        </div>
        <div class="pr-back">
          <div class="pr-back-center">
            <div id="pr-trans" class="pr-translation"></div>
            <div id="pr-ex" class="pr-sec pr-ex pr-example"></div>
            <div id="pr-fam" class="pr-fam"></div>
          </div>
          <div class="pr-back-actions">
            <button id="pr-bad"  class="pr-rating-btn" data-i18n="practice.not_good">Nicht gut</button>
            <button id="pr-okay" class="pr-rating-btn" data-i18n="practice.okay">Okay</button>
            <button id="pr-good" class="pr-rating-btn" data-i18n="practice.very_good">Sehr gut</button>
          </div>
        </div>
      </div>`;
  const anchor=document.getElementById('evaluation-card')||document.body;
  anchor.parentNode?anchor.parentNode.insertBefore(card,anchor):document.body.appendChild(card);
  bindPracticeControls();
}

function bindPracticeControls(){
  // Front: flip to back
  const flipF = document.getElementById('pr-flip-front');
  if(flipF) flipF.onclick = ()=> { showPractice(); };

  // Back: flip to front
  // Removed pr-back-btn handler (button no longer exists)

  // Back: rating buttons now grade and immediately advance
  const bad  = document.getElementById('pr-bad');
  const ok   = document.getElementById('pr-okay');
  const good = document.getElementById('pr-good');
  if(bad)  bad.onclick  = ()=> markAndNext('bad');
  if(ok)   ok.onclick   = ()=> markAndNext('ok');
  if(good) good.onclick = ()=> markAndNext('good');

  // Audio
  const pab = document.getElementById('pr-audio-btn');
  if(pab && !pab._bound){
    pab.addEventListener('click',(e)=>{ 
      e.stopPropagation(); 
      const lang=$('#target-lang')?.value||''; 
      const currentWord = PR.curr;
      if(currentWord) {
        pab.classList.add('playing');
        // For manual clicks, always play (don't check if word changed)
        ensurePracticeAudio(currentWord, lang, true).then(() => {
          const audioEl = document.getElementById('pr-audio-el');
          if(audioEl) {
            audioEl.addEventListener('ended', () => {
              pab.classList.remove('playing');
            }, { once: true });
            // Also handle errors
            audioEl.addEventListener('error', () => {
              pab.classList.remove('playing');
              console.warn('Audio playback error');
            }, { once: true });
          }
        }).catch(err => {
          console.error('Error playing audio:', err);
          pab.classList.remove('playing');
        });
      } else {
        console.warn('No current word to play audio for');
      }
    });
    pab._bound=true;
  }
}

// --- Networking + flow -------------------------------------------------------
async function ensurePracticeAudio(word, language, autoPlay = true){
  try{
    const el = document.getElementById('pr-audio-el');
    if(!word || !language || !el) {
      console.warn(`⚠️ ensurePracticeAudio: missing word (${word}), language (${language}), or element`);
      return;
    }
    
    // Normalize word for cache key
    const normalizedWord = String(word || '').trim().toLowerCase();
    const operationKey = `${normalizedWord}_${language}_${autoPlay}`;
    
    // If there's already an operation in progress for a different word, cancel it
    if(currentAudioOperation && currentAudioOperation.key !== operationKey) {
      console.log(`⚠️ Cancelling previous audio operation for "${currentAudioOperation.word}" in favor of "${word}"`);
      currentAudioOperation.cancelled = true;
      // Stop the previous audio
      try {
        el.pause();
        el.currentTime = 0;
      } catch(e) {
        // Ignore errors
      }
    }
    
    // Set current operation
    currentAudioOperation = {
      key: operationKey,
      word: normalizedWord,
      language: language,
      cancelled: false
    };
    
    // Stop any currently playing audio before loading new audio
    try {
      el.pause();
      el.currentTime = 0;
    } catch(e) {
      // Ignore errors when stopping audio
    }
    
    // Check cache first
    const cacheKey = `${normalizedWord}_${language}`;
    let audioUrl = audioCache.get(cacheKey);
    
    if (!audioUrl) {
      // Try to get from word data cache
      const wordData = await getWordData(word, language);
      
      // Check if operation was cancelled while fetching
      if(currentAudioOperation && currentAudioOperation.cancelled) {
        console.log(`⚠️ Audio operation cancelled for word "${word}" during word data fetch`);
        currentAudioOperation = null;
        return;
      }
      
      if(wordData && wordData.audio_url) {
        audioUrl = wordData.audio_url;
        // Convert S3 URL to proxy URL if needed (like the API does)
        if(audioUrl && typeof audioUrl === 'string' && audioUrl.includes('s3') && audioUrl.includes('amazonaws.com')) {
          // Extract path from S3 URL and convert to proxy URL
          try {
            const urlMatch = audioUrl.match(/\/media\/[^?]+/);
            if(urlMatch) {
              audioUrl = urlMatch[0]; // Use relative proxy URL
            }
          } catch(e) {
            // Keep original URL if conversion fails
          }
        }
        audioCache.set(cacheKey, audioUrl);
      } else {
        // Fetch from API
        const r = await fetch('/api/word/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({word, language}) });
        const js = await r.json();
        
        // Check if operation was cancelled while fetching
        if(currentAudioOperation && currentAudioOperation.cancelled) {
          console.log(`⚠️ Audio operation cancelled for word "${word}" during API fetch`);
          currentAudioOperation = null;
          return;
        }
        
        if(js && js.success && js.audio_url){ 
          audioUrl = js.audio_url;
          audioCache.set(cacheKey, audioUrl);
        }
      }
    } else {
      // If URL is from cache, ensure it's a proxy URL (not S3 URL)
      if(audioUrl && typeof audioUrl === 'string' && audioUrl.includes('s3') && audioUrl.includes('amazonaws.com')) {
        try {
          const urlMatch = audioUrl.match(/\/media\/[^?]+/);
          if(urlMatch) {
            audioUrl = urlMatch[0]; // Convert to relative proxy URL
            audioCache.set(cacheKey, audioUrl); // Update cache
          }
        } catch(e) {
          // Keep original URL if conversion fails
        }
      }
    }
    
    // Check if operation was cancelled before proceeding
    if(currentAudioOperation && currentAudioOperation.cancelled) {
      console.log(`⚠️ Audio operation cancelled for word "${word}" before loading`);
      currentAudioOperation = null;
      return;
    }
    
    if(audioUrl) {
      // Validate audio URL format
      if(typeof audioUrl !== 'string' || !audioUrl.trim()) {
        console.warn(`⚠️ Invalid audio URL format for word "${word}":`, audioUrl);
        currentAudioOperation = null;
        return;
      }
      
      // Verify word hasn't changed while fetching (race condition check)
      const currentWord = String(PR.curr || '').trim().toLowerCase();
      if(currentWord && currentWord !== normalizedWord) {
        // Word changed while we were fetching, don't play
        console.log(`⚠️ Audio skipped: word changed from "${normalizedWord}" to "${currentWord}"`);
        currentAudioOperation = null;
        return;
      }
      
      // Verify this operation is still current
      if(!currentAudioOperation || currentAudioOperation.key !== operationKey) {
        console.log(`⚠️ Audio operation superseded for word "${word}"`);
        return;
      }
      
      // Check if browser supports the audio format
      const audioFormats = ['audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/wav', 'audio/ogg'];
      const canPlay = audioFormats.some(format => {
        try {
          return el.canPlayType(format) !== '';
        } catch(e) {
          return false;
        }
      });
      
      if(!canPlay) {
        console.warn(`⚠️ Browser may not support audio format for word "${word}"`);
        // Continue anyway - browser might still play it
      }
      
      // Verify this operation is still current before setting source
      if(!currentAudioOperation || currentAudioOperation.key !== operationKey) {
        console.log(`⚠️ Audio operation superseded for word "${word}" before setting source`);
        return;
      }
      
      // Set audio source directly (like lesson.js does - browser handles encoding automatically)
      // For relative URLs (proxy URLs like /media/tts/...), use as-is
      // For absolute URLs, browser will handle Unicode encoding automatically
      el.src = audioUrl;
      
      // Store the expected URL for verification (browser may encode it)
      const expectedSrc = audioUrl;
      
      // Load the audio first
      el.load();
      
      // Wait for audio to be ready before playing (with timeout)
      try {
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            // Timeout is not fatal - audio might still play
            resolve();
          }, 3000); // 3 second timeout
          
          const onCanPlay = () => {
            clearTimeout(timeout);
            el.removeEventListener('canplay', onCanPlay);
            el.removeEventListener('error', onError);
            resolve();
          };
          
          const onError = (e) => {
            clearTimeout(timeout);
            el.removeEventListener('canplay', onCanPlay);
            el.removeEventListener('error', onError);
            // Don't reject - let play() handle the error
            resolve();
          };
          
          // If already loaded, resolve immediately
          if(el.readyState >= 2) { // HAVE_CURRENT_DATA or higher
            clearTimeout(timeout);
            resolve();
          } else {
            el.addEventListener('canplay', onCanPlay, { once: true });
            el.addEventListener('error', onError, { once: true });
          }
        });
      } catch(err) {
        console.warn(`⚠️ Audio load check failed for word "${word}":`, err);
        // Continue anyway - try to play
      }
      
      // Final check before playing
      if(!currentAudioOperation || currentAudioOperation.key !== operationKey) {
        console.log(`⚠️ Audio operation superseded for word "${word}" after loading`);
        currentAudioOperation = null;
        return;
      }
      
      if(autoPlay) {
        // Double-check word hasn't changed right before playing
        const finalCheckWord = String(PR.curr || '').trim().toLowerCase();
        if(finalCheckWord && finalCheckWord !== normalizedWord) {
          console.log(`⚠️ Audio skipped: word changed before play from "${normalizedWord}" to "${finalCheckWord}"`);
          currentAudioOperation = null;
          return;
        }
        
        // Verify audio element source matches what we set
        // Note: Browser converts relative URLs to absolute URLs and URL-encodes Unicode
        // So /media/tts/ka/მინდა__c0e676.mp3 becomes https://domain.com/media/tts/ka/%E1%83%9B%E1%83%98%E1%83%9C%E1%83%93%E1%83%90__c0e676.mp3
        const actualSrc = el.src || '';
        if(!actualSrc) {
          console.warn(`⚠️ Audio source is empty for word "${word}"`);
          currentAudioOperation = null;
          return;
        }
        
        // Extract path from actualSrc (which may be absolute) and compare with expectedSrc (which may be relative)
        let actualPath = actualSrc;
        let expectedPath = expectedSrc;
        
        try {
          // If actualSrc is absolute, extract just the path
          if(actualSrc.startsWith('http://') || actualSrc.startsWith('https://')) {
            const urlObj = new URL(actualSrc);
            actualPath = urlObj.pathname;
          }
          
          // Decode both paths to compare Unicode characters
          const decodedActual = decodeURIComponent(actualPath);
          const decodedExpected = decodeURIComponent(expectedPath);
          
          // Check if paths match (comparing decoded versions handles URL encoding)
          const pathsMatch = actualPath === expectedPath || 
                           decodedActual === decodedExpected ||
                           actualPath === decodedExpected ||
                           decodedActual === expectedPath;
          
          if(!pathsMatch) {
            console.warn(`⚠️ Audio source changed before play for word "${word}" (expected: ${expectedSrc}, got: ${el.src})`);
            currentAudioOperation = null;
            return;
          }
        } catch(e) {
          // If URL parsing/decoding fails, do a simple comparison
          const simpleMatch = actualSrc === expectedSrc || 
                             actualSrc.endsWith(expectedSrc) || 
                             expectedSrc.endsWith(actualSrc);
          if(!simpleMatch) {
            console.warn(`⚠️ Audio source changed before play for word "${word}" (expected: ${expectedSrc}, got: ${el.src})`);
            currentAudioOperation = null;
            return;
          }
        }
        
        try{ 
          const playPromise = el.play();
          if(playPromise !== undefined) {
            await playPromise;
            console.log(`✅ Audio playing for word: "${word}"`);
          }
        }catch(e){ 
          // AbortError is expected when audio is cancelled (e.g., new word loaded)
          // Don't log it as an error, just as info
          if(e.name === 'AbortError') {
            console.log(`ℹ️ Audio play aborted for word "${word}" (this is normal when switching words)`);
          } else if(e.name === 'NotAllowedError') {
            // Browser blocks autoplay - wait for user interaction
            console.log('🔇 Audio play blocked by browser policy, waiting for user interaction');
            
            // Set up one-time listener for user interaction
            const playAfterInteraction = () => {
              document.removeEventListener('pointerdown', playAfterInteraction, true);
              document.removeEventListener('click', playAfterInteraction, true);
              document.removeEventListener('keydown', playAfterInteraction, true);
              
              // Verify word hasn't changed and element is still valid
              if(PR.curr && PR.curr.trim().toLowerCase() === normalizedWord && el && el.src) {
                el.currentTime = 0;
                el.play().then(() => {
                  console.log(`✅ Audio playing for word "${word}" after user interaction`);
                }).catch(err => {
                  console.warn(`⚠️ Audio play failed after user interaction:`, err);
                });
              }
            };
            
            // Listen for any user interaction
            document.addEventListener('pointerdown', playAfterInteraction, true);
            document.addEventListener('click', playAfterInteraction, true);
            document.addEventListener('keydown', playAfterInteraction, true);
            
            // Also enable audio button click to trigger playback
            const audioBtn = document.getElementById('pr-audio-btn');
            if(audioBtn && !audioBtn.dataset.interactionListener) {
              audioBtn.dataset.interactionListener = 'true';
              const clickToPlay = () => {
                if(el && el.src) {
                  el.currentTime = 0;
                  el.play().catch(err => {
                    console.warn(`⚠️ Audio play failed on button click:`, err);
                  });
                }
              };
              audioBtn.addEventListener('click', clickToPlay, { once: true });
            }
          } else {
            console.warn(`⚠️ Audio play failed for word "${word}":`, e);
            if(e.name === 'NotSupportedError') {
              console.warn(`Audio format not supported for URL: ${audioUrl}`);
              // Try to clear the cache entry for this word to force a fresh fetch
              audioCache.delete(cacheKey);
            } else {
              console.warn(`Audio play error (${e.name}):`, e.message);
            }
          }
        }
      }
      
      // Clear operation on success
      if(currentAudioOperation && currentAudioOperation.key === operationKey) {
        currentAudioOperation = null;
      }
    } else {
      console.warn(`⚠️ No audio URL found for word: "${word}"`);
      currentAudioOperation = null;
    }
  }catch(e){
    console.error(`❌ Error in ensurePracticeAudio for word "${word}":`, e);
    currentAudioOperation = null;
  }
}

function setPracticeProgress(seen, remaining, total){
  const textEl = document.getElementById('pr-progress-text');
  const barEl = document.getElementById('pr-progress-bar-fill');
  const percentEl = document.getElementById('pr-progress-percent');
  const statsEl = document.getElementById('pr-stats');
  
  const s = Number(seen||0), r = Number(remaining||0), t = Number(total||0);
  const actualTotal = t > 0 ? t : s + r;
  
  // For queue-based practice, 'seen' already includes current word (PR._qi + 1)
  // For server-based practice, 'seen' is the count of completed words, so add 1 for current
  const isQueueBased = PR._queue && PR._queue.length > 0;
  const current = isQueueBased ? s : (PR.curr ? s + 1 : s);
  const percent = actualTotal > 0 ? Math.round((current / actualTotal) * 100) : 0;
  
  if(textEl) textEl.textContent = `${current} / ${actualTotal}`;
  if(barEl) barEl.style.width = `${percent}%`;
  if(percentEl) percentEl.textContent = `(${percent}%)`;
  
  // Update statistics
  if(statsEl && practiceStats.startTime) {
    const accuracy = (practiceStats.correct + practiceStats.incorrect) > 0 
      ? Math.round((practiceStats.correct / (practiceStats.correct + practiceStats.incorrect)) * 100)
      : 0;
    statsEl.innerHTML = `
      <span class="pr-stat-item">✓ ${practiceStats.correct}</span>
      <span class="pr-stat-item">✗ ${practiceStats.incorrect}</span>
      <span class="pr-stat-item">🔥 ${practiceStats.streak}</span>
      <span class="pr-stat-item">${accuracy}%</span>
    `;
  }
}

function renderPracticeCard(){
  const w = PR.curr || '';
  
  // Show loading state
  const cardEl = document.getElementById('pr-card');
  if(cardEl && !cardEl.classList.contains('pr-loaded')) {
    cardEl.classList.add('pr-loading');
  }
  
  if(PR._queue && PR._queue.length){
    const s = PR._qi + 1;
    const r = Math.max(0, PR._queue.length - s);
    setPracticeProgress(s, r, PR.total || PR._queue.length);
  } else {
    setPracticeProgress(PR.seen||0, PR.remaining||0, PR.total);
  }
  
  const frontEl = $('#pr-word'); 
  if(frontEl) frontEl.textContent = w;
  $('#pr-ipa') && ($('#pr-ipa').textContent = '');
  $('#pr-card')?.classList.remove('flipped');
  
  const lang = PR.language || $('#target-lang')?.value || '';
  
  // Use cached word data
  if(w && lang) {
    // Store current word to verify audio matches
    const currentWordForAudio = w;
    
    getWordData(w, lang).then(js => {
      // Verify word hasn't changed while loading
      if(PR.curr !== currentWordForAudio) return;
      
      if(js) {
        const ipaEl = document.getElementById('pr-ipa');
        if(ipaEl) ipaEl.textContent = js.ipa || '';
      }
      if(cardEl) cardEl.classList.remove('pr-loading');
      if(cardEl) cardEl.classList.add('pr-loaded');
    });
    
    // Play audio for current word only (only if audio element exists)
    const audioEl = document.getElementById('pr-audio-el');
    if(audioEl) {
      ensurePracticeAudio(w, lang, true);
    } else {
      console.warn('⚠️ Audio element not found, skipping audio playback');
    }
  } else {
    // If word or language is missing, still try to remove loading state
    if(cardEl) {
      cardEl.classList.remove('pr-loading');
      cardEl.classList.add('pr-loaded');
    }
    if(!w) {
      console.warn('⚠️ renderPracticeCard: No current word set (PR.curr is empty)');
    }
    if(!lang) {
      console.warn('⚠️ renderPracticeCard: No language set (PR.language and target-lang are empty)');
    }
  }
  
  const btn = document.getElementById('pr-audio-btn'); 
  if(btn) {
    btn.disabled = false;
    btn.classList.remove('playing');
  }
}

async function advanceToNextWord(){
  let next = await nextFromQueueSkippingMemorized();
  if(!next){
    const cand = String(PR._next||'').trim();
    if(cand){
      const lang = $('#target-lang')?.value||'';
      if(!(await isMemorized(cand, lang))) next = cand;
    }
  }
  if(next){ PR.curr = next; PR._next = null; renderPracticeCard(); }
  else { try{ showTab('evaluation'); }catch(_){} }
}

async function showPractice(){
  const w = PR.curr; if(!w) return;
  const lang = PR.language || $('#target-lang').value || 'en';
  
  // Use cached word data
  const js = await getWordData(w, lang) || {};
  const trans = js.translation||'';
  const ex = js.example||''; const exn = js.example_native||'';
  
  // Get user-specific familiarity
  const fam = await getFamiliarity(w, lang);
  
  const host = document.getElementById('pr-ex');
  if(host){
    host.innerHTML = '';
    if(ex || exn){
      host.insertAdjacentHTML('beforeend', `<div class="pr-val">${(exn||ex)}</div>`);
    }
  }
  $('#pr-trans') && ($('#pr-trans').textContent = trans);
  $('#pr-fam') && ($('#pr-fam').textContent = famLabel(fam));
  $('#pr-card')?.classList.add('flipped');
  const aBtn = document.getElementById('pr-audio-btn'); 
  if(aBtn) {
    aBtn.disabled = false;
    aBtn.classList.remove('playing');
  }
}

function famLabel(n){ const L=['Unbekannt','Gesehen','Lernen','Vertraut','Stark','Auswendig']; n = parseInt(n||0,10); if(!isFinite(n)||n<0) n=0; if(n>5) n=5; return L[n]; }

async function applyPracticeStartResponse(js, fallbackLevel = 1, expectedTotal = 0, fallbackWords = []){
  const targetLang = $('#target-lang')?.value || 'en';
  PR.id = js.run_id;
  const resolvedLevel = (js.level !== undefined && js.level !== null) ? js.level : fallbackLevel;
  PR.level = resolvedLevel;
  PR.language = js.language || targetLang;
  
  // If we have a custom word queue, use it instead of server response
  const isCustomWordList = (resolvedLevel === 0 || resolvedLevel === null || resolvedLevel === undefined) && PR._queue && PR._queue.length > 0;
  
  if(isCustomWordList){
    // For custom word lists, use the queue we already set up
    PR.curr = PR._queue[PR._qi] || PR._queue[0] || '';
    PR.total = PR._queue.length;
    PR.remaining = Math.max(0, PR._queue.length - 1);
    PR.seen = 0;
  } else {
    // For server-driven practice, use server response
    PR.curr = js.word || (fallbackWords[0] || '');
    PR.remaining = Number(js.remaining ?? Math.max(0, (expectedTotal || fallbackWords.length) - 1));
    PR.seen = Number(js.seen || 0);
    const totalGuess = expectedTotal || fallbackWords.length;
    PR.total = Number(js.total ?? js.remaining ?? totalGuess);

    try{
      await prebuildPracticeQueue(10);
      if(PR._queue.length > 0){
        const pick = await nextFromQueueSkippingMemorized();
        if(pick) PR.curr = pick;
      }
      const lang = $('#target-lang')?.value||'';
      if(PR.curr && await isMemorized(PR.curr, lang)){
        const alt = await nextFromQueueSkippingMemorized();
        if(alt) PR.curr = alt;
      }
    }catch(_){ }
  }

  try{
    const levelNumber = Number(resolvedLevel);
    if(Number.isFinite(levelNumber)){
      window._lt_level = levelNumber;
    }else{
      window._lt_level = window._lt_level || fallbackLevel || 1;
    }
    window._last_run_id = Number(PR.id) || window._last_run_id || null;
  }catch(_){ }

  setPracticeProgress(PR.seen, PR.remaining, PR.total);
  showTab('practice');
  bindPracticeControls();
  renderPracticeCard();
}

export async function startPracticeForLevel(level, runIdOverride){
  ensurePracticeUI();
  // reset state
  const targetLang = $('#target-lang')?.value || 'en';
  PR = {id:null, curr:'', remaining:0, seen:0, total:0, _next:null, _done:false, language: targetLang};

  // resolve run_id precedence: explicit override → current RUN → localStorage → summary API
  let run_id = runIdOverride || null;
  const RUN = window.RUN || {};
  if((RUN.level||0) === Number(level) && RUN.id){ run_id = RUN.id; }
  if(!run_id){ try{ const v = localStorage.getItem('siluma_last_run_'+String(level)); if(v) run_id = parseInt(v,10)||null; }catch(_){} }
  if(!run_id){
    try{
      const s = await fetch('/api/levels/summary'); const js = await s.json();
      if(js && js.success && Array.isArray(js.levels)){
        const rows = js.levels.filter(x => Number(x.level)===Number(level) && Number(x.run_id||0) > 0);
        if(rows.length){ run_id = rows.sort((a,b)=>Number(b.run_id)-Number(a.run_id))[0].run_id; }
      }
    }catch(_){ run_id = null; }
  }

  // start practice
  const targetLang = $('#target-lang')?.value || 'en';
  
  // Get auth headers if user is logged in
  const headers = { 'Content-Type': 'application/json' };
  if (window.authManager && window.authManager.isAuthenticated()) {
    Object.assign(headers, window.authManager.getAuthHeaders());
  }
  
  // Add native language header for unauthenticated users
  const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
  headers['X-Native-Language'] = nativeLanguage;
  
  const r = await fetch('/api/practice/start', { method:'POST', headers, body: JSON.stringify({level, run_id, exclude_max:true, language: targetLang}) });
  let js = null; try{ js = await r.json(); }catch(_){ js = null; }
  if(!r.ok || !js || js.success === false){ const msg = (js && (js.error||js.message)) || ('HTTP '+r.status); alert('Practice-Start fehlgeschlagen: '+msg); return; }

  // assign state
  await applyPracticeStartResponse(js, level, js.total || js.remaining || 0);
}

// Guard to prevent multiple simultaneous practice starts
let isStartingPractice = false;

export async function startPracticeWithWordList(wordList, label = 'custom'){
  // Prevent multiple simultaneous calls
  if(isStartingPractice){
    console.log('⚠️ Practice already starting, ignoring duplicate call');
    return;
  }
  
  isStartingPractice = true;
  try {
    // Reset statistics
    practiceStats = {
      correct: 0,
      incorrect: 0,
      streak: 0,
      maxStreak: 0,
      startTime: Date.now(),
      ratings: []
    };
    
    ensurePracticeUI();
    const targetLang = $('#target-lang')?.value || 'en';
    PR = {id:null, curr:'', remaining:0, seen:0, total:0, _next:null, _done:false, _queue:[], _qi:0, language: targetLang};

    const normalizedWords = [];
    const seen = new Set();
    (Array.isArray(wordList) ? wordList : []).forEach((word) => {
      const str = String(word || '').trim();
      if(!str) return;
      const key = str.toLowerCase();
      if(seen.has(key)) return;
      seen.add(key);
      normalizedWords.push(str);
    });

    if(!normalizedWords.length){
      const msg = window.t ? window.t('levels.no_remaining_words', 'Keine übrig gebliebenen Wörter (max. Stufe erreicht)') : 'Keine übrig gebliebenen Wörter (max. Stufe erreicht)';
      alert(msg);
      return;
    }

    // Store word list in queue for custom words practice
    PR._queue = [...normalizedWords];
    PR._qi = 0;
    PR.curr = normalizedWords[0] || ''; // Set first word immediately for faster start
    PR.total = normalizedWords.length;
    PR.level = 0; // Mark as custom word list
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }

    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;

    const payload = {
      level: 0,
      language: targetLang,
      custom_words: normalizedWords,
      label,
      exclude_max: true
    };

    // Start practice session on server (for tracking), but don't wait for it to show first word
    const response = fetch('/api/practice/start', {
      method: 'POST',
      headers,
      body: JSON.stringify(payload)
    }).then(async (r) => {
      let data = null;
      try{
        data = await r.json();
      }catch(_){ data = null; }

      if(r.ok && data && data.success !== false){
        // Update PR.id from server response
        if(data.run_id) PR.id = data.run_id;
      }
      // Don't block UI on API response - we already have the word list
    }).catch((err) => {
      console.warn('Practice start API call failed (non-blocking):', err);
    });

    // Show practice immediately with first word, don't wait for API
    await applyPracticeStartResponse({run_id: null, level: 0, language: targetLang, total: normalizedWords.length}, 0, normalizedWords.length, normalizedWords);
    
    // Wait for API call to complete in background (but don't block)
    await response;
  } finally {
    isStartingPractice = false;
  }
}

export async function startPracticeForLatestLevel(){
  try{
    // Get auth headers if user is logged in
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    const r = await fetch('/api/levels/summary', { headers }); const js = await r.json();
    if(!(js && js.success && Array.isArray(js.levels) && js.levels.length)){ alert('Kein abgeschlossenes Level gefunden'); return; }
    const done = js.levels.filter(x=>typeof x.score==='number');
    if(!done.length){ alert('Kein abgeschlossenes Level gefunden'); return; }
    const lvl = Math.max(...done.map(x=>Number(x.level)||1));
    startPracticeForLevel(lvl);
  }catch(_){ alert('Practice-Start fehlgeschlagen'); }
}

async function gradeAndFlip(mark){
  // Disable rating buttons during grading
  const ratingBtns = ['pr-bad', 'pr-okay', 'pr-good'].map(id => document.getElementById(id));
  ratingBtns.forEach(btn => { if(btn) btn.disabled = true; });
  
  try{
    // Update statistics
    const prevWord = PR.curr;
    const prevRating = practiceStats.ratings.length > 0 ? practiceStats.ratings[practiceStats.ratings.length - 1] : null;
    practiceStats.ratings.push({ word: prevWord, mark, timestamp: Date.now() });
    
    if(mark === 'good') {
      practiceStats.correct++;
      practiceStats.streak++;
      if(practiceStats.streak > practiceStats.maxStreak) {
        practiceStats.maxStreak = practiceStats.streak;
      }
    } else {
      practiceStats.incorrect++;
      practiceStats.streak = 0;
    }
    
    // Get auth headers if user is logged in
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    const levelValueRaw = (PR.level !== undefined && PR.level !== null) ? PR.level : window._lt_level;
    const levelValue = (levelValueRaw !== undefined && levelValueRaw !== null) ? levelValueRaw : 1;
    const resp = await fetch('/api/practice/grade', { method:'POST', headers, body: JSON.stringify({ run_id: PR.id, level: levelValue, language: PR.language || $('#target-lang')?.value || 'en', word: PR.curr, mark }) });
    const js = await resp.json();
    if(!PR._queue || !PR._queue.length){
      const nxt = js && (js.next || js.word || js.next_word);
      if(nxt) PR._next = nxt;
    }
    if(typeof js?.seen !== 'undefined') PR.seen = Number(js.seen)||0;
    if(typeof js?.remaining !== 'undefined') PR.remaining = Number(js.remaining)||0;
    setPracticeProgress(PR.seen, PR.remaining, PR.total);
    
    try{ if(typeof window.refreshMaxFam==='function') window.refreshMaxFam(); }catch(_){}
    
    // Check if practice is done: either js.done is true, or remaining is 0 and no queue/next word
    const isDone = js && (js.done || (js.remaining !== undefined && js.remaining <= 0 && !PR._queue?.length && !PR._next));
    if(isDone){ 
      finishPractice(); 
      return; 
    }
  }catch(_){ }
  finally {
    // Re-enable buttons
    ratingBtns.forEach(btn => { if(btn) btn.disabled = false; });
  }
  
  // Only show practice (flip card) if practice is not done
  if(!PR._done){
    await showPractice();
  }
}

// Undo last rating
function undoLastRating() {
  if(practiceStats.ratings.length === 0) return false;
  
  const lastRating = practiceStats.ratings.pop();
  if(lastRating.mark === 'good') {
    practiceStats.correct = Math.max(0, practiceStats.correct - 1);
    practiceStats.streak = Math.max(0, practiceStats.streak - 1);
  } else {
    practiceStats.incorrect = Math.max(0, practiceStats.incorrect - 1);
    // Streak was already reset, can't restore it accurately
  }
  
  // Go back to previous word
  if(PR._queue && PR._queue.length && PR._qi > 0) {
    PR._qi = PR._qi - 1;
    PR.curr = PR._queue[PR._qi];
    renderPracticeCard();
    setPracticeProgress(PR._qi + 1, PR._queue.length - (PR._qi + 1), PR.total || PR._queue.length);
    return true;
  }
  return false;
}

// Helper: grade and advance
async function markAndNext(mark){
  await gradeAndFlip(mark);
  // Only advance if practice is not done
  if(!PR._done){
    await gotoNextPractice();
  }
}

// Preload next words in background (data only, no audio playback)
async function preloadNextWords(count = 3) {
  if(!PR._queue || !PR._queue.length) return;
  const lang = $('#target-lang')?.value || '';
  const startIdx = PR._qi + 1;
  const wordsToPreload = PR._queue.slice(startIdx, startIdx + count);
  
  // Preload word data only (audio URLs will be cached when needed)
  // Don't call ensurePracticeAudio as it plays audio - we just want to cache the URLs
  const preloadPromises = wordsToPreload.map(async word => {
    // Preload word data (which includes audio_url)
    const wordData = await getWordData(word, lang);
    // Preload audio URL into cache without playing
    if(wordData && wordData.audio_url) {
      const cacheKey = `${word.toLowerCase()}_${lang}`;
      audioCache.set(cacheKey, wordData.audio_url);
    }
  });
  
  // Don't await - let it run in background
  Promise.all(preloadPromises).catch(() => {});
}

async function gotoNextPractice(){
  if(PR && PR._done){ finishPractice(); return; }

  if(PR._queue && PR._queue.length){
    // Check if this is a custom word list (level 0) - don't call prebuildPracticeQueue
    const isCustomWordList = PR.level === 0 || PR.level === null || PR.level === undefined;
    
    PR._qi = PR._qi + 1; // Increment to next index (0-based)
    if(PR._qi >= PR._queue.length){
      // Queue exhausted
      if(isCustomWordList){
        // For custom word lists, finish when queue is done
        finishPractice(); 
        return;
      }
      // For server-driven practice, try to rebuild queue
      await prebuildPracticeQueue(10);
      if(!PR._queue.length){ finishPractice(); return; }
      PR._qi = 0; // Reset to start of new queue
    }
    PR.curr = PR._queue[PR._qi]; // Use 0-based indexing
    renderPracticeCard();
    // Audio is already called in renderPracticeCard(), no need to call again
    
    // Preload next words in background
    preloadNextWords(3);
    return;
  }

  // Fallback: alte Server-Logik
  if(PR && PR._next){
    PR.curr = PR._next; PR._next=null;
    renderPracticeCard();
    // Audio is already called in renderPracticeCard(), no need to call again
    return;
  }
  try{
    // Get auth headers if user is logged in
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    const levelValueRaw = (PR.level !== undefined && PR.level !== null) ? PR.level : window._lt_level;
    const levelValue = (levelValueRaw !== undefined && levelValueRaw !== null) ? levelValueRaw : 1;
    const resp = await fetch('/api/practice/grade', { method:'POST', headers, body: JSON.stringify({ run_id: PR.id, level: levelValue, language: PR.language || $('#target-lang')?.value || 'en', word: PR.curr, mark: 'peek' }) });
    const js = await resp.json();
    const nxt = js && (js.next || js.word || js.next_word);
    if(nxt){
      let candidate = nxt;
      const lang=$('#target-lang')?.value||'';
      let attempts = 0;
      while(candidate && (await getFamiliarity(candidate, lang)) >= MAX_FAM && attempts < 200){
        // Get auth headers for peek call
        const peekHeaders = { 'Content-Type': 'application/json' };
        if (window.authManager && window.authManager.isAuthenticated()) {
          Object.assign(peekHeaders, window.authManager.getAuthHeaders());
        }
        const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
        peekHeaders['X-Native-Language'] = nativeLanguage;
        
        const r2 = await fetch('/api/practice/grade', { method:'POST', headers: peekHeaders, body: JSON.stringify({ run_id: PR.id, level: levelValue, language: PR.language || $('#target-lang')?.value || 'en', word: candidate, mark: 'peek' }) });
        const j2 = await r2.json();
        if(typeof j2?.remaining === 'number' && j2.remaining <= 0){ candidate=''; break; }
        candidate = j2 && (j2.next || j2.word || j2.next_word);
        attempts++;
      }
      if(!candidate){ finishPractice(); return; }
      PR.curr = candidate;
      if(typeof js?.seen === 'number') PR.seen = js.seen;
      if(typeof js?.remaining === 'number') PR.remaining = js.remaining;
      setPracticeProgress(PR.seen||0, PR.remaining||0, PR.total);
      renderPracticeCard();
      // Audio is already called in renderPracticeCard(), no need to call again
      return;
    }
    finishPractice(); return;
  }catch(_){ }
  finishPractice();
}

function togglePractice(){ const card = document.getElementById('pr-card'); if(!card) return; if(card.classList.contains('flipped')){ renderPracticeCard(); const btn=document.getElementById('pr-show'); if(btn) btn.textContent=window.t ? window.t('practice.show_button', 'Anzeigen') : 'Anzeigen'; } else { showPractice().then(()=>{ const btn=document.getElementById('pr-show'); if(btn) btn.textContent=window.t ? window.t('practice.back_button', 'Zurück') : 'Zurück'; }); } }

export function initPractice(){
  // Hotkeys: Space=zeigen, 1/2/3 bewerten und weiter, Backspace/Left Arrow=undo
  document.addEventListener('keydown',(e)=>{
    const pc = document.getElementById('practice-card');
    if(pc){ pc.classList.add('card'); }
    if(pc && pc.style.display===''){
      if(e.code==='Space'){ e.preventDefault(); togglePractice(); }
      if(e.key==='1'){ markAndNext('bad'); }
      if(e.key==='2'){ markAndNext('ok'); }
      if(e.key==='3'){ markAndNext('good'); }
      if((e.key==='Backspace' || e.key==='ArrowLeft') && !e.target.matches('input,textarea')){ 
        e.preventDefault(); 
        undoLastRating(); 
      }
    }
  });
}

function finishPractice(){
  PR._done = true;
  // Clear any pending audio operation
  currentAudioOperation = null;
  try{ const a = document.getElementById('pr-audio-el'); if(a){ a.pause?.(); a.removeAttribute('src'); } }catch(_){}
  const btn = document.getElementById('pr-audio-btn'); 
  if(btn) {
    btn.disabled = true;
    btn.classList.remove('playing');
  }
  
  // Calculate final statistics
  const totalWords = practiceStats.correct + practiceStats.incorrect;
  const accuracy = totalWords > 0 ? Math.round((practiceStats.correct / totalWords) * 100) : 0;
  const timeSpent = practiceStats.startTime ? Math.round((Date.now() - practiceStats.startTime) / 1000) : 0;
  
  // Show completion summary (optional - can be enhanced later)
  if(totalWords > 0) {
    console.log(`Practice completed: ${totalWords} words, ${accuracy}% accuracy, ${practiceStats.maxStreak} max streak, ${timeSpent}s`);
  }
  
  // Collect unique words that were practiced
  const practicedWords = new Set();
  if(practiceStats.ratings && Array.isArray(practiceStats.ratings)) {
    practiceStats.ratings.forEach(rating => {
      if(rating.word) {
        practicedWords.add(rating.word);
      }
    });
  }
  
  // Store practice statistics for evaluation display
  window._practiceEvalStats = {
    totalWords: totalWords,
    correct: practiceStats.correct,
    incorrect: practiceStats.incorrect,
    accuracy: accuracy,
    maxStreak: practiceStats.maxStreak,
    timeSpent: timeSpent,
    timestamp: Date.now(),
    practicedWords: Array.from(practicedWords), // Store list of words for familiarity calculation
    language: PR.language || $('#target-lang')?.value || 'en'
  };
  
  // Refresh level states after practice completion
  try{
    if (window.refreshLevelStates) {
      window.refreshLevelStates();
    }
  }catch(_){}
  
  // Clear caches (optional - or keep for better performance)
  // wordCache.clear();
  // audioCache.clear();
  
  // Invalidate words cache to ensure fresh data is loaded
  try{
    if (window.invalidateWordsCache) {
      const targetLang = document.getElementById('target-lang')?.value || 'en';
      window.invalidateWordsCache(targetLang);
    }
  }catch(_){}
  
  try{ window._eval_context = 'practice'; }catch(_){}
  try{ showTab('evaluation'); }catch(_){}
  
  // Trigger evaluation population after a short delay to ensure DOM is ready
  setTimeout(() => {
    try { 
      if (typeof window.populateEvaluationScore === 'function') {
        window.populateEvaluationScore(); 
      }
      if (typeof window.populateEvaluationStatus === 'function') {
        window.populateEvaluationStatus(); 
      }
    } catch(e) {
      console.log('Error populating evaluation:', e);
    }
  }, 100);
}

// Legacy globals
if(typeof window !== 'undefined'){
  window.startPracticeForLevel = startPracticeForLevel;
  window.startPracticeForLatestLevel = startPracticeForLatestLevel;
  window.startPracticeWithWordList = startPracticeWithWordList;
  window.getFamiliarity = getFamiliarity; // Export for evaluation.js
}
