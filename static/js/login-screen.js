/**
 * Login Screen Manager
 * Handles the initial login screen that shows during app initialization
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let isInitialized = false;
let initializationPromise = null;

/**
 * Show login screen
 */
export function showLoginScreen() {
    const screen = $('#login-screen');
    const appShell = $('#app-shell');
    
    if (screen) {
        screen.classList.remove('hidden');
    }
    
    if (appShell) {
        appShell.style.display = 'none';
    }
}

/**
 * Hide login screen and show app
 */
export function hideLoginScreen() {
    const screen = $('#login-screen');
    const appShell = $('#app-shell');
    
    if (screen) {
        screen.classList.add('hidden');
        // Remove from DOM after animation
        setTimeout(() => {
            if (screen) {
                screen.style.display = 'none';
            }
        }, 300);
    }
    
    if (appShell) {
        appShell.style.display = 'block';
    }
}

/**
 * Show loading state
 */
export function showLoginScreenLoading() {
    const loading = $('#login-screen-loading');
    const form = $('#login-screen-form');
    
    if (loading) {
        loading.style.display = 'block';
    }
    
    if (form) {
        form.style.display = 'none';
    }
}

/**
 * Show login form
 */
export function showLoginScreenForm() {
    const loading = $('#login-screen-loading');
    const form = $('#login-screen-form');
    const loginForm = $('#login-screen-login-form');
    const registerForm = $('#login-screen-register-form');
    
    if (loading) {
        loading.style.display = 'none';
    }
    
    if (form) {
        form.style.display = 'block';
    }
    
    // Show login form, hide register form
    if (loginForm) {
        loginForm.style.display = 'block';
    }
    
    if (registerForm) {
        registerForm.style.display = 'none';
    }
    
    // Clear errors
    hideLoginScreenError();
}

/**
 * Show register form
 */
export function showRegisterForm() {
    const loginForm = $('#login-screen-login-form');
    const registerForm = $('#login-screen-register-form');
    
    if (loginForm) {
        loginForm.style.display = 'none';
    }
    
    if (registerForm) {
        registerForm.style.display = 'block';
    }
    
    // Clear errors
    hideLoginScreenError();
}

/**
 * Show error message
 */
export function showLoginScreenError(message) {
    const errorEl = $('#login-screen-error');
    if (errorEl) {
        errorEl.textContent = message;
        errorEl.style.display = 'block';
    }
}

/**
 * Hide error message
 */
export function hideLoginScreenError() {
    const errorEl = $('#login-screen-error');
    if (errorEl) {
        errorEl.style.display = 'none';
        errorEl.textContent = '';
    }
}

/**
 * Initialize login screen event handlers
 */
function initLoginScreenHandlers() {
    // Login form submission
    const loginForm = $('#login-screen-login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleLoginScreenLogin();
        });
    }
    
    // Register form submission
    const registerForm = $('#login-screen-register-form');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleLoginScreenRegister();
        });
    }
    
    // Switch to register form
    const registerBtn = $('#login-screen-register-btn');
    if (registerBtn) {
        registerBtn.addEventListener('click', () => {
            showRegisterForm();
        });
    }
    
    // Switch back to login form
    const backToLoginBtn = $('#login-screen-back-to-login-btn');
    if (backToLoginBtn) {
        backToLoginBtn.addEventListener('click', () => {
            showLoginScreenForm();
        });
    }
}

/**
 * Handle login from login screen
 */
async function handleLoginScreenLogin() {
    const username = $('#login-screen-username')?.value.trim();
    const password = $('#login-screen-password')?.value;
    
    if (!username || !password) {
        showLoginScreenError('Bitte fülle alle Felder aus.');
        return;
    }
    
    hideLoginScreenError();
    showLoginScreenLoading();
    
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
            // Store session token
            localStorage.setItem('session_token', data.session_token);
            
            // Reload app initialization
            await initializeApp();
        } else {
            showLoginScreenError(data.error || 'Anmeldung fehlgeschlagen');
            showLoginScreenForm();
        }
    } catch (error) {
        console.error('Login error:', error);
        showLoginScreenError('Fehler bei der Anmeldung. Bitte versuche es erneut.');
        showLoginScreenForm();
    }
}

/**
 * Handle registration from login screen
 */
async function handleLoginScreenRegister() {
    const username = $('#login-screen-register-username')?.value.trim();
    const email = $('#login-screen-register-email')?.value.trim();
    const password = $('#login-screen-register-password')?.value;
    
    if (!username || !email || !password) {
        showLoginScreenError('Bitte fülle alle Felder aus.');
        return;
    }
    
    if (username.length < 3) {
        showLoginScreenError('Benutzername muss mindestens 3 Zeichen lang sein.');
        return;
    }
    
    if (password.length < 6) {
        showLoginScreenError('Passwort muss mindestens 6 Zeichen lang sein.');
        return;
    }
    
    hideLoginScreenError();
    showLoginScreenLoading();
    
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
            // Store session token
            localStorage.setItem('session_token', data.session_token);
            
            // Reload app initialization
            await initializeApp();
        } else {
            showLoginScreenError(data.error || 'Registrierung fehlgeschlagen');
            showLoginScreenForm();
        }
    } catch (error) {
        console.error('Registration error:', error);
        showLoginScreenError('Fehler bei der Registrierung. Bitte versuche es erneut.');
        showLoginScreenForm();
    }
}

/**
 * Initialize app (called after authentication check)
 */
async function initializeApp() {
    if (isInitialized) {
        return;
    }
    
    console.log('🚀 Starting app initialization...');
    
    // Import main initialization
    const { initializeAppContent } = await import('./main.js');
    
    // Also trigger custom level groups loading in background
    if (typeof window.showCustomLevelGroupsInLibrary === 'function') {
        // This will be called after topbar is initialized
        setTimeout(() => {
            try {
                window.showCustomLevelGroupsInLibrary();
            } catch (error) {
                console.warn('Could not load custom level groups:', error);
            }
        }, 500);
    }
    
    await initializeAppContent();
    
    isInitialized = true;
    hideLoginScreen();
    
    console.log('✅ App initialization complete');
}

/**
 * Check authentication and initialize app
 */
export async function checkAuthAndInitialize() {
    if (initializationPromise) {
        return initializationPromise;
    }
    
    initializationPromise = (async () => {
        // Show login screen immediately
        showLoginScreen();
        showLoginScreenLoading();
        
        // Initialize handlers
        initLoginScreenHandlers();
        
        // Check if user has session token
        const sessionToken = localStorage.getItem('session_token');
        
        if (!sessionToken) {
            // No session token, show login form
            showLoginScreenForm();
            return;
        }
        
        // Check session validity
        try {
            const response = await fetch('/api/auth/me', {
                headers: {
                    'Authorization': `Bearer ${sessionToken}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.user) {
                    // Valid session, initialize app in background
                    await initializeApp();
                    return;
                }
            }
        } catch (error) {
            console.error('Auth check failed:', error);
        }
        
        // Invalid session, show login form
        localStorage.removeItem('session_token');
        showLoginScreenForm();
    })();
    
    return initializationPromise;
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', checkAuthAndInitialize);
} else {
    checkAuthAndInitialize();
}

