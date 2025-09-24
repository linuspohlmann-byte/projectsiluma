// Words module: Tabelle + Sort/Filter/Selektion/Löschen
// Public API: loadWords(); zusätzlich window.loadWords für Legacy

// --- State ---
let WDATA = [];
const WCOLS = [
  {key:'sel', label:'✓', type:'sel'},
  {key:'word', label:'Wort'}, {key:'language', label:'Sprache'}, {key:'lemma', label:'Lemma'}, {key:'pos', label:'POS'},
  {key:'translation', label:'Übersetzung'}, {key:'example', label:'Beispiel'}, {key:'example_native', label:'Beispiel (Muttersprache)'},
  {key:'ipa', label:'IPA'}, {key:'gender', label:'Genus'}, {key:'plural', label:'Plural'},
  {key:'cefr', label:'CEFR'}, {key:'freq_rank', label:'Rang'},
  {key:'synonyms', label:'Synonyme'}, {key:'collocations', label:'Kollokationen'},
  {key:'tags', label:'Tags'}, {key:'note', label:'Notiz'},
  {key:'familiarity', label:'Bekanntheit'}, {key:'seen_count', label:'Gesehen'}, {key:'correct_count', label:'Korrekt'}, {key:'updated_at', label:'Zuletzt'}
];

// Function to invalidate words cache for a specific language
export function invalidateWordsCache(language) {
  const cacheKey = `words_data_${language}`;
  localStorage.removeItem(cacheKey);
  console.log(`Invalidated words cache for language: ${language}`);
  
  // Update header stats when words cache is invalidated (only for authenticated users)
  if (window.headerStats && window.headerStats.updateFromWordsData) {
    // Check if user is authenticated before updating
    const isAuthenticated = window.authManager && window.authManager.isAuthenticated();
    if (isAuthenticated) {
      window.headerStats.updateFromWordsData();
    }
  }
}
let WVIS = {};
let WSORT = {col:'updated_at', dir:'desc'};
let WFILTER = {col:'word', q:''};
let WSEL = new Set();
let WPAGE = 1;
let WPER = 20;

// --- Helpers ---
const $  = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));
function escapeHtml(s){ return String(s==null?'':s).replace(/[&<>\"']/g, c=>({"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c])); }
function wkey(c){ return 'siluma_wcol_'+c; }
function loadColVis(){ WCOLS.forEach(c=>{ if(c.key==='sel') return; try{ const v=localStorage.getItem(wkey(c.key)); if(v!==null) WVIS[c.key] = v==='1'; else WVIS[c.key]=true; }catch(_){WVIS[c.key]=true;} }); }
function saveColVis(){ WCOLS.forEach(c=>{ if(c.key==='sel') return; try{ localStorage.setItem(wkey(c.key), WVIS[c.key]?'1':'0'); }catch(_){} }); }
function normalizeCell(key, val){ if(val==null) return ''; if(Array.isArray(val)) return val.join(', '); if(typeof val==='object') return ''; return String(val); }
function updateSelCount(){ const el = $('#wb-selected'); if(el) el.textContent = `(${WSEL.size})`; const del = $('#wb-del'); if(del) del.disabled = WSEL.size===0; }
loadColVis();

// --- Toolbar ---
function renderWordsToolbar(){
  const opts = WCOLS.filter(c=>c.key!=='sel' && c.key!=='synonyms' && c.key!=='collocations' && c.key!=='tags');
  const sortCol = $('#wb-sort-col'); const sortDir = $('#wb-sort-dir');
  const filCol = $('#wb-filter-col'); const filQ = $('#wb-filter-q');
  if(sortCol) sortCol.innerHTML = opts.map(c=>`<option value="${c.key}">${c.label}</option>`).join('');
  if(filCol)  filCol.innerHTML  = opts.map(c=>`<option value="${c.key}">${c.label}</option>`).join('');
  if(sortCol) sortCol.value = WSORT.col; if(sortDir) sortDir.value = WSORT.dir;
  if(filCol)  filCol.value  = WFILTER.col; if(filQ) filQ.value = WFILTER.q;

  // Columns toggles
  const colsHost = $('#wb-cols');
  if(colsHost){
    colsHost.innerHTML='';
    WCOLS.forEach(c=>{
      if(c.key==='sel') return;
      const id='wcol_'+c.key; const wrap=document.createElement('label');
      wrap.className='row';
      wrap.innerHTML=`<input type="checkbox" id="${id}" ${WVIS[c.key]!==false?'checked':''}> ${c.label}`;
      colsHost.appendChild(wrap);
      wrap.querySelector('input').onchange=(e)=>{ WVIS[c.key]=!!e.target.checked; saveColVis(); applyWordsView(); };
    });
  }

  // Menü
  const menuBtn = $('#wb-menu'); const pop = $('#wb-pop');
  if(menuBtn && pop){
    // Remove existing event listeners to prevent duplicates
    if(window._wbMenuClick){ document.removeEventListener('click', window._wbMenuClick); }
    if(window._wbEsc){ document.removeEventListener('keydown', window._wbEsc); }
    
    // Menu button click handler
    menuBtn.onclick = (e) => {
      e.stopPropagation();
      pop.style.display = (pop.style.display === 'block') ? 'none' : 'block';
    };
    
    // Close menu when clicking outside
    window._wbMenuClick = (ev) => {
      if (pop.style.display === 'block' && !pop.contains(ev.target) && ev.target !== menuBtn) {
        pop.style.display = 'none';
      }
    };
    document.addEventListener('click', window._wbMenuClick);
    
    // ESC key handler
    window._wbEsc = (ev) => {
      if (ev.key === 'Escape' && pop.style.display === 'block') {
        pop.style.display = 'none';
      }
    };
    document.addEventListener('keydown', window._wbEsc);
  }

  // Sort/Filter
  if(sortCol) sortCol.onchange = (e)=>{ WSORT.col = e.target.value; WPAGE=1; applyWordsView(); if(pop) pop.style.display='none'; };
  if(sortDir) {
    // Handle sort direction button
    const sortDirBtn = $('#wb-sort-dir');
    if(sortDirBtn) {
      sortDirBtn.onclick = (e) => {
        WSORT.dir = WSORT.dir === 'asc' ? 'desc' : 'asc';
        sortDirBtn.textContent = WSORT.dir === 'asc' ? '↑' : '↓';
        WPAGE = 1;
        applyWordsView();
        if(pop) pop.style.display = 'none';
      };
      // Set initial button text
      sortDirBtn.textContent = WSORT.dir === 'asc' ? '↑' : '↓';
    }
  }
  if(filCol)  filCol.onchange  = (e)=>{ WFILTER.col = e.target.value; WPAGE=1; applyWordsView(); };
  if(filQ)    filQ.oninput     = (e)=>{ WFILTER.q   = e.target.value; WPAGE=1; applyWordsView(); };

  // Pager
  const bFirst = $('#wb-first'), bPrev = $('#wb-prev'), bNext = $('#wb-next'), bLast = $('#wb-last');
  if(bFirst) bFirst.onclick = ()=>{ WPAGE = 1; applyWordsView(); };
  if(bPrev)  bPrev.onclick  = ()=>{ WPAGE = Math.max(1, WPAGE-1); applyWordsView(); };
  if(bNext)  bNext.onclick  = ()=>{ WPAGE = WPAGE+1; applyWordsView(); };
  if(bLast)  bLast.onclick  = ()=>{ WPAGE = 1e9; applyWordsView(); };

  const perSel = $('#wb-per');
  if(perSel){
    perSel.value = (WPER===Infinity?'all':String(WPER));
    perSel.onchange = (e)=>{
      const v = e.target.value;
      WPER = (v==='all') ? Infinity : parseInt(v,10)||20;
      WPAGE = 1;
      applyWordsView();
    };
  }

  // Löschen
  const delBtn = $('#wb-del');
  if(delBtn){
    delBtn.onclick = async ()=>{
      if(WSEL.size===0) return;
      if(!confirm(`${WSEL.size} Einträge löschen?`)) return;
      const ids = Array.from(WSEL);
      try{
        // Get auth headers if user is logged in
        const headers = { 'Content-Type': 'application/json' };
        if (window.authManager && window.authManager.isAuthenticated()) {
          Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        // Add native language header for unauthenticated users
        const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
        headers['X-Native-Language'] = nativeLanguage;
        
        const resp = await fetch('/api/words/delete', {
          method:'POST', headers, body: JSON.stringify({ids})
        });
        const js = await resp.json();
        if(!js.success){ alert(js.error||'Fehler beim Löschen'); return; }
        // Invalidate cache and reload fresh data
        const currentLanguage = document.getElementById('target-lang')?.value || 'en';
        invalidateWordsCache(currentLanguage);
        
        const r = await fetch('/api/words', { headers });
        const rows = await r.json();
        WDATA = rows || [];
        WSEL.clear();
        updateSelCount();
        applyWordsView();
        try{ if(typeof window.refreshMaxFam==='function') window.refreshMaxFam(); }catch(_){}
        // Update header stats when words data changes (only for authenticated users)
        if (window.headerStats && window.headerStats.updateFromWordsData) {
          const isAuthenticated = window.authManager && window.authManager.isAuthenticated();
          if (isAuthenticated) {
            window.headerStats.updateFromWordsData();
          }
        }
        if(pop) pop.style.display = 'none';
      }catch(_){ alert('Netzwerkfehler beim Löschen'); }
    };
  }
}

// --- Render ---
function applyWordsView(){
  const tbody = $('#words-table tbody'); if(!tbody) return; tbody.innerHTML='';
  // Filter
  let arr = WDATA.slice();
  const q = (WFILTER.q||'').toLowerCase();
  if(q){ arr = arr.filter(row=> normalizeCell(WFILTER.col, row[WFILTER.col]).toLowerCase().includes(q)); }
  // Sort
  arr.sort((a,b)=>{
    const av = normalizeCell(WSORT.col, a[WSORT.col]);
    const bv = normalizeCell(WSORT.col, b[WSORT.col]);
    if(['freq_rank','familiarity','seen_count','correct_count'].includes(WSORT.col)){
      const an = parseFloat(av)||0, bn = parseFloat(bv)||0; return WSORT.dir==='asc' ? an-bn : bn-an;
    }
    return WSORT.dir==='asc' ? av.localeCompare(bv) : bv.localeCompare(av);
  });

  // Pagination
  const totalRows = arr.length;
  const totalPages = (WPER===Infinity) ? 1 : Math.max(1, Math.ceil(totalRows / WPER));
  if(WPAGE > totalPages) WPAGE = totalPages;
  if(WPAGE < 1) WPAGE = 1;
  const start = (WPAGE - 1) * WPER;
  const view = (WPER===Infinity) ? arr : arr.slice(start, start + WPER);

  // Select-all auf Sicht
  const allCb = $('#wb-all');
  if(allCb){
    allCb.checked = (view.length>0 && view.every(r=>WSEL.has(r.id)));
    allCb.onchange = (e)=>{ if(e.target.checked){ view.forEach(r=>WSEL.add(r.id)); } else { view.forEach(r=>WSEL.delete(r.id)); } updateSelCount(); applyWordsView(); };
  }

  // Zeilen - Compact version
  view.forEach(o=>{
    const tr = document.createElement('tr');
    
    // Selection checkbox
    const tdSel = document.createElement('td');
    tdSel.className = 'select-col';
    const cb = document.createElement('input');
    cb.type = 'checkbox';
    cb.checked = WSEL.has(o.id);
    cb.onchange = (e) => {
      if(e.target.checked) WSEL.add(o.id);
      else WSEL.delete(o.id);
      updateSelCount();
    };
    tdSel.appendChild(cb);
    tr.appendChild(tdSel);
    
    // Word
    const tdWord = document.createElement('td');
    tdWord.className = 'word-col';
    tdWord.innerHTML = `<strong>${escapeHtml(o.word||'')}</strong><br><small>${escapeHtml(o.language||'')}</small>`;
    tr.appendChild(tdWord);
    
    // Translation
    const tdTranslation = document.createElement('td');
    tdTranslation.className = 'translation-col';
    tdTranslation.innerHTML = escapeHtml(o.translation||'');
    tr.appendChild(tdTranslation);
    
    // Familiarity
    const tdFamiliarity = document.createElement('td');
    tdFamiliarity.className = 'familiarity-col';
    const familiarityLevel = Math.max(0, Math.min(5, parseInt(o.familiarity||0)));
    const familiarityText = window.tFamiliarity ? window.tFamiliarity(familiarityLevel) : ['Unknown','Seen','Learning','Familiar','Strong','Memorized'][familiarityLevel];
    const familiarityClass = ['unknown','seen','learning','familiar','strong','memorized'][familiarityLevel];
    tdFamiliarity.innerHTML = `<span class="familiarity-badge ${familiarityClass}">${familiarityText}</span>`;
    tr.appendChild(tdFamiliarity);
    
    // Example
    const tdExample = document.createElement('td');
    tdExample.className = 'example-col';
    tdExample.innerHTML = `<em>${escapeHtml(o.example||'')}</em>`;
    tr.appendChild(tdExample);
    
    // Actions
    const tdActions = document.createElement('td');
    tdActions.className = 'actions-col';
    tdActions.innerHTML = `
      <button class="action-btn" onclick="adjustFamiliarity('${o.word}', 1)" title="Bekanntheit erhöhen">+</button>
      <button class="action-btn" onclick="adjustFamiliarity('${o.word}', -1)" title="Bekanntheit verringern">-</button>
    `;
    tr.appendChild(tdActions);
    
    tbody.appendChild(tr);
  });

  // Pager-Info
  const pEl = $('#wb-page'), tEl = $('#wb-total');
  if(pEl) pEl.textContent = String(WPAGE);
  if(tEl) tEl.textContent = String(totalPages);

  updateSelCount();
  // Header-Visibility anwenden (skip select-all an Index 0)
  const headCells = $('#words-table thead tr').children; const keys = WCOLS.slice(1).map(c=>c.key);
  for(let i=0;i<keys.length;i++){ const key=keys[i]; const th=headCells[i+1]; if(th) th.style.display = WVIS[key]===false ? 'none' : ''; }
}

// --- Public ---
export async function loadWords(showWordsTab = true){
  // Get current language for filtering
  const currentLanguage = document.getElementById('target-lang')?.value || 'en';
  
  // Get auth headers if user is logged in
  const headers = {};
  if (window.authManager && window.authManager.isAuthenticated()) {
    Object.assign(headers, window.authManager.getAuthHeaders());
  }
  
  // Add native language header for unauthenticated users
  const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
  headers['X-Native-Language'] = nativeLanguage;
  
  // Always fetch fresh data from API
  let rows = null;
  const isAuthenticated = window.authManager && window.authManager.isAuthenticated();
  
  console.log(`Fetching words data for ${isAuthenticated ? 'authenticated' : 'unauthenticated'} user`);
  try {
    const r = await fetch(`/api/words?language=${encodeURIComponent(currentLanguage)}`, {
      headers
    });
    rows = await r.json();
    console.log(`API returned ${rows ? rows.length : 0} words`);
    
    // Cache the data for future use
    if (rows) {
      localStorage.setItem(`words_data_${currentLanguage}`, JSON.stringify(rows));
    }
  } catch (error) {
    console.log('Error fetching words from API:', error);
    
    // Fallback to cache for unauthenticated users
    if (!isAuthenticated) {
      const cachedWordsData = localStorage.getItem(`words_data_${currentLanguage}`);
      if (cachedWordsData) {
        try {
          rows = JSON.parse(cachedWordsData);
          console.log('Using cached words data as fallback', currentLanguage);
        } catch (parseError) {
          console.log('Error parsing cached words data:', parseError);
        }
      }
    }
  }
  
  WDATA = rows || [];
  WPAGE = 1;
  WSEL.clear();
  renderWordsToolbar();
  applyWordsView();
  if (showWordsTab) {
    try{ if(typeof window.showTab==='function') window.showTab('words'); }catch(_){}
  }
}

// Adjust familiarity for a word
export async function adjustFamiliarity(word, delta) {
  try {
    const currentLanguage = document.getElementById('target-lang')?.value || 'en';
    
    // Get auth headers if user is logged in
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    const response = await fetch(`/api/words/adjust-familiarity?language=${encodeURIComponent(currentLanguage)}`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ word, delta })
    });
    
    const result = await response.json();
    if (result.success) {
      // Reload words to reflect changes
      await loadWords();
    } else {
      console.error('Failed to adjust familiarity:', result.error);
    }
  } catch (error) {
    console.error('Error adjusting familiarity:', error);
  }
}

// Make adjustFamiliarity globally available
window.adjustFamiliarity = adjustFamiliarity;
// Make invalidateWordsCache globally available
window.invalidateWordsCache = invalidateWordsCache;

// Function to force refresh words for a specific language
export async function forceRefreshWords(language) {
  console.log(`🔄 Force refreshing words for language: ${language}`);
  
  // Clear cache for this language
  invalidateWordsCache(language);
  
  // Set the target language selector to the desired language
  const targetLangSelect = document.getElementById('target-lang');
  if (targetLangSelect) {
    targetLangSelect.value = language;
    console.log(`✅ Set target language to: ${language}`);
  }
  
  // Reload words
  await loadWords(true);
  console.log(`✅ Words refreshed for language: ${language}`);
}

// Make forceRefreshWords globally available
window.forceRefreshWords = forceRefreshWords;

// Debug function to check words status
export function debugWordsStatus() {
  const currentLanguage = document.getElementById('target-lang')?.value || 'en';
  const isAuthenticated = window.authManager && window.authManager.isAuthenticated();
  
  console.log('🔍 Words Debug Status:');
  console.log(`   Current language: ${currentLanguage}`);
  console.log(`   Authenticated: ${isAuthenticated}`);
  console.log(`   Words in memory: ${WDATA.length}`);
  console.log(`   Cache key: words_data_${currentLanguage}`);
  
  // Check cache
  const cachedData = localStorage.getItem(`words_data_${currentLanguage}`);
  if (cachedData) {
    try {
      const parsed = JSON.parse(cachedData);
      console.log(`   Cached words: ${parsed.length}`);
    } catch (e) {
      console.log(`   Cache parse error: ${e.message}`);
    }
  } else {
    console.log('   No cached data');
  }
  
  // Show sample words
  if (WDATA.length > 0) {
    console.log('   Sample words:');
    WDATA.slice(0, 5).forEach((word, i) => {
      console.log(`     ${i+1}. ${word.word} - ${word.translation} (familiarity: ${word.familiarity})`);
    });
  } else {
    console.log('   No words loaded');
  }
}

// Make debugWordsStatus globally available
window.debugWordsStatus = debugWordsStatus;

// Listen for language changes to reload words
document.addEventListener('DOMContentLoaded', () => {
  const targetLangSelect = document.getElementById('target-lang');
  if (targetLangSelect) {
    targetLangSelect.addEventListener('change', async () => {
      // Only reload if words tab is currently visible
      const wordsCard = document.getElementById('words-card');
      if (wordsCard && wordsCard.style.display !== 'none') {
        await loadWords();
      }
      
      // Update level card back data when language changes
      if (typeof window.updateLevelCardBackData === 'function') {
        window.updateLevelCardBackData();
      }
    });
  }
});

// Legacy für Inline-Nutzer
if(typeof window !== 'undefined'){ window.loadWords = loadWords; }