// practice.js — Flashcard practice flow
// Public API: initPractice(), startPracticeForLevel(level, runIdOverride), startPracticeForLatestLevel()
// Exposes legacy globals: window.startPracticeForLevel, window.startPracticeForLatestLevel

import { showTab } from './levels.js';

const $ = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));

// --- Module state ------------------------------------------------------------
let PR = { id:null, curr:'', remaining:0, seen:0, total:0, _next:null, _done:false, _queue:[], _qi:0 };

const MAX_FAM = 5;
async function getFamiliarity(word, language){
  try{
    // Get auth headers if user is logged in
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    const r = await fetch(`/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(language||($('#target-lang')?.value||''))}`, { headers });
    const js = await r.json();
    const fam = parseInt(js?.familiarity||0,10)||0; return fam;
  }catch(_){ return 0; }
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
      #pr-audio-btn{cursor:pointer;border:1px solid var(--border);border-radius:24px;padding:6px 10px;display:inline-flex;align-items:center;gap:6px}
      #pr-audio-btn[disabled]{opacity:.5;cursor:not-allowed}
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
    <div id="pr-progress" class="row" style="margin-bottom:12px;justify-content:center">
      <div id="pr-progress-text" class="pill" style="font-weight:700"></div>
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
            <button id="pr-bad"  class="btn secondary" data-i18n="practice.not_good">Nicht gut</button>
            <button id="pr-okay" class="btn secondary" data-i18n="practice.okay">Okay</button>
            <button id="pr-good" class="btn secondary" data-i18n="practice.very_good">Sehr gut</button>
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
    pab.addEventListener('click',(e)=>{ e.stopPropagation(); const lang=$('#target-lang')?.value||''; if(PR.curr) ensurePracticeAudio(PR.curr, lang); });
    pab._bound=true;
  }
}

// --- Networking + flow -------------------------------------------------------
async function ensurePracticeAudio(word, language){
  try{
    const el = document.getElementById('pr-audio-el');
    if(!word || !language || !el) return;
    const r = await fetch('/api/word/tts', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({word, language}) });
    const js = await r.json();
    if(js && js.success && js.audio_url){ el.src = js.audio_url; try{ await el.play(); }catch(_){ } }
  }catch(_){}
}

function setPracticeProgress(seen, remaining, total){
  const el = document.getElementById('pr-progress-text'); if(!el) return;
  const s = Number(seen||0), r = Number(remaining||0), t = Number(total||0);
  // Use the total from API if provided, otherwise calculate as fallback
  const actualTotal = t > 0 ? t : s + r;
  // Show current position (seen + 1) when there's a current word, otherwise just seen
  const current = PR.curr ? s + 1 : s;
  el.textContent = `${current} / ${actualTotal}`;
}

function renderPracticeCard(){
  const w = PR.curr || '';
    if(PR._queue && PR._queue.length){
      const s = Math.min(PR._qi, PR._queue.length);
      const r = Math.max(0, PR._queue.length - s);
      setPracticeProgress(s, r, PR.total);
    } else {
      setPracticeProgress(PR.seen||0, PR.remaining||0, PR.total);
    }
  const frontEl = $('#pr-word'); if(frontEl) frontEl.textContent = w;
  $('#pr-ipa') && ($('#pr-ipa').textContent = '');
  $('#pr-card')?.classList.remove('flipped');
  const lang = $('#target-lang')?.value||'';
  if(w){ ensurePracticeAudio(w, lang); }
  const btn = document.getElementById('pr-audio-btn'); if(btn) btn.disabled = false;
  fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}`)
    .then(r=>r.json()).then(js=>{ const el=document.getElementById('pr-ipa'); if(el) el.textContent = js.ipa||''; }).catch(()=>{});
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
  const nat  = localStorage.getItem('siluma_native') || 'de';
  let js={};
  try{ const r = await fetch(`/api/word?word=${encodeURIComponent(w)}&language=${encodeURIComponent(lang)}`); js = await r.json(); }catch(_){ js={}; }
  const trans = js.translation||'';
  const ex = js.example||''; const exn = js.example_native||'';
  const ipa = js.ipa||''; const syn = Array.isArray(js.synonyms)? js.synonyms.join(', ') : (js.synonyms||'');
  const col = Array.isArray(js.collocations)? js.collocations.join(', ') : (js.collocations||'');
  const pos = (js.pos||'').toUpperCase(); const lem = js.lemma||'';
  
  // Get user-specific familiarity instead of global familiarity
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
  const aBtn = document.getElementById('pr-audio-btn'); if(aBtn) aBtn.disabled=false;
  // Kein Auto-Audio auf der Rückseite
}

function famLabel(n){ const L=['Unbekannt','Gesehen','Lernen','Vertraut','Stark','Auswendig']; n = parseInt(n||0,10); if(!isFinite(n)||n<0) n=0; if(n>5) n=5; return L[n]; }

async function applyPracticeStartResponse(js, fallbackLevel = 1, expectedTotal = 0, fallbackWords = []){
  const targetLang = $('#target-lang')?.value || 'en';
  PR.id = js.run_id;
  const resolvedLevel = (js.level !== undefined && js.level !== null) ? js.level : fallbackLevel;
  PR.level = resolvedLevel;
  PR.language = js.language || targetLang;
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
  PR = {id:null, curr:'', remaining:0, seen:0, total:0, _next:null, _done:false};

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

export async function startPracticeWithWordList(wordList, label = 'custom'){
  ensurePracticeUI();
  PR = {id:null, curr:'', remaining:0, seen:0, total:0, _next:null, _done:false};

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

  const targetLang = $('#target-lang')?.value || 'en';
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

  const response = await fetch('/api/practice/start', {
    method: 'POST',
    headers,
    body: JSON.stringify(payload)
  });

  let data = null;
  try{
    data = await response.json();
  }catch(_){ data = null; }

  if(!response.ok || !data || data.success === false){
    const msg = (data && (data.error || data.message)) || `HTTP ${response.status}`;
    alert('Practice-Start fehlgeschlagen: ' + msg);
    return;
  }

  await applyPracticeStartResponse(data, 0, data.total || normalizedWords.length, normalizedWords);
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
    if(js && js.done){ finishPractice(); return; }
  }catch(_){ }
  await showPractice();
}

// Helper: grade and advance
async function markAndNext(mark){
  await gradeAndFlip(mark);
  await gotoNextPractice();
}

async function gotoNextPractice(){
  if(PR && PR._done){ finishPractice(); return; }

  if(PR._queue && PR._queue.length){
    PR._qi = Math.min(PR._qi + 1, PR._queue.length);
    if(PR._qi >= PR._queue.length){
      await prebuildPracticeQueue(10);
      if(!PR._queue.length){ finishPractice(); return; }
      PR._qi = 1;
    }
    PR.curr = PR._queue[PR._qi-1];
    renderPracticeCard();
    const lang=$('#target-lang')?.value||'';
    if(PR.curr){ ensurePracticeAudio(PR.curr, lang); }
    return;
  }

  // Fallback: alte Server-Logik
  if(PR && PR._next){
    PR.curr = PR._next; PR._next=null;
    renderPracticeCard();
    const lang=$('#target-lang')?.value||'';
    if(PR.curr){ ensurePracticeAudio(PR.curr, lang); }
    return;
  }
  try{
    const levelValueRaw = (PR.level !== undefined && PR.level !== null) ? PR.level : window._lt_level;
    const levelValue = (levelValueRaw !== undefined && levelValueRaw !== null) ? levelValueRaw : 1;
    const resp = await fetch('/api/practice/grade', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ run_id: PR.id, level: levelValue, language: PR.language || $('#target-lang')?.value || 'en', word: PR.curr, mark: 'peek' }) });
    const js = await resp.json();
    const nxt = js && (js.next || js.word || js.next_word);
    if(nxt){
      let candidate = nxt;
      const lang=$('#target-lang')?.value||'';
      let attempts = 0;
      while(candidate && (await getFamiliarity(candidate, lang)) >= MAX_FAM && attempts < 200){
        const r2 = await fetch('/api/practice/grade', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ run_id: PR.id, level: levelValue, language: PR.language || $('#target-lang')?.value || 'en', word: candidate, mark: 'peek' }) });
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
      if(PR.curr){ ensurePracticeAudio(PR.curr, lang); }
      return;
    }
    finishPractice(); return;
  }catch(_){ }
  finishPractice();
}

function togglePractice(){ const card = document.getElementById('pr-card'); if(!card) return; if(card.classList.contains('flipped')){ renderPracticeCard(); const btn=document.getElementById('pr-show'); if(btn) btn.textContent=window.t ? window.t('practice.show_button', 'Anzeigen') : 'Anzeigen'; } else { showPractice().then(()=>{ const btn=document.getElementById('pr-show'); if(btn) btn.textContent=window.t ? window.t('practice.back_button', 'Zurück') : 'Zurück'; }); } }

export function initPractice(){
  // Hotkeys: Space=zeigen, 1/2/3 bewerten und weiter
  document.addEventListener('keydown',(e)=>{
    const pc = document.getElementById('practice-card');
    if(pc){ pc.classList.add('card'); }
    if(pc && pc.style.display===''){
      if(e.code==='Space'){ e.preventDefault(); togglePractice(); }
      if(e.key==='1'){ markAndNext('bad'); }
      if(e.key==='2'){ markAndNext('ok'); }
      if(e.key==='3'){ markAndNext('good'); }
    }
  });
}

function finishPractice(){
  PR._done = true;
  try{ const a = document.getElementById('pr-audio-el'); if(a){ a.pause?.(); a.removeAttribute('src'); } }catch(_){}
  const btn = document.getElementById('pr-audio-btn'); if(btn) btn.disabled = true;
  
  // Refresh level states after practice completion
  try{
    if (window.refreshLevelStates) {
      window.refreshLevelStates();
    }
  }catch(_){}
  
  // Invalidate words cache to ensure fresh data is loaded
  try{
    if (window.invalidateWordsCache) {
      const targetLang = document.getElementById('target-lang')?.value || 'en';
      window.invalidateWordsCache(targetLang);
    }
  }catch(_){}
  
  try{ window._eval_context = 'practice'; }catch(_){}
  try{ showTab('evaluation'); }catch(_){}
}

// Legacy globals
if(typeof window !== 'undefined'){
  window.startPracticeForLevel = startPracticeForLevel;
  window.startPracticeForLatestLevel = startPracticeForLatestLevel;
  window.startPracticeWithWordList = startPracticeWithWordList;
}
