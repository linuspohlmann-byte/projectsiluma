/**
 * Onboarding Manager - Handles the user onboarding flow
 */
class OnboardingManager {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 4;
        this.onboardingData = {
            native_language: localStorage.getItem('siluma_native') || 'de',
            target_language: localStorage.getItem('siluma_target') || 'ar',
            proficiency_level: localStorage.getItem('siluma_cefr') || 'none',  // Default to A0
            learning_focus: 'daily life'
        };
        
        console.log('🎬 Onboarding initialized with data:', this.onboardingData);
        
        this.init();
    }

    init() {
        this.bindEvents();
        // Don't load languages here - wait until modal is shown
    }

    bindEvents() {
        // Navigation buttons
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('onboarding-next')) {
                this.nextStep();
            } else if (e.target.classList.contains('onboarding-back')) {
                this.previousStep();
            } else if (e.target.classList.contains('onboarding-finish')) {
                this.finishOnboarding();
            } else if (e.target.id === 'onboarding-skip') {
                this.skipOnboarding();
            }
        });

        // Topic selection
        document.addEventListener('click', (e) => {
            if (e.target.closest('.onboarding-option')) {
                this.selectTopic(e.target.closest('.onboarding-option'));
            }
        });

        // Form inputs
        document.addEventListener('change', (e) => {
            if (e.target.id === 'onboarding-native-lang') {
                this.onboardingData.native_language = e.target.value;
                this.applyNativeLanguage(e.target.value);
            } else if (e.target.id === 'onboarding-target-lang') {
                this.onboardingData.target_language = e.target.value;
            } else if (e.target.id === 'onboarding-cefr') {
                this.onboardingData.proficiency_level = e.target.value;
                console.log('📝 CEFR level changed to:', e.target.value);
            }
        });
    }

    async show() {
        document.getElementById('onboarding-modal').style.display = 'flex';
        this.currentStep = 1;
        this.updateProgress();
        this.showStep(1);
        
        console.log('🎬 Onboarding modal shown, loading languages...');
        
        // Load available languages first
        await this.loadAvailableLanguages();
        
        // Apply localization to onboarding elements
        if (window.applyI18n) {
            window.applyI18n();
        }
        
        console.log('✅ Onboarding initialization complete');
        
        // Focus first input if available
        setTimeout(() => {
            const firstInput = document.querySelector('.onboarding-step.active input, .onboarding-step.active select');
            if (firstInput) {
                firstInput.focus();
            }
        }, 100);
    }

    hide() {
        document.getElementById('onboarding-modal').style.display = 'none';
    }

    nextStep() {
        if (this.currentStep < this.totalSteps) {
            this.currentStep++;
            this.updateProgress();
            this.showStep(this.currentStep);
        }
    }

    previousStep() {
        if (this.currentStep > 1) {
            this.currentStep--;
            this.updateProgress();
            this.showStep(this.currentStep);
        }
    }

    showStep(step) {
        // Hide all steps
        document.querySelectorAll('.onboarding-step').forEach(stepEl => {
            stepEl.classList.remove('active');
        });

        // Show current step
        const currentStepEl = document.getElementById(`onboarding-step-${step}`);
        if (currentStepEl) {
            currentStepEl.classList.add('active');
        }

        // Update button visibility
        this.updateButtonVisibility();
    }

    updateProgress() {
        const progressFill = document.getElementById('onboarding-progress-fill');
        const progressText = document.getElementById('onboarding-progress-text');
        
        if (progressFill) {
            const percentage = (this.currentStep / this.totalSteps) * 100;
            progressFill.style.width = `${percentage}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${this.currentStep} / ${this.totalSteps}`;
        }
    }

    updateButtonVisibility() {
        const backButtons = document.querySelectorAll('.onboarding-back');
        const nextButtons = document.querySelectorAll('.onboarding-next');
        const finishButtons = document.querySelectorAll('.onboarding-finish');

        // Show/hide back buttons
        backButtons.forEach(btn => {
            btn.style.display = this.currentStep > 1 ? 'block' : 'none';
        });

        // Show/hide next vs finish buttons
        nextButtons.forEach(btn => {
            btn.style.display = this.currentStep < this.totalSteps ? 'block' : 'none';
        });

        finishButtons.forEach(btn => {
            btn.style.display = this.currentStep === this.totalSteps ? 'block' : 'none';
        });
    }

    selectTopic(optionElement) {
        // Remove selection from all options
        document.querySelectorAll('.onboarding-option').forEach(option => {
            option.classList.remove('selected');
        });

        // Add selection to clicked option
        optionElement.classList.add('selected');
        
        // Store selection
        this.onboardingData.learning_focus = optionElement.dataset.topic;
    }

    async loadAvailableLanguages() {
        try {
            console.log('📥 Loading available languages for onboarding...');
            
            // Check cache first
            const cachedLanguages = localStorage.getItem('available_languages');
            if (cachedLanguages) {
                try {
                    const languages = JSON.parse(cachedLanguages);
                    if (languages.success && languages.languages && languages.languages.length > 0) {
                        console.log('✅ Using cached available languages:', languages.languages.length, 'languages');
                        await this.populateLanguageSelects(languages.languages);
                        return;
                    }
                } catch (error) {
                    console.log('⚠️ Error parsing cached languages:', error);
                }
            }
            
            console.log('🌐 Fetching languages from API...');
            const response = await fetch('/api/available-languages');
            
            if (!response.ok) {
                throw new Error(`API returned ${response.status}: ${response.statusText}`);
            }
            
            const languages = await response.json();
            console.log('📋 API response:', languages);
            
            // Cache the result
            if (languages.success && languages.languages) {
                localStorage.setItem('available_languages', JSON.stringify(languages));
                console.log('✅ Cached', languages.languages.length, 'languages');
            }
            
            if (languages.success && languages.languages && languages.languages.length > 0) {
                console.log('✅ Populating language selects with', languages.languages.length, 'languages');
                await this.populateLanguageSelects(languages.languages);
            } else {
                console.error('❌ No languages returned from API');
                throw new Error('No languages available');
            }
        } catch (error) {
            console.error('❌ Failed to load available languages:', error);
            // Show user-friendly error
            this.showErrorMessage('Could not load language options. Please refresh the page.');
        }
    }

    async populateLanguageSelects(languages) {
        const nativeSelect = document.getElementById('onboarding-native-lang');
        const targetSelect = document.getElementById('onboarding-target-lang');

        // Populate native language select (same as available languages)
        if (nativeSelect) {
            nativeSelect.innerHTML = '';
            console.log('📝 Populating native language select with', languages.length, 'languages');
            languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                option.textContent = lang.native_name;
                option.setAttribute('data-i18n', `language_names.${lang.code}`);
                nativeSelect.appendChild(option);
            });
            
            // Set default to current or German
            const currentNative = localStorage.getItem('siluma_native') || 'de';
            if (nativeSelect.querySelector(`option[value="${currentNative}"]`)) {
                nativeSelect.value = currentNative;
                this.onboardingData.native_language = currentNative;
                console.log('✅ Set native language to:', currentNative);
            } else {
                console.warn('⚠️ Native language', currentNative, 'not found in options');
            }
            
            console.log('✅ Native language select populated with', nativeSelect.options.length, 'options');
            
            // Apply localization to the select options
            if (window.applyI18n) {
                window.applyI18n();
            }
        } else {
            console.error('❌ Native language select element not found');
        }

        // Populate target language select (same as available courses)
        if (targetSelect) {
            try {
                const currentNativeLang = localStorage.getItem('siluma_native') || 'de';
                console.log('🌐 Fetching available courses for native lang:', currentNativeLang);
                
                const response = await fetch(`/api/available-courses?native_lang=${currentNativeLang}`);
                
                if (!response.ok) {
                    throw new Error(`API returned ${response.status}: ${response.statusText}`);
                }
                
                const coursesData = await response.json();
                console.log('📋 Courses API response:', coursesData);
                
                if (coursesData.success && coursesData.languages && coursesData.languages.length > 0) {
                    targetSelect.innerHTML = '';
                    console.log('📝 Populating target language select with', coursesData.languages.length, 'courses');
                    
                    coursesData.languages.forEach(lang => {
                        const option = document.createElement('option');
                        option.value = lang.code;
                        option.textContent = `${lang.native_name || lang.name} (${lang.code.toUpperCase()})`;
                        option.setAttribute('data-i18n', `language_names.${lang.code}`);
                        targetSelect.appendChild(option);
                    });
                    
                    // Set default to current or Arabic
                    const currentTarget = localStorage.getItem('siluma_target') || 'ar';
                    if (targetSelect.querySelector(`option[value="${currentTarget}"]`)) {
                        targetSelect.value = currentTarget;
                        this.onboardingData.target_language = currentTarget;
                        console.log('✅ Set target language to:', currentTarget);
                    } else {
                        console.warn('⚠️ Target language', currentTarget, 'not found in options');
                    }
                    
                    console.log('✅ Target language select populated with', targetSelect.options.length, 'options');
                    
                    // Apply localization to the select options
                    if (window.applyI18n) {
                        window.applyI18n();
                    }
                } else {
                    throw new Error('No courses returned from API');
                }
            } catch (error) {
                console.error('❌ Failed to load available courses:', error);
                console.log('⚠️ Using fallback: populating with all available languages');
                
                // Fallback to using the same languages list
                targetSelect.innerHTML = '';
                languages.forEach(lang => {
                    const option = document.createElement('option');
                    option.value = lang.code;
                    option.textContent = lang.native_name;
                    option.setAttribute('data-i18n', `language_names.${lang.code}`);
                    targetSelect.appendChild(option);
                });
                
                const currentTarget = localStorage.getItem('siluma_target') || 'ar';
                if (targetSelect.querySelector(`option[value="${currentTarget}"]`)) {
                    targetSelect.value = currentTarget;
                    this.onboardingData.target_language = currentTarget;
                }
                
                console.log('✅ Target language select populated (fallback) with', targetSelect.options.length, 'options');
            }
        } else {
            console.error('❌ Target language select element not found');
        }
    }

    async applyNativeLanguage(langCode) {
        // Update localStorage
        localStorage.setItem('siluma_native', langCode);
        
        // Apply localization
        if (window.setLocale) {
            window.setLocale(langCode);
            
            // Listen for translations to be loaded
            const handleTranslationsLoaded = async (event) => {
                console.log('🌍 Onboarding: Translations loaded from:', event.detail.source, 'for locale:', event.detail.locale);
                
                // Apply i18n updates to onboarding elements
                if (window.applyI18n) {
                    window.applyI18n();
                }
                
                // Re-populate language selects with localized names
                await this.loadAvailableLanguages();
                
                // Remove the event listener
                window.removeEventListener('translationsLoaded', handleTranslationsLoaded);
            };
            
            // Add event listener for when translations are loaded
            window.addEventListener('translationsLoaded', handleTranslationsLoaded);
            
            // Fallback timeout in case the event doesn't fire
            setTimeout(async () => {
                window.removeEventListener('translationsLoaded', handleTranslationsLoaded);
                console.log('🌍 Onboarding: Fallback: Applying translations after timeout');
                
                // Apply i18n updates
                if (window.applyI18n) {
                    window.applyI18n();
                }
                
                // Re-populate language selects (this will also update target courses)
                await this.loadAvailableLanguages();
            }, 1000); // Fallback after 1 second
        }
    }

    async finishOnboarding() {
        try {
            console.log('🎯 Starting onboarding completion...');
            console.log('📝 Onboarding data:', this.onboardingData);
            
            // Get authentication headers
            const headers = {
                'Content-Type': 'application/json'
            };
            
            // Check if user is authenticated
            if (window.authManager && window.authManager.isAuthenticated()) {
                Object.assign(headers, window.authManager.getAuthHeaders());
                console.log('✅ User authenticated, adding auth headers');
            } else {
                // Fallback to session token from localStorage
                const sessionToken = localStorage.getItem('session_token');
                if (sessionToken) {
                    headers['Authorization'] = `Bearer ${sessionToken}`;
                    console.log('✅ Using session token from localStorage');
                } else {
                    console.warn('⚠️ No authentication found - user may not be logged in');
                }
            }
            
            // Save onboarding data to user settings
            const response = await fetch('/api/user/settings', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    native_language: this.onboardingData.native_language,
                    target_language: this.onboardingData.target_language,
                    proficiency_level: this.onboardingData.proficiency_level,
                    learning_focus: this.onboardingData.learning_focus,
                    onboarding_completed: true
                })
            });

            console.log('📡 Settings API response status:', response.status);
            const data = await response.json();
            console.log('📋 Settings API response data:', data);
            
            if (data.success) {
                console.log('✅ Onboarding data saved successfully');
                
                // Update course configuration
                this.updateCourseConfiguration();
                
                // Hide onboarding
                this.hide();
                
                // Show success message
                this.showSuccessMessage();
                
                // Trigger UI updates before reloading
                console.log('🔄 Triggering UI updates...');
                
                // Trigger levels refresh if available
                if (typeof window.renderLevels === 'function') {
                    try {
                        window.renderLevels();
                        console.log('✅ Levels refreshed');
                    } catch (error) {
                        console.log('⚠️ Could not refresh levels:', error);
                    }
                }
                
                // Trigger target language dropdown refresh if available
                if (typeof window.ensureTargetLangOptions === 'function') {
                    try {
                        window.ensureTargetLangOptions();
                        console.log('✅ Target language options refreshed');
                    } catch (error) {
                        console.log('⚠️ Could not refresh target language options:', error);
                    }
                }
                
                // Refresh the app to apply all changes
                console.log('🔄 Refreshing app in 1.5 seconds...');
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else {
                console.error('❌ Failed to save onboarding data:', data.error);
                this.showErrorMessage('Failed to save your preferences. Please try again.');
            }
        } catch (error) {
            console.error('❌ Onboarding completion error:', error);
            console.error('Error details:', error.message, error.stack);
            this.showErrorMessage('An error occurred. Please try again.');
        }
    }

    updateCourseConfiguration() {
        console.log('🔧 Updating course configuration with onboarding data...');
        console.log('📊 Current onboarding data:', this.onboardingData);
        
        // Update localStorage first
        localStorage.setItem('siluma_native', this.onboardingData.native_language);
        localStorage.setItem('siluma_target', this.onboardingData.target_language);
        localStorage.setItem('siluma_cefr', this.onboardingData.proficiency_level);
        localStorage.setItem('siluma_topic', this.onboardingData.learning_focus);
        
        console.log('✅ localStorage updated:', {
            native: this.onboardingData.native_language,
            target: this.onboardingData.target_language,
            cefr: this.onboardingData.proficiency_level,
            topic: this.onboardingData.learning_focus
        });
        
        // Verify localStorage was actually updated
        console.log('🔍 Verify localStorage values:', {
            native: localStorage.getItem('siluma_native'),
            target: localStorage.getItem('siluma_target'),
            cefr: localStorage.getItem('siluma_cefr'),
            topic: localStorage.getItem('siluma_topic')
        });
        
        // Update the main course configuration form
        const targetLangSelect = document.getElementById('target-lang');
        const cefrSelect = document.getElementById('cefr');
        const topicSelect = document.getElementById('topic');

        if (targetLangSelect) {
            targetLangSelect.value = this.onboardingData.target_language;
            console.log('✅ Set target-lang to:', this.onboardingData.target_language);
            
            // Trigger change event to update dependent UI
            targetLangSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
        
        if (cefrSelect) {
            // Ensure the value exists in the select options
            const valueToSet = this.onboardingData.proficiency_level;
            console.log('🔍 CEFR value from onboarding:', valueToSet);
            console.log('🔍 Available CEFR options:', Array.from(cefrSelect.options).map(o => o.value));
            
            const optionExists = Array.from(cefrSelect.options).some(opt => opt.value === valueToSet);
            
            if (optionExists) {
                cefrSelect.value = valueToSet;
                console.log('✅ Set cefr to:', valueToSet, '(option exists)');
            } else {
                console.warn('⚠️ CEFR value', valueToSet, 'not found in options');
                console.warn('⚠️ Available options are:', Array.from(cefrSelect.options).map(o => `${o.value}="${o.text}"`).join(', '));
                // Keep current value or fallback
            }
            
            // Trigger change event
            cefrSelect.dispatchEvent(new Event('change', { bubbles: true }));
        } else {
            console.warn('⚠️ CEFR select element not found on page');
        }
        
        if (topicSelect) {
            topicSelect.value = this.onboardingData.learning_focus;
            console.log('✅ Set topic to:', this.onboardingData.learning_focus);
            
            // Trigger change event
            topicSelect.dispatchEvent(new Event('change', { bubbles: true }));
        }
        
        // Update native language in settings if available
        const nativeLangSelect = document.getElementById('native-lang-setting');
        if (nativeLangSelect) {
            nativeLangSelect.value = this.onboardingData.native_language;
            nativeLangSelect.dispatchEvent(new Event('change', { bubbles: true }));
            console.log('✅ Set native language setting to:', this.onboardingData.native_language);
        }
        
        // Set the locale for the app
        if (window.setLocale) {
            window.setLocale(this.onboardingData.native_language);
            console.log('✅ Set app locale to:', this.onboardingData.native_language);
        }
        
        console.log('✅ Course configuration update complete');
    }

    skipOnboarding() {
        // Set default values (use current settings or fallback)
        this.onboardingData = {
            native_language: localStorage.getItem('siluma_native') || 'de',
            target_language: localStorage.getItem('siluma_target') || 'ar',
            proficiency_level: localStorage.getItem('siluma_cefr') || 'none',
            learning_focus: 'daily life'
        };

        this.updateCourseConfiguration();
        this.hide();
    }

    showSuccessMessage() {
        // Create a temporary success message
        const successDiv = document.createElement('div');
        successDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--success);
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            z-index: 10001;
            font-weight: 500;
            animation: slideInRight 0.3s ease;
        `;
        successDiv.textContent = 'Welcome to Siluma! Your preferences have been saved.';
        document.body.appendChild(successDiv);

        // Remove after 3 seconds
        setTimeout(() => {
            successDiv.remove();
        }, 3000);
    }

    showErrorMessage(message) {
        // Create a temporary error message
        const errorDiv = document.createElement('div');
        errorDiv.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--warn);
            color: white;
            padding: 16px 24px;
            border-radius: 12px;
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
            z-index: 10001;
            font-weight: 500;
            animation: slideInRight 0.3s ease;
        `;
        errorDiv.textContent = message;
        document.body.appendChild(errorDiv);

        // Remove after 5 seconds
        setTimeout(() => {
            errorDiv.remove();
        }, 5000);
    }
}

// Initialize onboarding manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.onboardingManager = new OnboardingManager();
});

// Add CSS animation for success message
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            opacity: 0;
            transform: translateX(100%);
        }
        to {
            opacity: 1;
            transform: translateX(0);
        }
    }
`;
document.head.appendChild(style);
