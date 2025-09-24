// Settings management
class SettingsManager {
    constructor() {
        this.currentSettings = null;
        this.init();
    }

    async init() {
        this.setupEventListeners();
        await this.loadSettings();
        await this.initializeTheme();
    }

    setupEventListeners() {
        // Settings button
        document.getElementById('settings-btn')?.addEventListener('click', () => {
            this.showSettingsModal();
        });

        // Save settings button
        document.getElementById('save-settings')?.addEventListener('click', () => {
            this.saveSettings();
        });

        // Reset progress button
        document.getElementById('reset-progress')?.addEventListener('click', () => {
            this.resetProgress();
        });

        // Modal close
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                if (e.target.closest('#settings-modal')) {
                    this.hideSettingsModal();
                }
            });
        });

        // Close modal on backdrop click
        document.getElementById('settings-modal')?.addEventListener('click', (e) => {
            if (e.target === e.currentTarget) {
                this.hideSettingsModal();
            }
        });

        // Theme change - apply immediately
        document.getElementById('settings-theme')?.addEventListener('change', (e) => {
            this.applyTheme(e.target.value);
            // Save settings immediately for non-authenticated users
            if (!window.authManager || !window.authManager.isAuthenticated()) {
                localStorage.setItem('siluma_theme', e.target.value);
            }
        });

        // Native language change - apply immediately
        document.getElementById('settings-native-lang')?.addEventListener('change', (e) => {
            this.applyNativeLanguage(e.target.value);
            // Save settings immediately for non-authenticated users
            if (!window.authManager || !window.authManager.isAuthenticated()) {
                localStorage.setItem('siluma_native', e.target.value);
            }
        });
    }

    showSettingsModal() {
        document.getElementById('settings-modal').style.display = 'flex';
        document.getElementById('settings-modal').style.alignItems = 'center';
        document.getElementById('settings-modal').style.justifyContent = 'center';
        document.body.style.overflow = 'hidden';
        
        // Ensure current settings are loaded before populating form
        this.ensureCurrentSettings().then(() => {
            this.populateSettingsForm();
            this.loadUserStats();
        });
    }
    
    async ensureCurrentSettings() {
        // If we don't have current settings, load them
        if (!this.currentSettings) {
            this._skipFormPopulation = true; // Skip form population in loadSettings
            await this.loadSettings();
            this._skipFormPopulation = false; // Reset flag
        }
        
        // Ensure we have the latest theme from localStorage
        if (this.currentSettings) {
            const savedTheme = localStorage.getItem('siluma_theme');
            if (savedTheme && this.currentSettings.theme !== savedTheme) {
                this.currentSettings.theme = savedTheme;
                console.log('🎨 Updated current settings theme from localStorage:', savedTheme);
            }
        }
    }

    hideSettingsModal() {
        document.getElementById('settings-modal').style.display = 'none';
        // Restore body scroll
        document.body.style.overflow = 'auto';
        this.clearMessages();
    }

    async loadSettings() {
        // Load available languages for native language dropdown
        await this.loadAvailableLanguages();
        
        // For authenticated users, load from server
        if (window.authManager && window.authManager.isAuthenticated()) {
            try {
                const response = await fetch('/api/user/settings', {
                    headers: window.authManager.getAuthHeaders()
                });

                if (response.ok) {
                    const data = await response.json();
                    this.currentSettings = data.settings || {};
                    this.populateSettingsForm();
                    // Apply loaded theme
                    if (this.currentSettings.theme) {
                        this.applyTheme(this.currentSettings.theme);
                    }
                    
                    // Apply loaded native language
                    if (this.currentSettings.native_language) {
                        this.applyNativeLanguage(this.currentSettings.native_language);
                    }
                    
                    console.log('🎨 Settings loaded from server:', this.currentSettings);
                } else {
                    // Use default settings if no settings found
                    this.currentSettings = this.getDefaultSettings();
                    this.populateSettingsForm();
                    console.log('🎨 Using default settings');
                }
            } catch (error) {
                console.error('Error loading settings:', error);
                this.currentSettings = this.getDefaultSettings();
                this.populateSettingsForm();
            }
        } else {
            // For non-authenticated users, load from localStorage
            this.currentSettings = this.getDefaultSettings();
            
            // Load theme from localStorage
            const savedTheme = localStorage.getItem('siluma_theme');
            if (savedTheme) {
                this.currentSettings.theme = savedTheme;
            }
            
            // Load native language from localStorage
            const savedNativeLang = localStorage.getItem('siluma_native');
            if (savedNativeLang) {
                this.currentSettings.native_language = savedNativeLang;
            }
            
            // Only populate form if not called from showSettingsModal
            if (!this._skipFormPopulation) {
                this.populateSettingsForm();
            }
            
            // Apply theme immediately
            if (this.currentSettings.theme) {
                this.applyTheme(this.currentSettings.theme);
            }
            
            // Apply native language immediately
            if (this.currentSettings.native_language) {
                this.applyNativeLanguage(this.currentSettings.native_language);
            }
            
            console.log('🎨 Settings loaded from localStorage:', this.currentSettings);
        }
    }

    async loadAvailableLanguages() {
        try {
            // Check cache first
            const cachedLanguages = localStorage.getItem('available_languages');
            if (cachedLanguages) {
                try {
                    const data = JSON.parse(cachedLanguages);
                    if (data.success && data.languages) {
                        console.log('Using cached available languages in settings');
                        const nativeLangSelect = document.getElementById('settings-native-lang');
                        if (nativeLangSelect) {
                            this.populateLanguageSelects(nativeLangSelect, data.languages);
                        }
                        return;
                    }
                } catch (error) {
                    console.log('Error parsing cached languages in settings:', error);
                }
            }
            
            const response = await fetch('/api/available-languages');
            if (response.ok) {
                const data = await response.json();
                
                // Cache the result
                if (data.success) {
                    localStorage.setItem('available_languages', JSON.stringify(data));
                }
                
                const nativeLangSelect = document.getElementById('settings-native-lang');
                if (nativeLangSelect && data.languages) {
                    // Clear existing options
                    nativeLangSelect.innerHTML = '';
                    
                    // Add options for each language
                    data.languages.forEach(lang => {
                        const option = document.createElement('option');
                        option.value = lang.code;
                        option.textContent = lang.native_name || lang.name;
                        nativeLangSelect.appendChild(option);
                    });
                    
                    // Set the current value after options are loaded
                    const currentNativeLang = this.currentSettings?.native_language || localStorage.getItem('siluma_native') || 'de';
                    nativeLangSelect.value = currentNativeLang;
                    console.log('🎨 Language options loaded, set value to:', currentNativeLang);
                }
            }
        } catch (error) {
            console.error('Error loading available languages:', error);
        }
    }

    getDefaultSettings() {
        return {
            theme: 'light',
            native_language: 'de'
        };
    }

    populateSettingsForm() {
        const settings = this.currentSettings || this.getDefaultSettings();
        
        // Get current theme from localStorage as fallback
        const currentTheme = settings.theme || localStorage.getItem('siluma_theme') || 'light';
        const currentNativeLang = settings.native_language || localStorage.getItem('siluma_native') || 'de';
        
        // Set form values
        const themeSelector = document.getElementById('settings-theme');
        const nativeLangSelector = document.getElementById('settings-native-lang');
        
        if (themeSelector) {
            themeSelector.value = currentTheme;
        }
        
        if (nativeLangSelector) {
            // Ensure the dropdown has options before setting value
            if (nativeLangSelector.options.length > 0) {
                nativeLangSelector.value = currentNativeLang;
                console.log('🎨 Native language dropdown set to:', currentNativeLang);
            } else {
                // If no options yet, wait for them to load and then set the value
                console.log('🎨 Waiting for language options to load before setting value');
                const checkOptions = () => {
                    if (nativeLangSelector.options.length > 0) {
                        nativeLangSelector.value = currentNativeLang;
                        console.log('🎨 Native language dropdown set to (delayed):', currentNativeLang);
                    } else {
                        setTimeout(checkOptions, 100);
                    }
                };
                checkOptions();
            }
        }
        
        // Debug: Log form population
        console.log('🎨 Form populated with theme:', currentTheme, 'native lang:', currentNativeLang);
    }

    async saveSettings() {
        const settings = {
            theme: document.getElementById('settings-theme').value,
            native_language: document.getElementById('settings-native-lang').value
        };

        // For authenticated users, save to server
        if (window.authManager && window.authManager.isAuthenticated()) {
            try {
                const response = await fetch('/api/user/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...window.authManager.getAuthHeaders()
                    },
                    body: JSON.stringify({ settings })
                });

                if (response.ok) {
                    this.currentSettings = settings;
                    const successMessage = window.t ? window.t('settings.saved_successfully', 'Settings saved successfully!') : 'Settings saved successfully!';
                    this.showSuccess(successMessage);
                    
                    // Apply theme change immediately
                    this.applyTheme(settings.theme);
                    
                    // Apply native language change immediately
                    this.applyNativeLanguage(settings.native_language);
                    
                    console.log('🎨 Settings saved to server:', settings);
                } else {
                    const data = await response.json();
                    const errorMessage = window.t ? window.t('settings.save_failed', 'Failed to save settings') : 'Failed to save settings';
                    this.showError(data.error || errorMessage);
                }
            } catch (error) {
                console.error('Error saving settings:', error);
                const errorMessage = window.t ? window.t('settings.save_failed', 'Failed to save settings. Please try again.') : 'Failed to save settings. Please try again.';
                this.showError(errorMessage);
            }
        } else {
            // For non-authenticated users, save to localStorage
            this.currentSettings = settings;
            localStorage.setItem('siluma_theme', settings.theme);
            localStorage.setItem('siluma_native', settings.native_language);
            const successMessage = window.t ? window.t('settings.saved_successfully', 'Settings saved successfully!') : 'Settings saved successfully!';
            this.showSuccess(successMessage);
            
            // Apply theme change immediately
            this.applyTheme(settings.theme);
            
            // Apply native language change immediately
            this.applyNativeLanguage(settings.native_language);
            
            console.log('🎨 Settings saved to localStorage:', settings);
        }
    }

    applyTheme(theme) {
        const body = document.body;
        const html = document.documentElement;
        
        // Remove existing theme classes
        body.classList.remove('theme-light', 'theme-dark', 'theme-auto');
        html.classList.remove('theme-light', 'theme-dark', 'theme-auto');
        
        // Apply new theme
        if (theme === 'auto') {
            body.classList.add('theme-auto');
            html.classList.add('theme-auto');
            // Listen for system theme changes
            this.setupSystemThemeListener();
        } else {
            body.classList.add(`theme-${theme}`);
            html.classList.add(`theme-${theme}`);
        }
        
        // Force apply background colors directly to ensure they stick
        this.forceApplyBackgroundColors(theme);
        
        // Store theme preference in localStorage for non-authenticated users
        localStorage.setItem('siluma_theme', theme);
        
        // Update the theme selector to reflect the current selection
        const themeSelector = document.getElementById('settings-theme');
        if (themeSelector) {
            themeSelector.value = theme;
        }
        
        // Debug: Log theme application
        console.log('🎨 Theme applied:', theme, 'Classes:', body.className);
    }
    
    forceApplyBackgroundColors(theme) {
        // Get the correct background color for the theme
        let bgColor;
        if (theme === 'dark') {
            bgColor = '#0f172a';
        } else if (theme === 'auto') {
            // Check system preference
            const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
            bgColor = prefersDark ? '#0f172a' : '#f8fafc';
        } else {
            bgColor = '#f8fafc'; // light theme
        }
        
        // Only apply background to root elements and empty areas
        const rootElements = [
            document.documentElement,
            document.body
        ];
        
        rootElements.forEach(el => {
            if (el) {
                el.style.setProperty('background-color', bgColor, 'important');
                el.style.setProperty('background', bgColor, 'important');
            }
        });
        
        // Apply to shell container if it exists
        const shell = document.querySelector('.shell');
        if (shell) {
            shell.style.setProperty('background-color', bgColor, 'important');
            shell.style.setProperty('background', bgColor, 'important');
        }
        
        // Apply to main content areas that don't have specific backgrounds
        const mainContent = document.querySelector('main');
        if (mainContent && !mainContent.style.backgroundColor) {
            mainContent.style.setProperty('background-color', bgColor, 'important');
            mainContent.style.setProperty('background', bgColor, 'important');
        }
        
        // Apply to any divs that are likely empty containers
        const allDivs = document.querySelectorAll('div');
        allDivs.forEach(div => {
            // Only apply to divs that don't have specific background classes or styles
            if (!div.classList.contains('card') && 
                !div.classList.contains('modal') && 
                !div.classList.contains('modal-content') &&
                !div.classList.contains('modal-header') &&
                !div.classList.contains('modal-body') &&
                !div.classList.contains('modal-footer') &&
                !div.classList.contains('tooltip') && 
                !div.classList.contains('level-card') && 
                !div.classList.contains('onboarding-container') &&
                !div.classList.contains('onboarding-modal') &&
                !div.classList.contains('pill') &&
                !div.classList.contains('button') &&
                !div.classList.contains('btn') &&
                !div.classList.contains('nav') &&
                !div.classList.contains('topbar') &&
                !div.classList.contains('config') &&
                !div.classList.contains('lesson') &&
                !div.classList.contains('practice') &&
                !div.classList.contains('evaluation') &&
                !div.classList.contains('alphabet') &&
                !div.classList.contains('words') &&
                !div.classList.contains('settings') &&
                !div.classList.contains('auth') &&
                !div.classList.contains('level') &&
                !div.classList.contains('row') &&
                !div.classList.contains('col') &&
                !div.classList.contains('field') &&
                !div.classList.contains('input') &&
                !div.classList.contains('select') &&
                !div.classList.contains('textarea') &&
                !div.style.backgroundColor &&
                !div.style.background &&
                !div.style.backgroundImage &&
                !div.style.backgroundSize &&
                !div.style.backgroundPosition) {
                div.style.setProperty('background-color', 'transparent', 'important');
            }
        });
        
        console.log('🎨 Force applied background color:', bgColor);
    }
    
    setupSystemThemeListener() {
        if (this.systemThemeListener) {
            this.systemThemeListener.removeEventListener('change', this.handleSystemThemeChange);
        }
        
        this.systemThemeListener = window.matchMedia('(prefers-color-scheme: dark)');
        this.handleSystemThemeChange = () => {
            // Re-apply auto theme when system preference changes
            const currentTheme = document.getElementById('settings-theme')?.value || localStorage.getItem('siluma_theme') || 'light';
            if (currentTheme === 'auto') {
                console.log('🎨 System theme changed, re-applying auto theme');
                this.applyTheme('auto');
                // Force apply background colors when system theme changes
                setTimeout(() => {
                    this.forceApplyBackgroundColors('auto');
                }, 50);
            }
        };
        
        this.systemThemeListener.addEventListener('change', this.handleSystemThemeChange);
        
        // Debug: Log system theme listener setup
        console.log('🎨 System theme listener setup. Current system preference:', this.systemThemeListener.matches ? 'dark' : 'light');
    }
    
    async applyNativeLanguage(nativeLang) {
        // Update the native language in localStorage
        localStorage.setItem('siluma_native', nativeLang);
        
        // Send native language to backend if user is authenticated
        if (window.authManager && window.authManager.isAuthenticated()) {
            try {
                const response = await fetch('/api/user/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...window.authManager.getAuthHeaders()
                    },
                    body: JSON.stringify({
                        native_language: nativeLang
                    })
                });
                
                if (response.ok) {
                    console.log('🌍 Native language updated in backend:', nativeLang);
                } else {
                    console.warn('⚠️ Failed to update native language in backend');
                }
            } catch (error) {
                console.error('❌ Error updating native language in backend:', error);
            }
        }
        
        // Debug: Log language application
        console.log('🌍 Native language applied:', nativeLang);
        
        // Trigger localization update and wait for it to complete
        if (window.setLocale) {
            // Check if we're already processing this language to prevent loops
            if (this.processingLanguage === nativeLang) {
                console.log('🌍 Already processing language change for:', nativeLang);
                return;
            }
            
            this.processingLanguage = nativeLang;
            
            // Remove any existing listeners first to prevent duplicates
            if (this.handleTranslationsLoaded) {
                window.removeEventListener('translationsLoaded', this.handleTranslationsLoaded);
            }
            
            // Create a new handler with proper cleanup
            this.handleTranslationsLoaded = async (event) => {
                // Only process if it's for the current language and we're still processing
                if (event.detail.locale !== nativeLang || this.processingLanguage !== nativeLang) {
                    return;
                }
                
                console.log('🌍 Translations loaded from:', event.detail.source, 'for locale:', event.detail.locale);
                
                // Apply i18n updates
                if (window.applyI18n) {
                    window.applyI18n();
                }
                
                // Apply select translations
                if (window.applySelectTranslations) {
                    window.applySelectTranslations();
                }
                
                // Update course language dropdown if it exists
                if (window.updateCourseLanguageDropdown) {
                    window.updateCourseLanguageDropdown(nativeLang);
                }
                
                // Force refresh of level states to update language-dependent content
                if (window.refreshLevelStates) {
                    window.refreshLevelStates();
                }
                
                // Update level group names for new language
                if (window.updateLevelGroupNames) {
                    try {
                        window.updateLevelGroupNames();
                        console.log('🌍 Level group names updated for new language');
                    } catch (error) {
                        console.warn('⚠️ Failed to update level group names:', error);
                    }
                }
                
                // Update all UI elements that might need language updates
                this.updateAllUIElements();
                
                // Reload all dynamic content that depends on language
                await this.reloadAllLanguageDependentContent(nativeLang);
                
                // Reload words in background first to show new familiarity data for the new native language
                if (window.loadWords) {
                    try {
                        await window.loadWords(false); // Don't switch to words tab
                        console.log('🌍 Words reloaded for new native language:', nativeLang);
                    } catch (error) {
                        console.warn('⚠️ Failed to reload words for new native language:', error);
                    }
                }
                
                // Navigate to homepage after language change
                if (window.showTab) {
                    try {
                        window.showTab('levels'); // Use 'levels' instead of 'home'
                        console.log('🌍 Navigated to homepage after language change');
                    } catch (error) {
                        console.warn('⚠️ Failed to navigate to homepage:', error);
                    }
                }
                
                console.log('🌍 Complete localization update finished for:', nativeLang);
                
                // Clean up and reset processing flag
                window.removeEventListener('translationsLoaded', this.handleTranslationsLoaded);
                this.handleTranslationsLoaded = null;
                this.processingLanguage = null;
            };
            
            // Add the event listener
            window.addEventListener('translationsLoaded', this.handleTranslationsLoaded);
            
            // Set the locale
            window.setLocale(nativeLang);
            
            // Fallback timeout in case the event doesn't fire
            setTimeout(() => {
                if (this.processingLanguage === nativeLang) {
                    if (this.handleTranslationsLoaded) {
                        window.removeEventListener('translationsLoaded', this.handleTranslationsLoaded);
                        this.handleTranslationsLoaded = null;
                    }
                    this.processingLanguage = null;
                    console.log('🌍 Fallback: Applying translations after timeout');
                
                // Apply i18n updates
                if (window.applyI18n) {
                    window.applyI18n();
                }
                
                // Apply select translations
                if (window.applySelectTranslations) {
                    window.applySelectTranslations();
                }
                
                // Update all UI elements
                this.updateAllUIElements();
                }
            }, 1000); // Fallback after 1 second
        }
    }
    
    updateAllUIElements() {
        // Update all elements that might need language updates
        try {
            console.log('🌍 Updating all UI elements for new language...');
            
            // Batch DOM updates to reduce reflows
            requestAnimationFrame(() => {
                this.performBatchUIUpdates();
            });
        } catch (error) {
            console.warn('Error updating UI elements:', error);
        }
    }
    
    performBatchUIUpdates() {
        // Batch all DOM updates together to minimize reflows
        try {
            
            // Update navigation buttons
            const navButtons = document.querySelectorAll('.nav button');
            navButtons.forEach(btn => {
                if (btn.id === 'nav-alphabet') {
                    btn.textContent = window.t ? window.t('navigation.alphabet', 'Alphabet') : 'Alphabet';
                } else if (btn.id === 'show-words') {
                    btn.textContent = window.t ? window.t('navigation.words', 'Words') : 'Words';
                }
            });
            
            // Update course configuration labels
            const courseLabel = document.querySelector('label[for="target-lang"]');
            if (courseLabel) {
                courseLabel.textContent = window.t ? window.t('labels.course', 'Zielsprache') : 'Zielsprache';
            }
            
            const levelLabel = document.querySelector('label[for="cefr"]');
            if (levelLabel) {
                levelLabel.textContent = window.t ? window.t('labels.level', 'Sprachniveau') : 'Sprachniveau';
            }
            
            const motivationLabel = document.querySelector('label[for="topic"]');
            if (motivationLabel) {
                motivationLabel.textContent = window.t ? window.t('labels.motivation', 'Motivation') : 'Motivation';
            }
            
            // Update course setup title
            const configTitle = document.querySelector('.config-title');
            if (configTitle) {
                configTitle.textContent = window.t ? window.t('labels.course_setup', 'Kurs einrichten') : 'Kurs einrichten';
            }
            
            const configSubtitle = document.querySelector('.config-subtitle');
            if (configSubtitle) {
                configSubtitle.textContent = window.t ? window.t('labels.course_setup_desc', 'Passen Sie Ihr Lernerlebnis an') : 'Passen Sie Ihr Lernerlebnis an';
            }
            
            // Update translation input placeholder
            const translationInput = document.getElementById('user-translation');
            if (translationInput) {
                translationInput.placeholder = window.t ? window.t('labels.translation', 'Ihre Übersetzung hier...') : 'Ihre Übersetzung hier...';
            }
            
            // Update all elements with data-i18n attributes
            const i18nElements = document.querySelectorAll('[data-i18n]');
            i18nElements.forEach(element => {
                const key = element.getAttribute('data-i18n');
                if (key && window.t) {
                    const translation = window.t(key);
                    if (translation && translation !== key) {
                        element.textContent = translation;
                    }
                }
            });
            
            // Update all elements with data-i18n-placeholder attributes
            const placeholderElements = document.querySelectorAll('[data-i18n-placeholder]');
            placeholderElements.forEach(element => {
                const key = element.getAttribute('data-i18n-placeholder');
                if (key && window.t) {
                    const translation = window.t(key);
                    if (translation && translation !== key) {
                        element.placeholder = translation;
                    }
                }
            });
            
            // Update tab labels
            this.updateTabLabels();
            
            // Update button texts
            this.updateButtonTexts();
            
            // Update table headers
            this.updateTableHeaders();
            
            // Update CEFR level labels
            this.updateCefrLevels();
            
            // Update topic labels
            this.updateTopicLabels();
            
            console.log('🌍 All UI elements updated successfully');
            
            // Update buttons
            const checkBtn = document.getElementById('check');
            if (checkBtn) {
                checkBtn.textContent = window.t ? window.t('buttons.check_answer', 'Check Answer') : 'Check Answer';
            }
            
            const abortBtn = document.getElementById('abort-level');
            if (abortBtn) {
                abortBtn.textContent = window.t ? window.t('buttons.abort', 'Cancel') : 'Cancel';
            }
            
            // Update evaluation elements
            const evalTitle = document.querySelector('.eval-title');
            if (evalTitle) {
                evalTitle.textContent = window.t ? window.t('status.level_completed', 'Level completed 🎉') : 'Level completed 🎉';
            }
            
            const practiceBtn = document.getElementById('eval-practice');
            if (practiceBtn) {
                practiceBtn.textContent = window.t ? window.t('buttons.practice_difficult', 'Practice Difficult Words') : 'Practice Difficult Words';
            }
            
            const backBtn = document.getElementById('eval-back');
            if (backBtn) {
                backBtn.textContent = window.t ? window.t('buttons.back_to_overview', 'Back to Overview') : 'Back to Overview';
            }
            
            // Update tooltip elements
            const tooltipElements = document.querySelectorAll('#tooltip [data-i18n]');
            tooltipElements.forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (key && window.t) {
                    el.textContent = window.t(key, el.textContent);
                }
            });
            
            // Update level tip elements
            const levelTipElements = document.querySelectorAll('#level-tip [data-i18n]');
            levelTipElements.forEach(el => {
                const key = el.getAttribute('data-i18n');
                if (key && window.t) {
                    el.textContent = window.t(key, el.textContent);
                }
            });
            
            console.log('🔄 All UI elements updated for new language');
        } catch (error) {
            console.warn('Error updating UI elements:', error);
        }
    }
    
    async initializeTheme() {
        // Load theme from localStorage or user settings
        let theme = 'light';
        let nativeLang = 'de';
        
        if (window.authManager && window.authManager.isAuthenticated()) {
            // For authenticated users, try to load from user settings
            try {
                const response = await fetch('/api/user/settings', {
                    headers: window.authManager.getAuthHeaders()
                });
                
                if (response.ok) {
                    const data = await response.json();
                    this.currentSettings = data.settings || {};
                    theme = this.currentSettings.theme || localStorage.getItem('siluma_theme') || 'light';
                    nativeLang = this.currentSettings.native_language || localStorage.getItem('siluma_native') || 'de';
                } else {
                    // Fallback to localStorage if server request fails
                    theme = localStorage.getItem('siluma_theme') || 'light';
                    nativeLang = localStorage.getItem('siluma_native') || 'de';
                }
            } catch (error) {
                console.warn('Failed to load user settings, using localStorage:', error);
                // Fallback to localStorage if server request fails
                theme = localStorage.getItem('siluma_theme') || 'light';
                nativeLang = localStorage.getItem('siluma_native') || 'de';
            }
        } else {
            // For non-authenticated users, load from localStorage
            theme = localStorage.getItem('siluma_theme') || 'light';
            nativeLang = localStorage.getItem('siluma_native') || 'de';
        }
        
        // Apply theme with force background colors
        this.applyTheme(theme);
        
        // Apply native language
        this.applyNativeLanguage(nativeLang);
        
        // Update selectors if they exist
        const themeSelector = document.getElementById('settings-theme');
        if (themeSelector) {
            themeSelector.value = theme;
        }
        
        const nativeLangSelector = document.getElementById('settings-native-lang');
        if (nativeLangSelector) {
            nativeLangSelector.value = nativeLang;
        }
        
        // Force apply background colors again after a short delay to ensure they stick
        setTimeout(() => {
            this.forceApplyBackgroundColors(theme);
        }, 100);
        
        // Debug: Log theme initialization
        console.log('🎨 Theme initialized:', theme, 'from', window.authManager && window.authManager.isAuthenticated() ? 'user settings' : 'localStorage');
    }

    async loadUserStats() {
        if (!window.authManager || !window.authManager.isAuthenticated()) {
            return;
        }

        try {
            const response = await fetch('/api/user/stats', {
                headers: window.authManager.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                this.updateStatsDisplay(data.stats || {});
            }
        } catch (error) {
            console.error('Error loading user stats:', error);
        }
    }

    updateStatsDisplay(stats) {
        document.getElementById('stat-levels-completed').textContent = stats.levels_completed || 0;
        document.getElementById('stat-words-learned').textContent = stats.words_learned || 0;
        document.getElementById('stat-streak').textContent = `${stats.current_streak || 0} days`;
    }

    async resetProgress() {
        if (!window.authManager || !window.authManager.isAuthenticated()) {
            const errorMessage = window.t ? window.t('settings.login_required_reset', 'Please log in to reset progress') : 'Please log in to reset progress';
            this.showError(errorMessage);
            return;
        }

        if (!confirm('Are you sure you want to reset all your progress? This action cannot be undone.')) {
            return;
        }

        try {
            const response = await fetch('/api/user/reset-progress', {
                method: 'POST',
                headers: window.authManager.getAuthHeaders()
            });

            if (response.ok) {
                const successMessage = window.t ? window.t('settings.reset_progress_success', 'Progress reset successfully!') : 'Progress reset successfully!';
                this.showSuccess(successMessage);
                this.loadUserStats();
                
                // Refresh level states to show reset progress
                if (window.refreshLevelStates) {
                    window.refreshLevelStates();
                }
            } else {
                const data = await response.json();
                const errorMessage = window.t ? window.t('settings.reset_progress_failed', 'Failed to reset progress') : 'Failed to reset progress';
                this.showError(data.error || errorMessage);
            }
        } catch (error) {
            console.error('Error resetting progress:', error);
            const errorMessage = window.t ? window.t('settings.reset_progress_failed', 'Failed to reset progress. Please try again.') : 'Failed to reset progress. Please try again.';
            this.showError(errorMessage);
        }
    }

    showError(message) {
        const errorElement = document.getElementById('settings-error');
        const successElement = document.getElementById('settings-success');
        
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
        if (successElement) {
            successElement.style.display = 'none';
        }
    }

    showSuccess(message) {
        const errorElement = document.getElementById('settings-error');
        const successElement = document.getElementById('settings-success');
        
        if (successElement) {
            successElement.textContent = message;
            successElement.style.display = 'block';
        }
        if (errorElement) {
            errorElement.style.display = 'none';
        }
    }

    clearMessages() {
        const errorElement = document.getElementById('settings-error');
        const successElement = document.getElementById('settings-success');
        
        if (errorElement) errorElement.style.display = 'none';
        if (successElement) successElement.style.display = 'none';
    }
}

// Initialize theme immediately when script loads (before DOM is ready)
(function() {
    // Load theme from localStorage immediately
    const savedTheme = localStorage.getItem('siluma_theme') || 'light';
    const body = document.body;
    const html = document.documentElement;
    
    // Remove existing theme classes
    body.classList.remove('theme-light', 'theme-dark', 'theme-auto');
    html.classList.remove('theme-light', 'theme-dark', 'theme-auto');
    
    // Apply saved theme immediately
    if (savedTheme === 'auto') {
        body.classList.add('theme-auto');
        html.classList.add('theme-auto');
    } else {
        body.classList.add(`theme-${savedTheme}`);
        html.classList.add(`theme-${savedTheme}`);
    }
    
    // Force apply background colors immediately
    let bgColor;
    if (savedTheme === 'dark') {
        bgColor = '#0f172a';
    } else if (savedTheme === 'auto') {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        bgColor = prefersDark ? '#0f172a' : '#f8fafc';
    } else {
        bgColor = '#f8fafc';
    }
    
    // Apply background immediately
    html.style.setProperty('background-color', bgColor, 'important');
    html.style.setProperty('background', bgColor, 'important');
    body.style.setProperty('background-color', bgColor, 'important');
    body.style.setProperty('background', bgColor, 'important');
    
    console.log('🎨 Theme applied immediately on load:', savedTheme);
})();

// Add missing function to SettingsManager class
SettingsManager.prototype.populateLanguageSelects = function(selectElement, languages) {
    if (!selectElement || !languages) return;
    
    selectElement.innerHTML = '';
    languages.forEach(lang => {
        const option = document.createElement('option');
        option.value = lang.code;
        option.textContent = lang.native_name || lang.name;
        option.setAttribute('data-i18n', `language_names.${lang.code}`);
        selectElement.appendChild(option);
    });
    
    // Set the current value after options are loaded
    const currentNativeLang = this.currentSettings?.native_language || localStorage.getItem('siluma_native') || 'de';
    selectElement.value = currentNativeLang;
    console.log('🎨 Language selects populated, set value to:', currentNativeLang);
    
    // Apply localization to the select options
    if (window.applyI18n) {
        window.applyI18n();
    }
};

// New function to reload all language-dependent content
SettingsManager.prototype.reloadAllLanguageDependentContent = async function(nativeLang) {
    console.log('🌍 Reloading all language-dependent content for:', nativeLang);
    
    try {
        // 1. Reload available languages with new native language
        if (window.loadAvailableLanguages) {
            await window.loadAvailableLanguages();
            console.log('🌍 Available languages reloaded');
        }
        
        // 2. Reload course data for new native language
        if (window.ensureTargetLangOptions) {
            window.ensureTargetLangOptions();
            console.log('🌍 Course options reloaded');
        }
        
        // 3. Reload level states with new language
        if (window.refreshLevelStates) {
            window.refreshLevelStates();
            console.log('🌍 Level states refreshed');
        }
        
        // 4. Reload header stats
        if (window.refreshHeaderStats) {
            window.refreshHeaderStats();
            console.log('🌍 Header stats refreshed');
        }
        
        // 5. Reload words data
        if (window.loadWords) {
            await window.loadWords(false);
            console.log('🌍 Words data reloaded');
        }
        
        // 6. Update all dropdowns and selects
        this.updateAllDropdowns(nativeLang);
        
        // 7. Force re-render of all tabs
        this.forceRerenderAllTabs();
        
        console.log('🌍 All language-dependent content reloaded successfully');
        
    } catch (error) {
        console.warn('⚠️ Error reloading language-dependent content:', error);
    }
};

// Update all dropdowns and selects
SettingsManager.prototype.updateAllDropdowns = function(nativeLang) {
    // Update native language dropdown
    const nativeLangSelect = document.getElementById('settings-native-lang');
    if (nativeLangSelect) {
        nativeLangSelect.value = nativeLang;
    }
    
    // Update target language dropdown
    const targetLangSelect = document.getElementById('target-lang');
    if (targetLangSelect) {
        // Trigger change event to reload course data
        targetLangSelect.dispatchEvent(new Event('change'));
    }
    
    // Update CEFR dropdown
    const cefrSelect = document.getElementById('cefr');
    if (cefrSelect) {
        // Apply translations to CEFR options
        const options = cefrSelect.querySelectorAll('option');
        options.forEach(option => {
            const key = option.getAttribute('data-i18n');
            if (key && window.t) {
                const translation = window.t(key);
                if (translation && translation !== key) {
                    option.textContent = translation;
                }
            }
        });
    }
    
    // Update topic dropdown
    const topicSelect = document.getElementById('topic');
    if (topicSelect) {
        const options = topicSelect.querySelectorAll('option');
        options.forEach(option => {
            const key = option.getAttribute('data-i18n');
            if (key && window.t) {
                const translation = window.t(key);
                if (translation && translation !== key) {
                    option.textContent = translation;
                }
            }
        });
    }
};

// Force re-render of all tabs
SettingsManager.prototype.forceRerenderAllTabs = function() {
    // Force re-render of levels tab
    if (window.renderLevels) {
        window.renderLevels();
    }
    
    // Force re-render of words tab
    if (window.renderWords) {
        window.renderWords();
    }
    
    // Force re-render of evaluation tab
    if (window.renderEvaluation) {
        window.renderEvaluation();
    }
    
    // Force re-render of settings tab
    this.updateAllUIElements();
};

// Update tab labels
SettingsManager.prototype.updateTabLabels = function() {
    const tabButtons = document.querySelectorAll('.tab-button');
    tabButtons.forEach(btn => {
        const key = btn.getAttribute('data-i18n');
        if (key && window.t) {
            const translation = window.t(key);
            if (translation && translation !== key) {
                btn.textContent = translation;
            }
        }
    });
};

// Update button texts
SettingsManager.prototype.updateButtonTexts = function() {
    const buttons = document.querySelectorAll('button[data-i18n]');
    buttons.forEach(btn => {
        const key = btn.getAttribute('data-i18n');
        if (key && window.t) {
            const translation = window.t(key);
            if (translation && translation !== key) {
                btn.textContent = translation;
            }
        }
    });
};

// Update table headers
SettingsManager.prototype.updateTableHeaders = function() {
    const tableHeaders = document.querySelectorAll('th[data-i18n]');
    tableHeaders.forEach(th => {
        const key = th.getAttribute('data-i18n');
        if (key && window.t) {
            const translation = window.t(key);
            if (translation && translation !== key) {
                th.textContent = translation;
            }
        }
    });
};

// Update CEFR level labels
SettingsManager.prototype.updateCefrLevels = function() {
    const cefrOptions = document.querySelectorAll('#cefr option[data-i18n]');
    cefrOptions.forEach(option => {
        const key = option.getAttribute('data-i18n');
        if (key && window.t) {
            const translation = window.t(key);
            if (translation && translation !== key) {
                option.textContent = translation;
            }
        }
    });
};

// Update topic labels
SettingsManager.prototype.updateTopicLabels = function() {
    const topicOptions = document.querySelectorAll('#topic option[data-i18n]');
    topicOptions.forEach(option => {
        const key = option.getAttribute('data-i18n');
        if (key && window.t) {
            const translation = window.t(key);
            if (translation && translation !== key) {
                option.textContent = translation;
            }
        }
    });
};

// Initialize settings manager when DOM is loaded
document.addEventListener('DOMContentLoaded', async () => {
    window.settingsManager = new SettingsManager();
    // Initialize theme again to ensure everything is properly set up
    await window.settingsManager.initializeTheme();
});
