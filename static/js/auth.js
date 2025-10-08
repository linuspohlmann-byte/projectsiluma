// Authentication management
class AuthManager {
    constructor() {
        this.sessionToken = localStorage.getItem('session_token');
        this.currentUser = null;
        this.init();
    }

    init() {
        this.setupEventListeners();
        this.checkAuthStatus();
    }

    setupEventListeners() {
        // Login button
        document.getElementById('login-btn')?.addEventListener('click', () => {
            this.showLoginModal();
        });

        // Register button
        document.getElementById('register-btn')?.addEventListener('click', () => {
            this.showRegisterModal();
        });

        // Settings button
        document.getElementById('settings-btn')?.addEventListener('click', () => {
            if (window.settingsManager) {
                window.settingsManager.showSettingsModal();
            }
        });

        // Logout button
        document.getElementById('logout-btn')?.addEventListener('click', () => {
            this.logout();
        });

        // Login form
        document.getElementById('login-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleLogin();
        });

        // Register form
        document.getElementById('register-form')?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleRegister();
        });

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', (e) => {
                this.hideModals();
            });
        });

        // Close modals on backdrop click
        document.querySelectorAll('.modal').forEach(modal => {
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    this.hideModals();
                }
            });
        });
    }

    async checkAuthStatus() {
        if (!this.sessionToken) {
            this.showLoginSection();
            return;
        }

        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${this.sessionToken}`
                }
            });

            if (response.ok) {
                const data = await response.json();
                this.currentUser = data.user;
                this.showAuthSection();
            } else {
                this.clearSession();
                this.showLoginSection();
            }
        } catch (error) {
            console.error('Auth check failed:', error);
            this.clearSession();
            this.showLoginSection();
        }
    }

    showLoginModal() {
        document.getElementById('login-modal').style.display = 'flex';
        document.getElementById('login-modal').style.alignItems = 'center';
        document.getElementById('login-modal').style.justifyContent = 'center';
        document.body.style.overflow = 'hidden';
        document.getElementById('login-username').focus();
    }

    showRegisterModal() {
        document.getElementById('register-modal').style.display = 'flex';
        document.getElementById('register-modal').style.alignItems = 'center';
        document.getElementById('register-modal').style.justifyContent = 'center';
        document.body.style.overflow = 'hidden';
        document.getElementById('register-username').focus();
    }

    hideModals() {
        document.getElementById('login-modal').style.display = 'none';
        document.getElementById('register-modal').style.display = 'none';
        if (window.settingsManager) {
            window.settingsManager.hideSettingsModal();
        }
        // Restore body scroll
        document.body.style.overflow = 'auto';
        this.clearErrors();
    }

    showLoginSection() {
        document.getElementById('login-section').style.display = 'flex';
        document.getElementById('auth-section').style.display = 'none';
    }

    showAuthSection() {
        document.getElementById('login-section').style.display = 'none';
        document.getElementById('auth-section').style.display = 'flex';
        
        // Update username display with current user data
        const userNameElement = document.getElementById('user-name');
        if (userNameElement) {
            userNameElement.textContent = this.currentUser?.username || 'User';
            console.log('👤 Username displayed:', this.currentUser?.username || 'User');
        }
    }

    async handleLogin() {
        const username = document.getElementById('login-username').value.trim();
        const password = document.getElementById('login-password').value;

        if (!username || !password) {
            this.showError('login-error', 'Please fill in all fields');
            return;
        }

        try {
            const response = await fetch('/api/auth/login', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password
                })
            });

            const data = await response.json();

            if (data.success) {
                this.sessionToken = data.session_token;
                this.currentUser = { id: data.user_id, username: username };
                localStorage.setItem('session_token', this.sessionToken);
                this.hideModals();
                this.showAuthSection();
                this.clearErrors();
                
                // Load full user data to get complete user information
                await this.loadCurrentUser();
                
                // Reload the app to ensure all modules initialize with authenticated state
                this.reloadApp();
                return;
            } else {
                this.showError('login-error', data.error || 'Login failed');
            }
        } catch (error) {
            console.error('Login error:', error);
            this.showError('login-error', 'Login failed. Please try again.');
        }
    }

    async handleRegister() {
        const username = document.getElementById('register-username').value.trim();
        const email = document.getElementById('register-email').value.trim();
        const password = document.getElementById('register-password').value;

        if (!username || !email || !password) {
            this.showError('register-error', 'Please fill in all fields');
            return;
        }

        if (username.length < 3) {
            this.showError('register-error', 'Username must be at least 3 characters');
            return;
        }

        if (password.length < 6) {
            this.showError('register-error', 'Password must be at least 6 characters');
            return;
        }

        try {
            const response = await fetch('/api/auth/register', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    email: email,
                    password: password
                })
            });

            const data = await response.json();

            if (data.success) {
                this.sessionToken = data.session_token;
                this.currentUser = { id: data.user_id, username: username };
                localStorage.setItem('session_token', this.sessionToken);
                this.hideModals();
                this.showAuthSection();
                this.clearErrors();
                
                // Load full user data to get complete user information
                await this.loadCurrentUser();
                
                // Show onboarding for new users
                if (window.onboardingManager) {
                    window.onboardingManager.show();
                }
                
                // Refresh level states to show user-specific data
                if (window.refreshLevelStates) {
                    window.refreshLevelStates();
                }
            } else {
                this.showError('register-error', data.error || 'Registration failed');
            }
        } catch (error) {
            console.error('Registration error:', error);
            this.showError('register-error', 'Registration failed. Please try again.');
        }
    }

    async logout() {
        try {
            if (this.sessionToken) {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    headers: {
                        'Authorization': `Bearer ${this.sessionToken}`
                    }
                });
            }
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            this.clearSession();
            this.showLoginSection();
            
            // Refresh level states to clear user-specific data
            if (window.refreshLevelStates) {
                window.refreshLevelStates();
            }
            
            // Invalidate words cache to clear user-specific data
            if (window.invalidateWordsCache) {
                const targetLang = document.getElementById('target-lang')?.value || 'en';
                window.invalidateWordsCache(targetLang);
            }
        }
    }

    clearSession() {
        this.sessionToken = null;
        this.currentUser = null;
        localStorage.removeItem('session_token');
    }

    showError(elementId, message) {
        const errorElement = document.getElementById(elementId);
        if (errorElement) {
            errorElement.textContent = message;
            errorElement.style.display = 'block';
        }
    }

    clearErrors() {
        document.getElementById('login-error').style.display = 'none';
        document.getElementById('register-error').style.display = 'none';
    }

    reloadApp(delay = 50) {
        if (typeof window === 'undefined' || !window.location?.reload) {
            return;
        }
        setTimeout(() => window.location.reload(), delay);
    }

    // Get current session token for API calls
    getAuthHeaders() {
        if (this.sessionToken) {
            return {
                'Authorization': `Bearer ${this.sessionToken}`
            };
        }
        return {};
    }

    // Check if user is authenticated
    isAuthenticated() {
        return !!this.sessionToken && !!this.currentUser;
    }

    // Get current user ID
    getCurrentUserId() {
        return this.currentUser?.id;
    }

    // Load current user data from server
    async loadCurrentUser() {
        if (!this.sessionToken) {
            return;
        }

        try {
            const response = await fetch('/api/auth/me', {
                headers: this.getAuthHeaders()
            });

            if (response.ok) {
                const data = await response.json();
                if (data.success && data.user) {
                    this.currentUser = data.user;
                    // Update the username display immediately
                    const userNameElement = document.getElementById('user-name');
                    if (userNameElement) {
                        userNameElement.textContent = this.currentUser.username;
                    }
                    console.log('✅ User data loaded:', this.currentUser.username);
                }
            } else {
                console.warn('⚠️ Failed to load user data');
            }
        } catch (error) {
            console.error('❌ Error loading user data:', error);
        }
    }
}

// Global auth manager instance
window.authManager = new AuthManager();

// Export for use in other modules
export { AuthManager };
