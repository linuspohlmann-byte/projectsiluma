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
  if (!progress) {
    // If no progress in window._customEvalProgress, but we have groupId and levelNumber,
    // try to fetch from API
    if (window._customEvalGroupId && level) {
      return {
        groupId: window._customEvalGroupId,
        levelNumber: level
      };
    }
    return null;
  }
  if (Number(progress.levelNumber) !== Number(level)) {
    // Level mismatch, but if we have groupId, we can still fetch
    if (progress.groupId) {
      return {
        groupId: progress.groupId,
        levelNumber: level
      };
    }
    return null;
  }
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
  
  // First, check for custom level progress (from window._customEvalProgress)
  const customProgress = getCustomEvalProgress(level);
  if (customProgress && customProgress.counts) {
    console.log('📊 Using custom eval progress from window._customEvalProgress:', customProgress);
    return normalizeCounts(customProgress.counts);
  }
  
  // For custom levels, try to fetch from custom_level_progress API
  if (customProgress && customProgress.groupId) {
    try {
      const headers = {};
      if (window.authManager && window.authManager.isAuthenticated()) {
        Object.assign(headers, window.authManager.getAuthHeaders());
      }
      
      const response = await fetch(`/api/custom-levels/${customProgress.groupId}/${customProgress.levelNumber}/progress-direct`, {
        headers
      });
      
      if (response.ok) {
        const progressData = await response.json();
        if (progressData.success) {
          const fam_counts = {
            0: parseInt(progressData.familiarity_0 || 0),
            1: parseInt(progressData.familiarity_1 || 0),
            2: parseInt(progressData.familiarity_2 || 0),
            3: parseInt(progressData.familiarity_3 || 0),
            4: parseInt(progressData.familiarity_4 || 0),
            5: parseInt(progressData.familiarity_5 || 0)
          };
          console.log('📊 Fetched custom level progress from API:', fam_counts);
          return normalizeCounts(fam_counts);
        }
      }
    } catch (error) {
      console.warn('⚠️ Error fetching custom level progress for evaluation:', error);
    }
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
      
      // Check if this is a practice evaluation
      if (window._eval_context === 'practice' && window._practiceEvalStats) {
        const stats = window._practiceEvalStats;
        const pct = stats.accuracy || 0;
        const C = 2*Math.PI*50;
        const off = C * (1 - pct/100);
        if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
        if(label){ label.textContent = pct + '%'; }
        console.log('📊 Practice evaluation score:', pct + '%');
        return;
      }
      
      const lvl = Number(window._lt_level || (window.RUN && window.RUN.level) || 1);
      const customProgress = getCustomEvalProgress(lvl);
      
      // Check custom progress first
      if (customProgress && typeof customProgress.scoreRatio === 'number') {
        const pct = Math.max(0, Math.min(100, Math.round(customProgress.scoreRatio * 100)));
        const C = 2*Math.PI*50;
        const off = C * (1 - pct/100);
        if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
        if(label){ label.textContent = pct + '%'; }
        return;
      }
      
      // For custom levels, try to fetch score from API if customProgress has groupId
      if (customProgress && customProgress.groupId) {
        try {
          const headers = {};
          if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
          }
          
          const response = await fetch(`/api/custom-levels/${customProgress.groupId}/${customProgress.levelNumber}/progress-direct`, {
            headers
          });
          
          if (response.ok) {
            const progressData = await response.json();
            if (progressData.success && progressData.score !== null && progressData.score !== undefined) {
              // Normalize score (can be 0-1 or 0-100)
              let scoreValue = Number(progressData.score);
              if (scoreValue > 1.0001) {
                scoreValue = scoreValue / 100; // Convert 0-100 to 0-1
              }
              const pct = Math.max(0, Math.min(100, Math.round(scoreValue * 100)));
              const C = 2*Math.PI*50;
              const off = C * (1 - pct/100);
              if(ring){ ring.setAttribute('stroke-dasharray', String(C.toFixed(2))); ring.setAttribute('stroke-dashoffset', String(off)); }
              if(label){ label.textContent = pct + '%'; }
              console.log('📊 Fetched custom level score from API:', pct + '%');
              return;
            }
          }
        } catch (error) {
          console.warn('⚠️ Error fetching custom level score for evaluation:', error);
        }
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
  // Check if this is a practice evaluation
  if (window._eval_context === 'practice' && window._practiceEvalStats) {
    const stats = window._practiceEvalStats;
    
    // Calculate familiarity counts for practiced words using the same approach as level evaluation
    let counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0};
    
    if(stats.practicedWords && Array.isArray(stats.practicedWords) && stats.practicedWords.length > 0) {
      const language = stats.language || $('#target-lang')?.value || 'en';
      
      // Fetch familiarity for all practiced words (same method as used in practice.js)
      try {
        const familiarityPromises = stats.practicedWords.map(async (word) => {
          try {
            // Use the same getFamiliarity function from practice.js if available
            if(typeof window.getFamiliarity === 'function') {
              return await window.getFamiliarity(word, language);
            }
            // Fallback: fetch word data directly (same as practice.js does)
            const headers = {};
            if (window.authManager && window.authManager.isAuthenticated()) {
              Object.assign(headers, window.authManager.getAuthHeaders());
            }
            const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
            headers['X-Native-Language'] = nativeLanguage;
            
            const r = await fetch(`/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(language)}`, { headers });
            if(r.ok) {
              const js = await r.json();
              if(js && js.familiarity !== undefined) {
                return parseInt(js.familiarity || 0, 10) || 0;
              }
            }
          } catch(e) {
            console.warn(`Failed to get familiarity for word "${word}":`, e);
          }
          return 0;
        });
        
        const familiarities = await Promise.all(familiarityPromises);
        
        // Count words by familiarity level (same logic as normalizeCounts)
        familiarities.forEach(fam => {
          const level = Math.max(0, Math.min(5, Math.floor(fam)));
          counts[level] = (counts[level] || 0) + 1;
        });
        
        // Normalize counts using the same function as level evaluation
        counts = normalizeCounts(counts);
        console.log('📊 Practice familiarity counts calculated:', counts);
      } catch(e) {
        console.warn('Failed to calculate practice familiarity counts:', e);
        counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0};
      }
    }
    
    // Update familiarity bars with animation (same as level evaluation)
    const total = Object.values(counts).reduce((sum, val) => sum + Number(val), 0);
    [0,1,2,3,4,5].forEach(s=>{
      const bar = document.querySelector(`#evaluation-card .familiarity-bar[data-status="${s}"]`);
      if(bar) {
        const countEl = bar.querySelector('.familiarity-count');
        const fillEl = bar.querySelector('.familiarity-fill');
        const count = Number(counts[s]||0);
        
        if(countEl) countEl.textContent = count;
        
        // Calculate percentage for progress bar (same as level evaluation)
        const percentage = total > 0 ? (count / total) * 100 : 0;
        
        if(fillEl) {
          // Animate the progress bar (same stagger animation as level evaluation)
          setTimeout(() => {
            fillEl.style.width = percentage + '%';
          }, s * 100);
        }
      }
    });
    
    // Use the same updateEvaluationStats function as level evaluation
    // This ensures consistent behavior between practice and level evaluations
    await updateEvaluationStats(counts);
    console.log('📊 Practice evaluation status updated (using same logic as level evaluation):', stats);
    return;
  }
  
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

// Update evaluation stats specifically for practice sessions
// Note: This function is kept for backward compatibility, but practice evaluation
// now uses updateEvaluationStats() for consistency with level evaluation
export async function updateEvaluationStatsForPractice(stats, counts = null) {
  // Delegate to the same function used by level evaluation for consistency
  if(counts && typeof counts === 'object') {
    await updateEvaluationStats(counts);
  } else {
    // Fallback: use practice stats directly
    const totalWordsEl = document.getElementById('total-words');
    const learnedWordsEl = document.getElementById('learned-words');
    const accuracyEl = document.getElementById('accuracy');
    
    if (!stats) return;
    
    const totalWords = stats.totalWords || 0;
    const learnedWords = stats.correct || 0;
    const accuracy = stats.accuracy || 0;
    
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
}

export async function updateEvaluationStats(counts) {
  const totalWordsEl = document.getElementById('total-words');
  const learnedWordsEl = document.getElementById('learned-words');
  const accuracyEl = document.getElementById('accuracy');
  
  // If no counts, try to get from custom progress
  if (!counts || Object.values(counts).reduce((sum, val) => sum + Number(val), 0) === 0) {
    const lvl = Number(window._lt_level || (window.RUN && window.RUN.level) || 1);
    const customProgress = getCustomEvalProgress(lvl);
    
    // Try to fetch from API if we have groupId
    if (customProgress && customProgress.groupId) {
      try {
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
          Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        const response = await fetch(`/api/custom-levels/${customProgress.groupId}/${customProgress.levelNumber}/progress-direct`, {
          headers
        });
        
        if (response.ok) {
          const progressData = await response.json();
          if (progressData.success) {
            const apiTotalWords = parseInt(progressData.total_words || 0);
            const apiLearnedWords = parseInt(progressData.familiarity_5 || 0);
            const apiAccuracy = apiTotalWords > 0 ? Math.round((apiLearnedWords / apiTotalWords) * 100) : 0;
            
            if (totalWordsEl) {
              animateNumber(totalWordsEl, 0, apiTotalWords, 1000);
            }
            
            if (learnedWordsEl) {
              animateNumber(learnedWordsEl, 0, apiLearnedWords, 1200);
            }
            
            if (accuracyEl) {
              animateNumber(accuracyEl, 0, apiAccuracy, 1400, '%');
            }
            
            console.log('📊 Updated evaluation stats from API:', { apiTotalWords, apiLearnedWords, apiAccuracy });
            return;
          }
        }
      } catch (error) {
        console.warn('⚠️ Error fetching custom level stats for evaluation:', error);
      }
    }
    
    // Fallback: use customProgress data if available
    if (customProgress) {
      const totalWords = customProgress.totalWords || 0;
      const learnedWords = customProgress.completedWords || 0;
      const accuracy = totalWords > 0 ? Math.round((learnedWords / totalWords) * 100) : 0;
      
      if (totalWordsEl) {
        animateNumber(totalWordsEl, 0, totalWords, 1000);
      }
      
      if (learnedWordsEl) {
        animateNumber(learnedWordsEl, 0, learnedWords, 1200);
      }
      
      if (accuracyEl) {
        animateNumber(accuracyEl, 0, accuracy, 1400, '%');
      }
      return;
    }
    
    // If no data at all, set to 0
    if (totalWordsEl) {
      totalWordsEl.textContent = '0';
    }
    if (learnedWordsEl) {
      learnedWordsEl.textContent = '0';
    }
    if (accuracyEl) {
      accuracyEl.textContent = '0%';
    }
    return;
  }
  
  // Calculate totals from counts
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
