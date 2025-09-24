

// topbar.js — Navigation, language/topic prefs, header widgets
// Public API: initTopbar(), refreshMaxFam()
// Depends on: levels.js (showTab, setNativeDropdownVisible), words.js (loadWords)

import { showTab, setNativeDropdownVisible } from './levels.js';
import { loadWords } from './words.js';
import { t, setLocale, applyI18n, applySelectTranslations } from '../i18n.js';
import { batchedFetch } from '../api-batcher.js';

const $ = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));

function cefrKey(){ return 'siluma_cefr_' + ($('#target-lang')?.value || 'en'); }
function loadCefrForLang(){ try{ const v = localStorage.getItem( cefrKey() ); if(v && $('#cefr')) $('#cefr').value = v; }catch(_){}}
function topicKey(){ return 'siluma_topic_' + ($('#target-lang')?.value || 'en'); }
function loadTopicForLang(){
  try{
    const key = topicKey();
    let val = localStorage.getItem(key);
    if(!val){
      const legacy = localStorage.getItem('siluma_topic');
      if(legacy) val = legacy;
      if(!val){
        const lang = $('#target-lang')?.value || 'en';
        const courseRaw = localStorage.getItem('siluma_course_'+lang);
        if(courseRaw){
          try{ const prefs = JSON.parse(courseRaw)||{}; if(typeof prefs.topic==='string' && prefs.topic) val = prefs.topic; }catch(_){ }
        }
      }
    }
    if(!val){ const sel=$('#topic'); if(sel && sel.options && sel.options.length){ val = sel.options[0].value; } }
    if(val && $('#topic')){ $('#topic').value = val; }
    if(val){ localStorage.setItem(key, val); }
  }catch(_){ }
}
function saveSessionPrefs(){
  try{
    const tgt = $('#target-lang')?.value || 'en';
    const nat = localStorage.getItem('siluma_native') || 'de';
    const cef = $('#cefr')?.value || 'none';
    const tpc = $('#topic')?.value || '';
    localStorage.setItem('siluma_target', tgt);
    localStorage.setItem('siluma_native', nat);
    localStorage.setItem( cefrKey(), cef );
    if(tpc) localStorage.setItem( topicKey(), tpc );
  }catch(_){ }
}
function restoreSettings(){
  try{
    const t = localStorage.getItem('siluma_target');
    const n = localStorage.getItem('siluma_native');
    
    // Set native language with fallback
    if(n) {
      localStorage.setItem('siluma_native', n);
    } else {
      localStorage.setItem('siluma_native', 'de'); // Default to German
    }
    
    // Set target language with fallback
    if(t){
      const sel = document.getElementById('target-lang');
      if(sel && !Array.from(sel.options).some(o=>o.value===t)){
        const o = document.createElement('option'); o.value=t; o.textContent=t; sel.appendChild(o);
      }
      $('#target-lang').value = t;
    } else {
      $('#target-lang').value = 'en'; // Default to English
    }
  }catch(_){ }
}
function restoreTopic(){
  try{
    const per = localStorage.getItem( topicKey() );
    if(per && $('#topic')){ $('#topic').value = per; return; }
    const legacy = localStorage.getItem('siluma_topic');
    if(legacy){
      localStorage.setItem( topicKey(), legacy );
      if($('#topic')) $('#topic').value = legacy;
    }
  }catch(_){ }
}

function codeToFlag(code){
  try{
    const c = String(code||'').toLowerCase();
    const map = { en:'🇬🇧', de:'🇩🇪', fr:'🇫🇷', it:'🇮🇹', es:'🇪🇸', pt:'🇵🇹', ru:'🇷🇺', tr:'🇹🇷', ka:'🇬🇪' };
    if(map[c]) return map[c];
    // try derive from region (e.g., en-US -> US)
    const region = (c.includes('-') ? c.split('-')[1] : c).toUpperCase();
    if(region.length===2){
      const A = 127397; // 0x1F1E6 - 'A'
      const flag = String.fromCodePoint(region.charCodeAt(0)+A, region.charCodeAt(1)+A);
      return flag;
    }
  }catch(_){ }
  return '🌐';
}

function ensureTargetLangOptions(){
  console.log('🔍 ensureTargetLangOptions called');
  const sel = document.getElementById('target-lang');
  if(sel){
    // Get current native language from localStorage, not from i18n system
    const currentNativeLang = localStorage.getItem('siluma_native') || 'de';
    console.log('🌍 Current native language (from localStorage):', currentNativeLang);
    console.log('🔍 DEBUGGING: i18n currentLocale:', window.currentLocale);
    
    // Load localization for current native language
    console.log('📥 Loading localization for:', currentNativeLang);
    batchedFetch(`/api/localization/${currentNativeLang}`)
      .then(data => {
        console.log('📋 Localization data received:', data);
        if(data.success && data.localization) {
          // Load available courses from server - use new courses API with native language
          console.log('🌐 Loading available courses list...');
          batchedFetch(`/api/available-courses?native_lang=${currentNativeLang}`)
            .then(langData => {
              console.log('📝 Languages data received:', langData);
              if(langData.success && langData.languages) {
                // Clear existing options
                sel.innerHTML = '';
                console.log('🧹 Cleared dropdown options');
                
                // Use languages in the order returned by API (CSV column order = population order)
                // No additional sorting needed - API already returns in correct order
                
                // Add all available courses with native names in CSV order
                console.log('🔍 DEBUGGING: Processing langData.languages:', langData.languages);
                console.log('🔍 DEBUGGING: Native language used for API call:', currentNativeLang);
                langData.languages.forEach(lang => {
                  const o = document.createElement('option');
                  o.value = lang.code;
                  o.textContent = `${lang.native_name || lang.name} (${lang.code.toUpperCase()})`;
                  o.setAttribute('aria-label', lang.native_name || lang.name);
                  sel.appendChild(o);
                  console.log(`🌍 Added course ${lang.code}: ${lang.native_name || lang.name} (native_lang: ${currentNativeLang})`);
                });
                
                                            // No "Add Language" option needed - only fully translated languages are available
                
                // Restore selected language if it was set
                const savedLang = localStorage.getItem('siluma_target');
                if(savedLang && langData.languages.some(l => l.code === savedLang)) {
                  sel.value = savedLang;
                }
                
                // Mark as localized to prevent applySelectTranslations from overriding
                sel.dataset.localized = 'true';
                console.log('✅ Dropdown localized and marked as localized');
                
                // Notify that dropdown is populated
                if (typeof window.onDropdownPopulated === 'function') {
                  window.onDropdownPopulated();
                }
              }
            })
            .catch(error => {
              console.error('❌ Error loading languages:', error);
              // Fallback to hardcoded languages if API fails
              fallbackToHardcodedLanguages();
            });
        }
      })
      .catch(error => {
        console.error('❌ Error loading localization:', error);
        // Fallback to hardcoded approach
        loadLanguagesWithFallback();
      });
  } else {
    console.log('❌ target-lang select element not found');
  }
}

function fallbackToHardcodedLanguages(){
  console.log('⚠️ fallbackToHardcodedLanguages: This function is deprecated - using API-based language loading');
  // This function is no longer needed as we use API-based language loading
  // Keep as empty function to prevent errors from existing calls
}

function loadLanguagesWithFallback(){
  console.log('⚠️ loadLanguagesWithFallback: This function is deprecated - using ensureTargetLangOptions instead');
  // This function is no longer needed as we use ensureTargetLangOptions with API-based loading
  // Keep as empty function to prevent errors from existing calls
}

async function ensureNativeLangOptions(){
  const sel = null; // Native language is now in settings
  if(!sel) return;
  
  try {
    // Check cache first
    const cachedLanguages = localStorage.getItem('available_languages');
    if (cachedLanguages) {
      try {
        const result = JSON.parse(cachedLanguages);
        if (result.success && result.languages) {
          console.log('Using cached available languages');
          populateLanguageOptions(result.languages);
          return;
        }
      } catch (error) {
        console.log('Error parsing cached languages:', error);
      }
    }
    
    // Load all available languages from API (already in CSV order)
    const response = await fetch('/api/available-languages');
    const result = await response.json();
    
    // Cache the result
    if (result.success) {
      localStorage.setItem('available_languages', JSON.stringify(result));
    }
    
    if (result.success && result.languages) {
      // Clear existing options
      sel.innerHTML = '';
      
      // Use languages in the order returned by API (CSV column order = population order)
      // No additional sorting needed - API already returns in correct order
      
      // Add all languages in CSV order
      for (const lang of result.languages) {
        const opt = document.createElement('option');
        opt.value = lang.code;
        opt.textContent = `${lang.native_name || lang.name} (${lang.code.toUpperCase()})`;
        opt.setAttribute('aria-label', lang.native_name || lang.name);
        sel.appendChild(opt);
      }
      
      console.log(`🌍 Loaded ${result.languages.length} languages for native language dropdown in CSV order`);
      
      // Restore saved native language or default to first language
      const savedNativeLang = localStorage.getItem('siluma_native');
      if (savedNativeLang && result.languages.some(l => l.code === savedNativeLang)) {
        sel.value = savedNativeLang;
        console.log('✅ Restored native language:', savedNativeLang);
      } else if (result.languages.length > 0) {
        sel.value = result.languages[0].code;
        console.log('✅ Defaulted native language to first in list:', result.languages[0].code);
      }
    } else {
      console.warn('⚠️ Failed to load languages from API, using fallback');
      // Fallback to built-in languages
      const builtins = ['de','en','fr','it','es','pt','ru','tr','ka'];
      builtins.forEach(c=>{
        const o=document.createElement('option'); 
        o.value=c; 
        o.textContent=codeToFlag(c); 
        o.setAttribute('aria-label', t(`language_names.${c}`, c.toUpperCase())); 
        sel.appendChild(o);
      });
    }
  } catch (error) {
    console.error('❌ Error loading languages:', error);
    // Fallback to built-in languages
    const builtins = ['de','en','fr','it','es','pt','ru','tr','ka'];
    builtins.forEach(c=>{
      const o=document.createElement('option'); 
      o.value=c; 
      o.textContent=codeToFlag(c); 
      o.setAttribute('aria-label', t(`language_names.${c}`, c.toUpperCase())); 
      sel.appendChild(o);
    });
  }
}

export async function refreshMaxFam(){
  const el = document.getElementById('maxfam-pill'); if(!el) return;
  const lang = document.getElementById('target-lang')?.value || 'en';
  
  // Try to get data from cached bulk API response first
  const cachedBulkData = localStorage.getItem(`bulk_data_${lang}`);
  if (cachedBulkData) {
    try {
      const data = JSON.parse(cachedBulkData);
      if (data.header_stats && data.header_stats.memorized_words !== undefined) {
        const n = data.header_stats.memorized_words;
        el.textContent = `★ Auswendig · ${lang.toUpperCase()}: ${n}`;
        return;
      }
    } catch (error) {
      console.log('Error parsing cached bulk data for maxfam:', error);
    }
  }
  
  // Fallback to API call if no cached data
  try{
    const r = await fetch(`/api/words/count_max?language=${encodeURIComponent(lang)}`);
    const js = await r.json();
    const n = Number((js && js.count) || 0);
    el.textContent = `★ Auswendig · ${lang.toUpperCase()}: ${n}`;
  }catch(_){ }
}

async function addNewLanguage(){
  const languageName = prompt('Bitte gib den Namen der neuen Sprache ein (z.B. "Schwedisch", "Polnisch"):');
  if(!languageName || languageName.trim() === '') return;
  
  try {
    // Show loading state
    const sel = document.getElementById('target-lang');
    const addOption = sel.querySelector('option[value="__add__"]');
    if(addOption) {
      addOption.textContent = '⏳ ' + t('ui.validating', 'Validiere...');
      addOption.disabled = true;
    }
    
    // Validate language with AI
    const response = await fetch('/api/language/validate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        language_name: languageName.trim(),
        native_lang: localStorage.getItem('siluma_native') || 'de'
      })
    });
    
    const result = await response.json();
    
    if(result.success && result.language_code) {
      // Refresh the language list to show the new language
      ensureTargetLangOptions();
      
      // Show success message
      alert(t('ui.language-added', 'Sprache {0} erfolgreich hinzugefügt').replace('{0}', languageName));
    } else {
      throw new Error(result.error || 'Unbekannter Fehler');
    }
  } catch(error) {
    console.error('Error adding language:', error);
    alert(t('ui.language-add-error', 'Fehler beim Hinzufügen der Sprache') + ': ' + error.message);
  } finally {
    // Restore add option
    if(addOption) {
      addOption.textContent = '➕ ' + t('ui.add-language', 'Sprache hinzufügen');
      addOption.disabled = false;
    }
  }
}

function bindNav(){
  const setActive = (id)=>{ $$('.nav button').forEach(b=> b.classList.remove('active')); if(id) $(id)?.classList.add('active'); };
  // Home button removed, using library tab instead
  // Library tab is handled by the main navigation system
  $('#show-words')?.addEventListener('click', ()=>{
    setActive('#show-words');
    showTab('words');
    try{ loadWords(); }catch(_){ }
    setNativeDropdownVisible(true);
  });
  $('#nav-alphabet')?.addEventListener('click', ()=>{
    setActive('#nav-alphabet');
    try{ if(window.startAlphabet) window.startAlphabet(); }catch(_){ }
    const abEntry=document.getElementById('alphabet-entry'); if(abEntry) abEntry.style.display='none';
  });
}

function bindPrefs(){
  // Language changes
  $('#target-lang')?.addEventListener('change', (e)=>{
    // No "Add Language" option - only fully translated languages are available
    
    loadCefrForLang();
    loadTopicForLang();
    saveSessionPrefs();
    
    // Refresh marketplace if it's currently active
    if (typeof window.refreshMarketplaceGroups === 'function') {
      window.refreshMarketplaceGroups();
    }
    try{ refreshMaxFam(); }catch(_){ }
    try{ if(typeof window.renderLevels==='function') window.renderLevels(); }catch(_){ }
    // COMPLETELY DISABLED applySelectTranslations to prevent interference with target-lang API names
    // try{ applySelectTranslations(); }catch(_){ }
  });
  // Native language change is now handled in settings
  // CEFR changes
  $('#cefr')?.addEventListener('change', (e)=>{ try{ localStorage.setItem( cefrKey(), e.target.value ); }catch(_){} saveSessionPrefs(); try{ if(typeof window.renderLevels==='function') window.renderLevels(); }catch(_){ } });
  // Topic changes (per language)
  $('#topic')?.addEventListener('change', (e)=>{ try{ localStorage.setItem( topicKey(), e.target.value ); }catch(_){ } });
  
  // Language changes - update header stats
  $('#target-lang')?.addEventListener('change', (e)=>{ 
    if(window.headerStats && window.headerStats.setLanguage) {
      window.headerStats.setLanguage(e.target.value);
    }
  });
}

export async function initTopbar(){
  // Clear any existing values first to prevent showing old values
  try {
    // Native language is now in settings
    $('#target-lang').value = '';
    $('#cefr').value = '';
    $('#topic').value = '';
  } catch(_) {}
  
  await ensureNativeLangOptions();
  
  // Restore settings from localStorage FIRST
  restoreSettings();
  restoreTopic();
  
  // Set initial UI locale from native language
  try{ 
    const nativeLangValue = localStorage.getItem('siluma_native') || 'de';
    console.log('🔍 DEBUGGING: Native lang value:', nativeLangValue);
    setLocale(nativeLangValue); 
    // Wait for translations to load before applying
    await new Promise(resolve => setTimeout(resolve, 500));
    applyI18n(); 
    // Apply translations to CEFR and topic dropdowns (but not target-lang which uses API)
    try { applySelectTranslations(); } catch(_) { }
  }catch(_){ }
  
  // THEN call ensureTargetLangOptions with the correct locale
  ensureTargetLangOptions();
  loadCefrForLang();
  saveSessionPrefs();
  bindNav();
  bindPrefs();
  refreshMaxFam();
  // initial state
  $$('.nav button').forEach(b=> b.classList.remove('active'));
  $('#nav-alphabet')?.classList.remove('active');
  // Home button removed, using library tab instead
  // Library tab is handled by the main navigation system
  
  // Notify that topbar is ready for header stats
  document.dispatchEvent(new CustomEvent('topbarReady'));
}

// Legacy exposure for inline callers
if(typeof window !== 'undefined'){
  window.refreshMaxFam = refreshMaxFam;
  window.ensureTargetLangOptions = ensureTargetLangOptions;
}
