// i18n-optimized.js - Optimierte Internationalisierung
// Performante und stabile Lokalisierungs-Initialisierung

class LocalizationManager {
  constructor() {
    this.currentLocale = 'en';
    this.translations = {};
    this.cache = new Map();
    this.loadingPromises = new Map();
    this.initialized = false;
    this.missingTranslationsLogged = new Set();
    
    // Default translations for English
    this.defaultTranslations = {
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
  }

  // Optimierte Initialisierung - lädt alle Sprachen auf einmal
  async initialize() {
    if (this.initialized) return;
    
    console.log('🚀 Initializing optimized localization system...');
    
    try {
      // Lade alle verfügbaren Sprachen parallel
      await this.loadAllLanguages();
      this.initialized = true;
      console.log('✅ Localization system initialized successfully');
    } catch (error) {
      console.warn('⚠️ Failed to initialize localization system:', error);
      // Fallback zu Standard-Übersetzungen
      this.translations = { ...this.defaultTranslations['en'] };
      this.initialized = true;
    }
  }

  // Lädt alle Sprachen parallel für maximale Performance
  async loadAllLanguages() {
    const languages = [
      'en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'tr', 'ka', 'ar', 'zh', 'ja', 'ko',
      'hi', 'bn', 'ur', 'id', 'ms', 'th', 'vi', 'pl', 'uk', 'ro', 'nl', 'sv', 'da',
      'no', 'fi', 'he', 'fa', 'gu', 'kn', 'ml', 'ta', 'te', 'pa', 'or', 'as', 'ne',
      'si', 'my', 'km', 'lo', 'hy', 'az', 'kk', 'ky', 'uz', 'tg', 'mn', 'ps', 'sd',
      'ks', 'cs', 'sk', 'sl', 'hr', 'sr', 'bs', 'mk', 'bg', 'sq', 'el', 'mt', 'cy',
      'ga', 'gd', 'br', 'co', 'ca', 'gl', 'eu', 'is', 'fo', 'lb', 'li', 'fy', 'af',
      'et', 'lv', 'lt', 'ha', 'yo', 'ig', 'ff', 'am', 'om', 'ti', 'so', 'zu', 'xh',
      'st', 'tn', 'ss', 'nr', 'nd', 've', 'ts', 'sn', 'ny', 'rw', 'rn', 'lg', 'mg',
      'wo', 'tl', 'jv', 'su', 'qu', 'gn', 'ay', 'sm', 'to', 'ty', 'mi', 'fj', 'bi',
      'eo', 'ia', 'ie', 'io', 'vo', 'la', 'cu', 'pi', 'sa', 'aa', 'ab', 'ae', 'ak',
      'an', 'av', 'ba', 'be', 'bh', 'bm', 'ce', 'ch', 'cr', 'cv', 'dz', 'ee', 'ht',
      'hz', 'ii', 'ik', 'iu', 'kg', 'ki', 'kj', 'kl', 'kr', 'ku', 'kv', 'kw', 'ln',
      'lu', 'mh', 'na', 'nb', 'ng', 'nn', 'nv', 'oc', 'oj', 'om', 'os', 'rm', 'sc',
      'se', 'sg', 'tk', 'tt', 'tw', 'ug', 'wa', 'yi', 'za'
    ];
    const uniqueLanguages = Array.from(new Set(languages.map(code => code.split('.')[0])));
    const fetches = uniqueLanguages.map(lang => this.fetchLanguageFromApi(lang));
    const results = await Promise.allSettled(fetches);
    results.forEach((result, index) => {
      const lang = uniqueLanguages[index];
      if (result.status === 'fulfilled' && result.value) {
        this.cache.set(lang, result.value);
      } else {
        console.warn(`⚠️ Failed to preload localization for ${lang}:`, result.reason);
      }
    });
  }

  async fetchLanguageFromApi(lang) {
    if (this.cache.has(lang)) {
      return this.cache.get(lang);
    }
    const response = await fetch(`/api/localization/${lang}`);
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }
    const data = await response.json();
    if (!data.success || !data.localization) {
      throw new Error('Invalid localization payload');
    }
    const merged = { ...(this.defaultTranslations['en'] || {}), ...data.localization };
    this.cache.set(lang, merged);
    return merged;
  }

  // Setzt Locale mit optimierter Performance
  async setLocale(locale) {
    const targetLocale = locale || 'en';
    
    // Wenn bereits geladen, sofort zurückgeben
    if (this.currentLocale === targetLocale && this.translations && Object.keys(this.translations).length > 0) {
      return Promise.resolve();
    }
    
    // Wenn bereits geladen wird, warten
    if (this.loadingPromises.has(targetLocale)) {
      return this.loadingPromises.get(targetLocale);
    }
    
    // Neue Übersetzungen laden
    const loadPromise = this.loadLocale(targetLocale);
    this.loadingPromises.set(targetLocale, loadPromise);
    
    try {
      await loadPromise;
      this.currentLocale = targetLocale;
      this.loadingPromises.delete(targetLocale);
      
      // Event für UI-Updates
      if (typeof window !== 'undefined') {
        window.dispatchEvent(new CustomEvent('translationsLoaded', { 
          detail: { locale: targetLocale, source: 'optimized' } 
        }));
      }
    } catch (error) {
      this.loadingPromises.delete(targetLocale);
      throw error;
    }
  }

  // Lädt spezifische Locale
  async loadLocale(locale) {
    try {
      const translations = await this.fetchLanguageFromApi(locale);
      this.translations = translations;
    } catch (error) {
      console.warn(`⚠️ Falling back to default translations for ${locale}:`, error);
      this.translations = this.defaultTranslations[locale] || this.defaultTranslations['en'] || {};
    }
  }

  // Übersetzungsfunktion
  t(key, fallback = null) {
    if (!key) return fallback || key;
    
    const normalizedKey = this.normalizeTranslationKey(key);
    
    // Suche in aktuellen Übersetzungen
    let value = this.lookupInTable(this.translations, normalizedKey, key);
    if (value !== undefined) return value;
    
    // Fallback zu Standard-Übersetzungen
    if (this.currentLocale !== 'en') {
      value = this.lookupInTable(this.defaultTranslations['en'], normalizedKey, key);
      if (value !== undefined) return value;
    }
    
    // Log missing translation
    if (!this.missingTranslationsLogged.has(`${this.currentLocale}:${normalizedKey}`)) {
      console.log(`🔍 Translation not found for key: ${key} (normalized: ${normalizedKey}), current locale: ${this.currentLocale}`);
      this.missingTranslationsLogged.add(`${this.currentLocale}:${normalizedKey}`);
    }
    
    return fallback || key;
  }

  // Hilfsfunktionen
  normalizeTranslationKey(key) {
    if (key === 'topics.daily.life') return 'topics.daily_life';
    if (key === 'topics.daily life') return 'topics.daily_life';
    return key;
  }

  lookupInTable(table, normalizedKey, rawKey) {
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

  // Apply i18n to DOM elements
  applyI18n() {
    try {
      const elements = document.querySelectorAll('[data-i18n]');
      
      elements.forEach(element => {
        const key = element.getAttribute('data-i18n');
        if (key) {
          const translation = this.t(key);
          if (translation && translation !== key) {
            element.textContent = translation;
          }
        }
      });
      
      // Handle placeholder translations
      const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
      placeholderElements.forEach(element => {
        const key = element.getAttribute('data-i18n-placeholder');
        if (key) {
          const translation = this.t(key);
          if (translation && translation !== key) {
            element.placeholder = translation;
          }
        }
      });
    } catch (error) {
      console.warn('applyI18n error:', error);
    }
  }

  // Apply select translations
  applySelectTranslations() {
    try {
      const selectElements = document.querySelectorAll('select[data-i18n-options]');
      
      selectElements.forEach(select => {
        const options = select.querySelectorAll('option[data-i18n]');
        options.forEach(option => {
          const key = option.getAttribute('data-i18n');
          if (key) {
            const translation = this.t(key);
            if (translation && translation !== key) {
              option.textContent = translation;
            }
          }
        });
      });
    } catch (error) {
      console.warn('applySelectTranslations error:', error);
    }
  }
}

// Globale Instanz
const localizationManager = new LocalizationManager();

// Exportiere Funktionen für Kompatibilität
export function setLocale(locale) {
  return localizationManager.setLocale(locale);
}

export function t(key, fallback = null) {
  return localizationManager.t(key, fallback);
}

export function applyI18n() {
  return localizationManager.applyI18n();
}

export function applySelectTranslations() {
  return localizationManager.applySelectTranslations();
}

export function initializeLocalization() {
  return localizationManager.initialize();
}

// Initialisiere beim Laden
if (typeof window !== 'undefined') {
  // Expose globally
  window.t = t;
  window.setLocale = setLocale;
  window.applyI18n = applyI18n;
  window.applySelectTranslations = applySelectTranslations;
  window.initializeLocalization = initializeLocalization;
  window.localizationManager = localizationManager;
  
  // Initialisiere automatisch
  initializeLocalization();
}
