/**
 * Onboarding Manager - Handles the user onboarding flow
 */
class OnboardingManager {
    constructor() {
        this.currentStep = 1;
        this.totalSteps = 4;
        this.onboardingData = {
            native_language: 'de',
            target_language: 'ar',
            proficiency_level: 'A1',
            learning_focus: 'daily life'
        };
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAvailableLanguages();
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
            }
        });
    }

    show() {
        document.getElementById('onboarding-modal').style.display = 'flex';
        this.currentStep = 1;
        this.updateProgress();
        this.showStep(1);
        
        // Apply localization to onboarding elements
        if (window.applyI18n) {
            window.applyI18n();
        }
        
        // Load available languages and apply localization
        this.loadAvailableLanguages();
        
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
            // Check cache first
            const cachedLanguages = localStorage.getItem('available_languages');
            if (cachedLanguages) {
                try {
                    const languages = JSON.parse(cachedLanguages);
                    if (languages.success && languages.languages) {
                        console.log('Using cached available languages in onboarding');
                        this.populateLanguageSelects(languages.languages);
                        return;
                    }
                } catch (error) {
                    console.log('Error parsing cached languages in onboarding:', error);
                }
            }
            
            const response = await fetch('/api/available-languages');
            const languages = await response.json();
            
            // Cache the result
            if (languages.success) {
                localStorage.setItem('available_languages', JSON.stringify(languages));
            }
            
            if (languages.success) {
                this.populateLanguageSelects(languages.languages);
            }
        } catch (error) {
            console.error('Failed to load available languages:', error);
        }
    }

    populateLanguageSelects(languages) {
        const nativeSelect = document.getElementById('onboarding-native-lang');
        const targetSelect = document.getElementById('onboarding-target-lang');

        if (nativeSelect) {
            nativeSelect.innerHTML = '';
            languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                option.textContent = lang.native_name;
                option.setAttribute('data-i18n', `language_names.${lang.code}`);
                nativeSelect.appendChild(option);
            });
            
            // Apply localization to the select options
            if (window.applyI18n) {
                window.applyI18n();
            }
        }

        if (targetSelect) {
            targetSelect.innerHTML = '';
            languages.forEach(lang => {
                const option = document.createElement('option');
                option.value = lang.code;
                option.textContent = lang.native_name;
                option.setAttribute('data-i18n', `language_names.${lang.code}`);
                targetSelect.appendChild(option);
            });
            
            // Apply localization to the select options
            if (window.applyI18n) {
                window.applyI18n();
            }
        }
    }

    applyNativeLanguage(langCode) {
        // Update localStorage
        localStorage.setItem('siluma_native', langCode);
        
        // Apply localization
        if (window.setLocale) {
            window.setLocale(langCode);
            
            // Listen for translations to be loaded
            const handleTranslationsLoaded = (event) => {
                console.log('🌍 Onboarding: Translations loaded from:', event.detail.source, 'for locale:', event.detail.locale);
                
                // Apply i18n updates to onboarding elements
                if (window.applyI18n) {
                    window.applyI18n();
                }
                
                // Re-populate language selects with localized names
                this.loadAvailableLanguages();
                
                // Remove the event listener
                window.removeEventListener('translationsLoaded', handleTranslationsLoaded);
            };
            
            // Add event listener for when translations are loaded
            window.addEventListener('translationsLoaded', handleTranslationsLoaded);
            
            // Fallback timeout in case the event doesn't fire
            setTimeout(() => {
                window.removeEventListener('translationsLoaded', handleTranslationsLoaded);
                console.log('🌍 Onboarding: Fallback: Applying translations after timeout');
                
                // Apply i18n updates
                if (window.applyI18n) {
                    window.applyI18n();
                }
                
                // Re-populate language selects
                this.loadAvailableLanguages();
            }, 1000); // Fallback after 1 second
        }
    }

    async finishOnboarding() {
        try {
            // Save onboarding data to user settings
            const response = await fetch('/api/user/settings', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                },
                body: JSON.stringify({
                    native_language: this.onboardingData.native_language,
                    target_language: this.onboardingData.target_language,
                    proficiency_level: this.onboardingData.proficiency_level,
                    learning_focus: this.onboardingData.learning_focus,
                    onboarding_completed: true
                })
            });

            const data = await response.json();
            
            if (data.success) {
                // Update course configuration
                this.updateCourseConfiguration();
                
                // Hide onboarding
                this.hide();
                
                // Show success message
                this.showSuccessMessage();
                
                // Refresh the app
                setTimeout(() => {
                    window.location.reload();
                }, 2000);
            } else {
                console.error('Failed to save onboarding data:', data.error);
                this.showErrorMessage('Failed to save your preferences. Please try again.');
            }
        } catch (error) {
            console.error('Onboarding completion error:', error);
            this.showErrorMessage('An error occurred. Please try again.');
        }
    }

    updateCourseConfiguration() {
        // Update the main course configuration form
        const targetLangSelect = document.getElementById('target-lang');
        const cefrSelect = document.getElementById('cefr');
        const topicSelect = document.getElementById('topic');

        if (targetLangSelect) {
            targetLangSelect.value = this.onboardingData.target_language;
        }
        
        if (cefrSelect) {
            cefrSelect.value = this.onboardingData.proficiency_level;
        }
        
        if (topicSelect) {
            topicSelect.value = this.onboardingData.learning_focus;
        }

        // Update localStorage
        localStorage.setItem('siluma_native', this.onboardingData.native_language);
        localStorage.setItem('siluma_target', this.onboardingData.target_language);
        localStorage.setItem('siluma_cefr', this.onboardingData.proficiency_level);
        localStorage.setItem('siluma_topic', this.onboardingData.learning_focus);
    }

    skipOnboarding() {
        // Set default values
        this.onboardingData = {
            native_language: 'de',
            target_language: 'ar',
            proficiency_level: 'A1',
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
