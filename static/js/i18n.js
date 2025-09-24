// i18n.js - Internationalization utilities
// Provides translation functions and locale management

let currentLocale = 'en';
let translations = {};
let translationsLoaded = false;

// Ensure translations are available globally
window.translations = translations;
window.translationsLoaded = false;
const missingTranslationsLogged = new Set();

// Default translations for English
const defaultTranslations = {
  'en': {
    'ui.add-language': 'Add Language',
    'ui.validating': 'Validating...',
    'ui.language-added': 'Language {0} successfully added',
    'ui.language-add-error': 'Error adding language',
    'lang.en': 'ENGLISH',
    'lang.de': 'GERMAN',
    'lang.fr': 'FRENCH',
    'lang.it': 'ITALIAN',
    'lang.es': 'SPANISH',
    'lang.pt': 'PORTUGUESE',
    'lang.ru': 'RUSSIAN',
    'lang.tr': 'TURKISH',
    'lang.ka': 'GEORGIAN'
  }
};

function normalizeTranslationKey(key) {
  if (key === 'topics.daily.life') return 'topics.daily_life';
  if (key === 'topics.daily life') return 'topics.daily_life';
  return key;
}

function lookupInTable(table, normalizedKey, rawKey) {
  if (!table) return undefined;

  if (Object.prototype.hasOwnProperty.call(table, normalizedKey)) {
    const direct = table[normalizedKey];
    if (direct !== undefined && direct !== null && String(direct).trim() !== '') {
      return direct;
    }
  }

  if (normalizedKey !== rawKey && Object.prototype.hasOwnProperty.call(table, rawKey)) {
    const directRaw = table[rawKey];
    if (directRaw !== undefined && directRaw !== null && String(directRaw).trim() !== '') {
      return directRaw;
    }
  }

  const segments = normalizedKey.split('.');
  let value = table;
  for (const segment of segments) {
    if (value && Object.prototype.hasOwnProperty.call(value, segment)) {
      value = value[segment];
    } else {
      value = undefined;
      break;
    }
  }

  if (value !== undefined && value !== null && String(value).trim() !== '') {
    return value;
  }

  return undefined;
}

function resolveTranslation(key, { quiet = false } = {}) {
  const normalizedKey = normalizeTranslationKey(key);
  const tables = [];
  if (translations && Object.keys(translations).length) tables.push(translations);
  if (defaultTranslations[currentLocale]) tables.push(defaultTranslations[currentLocale]);
  if (currentLocale !== 'en' && defaultTranslations['en']) tables.push(defaultTranslations['en']);

  for (const table of tables) {
    const value = lookupInTable(table, normalizedKey, key);
    if (value !== undefined) {
      return { value, normalizedKey };
    }
  }

  if (!quiet && !missingTranslationsLogged.has(`${currentLocale}:${normalizedKey}`)) {
    console.log(`🔍 Translation not found for key: ${key} (normalized: ${normalizedKey}), current locale: ${currentLocale}`);
    console.log(`🔍 Available translations: ${Object.keys(translations || {}).length} keys`);
    console.log(`🔍 Sample available keys: ${Object.keys(translations || {}).slice(0, 5).join(', ')}`);
    missingTranslationsLogged.add(`${currentLocale}:${normalizedKey}`);
  }

  return { value: undefined, normalizedKey };
}

function parseCSVLine(line) {
  const result = [];
  let current = '';
  let insideQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      const nextChar = line[i + 1];
      if (insideQuotes && nextChar === '"') {
        current += '"';
        i += 1;
      } else {
        insideQuotes = !insideQuotes;
      }
    } else if (char === ',' && !insideQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }

  result.push(current);
  return result;
}

// Translation function
export function t(key, fallback = '') {
  try {
    // If translations are not loaded yet, return fallback to avoid console spam
    if (!translationsLoaded && Object.keys(translations).length === 0) {
      return fallback || `[${key}]`;
    }
    
    const { value } = resolveTranslation(key);
    if (value === undefined) {
      if (fallback !== undefined && fallback !== null && fallback !== '') {
        return fallback;
      }
      return `[${key}]`;
    }

    return value;
  } catch (error) {
    console.warn('Translation error for key:', key, error);
    return `[${key}]` || fallback;
  }
}

// Get translation with fallback to nested keys
export function tNested(key, fallback = '') {
  try {
    // Try direct key first
    const direct = resolveTranslation(key, { quiet: true });
    if (direct.value !== undefined) return direct.value;
    
    // Try nested keys
    const keys = key.split('.');
    if (keys.length > 1) {
      // Try to find in different categories
      const categories = ['labels', 'buttons', 'dropdowns', 'status', 'sections', 'themes', 'topics', 'cefr_levels', 'word_types', 'familiarity_levels', 'tooltips', 'messages', 'navigation'];
      
      for (const category of categories) {
        const nested = resolveTranslation(`${category}.${keys[keys.length - 1]}`, { quiet: true });
        if (nested.value !== undefined) return nested.value;
      }
    }
    
    return fallback;
  } catch (error) {
    console.warn('Nested translation error for key:', key, error);
    return fallback;
  }
}

// Get section name translation
export function tSection(sectionName, fallback = '') {
  const primary = resolveTranslation(`sections.${sectionName}`, { quiet: true });
  if (primary.value !== undefined) return primary.value;

  const alt = resolveTranslation(`level_groups.${sectionName}`, { quiet: true });
  if (alt.value !== undefined) return alt.value;

  return fallback || sectionName;
}

// Get theme translation
export function tTheme(themeName, fallback = '') {
  return t(`level_themes.${themeName}`, themeName) || fallback;
}

// Get topic translation
export function tTopic(topicName, fallback = '') {
  return t(`topics.${topicName}`, topicName) || fallback;
}

// Get CEFR level translation
export function tCefr(cefrLevel, fallback = '') {
  return t(`cefr.${cefrLevel}`, cefrLevel) || fallback;
}

// Get word type translation
export function tWordType(wordType, fallback = '') {
  return t(`word_types.${wordType}`, wordType) || fallback;
}

// Get familiarity level translation
export function tFamiliarity(level, fallback = '') {
  const levelNames = ['unknown', 'seen', 'learning', 'familiar', 'strong', 'memorized'];
  const levelName = levelNames[level] || 'unknown';
  return t(`familiarity.${levelName}`, levelName) || fallback;
}

// Track if locale is being set to prevent multiple calls
let localeSettingInProgress = false;
let localeChangeTimeout = null;

// Set locale with debouncing
export function setLocale(locale) {
  // Clear any pending locale change
  if (localeChangeTimeout) {
    clearTimeout(localeChangeTimeout);
  }
  
  // Debounce locale changes to prevent rapid successive calls
  localeChangeTimeout = setTimeout(() => {
    performLocaleChange(locale);
  }, 150); // 150ms debounce
}

function performLocaleChange(locale) {
  // Prevent multiple simultaneous calls
  if (localeSettingInProgress) {
    console.log('🌍 Locale setting already in progress, skipping...');
    return;
  }
  
  localeSettingInProgress = true;
  currentLocale = locale || 'en';
  missingTranslationsLogged.clear();
  translationsLoaded = false;
  window.translationsLoaded = false;
  selectTranslationsApplied = false;
  
  // Update global reference
  if (typeof window !== 'undefined') {
    window.currentLocale = currentLocale;
  }
  
  // First try to load from API (with caching), then fallback to CSV, then to default translations
  loadTranslations(currentLocale).then(() => {
    console.log('🌍 Locale set to (API):', currentLocale);
    console.log('📋 Loaded API translations:', Object.keys(translations).length, 'keys');
    
    // Ensure translations are available globally
    window.translations = translations;
    
    // Trigger a custom event when translations are loaded
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('translationsLoaded', { 
        detail: { locale: currentLocale, source: 'API' } 
      }));
    }
  }).catch(() => {
    // Fallback to CSV-based translations
    loadTranslationsFromCSV(currentLocale).then(() => {
      console.log('🌍 Locale set to (CSV):', currentLocale);
      
      // Ensure translations are available globally
      window.translations = translations;
      console.log('📋 Loaded CSV translations:', Object.keys(translations).length, 'keys');
      
      // Trigger a custom event when translations are loaded
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('translationsLoaded', { 
          detail: { locale: currentLocale, source: 'CSV' } 
        }));
      }
    }).catch(() => {
      // Final fallback to default translations
      translations = defaultTranslations[currentLocale] || defaultTranslations['en'];
      console.log('🌍 Locale set to (fallback):', currentLocale);
      console.log('📋 Using fallback translations:', Object.keys(translations).length, 'keys');
      
      // Trigger a custom event when translations are loaded
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('translationsLoaded', { 
          detail: { locale: currentLocale, source: 'fallback' } 
        }));
      }
    });
  });
}

// Cache for translations to avoid multiple API calls
const translationCache = new Map();
const translationCacheExpiry = new Map(); // Track cache expiry
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes cache duration
let loadingInProgress = false;

// Load translations from server
async function loadTranslations(locale) {
  try {
    // Prevent multiple simultaneous loading
    if (loadingInProgress) {
      console.log('🌍 Translation loading already in progress, skipping...');
      return false;
    }
    
    loadingInProgress = true;
    
    // Check cache first with expiry
    if (translationCache.has(locale)) {
      const cacheTime = translationCacheExpiry.get(locale);
      const now = Date.now();
      
      if (cacheTime && (now - cacheTime) < CACHE_DURATION) {
        translations = translationCache.get(locale);
        window.translations = translations;
        translationsLoaded = true;
        window.translationsLoaded = true;
        loadingInProgress = false;
        localeSettingInProgress = false;
        console.log('🌍 Using cached translations for:', locale);
        return true;
      } else {
        // Cache expired, remove it
        translationCache.delete(locale);
        translationCacheExpiry.delete(locale);
        console.log('🌍 Cache expired for:', locale);
      }
    }
    
    // First try to load from CSV-based API
    const response = await fetch(`/api/localization/${locale}`);
    const data = await response.json();
    
    if (data.success && data.localization) {
      // Set translations globally first
      translations = { ...(defaultTranslations['en'] || {}), ...data.localization };
      window.translations = translations;
      translationsLoaded = true;
      window.translationsLoaded = true;
      
      // Cache the translations with expiry
      translationCache.set(locale, translations);
      translationCacheExpiry.set(locale, Date.now());
      
      console.debug('🔍 DEBUG: API returned translations structure:', Object.keys(translations).slice(0, 10));
      console.debug('🔍 DEBUG: Sample translation for navigation.start:', translations['navigation.start']);
      console.debug('🔍 DEBUG: Full translations object:', translations);
      
      console.log('📋 Loaded API translations:', Object.keys(translations).length, 'keys');
      
      // Debug: Check if specific keys are available
      const testKeys = ['labels.level', 'topbar.logout', 'buttons.check'];
      console.log('🔍 Debug - Test keys availability:');
      testKeys.forEach(key => {
        if (translations[key]) {
          console.log(`✅ ${key}: ${translations[key]}`);
        } else {
          console.log(`❌ ${key}: NOT FOUND`);
        }
      });
      
      // Reset flags
      loadingInProgress = false;
      localeSettingInProgress = false;
      return true;
    }
    throw new Error('Invalid localization data');
  } catch (error) {
    console.warn('Failed to load translations for locale:', locale, error);
    // Reset flags on error
    loadingInProgress = false;
    localeSettingInProgress = false;
    throw error;
  }
}

// Load translations directly from CSV file
async function loadTranslationsFromCSV(locale) {
  try {
    // Read CSV file directly
    const response = await fetch('/localization_complete.csv');
    const csvText = await response.text();
    
    if (!csvText) {
      throw new Error('CSV file is empty or not found');
    }
    
    console.debug('🔍 DEBUG: CSV file loaded, length:', csvText.length);
    const csvTranslations = {};
    
    // Parse CSV content
    const lines = csvText.split('\n');
    const headerLine = (lines[0] || '').replace(/^\ufeff/, '');
    const headers = parseCSVLine(headerLine);
    
    // Find the column index for the requested language
    // Complete mapping for all languages in CSV (alphabetically sorted)
    const langMapping = {
      'aa': 'aa', 'ab': 'ab', 'ae': 'ae', 'af': 'af', 'ak': 'ak', 'am': 'am', 'an': 'an', 'ar': 'ar', 'as': 'as', 'av': 'av', 'ay': 'ay', 'az': 'az',
      'ba': 'ba', 'be': 'be', 'bg': 'bg', 'bh': 'bh', 'bi': 'bi', 'bm': 'bm', 'bn': 'bn', 'bo': 'bo', 'br': 'br', 'bs': 'bs',
      'ca': 'ca', 'ce': 'ce', 'ch': 'ch', 'co': 'co', 'cr': 'cr', 'cs': 'cs', 'cu': 'cu', 'cv': 'cv', 'cy': 'cy',
      'da': 'da', 'de': 'de', 'dv': 'dv', 'dz': 'dz',
      'ee': 'ee', 'el': 'el', 'en': 'en', 'eo': 'eo', 'es': 'es', 'et': 'et', 'eu': 'eu',
      'fa': 'fa', 'ff': 'ff', 'fi': 'fi', 'fj': 'fj', 'fo': 'fo', 'fr': 'fr', 'fy': 'fy',
      'ga': 'ga', 'gd': 'gd', 'gl': 'gl', 'gn': 'gn', 'gu': 'gu', 'gv': 'gv',
      'ha': 'ha', 'he': 'he', 'hi': 'hi', 'ho': 'ho', 'hr': 'hr', 'ht': 'ht', 'hu': 'hu', 'hy': 'hy', 'hz': 'hz',
      'ia': 'ia', 'id': 'id', 'ie': 'ie', 'ig': 'ig', 'ii': 'ii', 'ik': 'ik', 'io': 'io', 'is': 'is', 'it': 'it', 'iu': 'iu',
      'ja': 'ja', 'jv': 'jv',
      'ka': 'ka', 'kg': 'kg', 'ki': 'ki', 'kj': 'kj', 'kk': 'kk', 'kl': 'kl', 'km': 'km', 'kn': 'kn', 'ko': 'ko', 'kr': 'kr', 'ks': 'ks', 'ku': 'ku', 'kv': 'kv', 'kw': 'kw', 'ky': 'ky',
      'la': 'la', 'lb': 'lb', 'lg': 'lg', 'li': 'li', 'ln': 'ln', 'lo': 'lo', 'lt': 'lt', 'lu': 'lu', 'lv': 'lv',
      'mg': 'mg', 'mh': 'mh', 'mi': 'mi', 'mk': 'mk', 'ml': 'ml', 'mn': 'mn', 'mr': 'mr', 'ms': 'ms', 'mt': 'mt', 'my': 'my',
      'na': 'na', 'nb': 'nb', 'nd': 'nd', 'ne': 'ne', 'ng': 'ng', 'nl': 'nl', 'nn': 'nn', 'no': 'no', 'nr': 'nr', 'nv': 'nv', 'ny': 'ny',
      'oc': 'oc', 'oj': 'oj', 'om': 'om', 'or': 'or', 'os': 'os',
      'pa': 'pa', 'pi': 'pi', 'pl': 'pl', 'ps': 'ps', 'pt': 'pt',
      'qu': 'qu',
      'rm': 'rm', 'rn': 'rn', 'ro': 'ro', 'ru': 'ru', 'rw': 'rw',
      'sa': 'sa', 'sc': 'sc', 'sd': 'sd', 'se': 'se', 'sg': 'sg', 'si': 'si', 'sk': 'sk', 'sl': 'sl', 'sm': 'sm', 'sn': 'sn', 'so': 'so', 'sq': 'sq', 'sr': 'sr', 'ss': 'ss', 'st': 'st', 'su': 'su', 'sv': 'sv', 'sw': 'sw',
      'ta': 'ta', 'te': 'te', 'tg': 'tg', 'th': 'th', 'ti': 'ti', 'tk': 'tk', 'tl': 'tl', 'tn': 'tn', 'to': 'to', 'tr': 'tr', 'ts': 'ts', 'tt': 'tt', 'tw': 'tw', 'ty': 'ty',
      'ug': 'ug', 'uk': 'uk', 'ur': 'ur', 'uz': 'uz',
      've': 've', 'vi': 'vi', 'vo': 'vo',
      'wa': 'wa', 'wo': 'wo',
      'xh': 'xh',
      'yi': 'yi', 'yo': 'yo',
      'za': 'za', 'zh': 'zh', 'zu': 'zu'
    };
    
    const targetColumn = langMapping[locale] || 'en';
    const keyIndex = headers.indexOf('KEY');
    const targetIndex = headers.indexOf(targetColumn);
    
    if (keyIndex === -1 || targetIndex === -1) {
      throw new Error(`Required columns not found: KEY=${keyIndex}, ${targetColumn}=${targetIndex}`);
    }
    
    console.debug('🔍 DEBUG: Looking for locale:', locale, 'in column:', targetColumn);
    
    // Process each line
    for (let i = 1; i < lines.length; i++) {
      const rawLine = lines[i];
      if (!rawLine) continue;

      if (!rawLine.trim()) continue;
      const parsed = parseCSVLine(rawLine.replace(/\r$/, ''));
      if (parsed.length <= Math.max(keyIndex, targetIndex)) continue;

      const key = parsed[keyIndex] ? parsed[keyIndex].trim() : '';
      const translation = parsed[targetIndex] ? parsed[targetIndex].trim() : '';

      if (key && translation && translation !== '#VALUE!' && translation !== '___') {
        csvTranslations[key] = translation;
      }
    }

    translations = { ...(defaultTranslations['en'] || {}), ...csvTranslations };
    window.translations = translations;
    translationsLoaded = true;
    window.translationsLoaded = true;
    translationCache.set(locale, translations);
    console.debug('🔍 DEBUG: CSV returned translations structure:', Object.keys(translations).slice(0, 10));
    console.debug('🔍 DEBUG: Sample translation for navigation.start:', translations['navigation.start']);
    return true;
  } catch (error) {
    console.warn('Failed to load CSV translations for locale:', locale, error);
    throw error;
  }
}

// Debouncing for applyI18n to prevent excessive calls
let applyI18nTimeout = null;

// Apply i18n to the page
export function applyI18n() {
  // Clear existing timeout
  if (applyI18nTimeout) {
    clearTimeout(applyI18nTimeout);
  }
  
  // Debounce the function call
  applyI18nTimeout = setTimeout(() => {
    try {
      // Find elements with data-i18n attribute and translate them
      // BUT skip target-lang options if they are already localized
      const elements = document.querySelectorAll('[data-i18n]');
      
      elements.forEach(el => {
        try {
          const key = el.getAttribute('data-i18n');
          if (!key) return;

          // Skip target-lang options if they are already localized
          if (el.closest('#target-lang') && el.closest('#target-lang').dataset.localized) {
            return;
          }

          const { value } = resolveTranslation(key, { quiet: true });
          if (value === undefined) {
            return;
          }

          if (el.children.length === 1 && el.children[0].tagName === 'SPAN') {
            el.children[0].textContent = value;
          } else {
            el.textContent = value;
          }
        } catch (err) {
          console.warn('applyI18n translation error:', err);
        }
      });
      
      // Find elements with data-i18n-placeholder attribute and translate placeholders
      const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
      placeholderElements.forEach(el => {
        const key = el.getAttribute('data-i18n-placeholder');
        if (key) {
          const { value } = resolveTranslation(key, { quiet: true });
          if (value !== undefined) {
            el.placeholder = value;
          }
        }
      });
      
      // Apply translations to common elements
      applyCommonTranslations();
      
      // Apply translations to select elements
      applySelectTranslations();
      
      // Update all dynamic content that might need translation
      updateDynamicContent();
    } catch (error) {
      console.warn('Error applying i18n:', error);
    }
  }, 100); // Debounce delay
}

// Apply translations to common elements
function applyCommonTranslations() {
  // Navigation buttons - only translate if they don't have data-i18n attribute
  // Home button removed, using library tab instead
  // Library tab is handled by the main navigation system
  
  const navAlphabetBtn = document.getElementById('nav-alphabet');
  if (navAlphabetBtn && !navAlphabetBtn.hasAttribute('data-i18n')) {
    navAlphabetBtn.textContent = t('navigation.alphabet', 'Alphabet');
  }
  
  const showWordsBtn = document.getElementById('show-words');
  if (showWordsBtn && !showWordsBtn.hasAttribute('data-i18n')) {
    showWordsBtn.textContent = t('navigation.words', 'Words');
  }
  
  // Course labels
  const courseLabel = document.querySelector('label[for="target-lang"]');
  if (courseLabel) courseLabel.textContent = t('labels.course', 'Zielsprache');
  
  const levelLabel = document.querySelector('label[for="cefr"]');
  if (levelLabel) levelLabel.textContent = t('labels.level', 'Sprachniveau');
  
  const motivationLabel = document.querySelector('label[for="topic"]');
  if (motivationLabel) motivationLabel.textContent = t('labels.motivation', 'Motivation');
  
  // Translation placeholder
  const translationInput = document.getElementById('user-translation');
  if (translationInput) translationInput.placeholder = t('labels.translation', 'Ihre Übersetzung hier...');
  
  // Buttons
  const startBtn = document.getElementById('lt-start');
  if (startBtn) startBtn.textContent = t('buttons.start', 'Start');
  
  const repeatBtn = document.getElementById('lt-repeat');
  if (repeatBtn) repeatBtn.textContent = t('buttons.repeat', 'Repeat');

  const settingsLabel = document.querySelector('#settings-btn .btn-text');
  if (settingsLabel) settingsLabel.textContent = t('topbar.settings', settingsLabel.textContent);

  const logoutLabel = document.querySelector('#logout-btn .btn-text');
  if (logoutLabel) logoutLabel.textContent = t('topbar.logout', logoutLabel.textContent);
  
  const checkBtn = document.getElementById('check');
  if (checkBtn) checkBtn.textContent = t('buttons.check', 'Check Answer');
  
  const abortBtn = document.getElementById('abort-level');
  if (abortBtn) abortBtn.textContent = t('buttons.abort', 'Cancel');
  
  // Evaluation
  const evalTitle = document.querySelector('.eval-title');
  if (evalTitle) evalTitle.textContent = t('status.level_completed', 'Level completed 🎉');
  
  // Practice button
  const practiceBtn = document.getElementById('lt-practice');
  if (practiceBtn) practiceBtn.textContent = t('buttons.practice', 'Practice');
  
  // Back button
  const backBtn = document.getElementById('eval-back');
  if (backBtn) backBtn.textContent = t('buttons.back', 'Back to Overview');
  
  // Difficult words practice button
  const diffWordsBtn = document.getElementById('eval-practice');
  if (diffWordsBtn) diffWordsBtn.textContent = t('buttons.difficult_words_practice', 'Practice Difficult Words');

  try {
    if (typeof window.updatePracticeActionLabels === 'function') {
      window.updatePracticeActionLabels();
    }
  } catch (_) {}
}

// Update dynamic content that might need translation
function updateDynamicContent() {
  try {
    // Update level cards if they exist
    const levelCards = document.querySelectorAll('.level-node');
    levelCards.forEach(card => {
      // Update level status text
      const statusElement = card.querySelector('.level-status');
      if (statusElement) {
        const status = statusElement.textContent.toLowerCase();
        if (status.includes('available')) {
          statusElement.textContent = t('status.available', 'Available');
        } else if (status.includes('completed')) {
          statusElement.textContent = t('status.completed', 'Completed');
        } else if (status.includes('locked')) {
          statusElement.textContent = t('status.locked', 'Locked');
        }
      }
    });
    
    // Update tooltip content
    const tooltipTitle = document.getElementById('tt-title');
    if (tooltipTitle && tooltipTitle.textContent) {
      // Tooltip title is usually a word, so we don't translate it
      // But we can update labels around it
    }
    
    
    // Update words table headers
    const tableHeaders = document.querySelectorAll('#words-table th');
    tableHeaders.forEach(header => {
      const text = header.textContent.toLowerCase();
      if (text.includes('wort')) {
        header.textContent = t('table.word', 'Word');
      } else if (text.includes('sprache')) {
        header.textContent = t('table.language', 'Language');
      } else if (text.includes('lemma')) {
        header.textContent = t('table.lemma', 'Lemma');
      } else if (text.includes('pos')) {
        header.textContent = t('table.pos', 'POS');
      } else if (text.includes('übersetzung')) {
        header.textContent = t('table.translation', 'Translation');
      } else if (text.includes('beispiel')) {
        header.textContent = t('table.example', 'Example');
      } else if (text.includes('bekanntheit')) {
        header.textContent = t('table.familiarity', 'Familiarity');
      }
    });
    
    console.log('🔄 Dynamic content updated for new language');
  } catch (error) {
    console.warn('Error updating dynamic content:', error);
  }
}

// Apply translations to select elements
// Track if select translations have been applied
let selectTranslationsApplied = false;

export function applySelectTranslations() {
  try {
    // COMPLETELY SKIP target-lang dropdown - it now uses API names directly
    const targetLangSelect = document.getElementById('target-lang');
    if (targetLangSelect) {
      if (!selectTranslationsApplied) {
        console.log('🔍 applySelectTranslations: COMPLETELY SKIPPING target-lang dropdown (uses API names)');
        selectTranslationsApplied = true;
      }
      // Mark as localized to prevent any future interference
      targetLangSelect.dataset.localized = 'true';
      // Continue to process other dropdowns (CEFR, topic)
    }
    
    // Apply native language dropdown translations
    const nativeLangSelect = document.getElementById('settings-native-lang');
    if (nativeLangSelect) {
      const options = nativeLangSelect.querySelectorAll('option');
      options.forEach(option => {
        const langCode = option.value;
        if (langCode) {
          const translatedName = t(`language_names.${langCode}`, option.textContent);
          option.textContent = translatedName;
        }
      });
    }
    
    // Apply CEFR level translations
    const cefrSelect = document.getElementById('cefr');
    if (cefrSelect) {
      const options = cefrSelect.querySelectorAll('option');
      options.forEach(option => {
        const cefrLevel = option.value;
        if (cefrLevel) {
          const translatedLevel = tCefr(cefrLevel, option.textContent);
          option.textContent = translatedLevel;
        }
      });
    }
    
    // Apply topic translations
    const topicSelect = document.getElementById('topic');
    if (topicSelect) {
      const options = topicSelect.querySelectorAll('option');
      options.forEach(option => {
        const topicValue = option.value;
        if (topicValue) {
          const translatedTopic = tTopic(topicValue, option.textContent);
          option.textContent = translatedTopic;
        }
      });
    }
  } catch (error) {
    console.warn('Error applying select translations:', error);
  }
}

// Initialize with default locale
setLocale('en');

// Expose globally for legacy code
if (typeof window !== 'undefined') {
  window.t = t;
  window.tNested = tNested;
  window.tSection = tSection;
  window.tTheme = tTheme;
  window.tTopic = tTopic;
  window.tCefr = tCefr;
  window.tWordType = tWordType;
  window.tFamiliarity = tFamiliarity;
  window.setLocale = setLocale;
  window.applyI18n = applyI18n;
  window.applySelectTranslations = applySelectTranslations;
  window.currentLocale = currentLocale;
} 

// Update dropdown translations when locale changes
export function updateDropdownTranslations() {
  try {
    const targetLangSelect = document.getElementById('target-lang');
    if (targetLangSelect) {
      console.log('🔄 updateDropdownTranslations: Skipping target-lang dropdown (uses API names)');
      // Skip target-lang dropdown - it uses API names directly
      // Only apply to other dropdowns that need translation updates
    }
  } catch (error) {
    console.warn('Error updating dropdown translations:', error);
  }
} 
