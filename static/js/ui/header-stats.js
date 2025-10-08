// Header Statistics Module
// Manages the display of course statistics in the modern header

import { t } from '../i18n.js';

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

// State
let currentLanguage = 'en';
let isUserAuthenticated = false;
let lastStatsUpdate = 0;
let statsUpdatePending = false;
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
    console.log('📊 Header stats: Initial auth state:', isUserAuthenticated);
    console.log('🔍 Auth debug - authManager exists:', !!window.authManager);
    if (window.authManager) {
      console.log('🔍 Auth debug - sessionToken:', !!window.authManager.sessionToken);
      console.log('🔍 Auth debug - currentUser:', !!window.authManager.currentUser);
      console.log('🔍 Auth debug - currentUser data:', window.authManager.currentUser);
    }
    
    // Listen for auth state changes
    document.addEventListener('authStateChanged', () => {
      const newAuthState = window.authManager.isAuthenticated();
      console.log('📊 Header stats: Auth state changed to:', newAuthState);
      isUserAuthenticated = newAuthState;
      updateStats(true); // Force update when auth state changes
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
    console.log('📊 Initial header stats update - language:', currentLanguage, 'authenticated:', isUserAuthenticated);
    updateStats(true); // Force update on initialization
  }, 100);
}

/**
 * Update all header statistics with intelligent batching
 */
export async function updateStats(force = false) {
  if (!currentLanguage) return;
  
  // Update authentication state before proceeding
  if (window.authManager) {
    isUserAuthenticated = window.authManager.isAuthenticated();
    console.log('🔍 UpdateStats auth debug - sessionToken:', !!window.authManager.sessionToken);
    console.log('🔍 UpdateStats auth debug - currentUser:', !!window.authManager.currentUser);
    console.log('🔍 UpdateStats auth debug - isAuthenticated result:', isUserAuthenticated);
  }
  
  // Batch multiple update requests
  if (!force && statsUpdatePending) {
    console.log('📊 Stats update batched - combining with pending update');
    return;
  }
  
  // Throttle updates to prevent excessive API calls
  const now = Date.now();
  if (!force && (now - lastStatsUpdate) < STATS_UPDATE_THROTTLE) {
    console.log('📊 Stats update throttled - too frequent');
    return;
  }
  
  statsUpdatePending = true;
  lastStatsUpdate = now;
  
  // Batch all stats updates in a single operation
  try {
    // Always use the words data API for both authenticated and unauthenticated users
    // The API endpoints handle both cases appropriately
    await updateFromWordsData();
    await updateLearningProgress();
  } catch (error) {
    console.error('Error updating header stats:', error);
  } finally {
    statsUpdatePending = false;
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
  if (!currentLanguage) {
    console.log('📊 Skipping words data update - no current language');
    return;
  }
  
  console.log('📊 Starting words data update for language:', currentLanguage, 'user authenticated:', isUserAuthenticated);
  
  try {
    // Get actual words data from the Words tab
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    // Add native language header for unauthenticated users
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    // Use separate API endpoints for better performance
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
    
    // Get active learning words (familiarity < 5)
    let learningResponse = null;
    if (isUserAuthenticated) {
      const learningParams = new URLSearchParams({
        language: currentLanguage,
        min_familiarity: '1',
        max_familiarity: '4',
        limit: '1'
      });
      learningResponse = await fetch(`/api/words/learning?${learningParams.toString()}`, {
        headers,
        signal: controller.signal
      });
    }
    
    // Get learned words count (familiarity = 5) - only for authenticated users
    let learnedResponse = null;
    if (isUserAuthenticated) {
      learnedResponse = await fetch(`/api/words/count_learned?language=${encodeURIComponent(currentLanguage)}`, { 
        headers,
        signal: controller.signal
      });
    }
    
    clearTimeout(timeoutId);
    
    let activeWords = 0;
    let learnedWords = 0;
    
    if (learningResponse) {
      if (learningResponse.ok) {
        const learningData = await learningResponse.json();
        if (learningData && learningData.success) {
          activeWords = learningData.total || 0;
          console.log('📊 Active words API response:', learningData);
        } else {
          console.warn('📊 Learning words response did not include success flag, raw data:', learningData);
        }
      } else {
        console.error('Failed to fetch learning words:', learningResponse.status, learningResponse.statusText);
      }
    } else {
      console.log('📊 Skipping learning words fetch - user not authenticated');
      activeWords = 0;
    }
    
    if (learnedResponse && learnedResponse.ok) {
      const learnedData = await learnedResponse.json();
      learnedWords = learnedData.count || 0;
      console.log('📊 Learned words API response:', learnedData);
    } else if (learnedResponse) {
      console.error('Failed to fetch learned words count:', learnedResponse.status, learnedResponse.statusText);
    } else {
      console.log('📊 Skipping learned words count - user not authenticated');
      learnedWords = 0;
    }
    
    // Update UI elements
    if (totalWordsEl) {
      totalWordsEl.textContent = activeWords.toLocaleString();
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
    
    // Expose latest counts globally for other modules (e.g. library cards)
    if (!window.headerStats) window.headerStats = {};
    window.headerStats.latestCounts = {
      activeWords,
      memorizedWords: learnedWords
    };
    document.dispatchEvent(new CustomEvent('headerStatsUpdated', {
      detail: { activeWords, memorizedWords: learnedWords }
    }));
    
    console.log('📊 Header stats updated from words data:', { activeWords, learnedWords });
  } catch (error) {
    if (error.name === 'AbortError') {
      console.log('⏱️ Header stats update timed out - using fallback data');
      // Fallback to bulk data if words API is too slow
      if (window.headerStats && window.headerStats.updateFromBulkData) {
        window.headerStats.updateFromBulkData({ total_words: 0, memorized_words: 0 });
      }
    } else {
      console.error('Error updating header stats from words data:', error);
    }
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
