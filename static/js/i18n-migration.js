// i18n-migration.js - Migration zur optimierten Lokalisierung
// Stellt sicher, dass die neue Methode nahtlos funktioniert

import { initializeLocalization, setLocale, t, applyI18n, applySelectTranslations } from './i18n-optimized.js';

class LocalizationMigration {
  constructor() {
    this.migrated = false;
    this.originalFunctions = {};
    this.init();
  }

  init() {
    // Warte bis DOM geladen ist
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => this.migrate());
    } else {
      this.migrate();
    }
  }

  async migrate() {
    if (this.migrated) return;
    
    console.log('🔄 Migrating to optimized localization system...');
    
    try {
      // Initialisiere das neue System
      await initializeLocalization();
      
      // Speichere ursprüngliche Funktionen für Fallback
      this.originalFunctions = {
        setLocale: window.setLocale,
        t: window.t,
        applyI18n: window.applyI18n,
        applySelectTranslations: window.applySelectTranslations
      };
      
      // Ersetze globale Funktionen
      this.replaceGlobalFunctions();
      
      // Migriere bestehende Locale
      await this.migrateCurrentLocale();
      
      this.migrated = true;
      console.log('✅ Migration to optimized localization completed');
      
    } catch (error) {
      console.warn('⚠️ Migration failed, falling back to original system:', error);
      this.restoreOriginalFunctions();
    }
  }

  replaceGlobalFunctions() {
    // Ersetze globale Funktionen mit optimierten Versionen
    window.setLocale = this.optimizedSetLocale.bind(this);
    window.t = t;
    window.applyI18n = applyI18n;
    window.applySelectTranslations = applySelectTranslations;
    
    // Füge neue Funktionen hinzu
    window.initializeLocalization = initializeLocalization;
    window.localizationManager = window.localizationManager;
  }

  async optimizedSetLocale(locale) {
    try {
      await setLocale(locale);
      
      // Warte auf Event und wende Übersetzungen an
      return new Promise((resolve) => {
        const handleTranslationsLoaded = (event) => {
          if (event.detail.locale === locale) {
            window.removeEventListener('translationsLoaded', handleTranslationsLoaded);
            resolve();
          }
        };
        
        window.addEventListener('translationsLoaded', handleTranslationsLoaded);
        
        // Fallback nach 2 Sekunden
        setTimeout(() => {
          window.removeEventListener('translationsLoaded', handleTranslationsLoaded);
          resolve();
        }, 2000);
      });
    } catch (error) {
      console.warn('Failed to set locale:', error);
      // Fallback zu ursprünglicher Methode
      if (this.originalFunctions.setLocale) {
        this.originalFunctions.setLocale(locale);
      }
    }
  }

  async migrateCurrentLocale() {
    // Lade aktuelle Locale aus localStorage
    const currentLocale = localStorage.getItem('siluma_native') || 'de';
    
    // Setze Locale im neuen System
    await this.optimizedSetLocale(currentLocale);
    
    // Wende Übersetzungen an
    applyI18n();
    applySelectTranslations();
  }

  restoreOriginalFunctions() {
    // Stelle ursprüngliche Funktionen wieder her
    if (this.originalFunctions.setLocale) {
      window.setLocale = this.originalFunctions.setLocale;
    }
    if (this.originalFunctions.t) {
      window.t = this.originalFunctions.t;
    }
    if (this.originalFunctions.applyI18n) {
      window.applyI18n = this.originalFunctions.applyI18n;
    }
    if (this.originalFunctions.applySelectTranslations) {
      window.applySelectTranslations = this.originalFunctions.applySelectTranslations;
    }
  }
}

// Starte Migration
new LocalizationMigration();

// Exportiere für manuelle Verwendung
export { LocalizationMigration };

