// Header Statistics Module
// Manages the display of course statistics in the modern header

import { t } from '../i18n.js';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// State
let currentLanguage = 'en';
let isUserAuthenticated = false;
let lastStatsUpdate = 0;
const STATS_UPDATE_THROTTLE = 2000; // Minimum 2 seconds between updates

// Elements
let totalWordsEl, memorizedWordsEl, progressEl;

/**
 * Initialize header statistics
 */
export function initHeaderStats() {
  // Get elements
  totalWordsEl = $('#total-words-count');
  memorizedWordsEl = $('#memorized-words-count');
  progressEl = $('#learning-progress');
  
  // Initialize current language from the dropdown value
  const targetLangSelect = $('#target-lang');
  if (targetLangSelect) {
    currentLanguage = targetLangSelect.value || 'en';
  }
  
  // Listen for language changes
  if (targetLangSelect) {
    targetLangSelect.addEventListener('change', (e) => {
      currentLanguage = e.target.value;
      updateStats();
    });
  }
  
  // Listen for authentication changes
  if (window.authManager) {
    // Check initial state
    isUserAuthenticated = window.authManager.isAuthenticated();
    
    // Listen for auth state changes
    document.addEventListener('authStateChanged', () => {
      isUserAuthenticated = window.authManager.isAuthenticated();
      updateStats();
    });
  }
  
  // Listen for topbar ready event to ensure language is properly set
  document.addEventListener('topbarReady', () => {
    // Re-check language after topbar is fully initialized
    if (targetLangSelect && targetLangSelect.value) {
      currentLanguage = targetLangSelect.value;
    }
    updateStats();
  });
  
  // Initial update with a small delay to ensure language is set
  setTimeout(() => {
    // Re-check language in case it was set after initialization
    if (targetLangSelect && targetLangSelect.value) {
      currentLanguage = targetLangSelect.value;
    }
    updateStats();
  }, 100);
}

/**
 * Update all header statistics with throttling
 */
export async function updateStats(force = false) {
  if (!currentLanguage) return;
  
  // Throttle updates to prevent excessive API calls
  const now = Date.now();
  if (!force && (now - lastStatsUpdate) < STATS_UPDATE_THROTTLE) {
    console.log('📊 Stats update throttled - too frequent');
    return;
  }
  lastStatsUpdate = now;
  
  try {
    if (isUserAuthenticated) {
      // For authenticated users, use the more accurate words data
      await updateFromWordsData();
    } else {
      // For unauthenticated users, use the bulk API data (fallback)
      // This will be called from the levels module when bulk data is available
      console.log('User not authenticated - using bulk API data for stats');
    }
    await updateLearningProgress();
  } catch (error) {
    console.error('Error updating header stats:', error);
  }
}

/**
 * Update header stats from bulk API data (optimized)
 */
export function updateFromBulkData(headerStats) {
  if (!headerStats) return;
  
  try {
    // Only update if values have changed to prevent unnecessary DOM updates
    const currentTotal = totalWordsEl ? totalWordsEl.textContent : '';
    const currentMemorized = memorizedWordsEl ? memorizedWordsEl.textContent : '';
    
    const newTotal = headerStats.total_words !== undefined ? headerStats.total_words.toLocaleString() : currentTotal;
    const newMemorized = headerStats.memorized_words !== undefined ? headerStats.memorized_words.toLocaleString() : currentMemorized;
    
    // Update total words count only if changed
    if (totalWordsEl && headerStats.total_words !== undefined && currentTotal !== newTotal) {
      totalWordsEl.textContent = newTotal;
      totalWordsEl.style.transform = 'scale(1.1)';
      setTimeout(() => {
        totalWordsEl.style.transform = 'scale(1)';
      }, 200);
    }
    
    // Update memorized words count only if changed
    if (memorizedWordsEl && headerStats.memorized_words !== undefined && currentMemorized !== newMemorized) {
      memorizedWordsEl.textContent = newMemorized;
      memorizedWordsEl.style.transform = 'scale(1.1)';
      setTimeout(() => {
        memorizedWordsEl.style.transform = 'scale(1)';
      }, 200);
    }
    
    console.log('📊 Header stats updated from bulk data:', headerStats);
  } catch (error) {
    console.error('Error updating header stats from bulk data:', error);
  }
}

/**
 * Update header stats from actual words data (more accurate)
 */
export async function updateFromWordsData() {
  if (!currentLanguage) return;
  
  // Only update from words data if user is authenticated
  if (!isUserAuthenticated) {
    console.log('Skipping words data update - user not authenticated');
    return;
  }
  
  try {
    // Get actual words data from the Words tab
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    // Add language parameter as required by the API
    const response = await fetch(`/api/words?language=${encodeURIComponent(currentLanguage)}`, { headers });
    if (!response.ok) {
      console.error('Failed to fetch words data for stats:', response.status, response.statusText);
      return;
    }
    
    const words = await response.json();
    
    // Count total words
    const totalWords = words.length;
    
    // Count learned words (familiarity = 5)
    const learnedWords = words.filter(word => word.familiarity === 5).length;
    
    // Update UI elements
    if (totalWordsEl) {
      totalWordsEl.textContent = totalWords.toLocaleString();
      totalWordsEl.style.transform = 'scale(1.1)';
      setTimeout(() => {
        totalWordsEl.style.transform = 'scale(1)';
      }, 200);
    }
    
    if (memorizedWordsEl) {
      memorizedWordsEl.textContent = learnedWords.toLocaleString();
      memorizedWordsEl.style.transform = 'scale(1.1)';
      setTimeout(() => {
        memorizedWordsEl.style.transform = 'scale(1)';
      }, 200);
    }
    
    console.log('📊 Header stats updated from words data:', { totalWords, learnedWords });
  } catch (error) {
    console.error('Error updating header stats from words data:', error);
  }
}

/**
 * Update total words count for current language
 */
async function updateTotalWordsCount() {
  if (!totalWordsEl) return;
  
  // This function is now deprecated - use updateFromBulkData instead
  // The bulk API already provides header stats, so individual calls are not needed
  console.log('updateTotalWordsCount called - this should be replaced by updateFromBulkData');
}

/**
 * Update memorized words count (familiarity level 5)
 */
async function updateMemorizedWordsCount() {
  if (!memorizedWordsEl) return;
  
  // This function is now deprecated - use updateFromBulkData instead
  // The bulk API already provides header stats, so individual calls are not needed
  console.log('updateMemorizedWordsCount called - this should be replaced by updateFromBulkData');
}

/**
 * Update learning progress percentage
 */
async function updateLearningProgress() {
  if (!progressEl) return;
  
  try {
    if (isUserAuthenticated) {
      // For authenticated users, calculate progress based on completed levels
      const response = await fetch(`/api/user/progress-summary?language=${encodeURIComponent(currentLanguage)}`, {
        headers: window.authManager ? window.authManager.getAuthHeaders() : {}
      });
      
      if (response.ok) {
        const data = await response.json();
        const progress = data.overall_progress || 0;
        progressEl.textContent = `${Math.round(progress)}%`;
      } else {
        progressEl.textContent = '0%';
      }
    } else {
      // For unauthenticated users, show 0%
      progressEl.textContent = '0%';
    }
    
    // Add animation
    progressEl.style.transform = 'scale(1.1)';
    setTimeout(() => {
      progressEl.style.transform = 'scale(1)';
    }, 200);
  } catch (error) {
    console.error('Error fetching learning progress:', error);
    progressEl.textContent = '0%';
  }
}

/**
 * Refresh stats when user completes a level or word
 */
export function refreshStats() {
  updateStats();
}

/**
 * Set language for stats
 */
export function setLanguage(language) {
  currentLanguage = language;
  updateStats();
}

/**
 * Set authentication state
 */
export function setAuthenticationState(authenticated) {
  isUserAuthenticated = authenticated;
  updateStats();
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initHeaderStats);
} else {
  initHeaderStats();
}

// Export for global access
if (typeof window !== 'undefined') {
  window.headerStats = {
    update: updateStats,
    refresh: refreshStats,
    setLanguage,
    setAuthenticationState,
    updateFromBulkData,
    updateFromWordsData
  };
}
