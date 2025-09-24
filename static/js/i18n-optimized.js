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
    
    // Language mapping for CSV columns
    this.langMapping = {
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
    const languages = ['en', 'de', 'fr', 'es', 'it', 'pt', 'ru', 'tr', 'ka', 'ar', 'zh', 'ja', 'ko', 'hi', 'bn', 'ur', 'id', 'ms', 'th', 'vi', 'pl', 'uk', 'ro', 'nl', 'sv', 'da', 'no', 'fi', 'he', 'fa', 'gu', 'kn', 'ml', 'ta', 'te', 'pa', 'or', 'as', 'ne', 'si', 'my', 'km', 'lo', 'bo', 'dz', 'hy', 'az', 'kk', 'ky', 'uz', 'tg', 'mn', 'ps', 'sd', 'ks', 'cs', 'sk', 'sl', 'hr', 'sr', 'bs', 'mk', 'bg', 'sq', 'el', 'mt', 'cy', 'ga', 'gd', 'gv', 'br', 'co', 'ca', 'gl', 'eu', 'is', 'fo', 'lb', 'li', 'fy', 'af', 'et', 'lv', 'lt', 'ha', 'yo', 'ig', 'ff', 'am', 'om', 'ti', 'so', 'zu', 'xh', 'st', 'tn', 'ss', 'nr', 'nd', 've', 'ts', 'sn', 'ny', 'rw', 'rn', 'lg', 'mg', 'wo', 'tl', 'jv', 'su', 'qu', 'gn', 'ay', 'sm', 'to', 'ty', 'mi', 'fj', 'bi', 'eo', 'ia', 'ie', 'io', 'vo', 'la', 'cu', 'pi', 'sa', 'aa', 'ab', 'ae', 'ak', 'an', 'av', 'ba', 'be', 'bh', 'bi.1', 'bm', 'bo.1', 'ce', 'ch', 'cr', 'cv', 'dz', 'ee', 'eo.1', 'es.1', 'et.1', 'eu.1', 'fa.1', 'ff.1', 'fi.1', 'fj.1', 'fo.1', 'fy.1', 'ga.1', 'gd.1', 'gl.1', 'gn.1', 'gu.1', 'gv.1', 'ha.1', 'he.1', 'hi.1', 'ho', 'hr.1', 'ht', 'hu', 'hz', 'ia.1', 'id.1', 'ie.1', 'ig.1', 'ii', 'ik', 'io.1', 'is.1', 'it.1', 'iu', 'jv.1', 'kg', 'ki', 'kj', 'kl', 'km.1', 'kn.1', 'kr', 'ks.1', 'ku', 'kv', 'kw', 'la.1', 'lb.1', 'lg.1', 'li.1', 'ln', 'lo.1', 'lt.1', 'lu', 'lv.1', 'mh', 'mi.1', 'mk.1', 'mn.1', 'ms.1', 'mt.1', 'my.1', 'na', 'nb', 'nd.1', 'ne.1', 'ng', 'nn', 'nr.1', 'nv', 'ny.1', 'oc', 'oj', 'om.1', 'or.1', 'os', 'pa.1', 'pi.1', 'pl.1', 'ps.1', 'pt.1', 'qu.1', 'rm', 'rn.1', 'ro.1', 'ru.1', 'rw.1', 'sa.1', 'sc', 'sd.1', 'se', 'sg', 'si.1', 'sk.1', 'sl.1', 'sm.1', 'sn.1', 'so.1', 'sq.1', 'sr.1', 'ss.1', 'st.1', 'su.1', 'sv.1', 'sw.1', 'ta.1', 'te.1', 'tg.1', 'th.1', 'ti.1', 'tk', 'tl.1', 'tn.1', 'to.1', 'tr.1', 'ts.1', 'tt', 'tw', 'ty.1', 'ug', 'uk.1', 'ur.1', 'uz.1', 've.1', 'vi.1', 'vo.1', 'wa', 'wo.1', 'xh.1', 'yi', 'yo.1', 'za', 'zu.1'];
    
    // Lade CSV-Datei einmal und parse alle Sprachen
    const csvData = await this.loadCSVData();
    if (csvData) {
      this.parseAllLanguages(csvData, languages);
    }
  }

  // Lädt CSV-Datei einmal und cached sie
  async loadCSVData() {
    try {
      const response = await fetch('/localization_complete.csv');
      if (!response.ok) throw new Error('Failed to load CSV');
      
      const csvText = await response.text();
      if (!csvText) throw new Error('CSV file is empty');
      
      return this.parseCSV(csvText);
    } catch (error) {
      console.warn('Failed to load CSV data:', error);
      return null;
    }
  }

  // Parst CSV-Datei in strukturiertes Format
  parseCSV(csvText) {
    const lines = csvText.split('\n');
    const headerLine = (lines[0] || '').replace(/^\ufeff/, '');
    const headers = this.parseCSVLine(headerLine);
    
    const data = [];
    for (let i = 1; i < lines.length; i++) {
      const line = lines[i];
      if (!line.trim()) continue;
      
      const parsed = this.parseCSVLine(line.replace(/\r$/, ''));
      if (parsed.length > 0) {
        data.push(parsed);
      }
    }
    
    return { headers, data };
  }

  // Parst alle Sprachen aus CSV-Daten
  parseAllLanguages(csvData, languages) {
    const { headers, data } = csvData;
    const keyIndex = headers.indexOf('KEY');
    
    if (keyIndex === -1) {
      throw new Error('KEY column not found in CSV');
    }
    
    // Erstelle Übersetzungen für alle Sprachen
    for (const lang of languages) {
      const targetColumn = this.langMapping[lang] || 'en';
      const targetIndex = headers.indexOf(targetColumn);
      
      if (targetIndex === -1) {
        console.warn(`Language ${lang} not found in CSV, skipping`);
        continue;
      }
      
      const langTranslations = {};
      
      for (const row of data) {
        if (row.length <= Math.max(keyIndex, targetIndex)) continue;
        
        const key = row[keyIndex];
        const value = row[targetIndex];
        
        if (key && value && value.trim() !== '') {
          langTranslations[key] = value;
        }
      }
      
      // Cache die Übersetzungen
      this.cache.set(lang, langTranslations);
    }
    
    console.log(`📋 Loaded translations for ${this.cache.size} languages`);
  }

  // CSV Line Parser
  parseCSVLine(line) {
    const result = [];
    let current = '';
    let insideQuotes = false;

    for (let i = 0; i < line.length; i++) {
      const char = line[i];

      if (char === '"') {
        const nextChar = line[i + 1];
        if (insideQuotes && nextChar === '"') {
          current += '"';
          i++; // Skip next quote
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
    // Prüfe Cache zuerst
    if (this.cache.has(locale)) {
      this.translations = this.cache.get(locale);
      return;
    }
    
    // Fallback zu Standard-Übersetzungen
    this.translations = this.defaultTranslations[locale] || this.defaultTranslations['en'];
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

