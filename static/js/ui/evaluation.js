// --- Evaluation helpers ------------------------------------------------------
export function normalizeCounts(data){
  let counts = {0:0,1:0,2:0,3:0,4:0,5:0};
  if(!data) return counts;
  if(data.counts && typeof data.counts==='object') return normalizeCounts(data.counts);
  if(data.status_counts && typeof data.status_counts==='object') return normalizeCounts(data.status_counts);
  if(data.fam_counts && typeof data.fam_counts==='object') return normalizeCounts(data.fam_counts);
  if(Array.isArray(data)){ [0,1,2,3,4,5].forEach(i=>{ counts[i]=Number(data[i]||0); }); return counts; }
  if(typeof data==='object'){
    // direct numeric-string keys like {"0":1,...}
    let picked=false;
    [0,1,2,3,4,5].forEach(i=>{
      const k = String(i);
      if(Object.prototype.hasOwnProperty.call(data, k)){
        counts[i] = Number(data[k]||0);
        picked=true;
      }
    });
    if(picked) return counts;
    // named keys fallbacks
    const map = {unknown:0, seen:1, learning:2, familiar:3, strong:4, memorized:5,
                 unbekannt:0, gesehen:1, lernen:2, vertraut:3, stark:4, auswendig:5};
    Object.keys(map).forEach(k=>{ if(k in data) counts[ map[k] ] = Number(data[k]||0); });
    Object.keys(data).forEach(k=>{ if(/^count[0-5]$/.test(k)) counts[ Number(k.replace('count','')) ] = Number(data[k]||0); });
  }
  return counts;
}

function getCustomEvalProgress(level){
  const progress = typeof window !== 'undefined' ? window._customEvalProgress : null;
  if (!progress) return null;
  if (Number(progress.levelNumber) !== Number(level)) return null;
  return progress;
}

function normalizeScorePercent(value){
  if (value === null || value === undefined) return NaN;
  let num = Number(value);
  if (!Number.isFinite(num)) return NaN;
  if (num > 1.0001) return Math.max(0, Math.min(100, num));
  if (num < 0) num = 0;
  return Math.max(0, Math.min(100, num * 100));
}

export async function fetchStatusCounts(level, run){
  const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
  const customProgress = getCustomEvalProgress(level);
  if (customProgress && customProgress.counts) {
    return normalizeCounts(customProgress.counts);
  }
  
  if (isUserAuthenticated) {
    // For authenticated users, use cached bulk data instead of API call
    try{
      const lang = (document.getElementById('target-lang')?.value||'').trim();
      
      // Try to get data from cached bulk API response
      const cachedBulkData = localStorage.getItem(`bulk_data_${lang}`);
      if (cachedBulkData) {
        const data = JSON.parse(cachedBulkData);
        const levelData = data.levels && data.levels[level];
        if (levelData && levelData.success) {
          const raw = levelData.fam_counts || (levelData.data && levelData.data.fam_counts) || levelData;
          return normalizeCounts(raw||{});
        }
      }
    }catch(_){ 
      /* fallback to empty counts for authenticated users */ 
    }
    // If no user-specific data, return empty counts
    return {0:0,1:0,2:0,3:0,4:0,5:0};
  } else {
    // For unauthenticated users, use global data
    try{
      const r = await fetch('/api/levels/summary');
      const js = await r.json();
      if(!(js && js.success && Array.isArray(js.levels))) return {0:0,1:0,2:0,3:0,4:0,5:0};
      const rows = js.levels.filter(x=> Number(x.level) === Number(level));
      if(!rows.length) return {0:0,1:0,2:0,3:0,4:0,5:0};
      let row = null;
      if(run){ row = rows.find(x=> Number(x.run_id) === Number(run)) || null; }
      if(!row){ row = rows.sort((a,b)=> Number(b.run_id||0) - Number(a.run_id||0))[0]; }
      const fc = row && row.fam_counts;
      return normalizeCounts(fc||{});
    }catch(_){ return {0:0,1:0,2:0,3:0,4:0,5:0}; }
  }
}

export async function populateEvaluationScore(){
      const ring = document.getElementById('eval-ring');
      const label = document.getElementById('eval-ring-txt');
      const lvl = Number(window._lt_level || (window.RUN && window.RUN.level) || 1);
      const customProgress = getCustomEvalProgress(lvl);
      if (customProgress && typeof customProgress.scoreRatio === 'number') {
      const pct = Math.max(0, Math.min(100, Math.round(customProgress.scoreRatio * 100)));
        const C = 2*Math.PI*50;
        const off = C * (1 - pct/100);
        if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
        if(label){ label.textContent = pct + '%'; }
        return;
      }
      let val = NaN;
      
      // Check if user is authenticated
      const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
      
      if (isUserAuthenticated) {
        // For authenticated users, use cached bulk data instead of API call
        try{
          const targetLang = document.getElementById('target-lang')?.value || 'en';
          const cachedBulkData = localStorage.getItem(`bulk_data_${targetLang}`);
          if (cachedBulkData) {
            const data = JSON.parse(cachedBulkData);
            const levelData = data.levels && data.levels[lvl];
            if (levelData && levelData.success) {
              // Use user-specific progress if available
              if(levelData.user_progress && levelData.user_progress.score !== undefined) {
                val = Number(levelData.user_progress.score || 0);
              } else if(levelData.last_score !== undefined) {
                val = Number(levelData.last_score || 0);
              }
            }
          }
        }catch(_){ val = NaN; }
      } else {
        // For unauthenticated users, use global data
        try{
          const r = await fetch('/api/levels/summary');
          const js = await r.json();
          if(js && js.success && Array.isArray(js.levels)){
            const rows = js.levels.filter(x=>Number(x.level)===lvl && typeof x.score !== 'undefined');
            if(rows.length){
              const run = Number(window._last_run_id||0)||0;
              let row = run ? (rows.find(x=>Number(x.run_id)===run) || null) : null;
              if(!row){ row = rows.sort((a,b)=>Number(b.run_id||0)-Number(a.run_id||0))[0]; }
              val = Number((row && row.score) || 0);
            }
          }
        }catch(_){ val = NaN; }
      }
      // Optional: if backend returns no score but MC exists, still show MC-only
      if(!isFinite(val)){
        const mcOnly = (typeof window._mc_ratio === 'number') ? window._mc_ratio : NaN;
        if(isFinite(mcOnly)){
          const pct = Math.max(0, Math.min(100, mcOnly * 100));
          const C = 2*Math.PI*50; const off = C * (1 - pct/100);
          if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
          if(label){ label.textContent = Math.round(pct) + '%'; }
          return;
        }
        if(ring){ ring.setAttribute('stroke-dashoffset','314.16'); }
        if(label) label.textContent = '–';
        return;
      }
      // Use the same score as level card (Translation score only for consistency)
      // Note: MC and SB scores are not persistent, so we only use Translation score
      const pct = normalizeScorePercent(val);
      const C = 2*Math.PI*50; // 314.16 for radius 50
      const off = C * (1 - pct/100);
      if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
      if(label){ label.textContent = Math.round(pct) + '%'; }
    }
export async function populateEvaluationStatus(){
  const lvl = Number(window._lt_level || (window.RUN && window.RUN.level) || 1);
  const run = Number(window._last_run_id||0)||0;
  const counts = await fetchStatusCounts(lvl, run);
  
  // Update familiarity bars with animation
  [0,1,2,3,4,5].forEach(s=>{
    const bar = document.querySelector(`#evaluation-card .familiarity-bar[data-status="${s}"]`);
    if(bar) {
      const countEl = bar.querySelector('.familiarity-count');
      const fillEl = bar.querySelector('.familiarity-fill');
      const count = Number(counts[s]||0);
      
      if(countEl) countEl.textContent = count;
      
      // Calculate percentage for progress bar
      const total = Object.values(counts).reduce((sum, val) => sum + Number(val), 0);
      const percentage = total > 0 ? (count / total) * 100 : 0;
      
      if(fillEl) {
        // Animate the progress bar
        setTimeout(() => {
          fillEl.style.width = percentage + '%';
        }, s * 100); // Stagger animation
      }
    }
  });
  
  // Update statistics
  await updateEvaluationStats(counts);
}

export async function updateEvaluationStats(counts) {
  const totalWordsEl = document.getElementById('total-words');
  const learnedWordsEl = document.getElementById('learned-words');
  const accuracyEl = document.getElementById('accuracy');
  
  if (!counts) return;
  
  // Calculate totals
  const totalWords = Object.values(counts).reduce((sum, val) => sum + Number(val), 0);
  const learnedWords = Number(counts[5] || 0); // Familiarity level 5 = learned
  const accuracy = totalWords > 0 ? Math.round((learnedWords / totalWords) * 100) : 0;
  
  // Update elements with animation
  if (totalWordsEl) {
    animateNumber(totalWordsEl, 0, totalWords, 1000);
  }
  
  if (learnedWordsEl) {
    animateNumber(learnedWordsEl, 0, learnedWords, 1200);
  }
  
  if (accuracyEl) {
    animateNumber(accuracyEl, 0, accuracy, 1400, '%');
  }
}

function animateNumber(element, start, end, duration, suffix = '') {
  const startTime = performance.now();
  
  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    
    // Easing function for smooth animation
    const easeOut = 1 - Math.pow(1 - progress, 3);
    const current = Math.round(start + (end - start) * easeOut);
    
    element.textContent = current + suffix;
    
    if (progress < 1) {
      requestAnimationFrame(update);
    }
  }
  
  requestAnimationFrame(update);
}
export async function startPracticeFromLatestRun(lvl){
      let run_id = null;
      try{
        const r = await fetch('/api/levels/summary');
        const js = await r.json();
        if(js && js.success && Array.isArray(js.levels)){
          const rows = js.levels.filter(x=>Number(x.level)===Number(lvl) && Number(x.run_id||0)>0);
          if(rows.length){ run_id = rows.sort((a,b)=>Number(b.run_id)-Number(a.run_id))[0].run_id; }
        }
      }catch(_){ run_id = null; }
      await startPracticeForLevel(Number(lvl)||1, run_id||null);
    }
import { highlightLevel } from './levels.js';
import { showTab, setNativeDropdownVisible } from './levels.js';
export function wireEvaluationButtons(){
      const btnPractice = document.getElementById('eval-practice');
      const btnBack = document.getElementById('eval-back');
      
      if(btnPractice){ 
        // Remove any existing listeners to prevent duplicates
        btnPractice.onclick = null;
        btnPractice.onclick = async ()=>{ 
          const lvl = Number(window._lt_level||0)||1; 
          const host = document.querySelector('.topbar-right'); 
          if(host) host.style.display='none'; 
          await startPracticeFromLatestRun(lvl); 
        }; 
      }
      
      if(btnBack){ 
        // Remove any existing listeners to prevent duplicates
        btnBack.onclick = null;
        btnBack.onclick = ()=>{ 
          console.log('🔄 Back button clicked - navigating to levels overview');
          showTab('levels'); 
          renderLevels(); 
          setNativeDropdownVisible(true); 
        }; 
      }
    }
export async function showEvaluation(results, score, famCounts, wordsCount){
  try{ if(typeof window.showTab==='function') window.showTab('evaluation'); }catch(_){}
  try{
    if(results && typeof results === 'object'){
      if(typeof results.run_id !== 'undefined') window._last_run_id = Number(results.run_id)||window._last_run_id||null;
      if(typeof results.level  !== 'undefined') window._lt_level    = Number(results.level)||window._lt_level||1;
    }
  }catch(_){}

  let counts = famCounts;
  if(!counts){
    const lvl = Number(window._lt_level || (window.RUN && window.RUN.level) || 1);
    const run = Number(window._last_run_id||0)||0;
    try{ counts = await fetchStatusCounts(lvl, run); }catch(_){ counts = null; }
  }
  
  // Populate the new evaluation UI
  try{ populateEvaluationScore(); }catch(_){}
  try{ populateEvaluationStatus(); }catch(_){}
  
  // Apply localization
  try{ 
    if(typeof window.applyI18n === 'function') {
      window.applyI18n();
    }
  }catch(_){}
}

// Rating system removed - replaced with attractive evaluation display

// Wire the back button and intercept fetch to open Evaluation view
if (typeof document !== 'undefined'){
  document.addEventListener('DOMContentLoaded', ()=>{
    // Ensure buttons are wired after DOM is ready (in case wireEvaluationButtons was called too early)
    setTimeout(() => {
      wireEvaluationButtons();
    }, 100);
  });

  (function wrapFetchForEval(){
    const origFetch = window.fetch;
    function showEval(mode){
      try{ window._eval_context = mode || 'lesson'; }catch(_){}
      try{ if(typeof window.showLoader==='function') window.showLoader(); }catch(_){}
      setTimeout(()=>{
        try{ window.showTab('evaluation'); }catch(_){}
        try{ window.setNativeDropdownVisible(true); }catch(_){}
        try{ if(typeof window.hideLoader==='function') window.hideLoader(); }catch(_){}
      }, 0);
    }
    window.fetch = async function(...args){
      const req = args[0];
      const url = (typeof req === 'string') ? req : (req && req.url) || '';
      const isCountMax = url.includes('/api/words/count_max');
      const isPracticeApi = url.includes('/api/practice');
      const lessonEl = document.getElementById('lesson');
      const lessonShown = lessonEl && window.getComputedStyle(lessonEl).display !== 'none';

      if(isCountMax && lessonShown){
        try{ if(typeof window.showLoader==='function') window.showLoader(); }catch(_){}
        const checkBtn = document.getElementById('check');
        if(checkBtn){ checkBtn.disabled = true; checkBtn.style.opacity = '0.8'; }
      }

      const p = origFetch.apply(this, args);
      try{
        const res = await p;
        if(isCountMax && lessonShown){ showEval('lesson'); }
        if(isPracticeApi){
          try{
            const clone = res.clone();
            const data = await clone.json();
            const done = !!(data && (data.done || data.finished));
            const todoEmpty = !!(data && Array.isArray(data.todo) && data.todo.length===0);
            if(done || todoEmpty){
              try{ if(typeof data.run_id!=='undefined') window._last_run_id = Number(data.run_id)||window._last_run_id||null; }catch(_){}
              try{ if(typeof data.level!=='undefined')  window._lt_level    = Number(data.level)||window._lt_level||1; }catch(_){}
              const lvl = Number(window._lt_level||1); const run = Number(window._last_run_id||0)||0;

              // Persist fam_counts into the per-language level JSON on the backend
              try{
                const lang = (document.getElementById('target-lang')?.value||'').trim();
                if(run){ await fetch('/api/level/finish', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ run_id: run, language: lang }) }); }
              }catch(_){ }

              let counts=null; try{ counts = await fetchStatusCounts(lvl, run); }catch(_){}
              try{ await window.showEvaluation({run_id: run, level: lvl, results: []}, 0, counts, 0); }catch(_){ showEval('practice'); }
            }
          }catch(_){}
        }
        return res;
      }catch(err){
        try{ if(typeof window.hideLoader==='function') window.hideLoader(); }catch(_){}
        throw err;
      }
    };
  })();
}

// Legacy exposure
if(typeof window !== 'undefined'){
  window.showEvaluation = showEvaluation;
  window.populateEvaluationScore = populateEvaluationScore;
  window.populateEvaluationStatus = populateEvaluationStatus;
  window.fetchStatusCounts = fetchStatusCounts;
  window.normalizeCounts = normalizeCounts;
}
