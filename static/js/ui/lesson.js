// Lesson module: Start/Render/Submit eines Levels
// Public API: initLesson(), startLevelWithTopic(level, topic)
// Legacy: window.startLevelWithTopic / window.startLevel / window.abortLevel

import { openTooltip, playOrGenAudio } from './tooltip.js';
import { showTab, showLoader, hideLoader } from './levels.js';
import { populateEvaluationScore, populateEvaluationStatus } from './evaluation.js';

const $ = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));

// ---- Word data client cache ----
const WORDS_CACHE = new Map(); // key: lang + '|' + word
const ck = (w, lang)=> `${lang}|${String(w||'').trim()}`;
function cachePut(row){
  if(!row) return;
  const key = ck(row.word, row.language || RUN.target || 'en');
  WORDS_CACHE.set(key, row);
}
function cacheGet(word, lang){ return WORDS_CACHE.get(ck(word, lang||RUN.target||'en')); }

function normalizeScoreForLesson(raw) {
  if (raw === null || raw === undefined) return 0;
  let num = Number(raw);
  if (!Number.isFinite(num)) return 0;
  if (num > 1.0001) num = num / 100;
  if (num < 0) num = 0;
  if (num > 1 && num < 1.0001) num = 1;
  if (num > 1) num = 1;
  return num;
}

function normalizeCustomProgressForLesson(progress) {
  if (!progress) return null;
  const counts = {0:0,1:0,2:0,3:0,4:0,5:0};
  const source = progress.counts || progress.fam_counts || progress.famCounts || {};
  Object.keys(counts).forEach(key => {
    const numKey = Number(key);
    const rawVal = source[numKey] ?? source[String(numKey)] ?? 0;
    counts[numKey] = Number(rawVal) || 0;
  });
  const totalWords = Number(progress.total_words !== undefined ? progress.total_words : Object.values(counts).reduce((sum, val) => sum + Number(val || 0), 0)) || 0;
  const completedWords = Number(counts[5] || 0);
  const scoreRaw = progress.score_raw !== undefined ? progress.score_raw : progress.score;
  const scoreRatio = normalizeScoreForLesson(scoreRaw);
  const scorePercent = Math.round(scoreRatio * 100);
  const progressPercent = totalWords > 0 ? Math.round((completedWords / totalWords) * 100) : 0;
  return {
    fam_counts: counts,
    total_words: totalWords,
    completed_words: completedWords,
    progress_percent: progressPercent,
    score: scoreRatio,
    score_percent: scorePercent,
    status: progress.status || 'completed',
    completed_at: progress.completed_at || null
  };
}

// ---- Enhanced Instruction Display ----
function displayEnhancedInstruction(taskType, resultBox, options = {}) {
  if (!resultBox) return;
  
  // Remove old instruction classes
  resultBox.classList.remove('hint', 'instruction-panel', 'mc-task', 'sb-task', 'translate-task');
  
  // Get instruction text based on task type
  let instructionText = '';
  let icon = '';
  let highlightText = '';
  
  switch (taskType) {
    case 'mc':
      instructionText = window.t ? 
        window.t('instructions.choose_word', 'Wähle das fehlende Wort aus und setze es in die Lücke.') : 
        'Wähle das fehlende Wort aus und setze es in die Lücke.';
      icon = '🎯';
      highlightText = 'Wort auswählen';
      break;
      
    case 'sb':
      instructionText = window.t ? 
        window.t('instructions.build_sentence', 'Baue den Satz aus den Wörtern in der richtigen Reihenfolge.') : 
        'Baue den Satz aus den Wörtern in der richtigen Reihenfolge.';
      icon = '🧩';
      highlightText = 'Satz bauen';
      break;
      
    case 'translate':
      const nativeName = options.nativeName || 'Deutsch';
      instructionText = window.t ? 
        window.t('instructions.translate_sentence', 'Übersetze den folgenden Satz nach {nativeName}').replace('{nativeName}', nativeName) :
        `Übersetze den folgenden Satz nach <span class="instruction-highlight">${escapeHtml(nativeName)}</span>. Tipp: Klicke einzelne <span class="instruction-highlight">Wörter</span> für Tooltip, Details und <span class="instruction-highlight">Audio</span>.`;
      icon = '🔄';
      highlightText = 'Übersetzen';
      break;
      
    default:
      return; // Unknown task type, don't display anything
  }
  
  // Create enhanced instruction HTML
  const instructionHTML = `
    <span class="instruction-icon">${icon}</span>
    <span class="instruction-text">${instructionText}</span>
  `;
  
  // Apply classes and content
  resultBox.classList.add('instruction-panel', `${taskType}-task`);
  resultBox.innerHTML = instructionHTML;
}

// Global function to check if word needs enrichment
function needsEnrichment(word, lang) {
  const cached = cacheGet(word, lang);
  const hasT = !!(cached && (cached.translation||'').trim());
  const hasL = !!(cached && (cached.lemma||'').trim());
  const hasP = !!(cached && (cached.pos||'').trim());
  return !(hasT && (hasL || hasP));
}

// Global function to enrich a single word (with caching check)
async function enrichWordIfNeeded(word, lang, nat, sentence_context = '', sentence_native = '') {
  if (!needsEnrichment(word, lang)) {
    console.log(`🎯 Word already enriched, skipping: ${word}`);
    return;
  }
  
  console.log(`📚 Enriching word: ${word}`);
  
  // Check if we're in a custom level context
  const isCustomLevel = window.RUN && (window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP);
  
  const headers = { 'Content-Type': 'application/json' };
  if (window.authManager && window.authManager.isAuthenticated()) {
    Object.assign(headers, window.authManager.getAuthHeaders());
  }
  
  if (isCustomLevel) {
    // Use custom level batch enrichment API
    const groupId = window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP;
    const levelNumber = window.RUN._customLevelNumber || window.SELECTED_CUSTOM_LEVEL || 1;
    
    return fetch(`/api/custom-levels/${groupId}/${levelNumber}/enrich_batch`, {
      method:'POST', 
      headers, 
      body: JSON.stringify({ 
        words: [word],
        language:lang, 
        native_language:nat,
        sentence_context: sentence_context,
        sentence_native: sentence_native
      })
    });
  } else {
    // Use standard enrichment API
    return fetch('/api/word/enrich', { 
      method:'POST', 
      headers, 
      body: JSON.stringify({ 
        word:word, 
        language:lang, 
        native_language:nat,
        sentence_context: sentence_context,
        sentence_native: sentence_native
      })
    });
  }
}
async function batchGetWords(words, lang){
  const uniq = Array.from(new Set((words||[]).map(w=>String(w||'').trim()).filter(Boolean)));
  if(!uniq.length) return [];
  const miss = uniq.filter(w=> !cacheGet(w, lang));
  if(!miss.length) return uniq.map(w=> cacheGet(w, lang)).filter(Boolean);
  try{
    const headers = { 'Content-Type': 'application/json' };
    
    // Add authentication header if session token exists
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    
    // Use relative URL to avoid CORS issues
    const apiUrl = '/api/words/get_many';
    console.log('🔧 batchGetWords API call:', apiUrl, { words: miss, language: lang||RUN.target||'en' });
    
    const r = await fetch(apiUrl, { method:'POST', headers, body: JSON.stringify({ words: miss, language: lang||RUN.target||'en' }) });
    
    if (!r.ok) {
      console.error('❌ batchGetWords API error:', r.status, r.statusText);
      return [];
    }
    
    const js = await r.json();
    const arr = (js && js.success && Array.isArray(js.data)) ? js.data : [];
    arr.forEach(cachePut);
    return uniq.map(w=> cacheGet(w, lang)).filter(Boolean);
  }catch(e){
    console.error('❌ batchGetWords error:', e);
    return []; 
  }
}

// --- Audio replay button helper ---
function bindReplayFor(text){
  const btn = document.getElementById('lesson-replay');
  if(!btn) return;
  btn.disabled = !text || !text.trim();
  btn.onclick = async ()=>{ try{ await speakSentenceOnce(text); }catch(_){ } };
}
function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }

let RUN = { id:null, items:[], idx:0, target:'en', native:'de', answered:false, queue:[], selectedOption:null, mcCorrect:0, mcTotal:0, sbCorrect:0, sbTotal:0, _reuse:true, _overrideTopic:'' };if(typeof window!=='undefined'){ window.RUN = RUN; }
let AUTOPLAY_UNLOCKED = false;
function unlockAudio(){
  if(AUTOPLAY_UNLOCKED) return;
  try{
    const C = window.AudioContext || window.webkitAudioContext;
    if(C){
      const ctx = new C();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      gain.gain.value = 0.0001; // nahezu stumm
      osc.connect(gain); gain.connect(ctx.destination);
      osc.start();
      setTimeout(()=>{ try{ osc.stop(); ctx.close(); }catch(_){} }, 30);
    }
  }catch(_){}
  AUTOPLAY_UNLOCKED = true;
}

function primeSentenceAudio(){
  try{
    let a = window._sentenceAudio;
    if(!a){ a = new Audio(); a.preload='auto'; window._sentenceAudio = a; }
    // ultrakurzer stummer MP3-Frame
    const SILENT = 'data:audio/mp3;base64,//uQZAAAAAAAAAAAAAAAAAAAAAAAWGluZwAAAA8AAAACAAACcQCAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA';
    a.src = SILENT;
    a.muted = true;
    const p = a.play();
    if(p && p.then){ p.then(()=>{ try{ a.pause(); a.currentTime=0; a.muted=false; }catch(_){} }).catch(()=>{}); }
  }catch(_){}
}

// --- Sequential sentence audio playback helpers ---

let SPEAK_GEN = 0;
function tokenizeWords(txt){
  const out=[]; if(!txt) return out;
  const re=/\p{L}+(?:'\p{L}+)?/gu; let m; while((m=re.exec(txt))){ out.push(m[0]); }
  return out;
}
function waitAudioEndOrTimeout(ms=1400){
  return new Promise(resolve=>{
    const a = document.getElementById('tt-audio-el');
    let done=false; const finish=()=>{ if(done) return; done=true; try{ a && a.removeEventListener('ended', finish); }catch(_){ } resolve(); };
    try{ a && a.addEventListener('ended', finish, { once:true }); }catch(_){ }
    setTimeout(finish, ms);
  });
}

// --------- TTS Prefetching helpers for seamless sequential playback ----------
async function ttsUrlFor(word){
  const lang = RUN.target || (document.getElementById('target-lang')?.value||'en');
  try{
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    const r = await fetch('/api/word/tts', { method:'POST', headers, body: JSON.stringify({ word, language: lang }) });
    const js = await r.json();
    if(js && js.success && js.audio_url) return js.audio_url;
  }catch(_){ }
  return '';
}

function loadAudio(src, timeoutMs=2000){
  return new Promise(resolve=>{
    try{
      const a = new Audio();
      a.preload = 'auto';
      a.src = src; // trigger load
      let done=false; const finish=()=>{ if(done) return; done=true; resolve(a); };
      const onReady = ()=>{ a.removeEventListener('canplaythrough', onReady); finish(); };
      a.addEventListener('canplaythrough', onReady, { once:true });
      setTimeout(finish, timeoutMs);
    }catch(_){ resolve(null); }
  });
}

async function prefetchSentenceAudio(words){
  const uniq = words.map(w=>String(w||'').trim()).filter(Boolean);
  // Prefetch URLs in parallel
  const urls = await Promise.all(uniq.map(w=> ttsUrlFor(w)));
  // Build aligned playlist of Audio elements
  const list = [];
  for(let i=0;i<uniq.length;i++){
    const url = urls[i];
    if(url){
      const a = await loadAudio(url, 2000);
      if(a) list.push(a); else list.push(null);
    } else {
      list.push(null);
    }
  }
  return list;
}

// --------- Sequential playlist-based TTS playback for minimal gaps ----------
async function speakWordsSequential(words){
  const myGen = ++SPEAK_GEN;
  const playlist = await prefetchSentenceAudio(words);
  for(let i=0;i<words.length;i++){
    if(myGen !== SPEAK_GEN) return; // canceled by newer render
    const a = playlist[i];
    if(a && a.src){
      try{ a.currentTime = 0; await a.play(); }catch(_){ }
      await new Promise(res=>{ a.addEventListener('ended', ()=>res(), { once:true }); setTimeout(()=>res(), 2200); });
    } else {
      // Fallback auf bestehende Einzel-Wiedergabe
      try{ await playOrGenAudio(words[i]); }catch(_){ }
      await waitAudioEndOrTimeout(1000);
    }
  }
}

async function speakSentenceOnce(text){
  const myGen = ++SPEAK_GEN; // cancelt vorherige Sequenz
  const lang = RUN.target || (document.getElementById('target-lang')?.value||'en');
  if(!text || !text.trim()) return;
  try{
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    const r = await fetch('/api/sentence/tts', {
      method:'POST', headers,
      body: JSON.stringify({ text, language: lang })
    });
    const js = await r.json();
    if(js && js.success && js.audio_url && myGen===SPEAK_GEN){
      let a = window._sentenceAudio;
      if(!a){ a = new Audio(); a.preload='auto'; window._sentenceAudio = a; }
      a.src = js.audio_url; a.muted = false; a.currentTime = 0;
      try{ await a.play(); }
      catch(e){
        if(e && (e.name==='NotAllowedError' || e.name==='AbortError')){
          const once = ()=>{ document.removeEventListener('pointerdown', once, true); a.currentTime=0; a.play().catch(()=>{}); };
          document.addEventListener('pointerdown', once, true);
        }
      }
    }
  }catch(_){}
}

function setProgress(curr,total){
  const el=document.getElementById('progress'); if(!el) return;
  const tot = (typeof total==='number' && total>0) ? total : (RUN.queue && RUN.queue.length ? RUN.queue.length : (RUN.items?.length||1));
  const pct = Math.max(0, Math.min(100, Math.round(100*curr/Math.max(tot,1))));
  el.style.width = pct+'%';
}

function uniqWords(arr){
  const seen=new Set(); const out=[];
  for(const w of (arr||[])){ const k=String(w||'').trim(); if(k && !seen.has(k)){ seen.add(k); out.push(k); } }
  return out;
}

function buildTaskQueue(){
  const q=[]; 
  
  // Ensure RUN.items is an array
  if (!Array.isArray(RUN.items)) {
    console.error('RUN.items is not an array:', RUN.items);
    RUN.items = [];
  }
  
  const maxItems = Math.min(5, RUN.items.length);
  const allWords = uniqWords([].concat(...RUN.items.map(it=>it.words||[])));

  for(let i=0;i<maxItems; i++){
    const it = RUN.items[i];

    // Translation
    q.push({ type:'tr', i });

    // Multiple-choice
    const targetWords = uniqWords(it.words||[]);
    const pick = targetWords[Math.floor(Math.random()*Math.max(1,targetWords.length))] || '';
    const text = String(it.text_target||'');
    
    console.log('🔧 Building MC task:', {
        itemIndex: i,
        text: text,
        targetWords: targetWords,
        pick: pick,
        allWords: allWords,
        itemWords: it.words
    });
    
    const re = new RegExp(`\\b${pick.replace(/[.*+?^${}()|[\\]\\\\]/g,'\\$&')}\\b`,'u');
    const cloze = re.test(text) ? text.replace(re, '____') : text;
    
    console.log('🔧 MC regex test:', {
        pick: pick,
        regex: re,
        text: text,
        testResult: re.test(text),
        cloze: cloze
    });
    const pool = allWords.filter(w=>w && w!==pick);
    const d1 = pool[Math.floor(Math.random()*Math.max(1,pool.length))] || pick;
    const d2 = pool.filter(w=>w!==d1)[Math.floor(Math.random()*Math.max(1,Math.max(0,pool.length-1)))] || pick;
    const opts = [pick, d1, d2].filter((v,i,a)=>a.indexOf(v)===i);
    while(opts.length<3){ opts.push(pick); }
    for(let k=opts.length-1;k>0;k--){ const r=Math.floor(Math.random()*(k+1)); [opts[k],opts[r]]=[opts[r],opts[k]]; }
    const answer = opts.indexOf(pick);
    
    console.log('✅ MC task created:', {
        cloze: cloze,
        pick: pick,
        options: opts,
        answer: answer
    });
    
    q.push({ type:'mc', i, cloze, pick, options:opts, answer });

    // Sentence Builder
    const original = String(it.text_target||'');
    const sbWords = tokenizeWords(original);
    const sbOptions = sbWords.slice();
    for(let k=sbOptions.length-1;k>0;k--){ const r=Math.floor(Math.random()*(k+1)); [sbOptions[k],sbOptions[r]]=[sbOptions[r],sbOptions[k]]; }
    q.push({ type:'sb', i, words: sbWords, options: sbOptions });
  }

  // global mischen und auf 15 begrenzen
  for(let k=q.length-1;k>0;k--){ const r=Math.floor(Math.random()*(k+1)); [q[k],q[r]]=[q[r],q[k]]; }
  RUN.queue = q.slice(0, Math.min(15, q.length));
}

async function highlightWordsByFamiliarity(it){
  try{
    const lang = RUN.target;
    const words = uniqWords(it.words||[]);
    await batchGetWords(words, lang);
    words.forEach(w=>{
      const row = cacheGet(w, lang) || {};
      const fam = parseInt(row.familiarity||0,10)||0;
      
      // Highlight sentence-wrap words
      const sentenceNodes = $$('#sentence-wrap .word[data-word="'+CSS.escape(w)+'"]');
      sentenceNodes.forEach(n=>{
        n.classList.remove('fam-0','fam-1','fam-2');
        if(fam===0) n.classList.add('fam-0');
        else if(fam===1||fam===2) n.classList.add('fam-1');
      });
      
      // Highlight MC options
      const mcNodes = $$('#mc-options button[data-word="'+CSS.escape(w)+'"]');
      mcNodes.forEach(n=>{
        n.classList.remove('fam-0','fam-1','fam-2');
        if(fam===0) n.classList.add('fam-0');
        else if(fam===1||fam===2) n.classList.add('fam-1');
      });
      
      // Highlight SB options and chips
      const sbOptionNodes = $$('.sb-options button[data-word="'+CSS.escape(w)+'"]');
      const sbChipNodes = $$('.sb-area .sb-chip[data-word="'+CSS.escape(w)+'"]');
      [...sbOptionNodes, ...sbChipNodes].forEach(n=>{
        n.classList.remove('fam-0','fam-1','fam-2');
        if(fam===0) n.classList.add('fam-0');
        else if(fam===1||fam===2) n.classList.add('fam-1');
      });
    });
  }catch(_){}
}

async function prefetchWordsForCurrent(it){
  try{
    const lang = RUN.target, nat = RUN.native;
    const words = uniqWords(it.words||[]).slice(0,12);
    // Single batch fetch to populate cache
    const rows = await batchGetWords(words, lang);
    const need = new Set();
    words.forEach(w=>{
      const row = cacheGet(w, lang);
      const hasT = !!(row && (row.translation||'').trim());
      const hasL = !!(row && (row.lemma||'').trim());
      const hasP = !!(row && (row.pos||'').trim());
      
      // Debug logging
      console.log(`🔍 Cache check for word "${w}":`, {
        cached: !!row,
        hasTranslation: hasT,
        hasLemma: hasL,
        hasPos: hasP,
        needsEnrichment: !(hasT && (hasL || hasP)),
        row: row
      });
      
      if(!(hasT && (hasL || hasP))) need.add(w);
    });
    // Enrich only those still missing core fields
    if (need.size > 0) {
      console.log(`📚 Enriching ${need.size} words that need enrichment`);
      
      // Check if we're in a custom level context
      const isCustomLevel = window.RUN && (window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP);
      
      if (isCustomLevel) {
        // Use custom level batch enrichment API
        const groupId = window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP;
        const levelNumber = window.RUN._customLevelNumber || window.SELECTED_CUSTOM_LEVEL || 1;
        
        try {
          const headers = { 'Content-Type': 'application/json' };
          if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
          }
          
          const response = await fetch(`/api/custom-levels/${groupId}/${levelNumber}/enrich_batch`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              words: Array.from(need),
              language: lang,
              native_language: nat,
              sentence_context: '',
              sentence_native: ''
            })
          });
          
          if (response.ok) {
            console.log('✅ Custom level batch enrichment successful');
          } else {
            console.log('⚠️ Custom level batch enrichment failed, falling back to individual requests');
            // Fallback to individual requests
            await Promise.all(Array.from(need).map(w=> 
              enrichWordIfNeeded(w, lang, nat, '', '').catch(()=>{})
            ));
          }
        } catch (error) {
          console.log('⚠️ Custom level batch enrichment error, falling back to individual requests:', error);
          // Fallback to individual requests
          await Promise.all(Array.from(need).map(w=> 
            enrichWordIfNeeded(w, lang, nat, '', '').catch(()=>{})
          ));
        }
      } else {
        // Use individual requests for non-custom levels
        await Promise.all(Array.from(need).map(w=> 
          enrichWordIfNeeded(w, lang, nat, '', '').catch(()=>{})
        ));
      }
    } else {
      console.log('🎯 All words already enriched, skipping enrichment');
    }
    // Refresh cache for enriched words
    if(need.size) await batchGetWords(Array.from(need), lang);
  }catch(_){}
}

async function prewarmSentenceTTS(text){
  const lang = RUN.target || (document.getElementById('target-lang')?.value||'en');
  if(!text || !text.trim()) return;
  try{
    const headers = { 'Content-Type': 'application/json' };
    
    // Add authentication header if session token exists
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    
    const r = await fetch('/api/sentence/tts', {
      method:'POST', headers,
      body: JSON.stringify({ text, language: lang })
    });
    try{ await r.json(); }catch(_){ }
  }catch(_){ }
}

function collectWords(it){ return uniqWords(it?.words||[]); }

// Batch-Enrichment für bessere Performance
async function batchEnrichWords(words, lang, nat, sentence_context, sentence_native) {
  if (!words || words.length === 0) return;
  
  // Limit batch size to prevent timeout issues
  const BATCH_SIZE = 10;
  if (words.length > BATCH_SIZE) {
    console.log(`🔧 Splitting ${words.length} words into batches of ${BATCH_SIZE}`);
    const batches = [];
    for (let i = 0; i < words.length; i += BATCH_SIZE) {
      batches.push(words.slice(i, i + BATCH_SIZE));
    }
    
    // Process batches sequentially to avoid overwhelming the server
    for (const batch of batches) {
      await batchEnrichWords(batch, lang, nat, sentence_context, sentence_native);
      // Small delay between batches
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    return;
  }
  
  try {
    const headers = { 'Content-Type': 'application/json' };
    
    // Add authentication header if session token exists
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    
    // Batch-Request für alle Wörter gleichzeitig
    // Use custom level API if this is a custom level
    let response;
    if (RUN._customGroupId && RUN._customLevelNumber) {
      console.log('🔧 Using custom level enrich_batch API:', RUN._customGroupId, RUN._customLevelNumber);
      response = await fetch(`/api/custom-levels/${RUN._customGroupId}/${RUN._customLevelNumber}/enrich_batch`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          words: words,
          language: lang,
          native_language: nat,
          sentence_context: sentence_context,
          sentence_native: sentence_native
        })
      });
    } else {
      // Check if we're in a custom level context
      const isCustomLevel = window.RUN && (window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP);
      
      if (isCustomLevel) {
        // Use custom level batch enrichment API
        const groupId = window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP;
        const levelNumber = window.RUN._customLevelNumber || window.SELECTED_CUSTOM_LEVEL || 1;
        
        response = await fetch(`/api/custom-levels/${groupId}/${levelNumber}/enrich_batch`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            words: words,
            language: lang,
            native_language: nat,
            sentence_context: sentence_context,
            sentence_native: sentence_native
          })
        });
      } else {
        // Use standard batch enrichment API
        response = await fetch('/api/word/enrich_batch', {
          method: 'POST',
          headers,
          body: JSON.stringify({
            words: words,
            language: lang,
            native_language: nat,
            sentence_context: sentence_context,
            sentence_native: sentence_native
          })
        });
      }
    }
    
    if (!response.ok) {
      // Log the error but don't fallback to individual requests
      console.log('Batch enrich failed with status:', response.status, response.statusText);
      console.log('Skipping individual enrichment to avoid performance issues');
      
      // Instead of individual requests, just log which words need enrichment
      // The user can still use the level, words will be enriched on-demand
      console.log('Words that need enrichment:', words);
      return;
    }
  } catch (err) {
    console.log('Batch enrichment error:', err);
  }
}

// Enrich only the words for a single item, with smart caching
async function preEnrichItemBlocking(it){
  try{
    const lang = RUN.target, nat = RUN.native;
    const words = collectWords(it);
    const total = words.length;
    if(total===0) return;

    // 1) Satz-TTS sofort starten (parallel)
    const ttsPromise = prewarmSentenceTTS(String(it?.text_target||''));

    // 2) Prüfe Cache zuerst - nur fehlende Wörter enrichieren
    const needEnrichment = [];
    const cachedWords = await batchGetWords(words, lang);
    
    words.forEach(w => {
      const cached = cacheGet(w, lang);
      // More comprehensive check for existing enrichment
      const hasTranslation = !!(cached && (cached.translation || '').trim());
      const hasBasicInfo = !!(cached && ((cached.lemma || '').trim() || (cached.pos || '').trim()));
      const hasAdvancedInfo = !!(cached && (
        (cached.ipa || '').trim() || 
        (cached.example || '').trim() || 
        (cached.synonyms || []).length > 0 ||
        (cached.collocations || []).length > 0
      ));
      
      // Only enrich if missing basic translation OR missing both lemma/pos AND advanced info
      if (!hasTranslation || (!hasBasicInfo && !hasAdvancedInfo)) {
        needEnrichment.push(w);
      }
    });

    // Nur fehlende Wörter enrichieren
    if (needEnrichment.length > 0) {
      // Get sentence context for word enrichment
      const sentence_context = String(it?.text_target || '');
      const sentence_native = String(it?.text_native_ref || '');
      
      // Batch-Enrichment für bessere Performance
      await batchEnrichWords(needEnrichment, lang, nat, sentence_context, sentence_native);

      // Cache für enrichierte Wörter aktualisieren
      await batchGetWords(needEnrichment, lang);
    }

    // 3) Sicherstellen, dass das Satz-Audio fertig ist
    await ttsPromise;
  }catch(_){}
}

// Helper function to find context for a word
function findWordContext(word, items, excludeIdx) {
  for (let i = 0; i < items.length; i++) {
    if (i === excludeIdx) continue;
    const item = items[i];
    const words = collectWords(item);
    if (words.includes(word)) {
      return {
        sentence_context: String(item?.text_target || ''),
        sentence_native: String(item?.text_native_ref || '')
      };
    }
  }
  return { sentence_context: '', sentence_native: '' };
}

// Enrich remaining items in background, no loader updates
async function preEnrichRestBackground(items, excludeIdx){
  try{
    const lang = RUN.target, nat = RUN.native;
    const set = new Set();
    items.forEach((it,idx)=>{ if(idx!==excludeIdx){ for(const w of collectWords(it)) set.add(w); } });
    const words = Array.from(set);
    if(!words.length) return;
    const CONC = Math.min(50, Math.max(8, Math.ceil(words.length/8)));
    const queue = words.slice();
    const worker = async ()=>{
      while(queue.length){
        const w = queue.pop();
        try{ 
          const headers = { 'Content-Type': 'application/json' };
          if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
          }
          
          // Find context for this word
          const context = findWordContext(w, items, excludeIdx);
          
          // Use the global enrichment function
          await enrichWordIfNeeded(w, lang, nat, context.sentence_context, context.sentence_native);
        }catch(_){ }
      }
    };
    // fire-and-forget
    Promise.all(Array.from({length: Math.min(CONC, words.length)}, ()=>worker())).catch(()=>{});
  }catch(_){ }
}

// Adjust familiarity helper for MC
async function adjustFamiliarity(word, delta){
  if(!word) return;
  const lang = RUN.target || (document.getElementById('target-lang')?.value||'en');
  try{
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    const r = await fetch(`/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(lang)}`, { headers });
    const js = await r.json();
    let fam = parseInt(js?.familiarity||0,10)||0;
    fam = Math.max(0, Math.min(5, fam + (Number(delta)||0)));
    // Add native language header for unauthenticated users
    const upsertHeaders = { 'Content-Type': 'application/json' };
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    upsertHeaders['X-Native-Language'] = nativeLanguage;
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(upsertHeaders, window.authManager.getAuthHeaders());
    }
    
    await fetch('/api/word/upsert', { method:'POST', headers: upsertHeaders, body: JSON.stringify({ word, language: lang, familiarity: fam }) });
    
    // Invalidate words cache to ensure fresh data is loaded
    try{
      if (typeof window.invalidateWordsCache === 'function') {
        window.invalidateWordsCache(lang);
      }
    }catch(_){}
  }catch(_){ /* ignore */ }
}

// Deprecated: kept as shim, no longer used. Use preEnrichItemBlocking + preEnrichRestBackground.
async function preEnrichAll(items){
  try{ if(Array.isArray(items) && items.length){ await preEnrichItemBlocking(items[0]); preEnrichRestBackground(items, 0); } }catch(_){ }
}

async function renderCurrent(){
  const task = RUN.queue && RUN.queue[RUN.idx];
  const it = task ? RUN.items[task.i] : RUN.items[RUN.idx];
  if(!it) return;
  // Cancel any previous playback sequence
  SPEAK_GEN++; // cancel any previous playback sequence
  setProgress(RUN.idx, RUN.queue?.length||RUN.items.length);

  const wrap = $('#sentence-wrap'); if(!wrap) return; wrap.innerHTML='';
  const original = String(it.text_target||'');

  // Reset common UI
  RUN.selectedOption = null;
  const resBox = $('#result'); if(resBox){ resBox.classList.remove('success', 'error'); resBox.classList.add('hint'); resBox.innerHTML=''; }
  const ta=$('#user-translation');
  const btn=$('#check'); if(btn){ btn.disabled=true; btn.style.opacity='0.6'; btn.classList.remove('ready', 'continue'); }
  
  // Reset all MC option states
  const mcOptions = document.querySelectorAll('#mc-options button, .mc-options-grid button');
  mcOptions.forEach(opt => opt.classList.remove('active', 'ok', 'bad'));
  
  // Add event listener to enable button when user types
  if(ta && btn) {
    ta.addEventListener('input', () => {
      const hasText = ta.value.trim().length > 0;
      btn.disabled = !hasText;
      btn.style.opacity = hasText ? '' : '0.6';
      console.log('🔧 Translation input changed, button enabled:', hasText);
    });
  }

  if(task && task.type==='mc'){
    console.log('🔧 Rendering MC task:', {
      task: task,
      original: original,
      pick: task.pick
    });
    
    // Satz mit Lücke + klickbare Wörter, plus Replay-Button neben Satz
    const rowWrap = document.createElement('div'); rowWrap.className='sentence-row';
    const p = document.createElement('div'); p.className='sentence';
    const frag = document.createDocumentFragment();
    const re=/\p{L}+(?:'\p{L}+)?/gu; let last=0; let m; let gapDone=false; const txt = original;
    while((m=re.exec(txt))){
      if(m.index>last) frag.appendChild(document.createTextNode(txt.slice(last,m.index)));
      const w=m[0];
      if(!gapDone && w===task.pick){
        console.log('🔧 Creating gap for word:', w, 'at position:', m.index);
        const gap=document.createElement('span'); gap.id='mc-gap'; gap.className='word'; gap.textContent='____';
        frag.appendChild(gap); gapDone=true; last=re.lastIndex; continue;
      }
      const span=document.createElement('span');
      span.className='word'; span.textContent=w; span.dataset.word=w;
      span.onclick=async(ev)=>{ ev.stopPropagation(); await openTooltip(ev.currentTarget,w); playOrGenAudio(w); };
      frag.appendChild(span); last=re.lastIndex;
    }
    if(last<txt.length) frag.appendChild(document.createTextNode(txt.slice(last)));
    p.appendChild(frag);
    rowWrap.appendChild(p);
    wrap.appendChild(rowWrap);
    
    console.log('🔧 MC sentence rendered, gapDone:', gapDone, 'gap element:', document.getElementById('mc-gap'));
    const rrow = document.createElement('div'); rrow.className='replay-row';
    const rbtn = document.createElement('button'); rbtn.id='lesson-replay'; rbtn.className='icon-btn'; rbtn.title='Satz erneut abspielen'; rbtn.setAttribute('aria-label','Satz erneut abspielen'); rbtn.textContent='🔊';
    rrow.appendChild(rbtn);
    wrap.appendChild(rrow);
    bindReplayFor(original);

    if(ta) ta.parentElement.style.display='none';

    // Optionen direkt UNTER dem Satz, also ÜBER Textarea/Buttons
    let row = document.getElementById('mc-options');
    if(!row){ 
      row = document.createElement('div'); 
      row.id='mc-options'; 
      row.className='mc-options-container'; 
      row.style.marginTop='16px'; 
    }
    row.innerHTML='';
    
    // Add descriptive label for MC options
    const labelDiv = document.createElement('div');
    labelDiv.className = 'mc-label';
    labelDiv.textContent = window.t ? window.t('labels.choose_word', 'Wort auswählen') : 'Wort auswählen';
    row.appendChild(labelDiv);
    
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'mc-options-grid';
    row.appendChild(optionsContainer);
    task.options.forEach((opt,idx)=>{
      const b=document.createElement('button'); b.className='secondary'; b.textContent=opt; b.style.fontSize='18px';
      b.onclick=()=>{ 
        if(RUN.answered) return; // lock after submit
        RUN.selectedOption = idx;
        Array.from(optionsContainer.children).forEach(ch=> ch.classList.remove('active'));
        b.classList.add('active');
        try{ playOrGenAudio(opt); }catch(_){}
        if(btn){ btn.disabled=false; btn.style.opacity='1'; btn.classList.add('ready'); btn.textContent=window.t ? window.t('buttons.check_answer', 'Antwort prüfen') : 'Antwort prüfen'; }
      };
      optionsContainer.appendChild(b);
    });
    wrap.appendChild(row);
    RUN.answered = false;
    // Enhanced instruction display for MC tasks
    displayEnhancedInstruction('mc', resBox);
    // Familiarity auch für MC-Satz
    highlightWordsByFamiliarity(it);
    // Auto-play full sentence once (gap uses the real word)
    try{ await speakSentenceOnce(original); }catch(_){ }

    if(btn){ btn.textContent=window.t ? window.t('buttons.check_answer', 'Antwort prüfen') : 'Antwort prüfen'; btn.onclick=submitAnswer; btn.disabled=true; btn.style.opacity='0.6'; }
  } else if(task && task.type==='sb'){
    const original = String(it.text_target||'');
    const rrow = document.createElement('div'); rrow.className='replay-row';
    const rbtn = document.createElement('button'); rbtn.id='lesson-replay'; rbtn.className='icon-btn';
    rbtn.title='Satz erneut abspielen'; rbtn.setAttribute('aria-label','Satz erneut abspielen'); rbtn.textContent='🔊';
    rrow.appendChild(rbtn);
    wrap.appendChild(rrow);
    bindReplayFor(original);

    if(ta) ta.parentElement.style.display='none';

    // --- SB Container: trennt gewählte und verfügbare Optionen visuell ---
    let shell = document.getElementById('sb-wrap');
    if(!shell){ shell = document.createElement('div'); shell.id='sb-wrap'; shell.className='sb-wrap'; }
    shell.innerHTML='';

    // Sections with labels
    const secTop = document.createElement('div'); secTop.className = 'sb-section';
    const labTop = document.createElement('div'); labTop.className = 'sb-label'; labTop.textContent = 'Satz aufbauen';
    let area = document.createElement('div'); area.id='sb-area'; area.className='sb-area';
    secTop.appendChild(labTop); secTop.appendChild(area);

    const secBot = document.createElement('div'); secBot.className = 'sb-section';
    const labBot = document.createElement('div'); labBot.className = 'sb-label'; labBot.textContent = 'Verfügbare Wörter';
    let opts = document.createElement('div'); opts.id='sb-options'; opts.className='sb-options';
    secBot.appendChild(labBot); secBot.appendChild(opts);

    const chosen = [];
    let dragFrom = -1;

    // Compute insertion index near pointer by nearest chip center
    function computeInsertIndex(container, x, y){
      const kids = Array.from(container.children);
      if(!kids.length) return 0;
      let bestIdx = kids.length;
      let best = Infinity;
      for(let i=0;i<kids.length;i++){
        const r = kids[i].getBoundingClientRect();
        const cx = r.left + r.width/2;
        const cy = r.top + r.height/2;
        const dx = cx - x, dy = cy - y;
        const d2 = dx*dx + dy*dy;
        if(d2 < best){ best = d2; bestIdx = (x < cx ? i : i+1); }
      }
      return Math.max(0, Math.min(kids.length, bestIdx));
    }

    const renderChosen = ()=>{
      area.innerHTML='';
      // Render chosen chips first
      const total = (task.words||[]).length;
      chosen.forEach((obj, pos)=>{
        const b = document.createElement('button');
        b.className = 'secondary sb-chip';
        b.textContent = obj.text;
        b.style.fontSize = '18px';
        b.title = 'Klicken zum Entfernen. Ziehen zum Umordnen';
        b.draggable = true;
        b.addEventListener('click', ()=>{
          if(RUN.answered) return;
          chosen.splice(pos,1);
          renderChosen();
          renderOptions();
        });
        b.addEventListener('dragstart', (ev)=>{
          dragFrom = pos;
          try{ ev.dataTransfer?.setData('text/plain', String(pos)); }catch(_){ }
          try{ ev.dataTransfer.effectAllowed = 'move'; }catch(_){ }
        });
        area.appendChild(b);
      });
      // Append placeholders for remaining slots
      const remaining = Math.max(0, total - chosen.length);
      for(let i=0;i<remaining;i++){
        const ph = document.createElement('div');
        ph.className='sb-placeholder';
        ph.textContent='';
        area.appendChild(ph);
      }
    };

    // Single container-level handlers to avoid duplicate listeners and index drift
    area.ondragover = (ev)=>{ ev.preventDefault(); area.classList.add('highlight'); try{ ev.dataTransfer.dropEffect = 'move'; }catch(_){ } };
    area.ondrop = (ev)=>{
      area.classList.remove('highlight');
      ev.preventDefault();
      if(dragFrom < 0 || dragFrom >= chosen.length) return;
      const toRaw = computeInsertIndex(area, ev.clientX, ev.clientY);
      const to = toRaw > dragFrom ? toRaw - 1 : toRaw;
      if(to === dragFrom) return;
      const item = chosen.splice(dragFrom, 1)[0];
      chosen.splice(Math.max(0,Math.min(chosen.length, to)), 0, item);
      dragFrom = -1;
      renderChosen();
    };
    area.ondragleave = ()=>{ area.classList.remove('highlight'); };

    const renderOptions = ()=>{
      opts.innerHTML='';
      (task.options||[]).forEach((opt, idx)=>{
        const used = chosen.some(c => c.idx === idx);
        const b = document.createElement('button');
        b.className = 'secondary';
        b.textContent = opt;
        b.style.fontSize = '18px';
        if(used){ b.style.display='none'; }
        b.onclick = async ()=>{
          if(RUN.answered || used) return;
          chosen.push({ text: opt, idx }); // index speichern
          try{ await playOrGenAudio(opt); }catch(_){ }
          renderChosen(); renderOptions();
          if(btn){ btn.disabled=false; btn.style.opacity='1'; btn.classList.add('ready'); btn.textContent=window.t ? window.t('buttons.check_answer', 'Antwort prüfen') : 'Antwort prüfen'; }
        };
        opts.appendChild(b);
      });
    };

    renderChosen();
    renderOptions();

    shell.appendChild(secTop);
    shell.appendChild(secBot);
    wrap.appendChild(shell);

    RUN.answered = false;
    // Enhanced instruction display for SB tasks
    displayEnhancedInstruction('sb', resBox);
    try{ await speakSentenceOnce(original); }catch(_){ }
    if(btn){ btn.textContent=window.t ? window.t('buttons.check_answer', 'Antwort prüfen') : 'Antwort prüfen'; btn.onclick=submitAnswer; btn.disabled=true; btn.style.opacity='0.6'; }
  } else {
    // Translation layout: original sentence tokens with tooltips, plus Replay-Button next to sentence
    if(ta) ta.parentElement.style.display='';
    const rowWrap = document.createElement('div'); rowWrap.className='sentence-row';
    const p = document.createElement('div'); p.className='sentence';
    const frag=document.createDocumentFragment();
    const re=/\p{L}+(?:'\p{L}+)?/gu; let last=0; let m;
    while((m=re.exec(original))){
      if(m.index>last) frag.appendChild(document.createTextNode(original.slice(last,m.index)));
      const w=m[0];
      const span=document.createElement('span');
      span.className='word'; span.textContent=w; span.dataset.word=w;
      span.onclick=async(ev)=>{ ev.stopPropagation(); await openTooltip(ev.currentTarget,w); playOrGenAudio(); };
      frag.appendChild(span); last=re.lastIndex;
    }
    if(last<original.length) frag.appendChild(document.createTextNode(original.slice(last)));
    p.appendChild(frag);
    const rbtn2 = document.createElement('button'); rbtn2.id='lesson-replay'; rbtn2.className='icon-btn'; rbtn2.title='Satz erneut abspielen'; rbtn2.setAttribute('aria-label','Satz erneut abspielen'); rbtn2.textContent='🔊';
    rowWrap.appendChild(p);
    rowWrap.appendChild(rbtn2);
    wrap.appendChild(rowWrap);
    bindReplayFor(original);

    if(ta) ta.value='';
    const nativeSel=null; // Native language is now in settings
    const nativeName = nativeSel ? (nativeSel.options[nativeSel.selectedIndex]?.text || nativeSel.value) : RUN.native;
    
    // Add label for translation textarea
    const textareaContainer = ta ? ta.parentElement : null;
    if (textareaContainer && !textareaContainer.querySelector('.translate-label')) {
      const labelDiv = document.createElement('div');
      labelDiv.className = 'translate-label';
      const nativeLangName = nativeName || 'Deutsch';
      labelDiv.textContent = window.t ? 
        window.t('labels.your_translation', `Ihre Übersetzung nach ${nativeLangName}`) : 
        `Ihre Übersetzung nach ${nativeLangName}`;
      textareaContainer.insertBefore(labelDiv, ta);
    }
    
    // Enhanced instruction display for translation tasks
    displayEnhancedInstruction('translate', resBox, { nativeName });
    RUN.answered=false;
    if(btn){ btn.textContent=window.t ? window.t('buttons.check_answer', 'Antwort prüfen') : 'Antwort prüfen'; btn.onclick=submitAnswer; }
    // Lazy loading - nur bei Bedarf enrichieren
    highlightWordsByFamiliarity(it);
    
    // Wörter im Hintergrund vorbereiten (nicht blockierend)
    setTimeout(() => {
      prefetchWordsForCurrent(it);
    }, 100);
    // Auto-play full sentence once (nicht blockierend)
    speakSentenceOnce(original).catch(_ => {});
    // remove MC row if present
    const old = document.getElementById('mc-options'); if(old) old.remove();
  }
}

async function submitAnswer(){
  console.log('🔧 submitAnswer called');
  const task = RUN.queue && RUN.queue[RUN.idx];
  console.log('🔧 Current task:', task);
  if(task && task.type==='mc'){
    // Multiple-choice evaluation only client-side
    const row = document.getElementById('mc-options');
    const btns = row ? Array.from(row.children) : [];
    const correct = (RUN.selectedOption === task.answer);
    
    // Play sound effect based on correctness
    if (window.soundManager) {
      if (correct) {
        window.soundManager.playCorrect();
      } else {
        window.soundManager.playIncorrect();
      }
    }
    
    // update word familiarity based on correctness
    try{ adjustFamiliarity(task.pick, correct? +1 : -1); }catch(_){}
    // record MC result server-side if supported
    try{
      const it = RUN.items[task.i];
      const headers = { 'Content-Type': 'application/json' };
      
      // Add authentication header if session token exists
      const sessionToken = localStorage.getItem('session_token');
      if (sessionToken) {
        headers['Authorization'] = `Bearer ${sessionToken}`;
      }
      
      // Use custom level API if this is a custom level
      if (RUN._customGroupId && RUN._customLevelNumber) {
        console.log('🔧 Using custom level submit_mc API:', RUN._customGroupId, RUN._customLevelNumber);
        console.log('🔧 Custom level context available:', {
          groupId: RUN._customGroupId,
          levelNumber: RUN._customLevelNumber,
          runId: RUN.id
        });
        await fetch(`/api/custom-levels/${RUN._customGroupId}/${RUN._customLevelNumber}/submit_mc`, { 
          method:'POST', 
          headers, 
          body: JSON.stringify({ 
            run_id: RUN.id, 
            idx: it?.idx, 
            word: task.pick, 
            answer: RUN.selectedOption,
            correct_answer: task.answer,
            correct: !!correct 
          }) 
        });
      } else {
        console.log('🔧 Using standard level submit_mc API (no custom level context)');
        await fetch('/api/level/submit_mc', { method:'POST', headers, body: JSON.stringify({ run_id: RUN.id, idx: it?.idx, word: task.pick, correct: !!correct }) });
      }
    }catch(_){ /* optional endpoint */ }
    // update local MC stats
    RUN.mcTotal = (RUN.mcTotal||0) + 1;
    if(correct) RUN.mcCorrect = (RUN.mcCorrect||0) + 1;
    btns.forEach((b,idx)=>{
      b.classList.remove('ok','bad','active');
      b.disabled = true; // lock options after submit
      if(idx===task.answer) b.classList.add('ok');
      else if(idx===RUN.selectedOption) b.classList.add('bad');
    });
    const gap = document.getElementById('mc-gap');
    if(gap){ gap.textContent = task.options[task.answer]; }
    const box=$('#result');
    if(box){ 
      // Get the correct translation in native language
      const item = RUN.items[task.i];
      let translation = '';
      if (item) {
        translation = item.text_native_ref || item.text_native || item.translation || '';
      }
      
      console.log('🔧 MC result display:', {
        correct: correct,
        item: item,
        translation: translation,
        text_native_ref: item?.text_native_ref,
        text_native: item?.text_native,
        translation_field: item?.translation
      });
      
      box.classList.remove('hint', 'success', 'error');
      box.classList.add(correct ? 'success' : 'error');
      box.innerHTML = (correct ? (window.t ? window.t('results.correct', 'Richtig') : 'Richtig') : (window.t ? window.t('results.incorrect', 'Falsch') : 'Falsch')) + ` <i>${escapeHtml(translation)}</i>`; 
    }
    // progress for MC
    setProgress(RUN.idx+1, RUN.queue?.length||RUN.items.length);
    RUN.answered=true;
    const btn=$('#check'); if(btn){ btn.textContent=window.t ? window.t('buttons.continue', 'Weiter') : 'Weiter'; btn.onclick=nextItem; btn.disabled=false; btn.style.opacity='1'; btn.classList.add('continue'); btn.classList.remove('ready'); }
    return;
  }
  else if(task && task.type==='sb'){
    const area = document.getElementById('sb-area'); const row = document.getElementById('sb-options');
    const chosen = Array.from(area?.querySelectorAll('button')||[]).map(b=>b.textContent||'');
    const expected = (task.words||[]).slice();
    const ok = chosen.length===expected.length && chosen.every((w,i)=> String(w)===String(expected[i]));
    
    // Play sound effect based on correctness
    if (window.soundManager) {
      if (ok) {
        window.soundManager.playCorrect();
      } else {
        window.soundManager.playIncorrect();
      }
    }
    
    RUN.answered = true; RUN.sbTotal = (RUN.sbTotal||0)+1; if(ok) RUN.sbCorrect = (RUN.sbCorrect||0)+1;
    // Familiarity für alle Wörter
    try{ (task.words||[]).forEach(w=> adjustFamiliarity(w, ok? +1 : -1)); }catch(_){}
    if(row){ Array.from(row.children).forEach(ch=> ch.disabled=true); }
    if(area){ Array.from(area.children).forEach(ch=> ch.disabled=true); }
    const box=$('#result');
    if(box){ 
      // Get the correct translation in native language
      const item = RUN.items[task.i];
      let translation = '';
      if (item) {
        translation = item.text_native_ref || item.text_native || item.translation || '';
      }
      
      console.log('🔧 SB result display:', {
        correct: ok,
        item: item,
        translation: translation,
        text_native_ref: item?.text_native_ref,
        text_native: item?.text_native,
        translation_field: item?.translation
      });
      
      box.classList.remove('hint', 'success', 'error'); 
      box.classList.add(ok ? 'success' : 'error');
      box.innerHTML = (ok ? (window.t ? window.t('results.correct', 'Richtig') : 'Richtig') : (window.t ? window.t('results.incorrect', 'Falsch') : 'Falsch')) + ` <i>${escapeHtml(translation)}</i>`; 
    }
    const btnNext=$('#check'); if(btnNext){ btnNext.textContent='Weiter'; btnNext.disabled=false; btnNext.style.opacity='1'; btnNext.classList.add('continue'); btnNext.classList.remove('ready'); btnNext.onclick=nextItem; }
    return;
  }
  // Translation branch as before
  console.log('🔧 Translation submit branch');
  const it=RUN.items[(task?task.i:RUN.idx)]; if(!it) return;
  const user=$('#user-translation')?.value.trim(); 
  console.log('🔧 User translation:', user);
  if(!user){ alert('Bitte übersetzen.'); return; }
  const btn=$('#check'); if(btn){ btn.disabled=true; btn.style.opacity='0.6'; }
  try{
    const headers = { 'Content-Type': 'application/json' };
    
    // Add authentication header if session token exists
    const sessionToken = localStorage.getItem('session_token');
    if (sessionToken) {
      headers['Authorization'] = `Bearer ${sessionToken}`;
    }
    
    // Use custom level API if this is a custom level
    let r, js;
    if (RUN._customGroupId && RUN._customLevelNumber) {
      console.log('🔧 Using custom level submit API:', RUN._customGroupId, RUN._customLevelNumber);
      console.log('🔧 Custom level context available:', {
        groupId: RUN._customGroupId,
        levelNumber: RUN._customLevelNumber,
        runId: RUN.id
      });
      r = await fetch(`/api/custom-levels/${RUN._customGroupId}/${RUN._customLevelNumber}/submit`, {
        method:'POST',
        headers,
        body: JSON.stringify({
          run_id: RUN.id,
          answers: [{idx: it.idx, translation: user}]
        })
      });
    } else {
      console.log('🔧 Using standard level submit API (no custom level context)');
      r = await fetch('/api/level/submit', {
        method:'POST',
        headers,
        body: JSON.stringify({run_id: RUN.id, answers: [{idx: it.idx, translation: user}]})
      });
    }
    
    js = await r.json(); 
    if(!js.success){ 
      console.error('❌ Submit API error:', js.error);
      alert(js.error||'Fehler'); 
      return; 
    }
    console.log('✅ Submit API success:', js);
    const all=js.results||[]; const res=all.find(r=>Number(r.idx)===Number(it.idx))||all[all.length-1]||{similarity:0,ref:''};
    
    // Play sound effect based on similarity score (threshold 0.75)
    if (window.soundManager) {
      const passed = res.similarity >= 0.75;
      if (passed) {
        window.soundManager.playCorrect();
      } else {
        window.soundManager.playIncorrect();
      }
    }
    
    const box=$('#result'); 
    if(box) {
      const passed = res.similarity >= 0.75;
      box.classList.remove('hint', 'success', 'error');
      box.classList.add(passed ? 'success' : 'error');
      
      // Get the correct answer in native language
      let correctAnswer = res.ref || '';
      if (it.text_native_ref) {
        correctAnswer = it.text_native_ref;
      } else if (it.text_native) {
        correctAnswer = it.text_native;
      } else if (it.translation) {
        correctAnswer = it.translation;
      }
      
      console.log('🔧 Displaying result:', {
        similarity: res.similarity,
        correctAnswer: correctAnswer,
        itemData: it
      });
      
      box.innerHTML = window.t ? window.t('results.similarity', 'Ähnlichkeit: {similarity} · Korrekt: {ref}').replace('{similarity}', `<b>${res.similarity}</b>`).replace('{ref}', `<i>${escapeHtml(correctAnswer)}</i>`) : `Ähnlichkeit: <b>${res.similarity}</b> · Korrekt: <i>${escapeHtml(correctAnswer)}</i>`;
    }
    setProgress(RUN.idx+1, RUN.queue?.length||RUN.items.length);

    try{ // leichte Anreicherung
      const lang=RUN.target, nat=RUN.native;
      const words=uniqWords(it.words||[]).slice(0,8);
      
      // Check which words actually need enrichment
      const need = new Set();
      words.forEach(w=>{
        const cached = cacheGet(w, lang);
        if(!cached || !cached.translation || !cached.pos){
          need.add(w);
        }
      });
      
      if (need.size > 0) {
        console.log(`📚 Post-answer enriching ${need.size} words that need enrichment`);
        
        // Check if we're in a custom level context
        const isCustomLevel = window.RUN && (window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP);
        
        if (isCustomLevel) {
          // Use custom level batch enrichment API
          const groupId = window.RUN._customGroupId || window.SELECTED_CUSTOM_GROUP;
          const levelNumber = window.RUN._customLevelNumber || window.SELECTED_CUSTOM_LEVEL || 1;
          
          const headers = { 'Content-Type': 'application/json' };
          if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
          }
          
          fetch(`/api/custom-levels/${groupId}/${levelNumber}/enrich_batch`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              words: Array.from(need),
              language: lang,
              native_language: nat,
              sentence_context: '',
              sentence_native: ''
            })
          }).then(() => {
            console.log('✅ Post-answer custom level batch enrichment successful');
          }).catch((error) => {
            console.log('⚠️ Post-answer custom level batch enrichment failed:', error);
            // Fallback to individual requests
            for(const w of Array.from(need)){ 
              enrichWordIfNeeded(w, lang, nat, '', '').catch(()=>{}); 
            }
          });
        } else {
          // Use individual requests for non-custom levels
          for(const w of Array.from(need)){ 
            enrichWordIfNeeded(w, lang, nat, '', '').catch(()=>{}); 
          }
        }
      } else {
        console.log('🎯 All words already enriched, skipping post-answer enrichment');
      }
    }catch(_){}

    RUN.answered=true;
    const btn2=$('#check'); if(btn2){ btn2.textContent='Weiter'; btn2.onclick=nextItem; btn2.disabled=false; btn2.style.opacity='1'; btn2.classList.add('continue'); btn2.classList.remove('ready'); }
  } finally { const b=$('#check'); if(b){ b.disabled=false; b.style.opacity=''; } }
}

async function finishLevel(){
  try{ window._eval_context = 'lesson'; }catch(_){ }
  window._customEvalProgress = null;
  try{
    window._mc_ratio = (RUN.mcTotal>0) ? (RUN.mcCorrect/RUN.mcTotal) : null; window._mc_inject = true;
    window._sb_ratio = (RUN.sbTotal>0) ? (RUN.sbCorrect/RUN.sbTotal) : null; window._sb_inject = true;
  }catch(_){ }

  const headers = { 'Content-Type': 'application/json' };
  const sessionToken = localStorage.getItem('session_token');
  if (sessionToken) headers['Authorization'] = `Bearer ${sessionToken}`;
  const targetLang = document.getElementById('target-lang')?.value || 'en';
  const isCustomLevel = Boolean(RUN._customGroupId && RUN._customLevelNumber);
  const finishedGroupId = RUN._customGroupId;
  const finishedLevelNumber = RUN._customLevelNumber;
  let finishResponse = null;

  try {
    if (isCustomLevel) {
      console.log('🔧 Using custom level finish API:', finishedGroupId, finishedLevelNumber);
      const score = (RUN.mcTotal > 0) ? (RUN.mcCorrect / RUN.mcTotal) : 0.0;
      const res = await fetch(`/api/custom-levels/${finishedGroupId}/${finishedLevelNumber}/finish`, {
        method: 'POST',
        headers,
        body: JSON.stringify({ run_id: RUN.id, language: targetLang, score })
      });
      if (res.ok) {
        const payload = await res.json();
        if (payload && payload.success) {
          finishResponse = payload;
        } else {
          console.log('⚠️ Custom level finish response missing success flag:', payload);
        }
      } else {
        console.log('⚠️ Custom level finish request failed with status', res.status);
      }
    } else {
      await fetch('/api/level/finish', { method: 'POST', headers, body: JSON.stringify({ run_id: RUN.id, language: targetLang }) });
    }
  } catch (error) {
    console.log('⚠️ Error finishing level:', error);
  }

  if (isCustomLevel && finishResponse) {
    let normalized = null;
    try {
      if (typeof window.updateCustomLevelCardProgress === 'function') {
        normalized = window.updateCustomLevelCardProgress(finishedGroupId, finishedLevelNumber, finishResponse);
      }
    } catch (error) {
      console.log('⚠️ Failed to update custom level card after finish:', error);
    }
    if (!normalized) normalized = normalizeCustomProgressForLesson(finishResponse);
    if (normalized) {
      window._customEvalProgress = {
        groupId: finishedGroupId,
        levelNumber: finishedLevelNumber,
        counts: normalized.fam_counts,
        totalWords: normalized.total_words,
        completedWords: normalized.completed_words,
        scoreRatio: normalized.score,
        scorePercent: normalized.score_percent,
        status: normalized.status,
        completedAt: normalized.completed_at,
        timestamp: Date.now()
      };
      if (!window.cachedGroupProgress) window.cachedGroupProgress = {};
      window.cachedGroupProgress[finishedLevelNumber] = normalized;
    }
  } else if (!isCustomLevel) {
    window._customEvalProgress = null;
  }

  if (isCustomLevel) {
    RUN._customGroupId = null;
    RUN._customLevelNumber = null;
  }

  showTab('evaluation');
  try { await populateEvaluationScore(); } catch(_){ }
  try { await populateEvaluationStatus(); } catch(_){ }

  try{ 
    if(typeof window.renderLevels==='function') window.renderLevels(); 
    if(typeof window.refreshLevelStates==='function') window.refreshLevelStates();
  }catch(_){ }
  
  try{
    const lang = document.getElementById('target-lang')?.value || 'en';
    if (typeof window.invalidateWordsCache === 'function') {
      window.invalidateWordsCache(lang);
    }
  }catch(_){ }
}


function nextItem(){
  if(!RUN.answered) return;
  const lastIdx = (RUN.queue?.length||RUN.items.length) - 1;
  if(RUN.idx < lastIdx){
    RUN.idx++;
    renderCurrent();
  } else {
    finishLevel();
  }
}

async function startLevel(lvl){
  window._customEvalProgress = null;
  // Check if this is a custom level with pre-loaded data
  if (RUN._customLevelData) {
    console.log('🎯 Starting custom level with pre-loaded data');
    
    // Use custom level data directly
    RUN.target = $('#target-lang')?.value || 'en';
    RUN.native = localStorage.getItem('siluma_native') || 'de';
    RUN.level = Number(lvl) || 1;
    RUN.mcCorrect = 0; 
    RUN.mcTotal = 0;
    RUN.id = null; // Custom levels don't have run_id initially
    RUN.items = RUN._customLevelData;
    RUN.idx = 0;
    
    showTab('lesson');
    unlockAudio();
    primeSentenceAudio();
    
    try{ const abEntry=document.getElementById('alphabet-entry'); if(abEntry) abEntry.style.display='none'; }catch(_){}
    try{ const abCard=document.getElementById('alphabet-card'); if(abCard) abCard.style.display='none'; }catch(_){}
    
    const pc=document.getElementById('practice-card'); if(pc) pc.style.display='none';
    showLoader('Custom Level wird gestartet…');
    
    try {
      // Build task queue for custom level
      buildTaskQueue();
      const firstTask = RUN.queue && RUN.queue[0];
      const firstItem = firstTask ? RUN.items[firstTask.i] : RUN.items[0];
      
      // Hide loader immediately
      hideLoader();
      
      // Render the first item
      renderCurrent();
      
      // Keep custom level context for API calls during the lesson
      // RUN._customGroupId and RUN._customLevelNumber will be cleared in finishLevel()
      
      // Enrichment in background
      setTimeout(() => {
        Promise.all([
          preEnrichItemBlocking(firstItem),
          preEnrichRestBackground(RUN.items, firstTask ? firstTask.i : 0)
        ]).catch(err => console.log('Background enrichment error:', err));
      }, 50);
      
      // Ensure words are loaded for tooltips
      setTimeout(async () => {
        try {
          const allWords = [];
          RUN.items.forEach(item => {
            if (item.words && Array.isArray(item.words)) {
              allWords.push(...item.words);
            }
          });
          const uniqueWords = [...new Set(allWords)];
          console.log('🔧 Loading words for tooltips:', uniqueWords);
          await batchGetWords(uniqueWords, RUN.target);
          
      // Skip redundant enrichment for tooltips - words are already enriched in preEnrichItemBlocking
      // This prevents duplicate enrichment requests that cause performance issues
      console.log('🔧 Tooltips will use existing enriched words from cache');
      
      // Set up tooltip context for custom levels
      if (RUN._customGroupId && RUN._customLevelNumber) {
        console.log('🔧 Setting up tooltip context for custom level');
        // The tooltip system will now use the custom level context
      }
        } catch (err) {
          console.log('Error loading words for tooltips:', err);
        }
      }, 100);
      
      return; // Exit early for custom levels
    } catch (e) {
      hideLoader();
      throw e;
    }
  }
  
  // Check if this is a custom level that needs API integration
  if (RUN._customGroupId && RUN._customLevelNumber) {
    console.log('🎯 Starting custom level via API:', RUN._customGroupId, RUN._customLevelNumber);
    console.log('🔍 Custom level context:', { groupId: RUN._customGroupId, levelNumber: RUN._customLevelNumber });
    
    // Use custom level API instead of standard level API
    RUN.target = $('#target-lang')?.value || 'en';
    RUN.native = localStorage.getItem('siluma_native') || 'de';
    RUN.level = Number(lvl) || 1;
    RUN.mcCorrect = 0; 
    RUN.mcTotal = 0;
    
    showTab('lesson');
    unlockAudio();
    primeSentenceAudio();
    
    try{ const abEntry=document.getElementById('alphabet-entry'); if(abEntry) abEntry.style.display='none'; }catch(_){}
    try{ const abCard=document.getElementById('alphabet-card'); if(abCard) abCard.style.display='none'; }catch(_){}
    
    const pc=document.getElementById('practice-card'); if(pc) pc.style.display='none';
    showLoader('Custom Level wird gestartet…');
    
    try {
      const headers = { 'Content-Type': 'application/json' };
      
      // Add authentication header if session token exists
      const sessionToken = localStorage.getItem('session_token');
      if (sessionToken) {
        headers['Authorization'] = `Bearer ${sessionToken}`;
      }
      
      const r = await fetch(`/api/custom-levels/${RUN._customGroupId}/${RUN._customLevelNumber}/start`, {
        method: 'POST', 
        headers, 
        body: JSON.stringify({})
      });
      const js = await r.json();
      if (!js.success) { 
        alert(js.error || 'Fehler beim Starten des Custom Levels'); 
        hideLoader();
        return; 
      }
      
      RUN.id = js.run_id; 
      RUN.items = js.items; 
      RUN.idx = 0;
      
      // Ensure custom level context is set for API calls
      console.log('🔧 Custom level context set:', {
        groupId: RUN._customGroupId,
        levelNumber: RUN._customLevelNumber,
        runId: RUN.id
      });
      
      // Verify context is properly set
      if (!RUN._customGroupId || !RUN._customLevelNumber) {
        console.error('❌ Custom level context not properly set!');
        console.error('RUN._customGroupId:', RUN._customGroupId);
        console.error('RUN._customLevelNumber:', RUN._customLevelNumber);
        console.error('Available RUN properties:', Object.keys(RUN));
        
        // Try to recover from custom level data
        if (RUN._customLevelData) {
          console.log('🔧 Attempting to recover context from custom level data');
          // Context should have been set in startCustomLevel
          // This is a fallback - the context should be set before this point
        }
      }
      
      // Build task queue for custom level
      buildTaskQueue();
      const firstTask = RUN.queue && RUN.queue[0];
      const firstItem = firstTask ? RUN.items[firstTask.i] : RUN.items[0];
      
      // Hide loader immediately
      hideLoader();
      
      // Render the first item
      renderCurrent();
      
      // Keep custom level data for API calls during the lesson
      // RUN._customGroupId and RUN._customLevelNumber will be cleared in finishLevel()
      
      // Enrichment in background
      setTimeout(() => {
        Promise.all([
          preEnrichItemBlocking(firstItem),
          preEnrichRestBackground(RUN.items, firstTask ? firstTask.i : 0)
        ]).catch(err => console.log('Background enrichment error:', err));
      }, 50);
      
      return; // Exit early for custom levels
    } catch (e) {
      hideLoader();
      throw e;
    }
  }
  
  // Standard level logic (existing code)
  // Check if level is locked (60% requirement)
  if (lvl > 1) {
    const prevLevel = lvl - 1;
    const prevLevelElement = document.querySelector(`[data-level="${prevLevel}"]`);
    
    if (prevLevelElement && prevLevelElement.dataset.bulkData) {
      try {
        const prevLevelData = JSON.parse(prevLevelElement.dataset.bulkData);
        const prevScore = prevLevelData?.last_score || 0;
        const isPrevCompleted = prevLevelData?.status === 'completed' && Number(prevScore) > 0.6;
        
        if (!isPrevCompleted) {
          // Show elegant locked message instead of starting level
          if (typeof window.showLevelLockedMessage === 'function') {
            window.showLevelLockedMessage(lvl, prevLevel, prevScore);
          } else {
            alert(`Level ${lvl} ist gesperrt. Du musst Level ${prevLevel} mit mindestens 60% abschließen.`);
          }
          return; // Don't start the level
        }
      } catch (error) {
        console.log('Error checking previous level data:', error);
        // If we can't check, allow the level to start (fallback)
      }
    }
  }
  
  RUN.target=$('#target-lang')?.value||'en';
  RUN.native=localStorage.getItem('siluma_native')||'de';
  RUN.level=Number(lvl)||1;
  RUN.mcCorrect = 0; RUN.mcTotal = 0;
  showTab('lesson');
  unlockAudio();
  primeSentenceAudio();
  try{ const abEntry=document.getElementById('alphabet-entry'); if(abEntry) abEntry.style.display='none'; }catch(_){}
  try{ const abCard=document.getElementById('alphabet-card'); if(abCard) abCard.style.display='none'; }catch(_){}

  // Use level-specific topics if no override topic is provided
  const levelTopics = {
    1: 'Stellen Sie sich vor',
    2: 'Meine Familie',
    3: 'Mein Zuhause', 
    4: 'Meine Hobbys',
    5: 'Mein Tag'
  };
  
  const chosenTopic=(RUN._overrideTopic&&RUN._overrideTopic.trim())||($('#topic')?.value)||levelTopics[RUN.level]||'daily life';
  const cefrVal = ($('#cefr')?.value||'none');
  const prompt = (window.buildLevelPrompt ? window.buildLevelPrompt(RUN.level, { target_lang: RUN.target, native_lang: RUN.native, cefr: cefrVal, topic: chosenTopic }) : '');
  const payload={ level:RUN.level, target_lang:RUN.target, native_lang:RUN.native, topic:chosenTopic, cefr:cefrVal, prompt, reuse: !!RUN._reuse };

  const pc=document.getElementById('practice-card'); if(pc) pc.style.display='none';
  showLoader('Level wird gestartet…');
  try{
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    const r=await fetch('/api/level/start',{method:'POST',headers,body:JSON.stringify(payload)});
    const js=await r.json();
    if(!js.success){ alert(js.error||'Fehler'); return; }
    RUN.id=js.run_id; RUN.items=js.items; RUN.idx=0; RUN._overrideTopic='';
    // Keep _reuse=true to continue reusing existing levels
    // Baue die Queue, ermittle die erste anzuzeigende Aufgabe
    buildTaskQueue();
    const firstTask = RUN.queue && RUN.queue[0];
    const firstItem = firstTask ? RUN.items[firstTask.i] : RUN.items[0];
    // Ladebildschirm sofort verstecken
    hideLoader();
    
    // UI sofort freigeben - Enrichment im Hintergrund
    renderCurrent();
    
    // Enrichment parallel im Hintergrund starten (nicht blockierend)
    setTimeout(() => {
      Promise.all([
        preEnrichItemBlocking(firstItem),
        preEnrichRestBackground(RUN.items, firstTask ? firstTask.i : 0)
      ]).catch(err => console.log('Background enrichment error:', err));
    }, 50); // Minimale Verzögerung
  } catch (e) {
    hideLoader();
    throw e;
  }
}

function startLevelWithTopic(lvl,topic,reuse=false){ 
    // Ensure topic is a string before calling trim()
    const topicStr = String(topic || '').trim();
    RUN._overrideTopic = topicStr; 
    RUN._reuse = !!reuse; 
    startLevel(lvl); 
}

function abortLevel(){
  if(!confirm('Level wirklich abbrechen? Fortschritt in diesem Durchlauf geht verloren.')) return;
  const les=document.getElementById('lesson'); if(les) les.style.display='none';
  const levels=document.getElementById('levels-card'); if(levels) levels.style.display='';
  RUN = { id:null, items:[], idx:0, target: $('#target-lang')?.value||'en', native: localStorage.getItem('siluma_native')||'de', answered:false, queue:[], selectedOption:null, mcCorrect:0, mcTotal:0 };
  if(typeof window!=='undefined'){ window.RUN = RUN; window._mc_ratio = null; window._mc_inject = false; }
  setProgress(0,1);
}

export function initLesson(){
  const checkBtn=document.getElementById('check'); if(checkBtn) checkBtn.onclick=submitAnswer;
  const abortBtn=document.getElementById('abort-level'); if(abortBtn) abortBtn.onclick=abortLevel;
  document.addEventListener('keydown',(e)=>{
    // Handle Enter key for various UI elements
    if(e.key === 'Enter' && !e.shiftKey){
      const checkBtn = document.getElementById('check');
      
      if(checkBtn && !checkBtn.disabled){
        // Enter key triggers the check button (submit answer or continue)
        e.preventDefault();
        checkBtn.click();
        return;
      }
    }
    
    // Handle Enter key for Multiple Choice options
    if(e.key === 'Enter' && !e.shiftKey){
      const mcOptions = document.getElementById('mc-options');
      if(mcOptions && !RUN.answered){
        const activeBtn = mcOptions.querySelector('button.active');
        if(activeBtn){
          e.preventDefault();
          activeBtn.click();
          return;
        }
      }
    }
    
    // Handle Enter key for Sentence Building options
    if(e.key === 'Enter' && !e.shiftKey){
      const sbOptions = document.getElementById('sb-options');
      if(sbOptions && !RUN.answered){
        const firstAvailable = sbOptions.querySelector('button:not([style*=\"display: none\"])');
        if(firstAvailable){
          e.preventDefault();
          firstAvailable.click();
          return;
        }
      }
    }
  });
}

// Legacy für Inline-Aufrufer
if(typeof window!=='undefined'){
  window.startLevelWithTopic = startLevelWithTopic;
  window.startLevel = startLevel;
  window.abortLevel = abortLevel;
}
