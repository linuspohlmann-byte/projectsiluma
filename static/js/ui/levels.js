// import { normalizeCounts, fetchStatusCounts } from './evaluation.js';
// local DOM helpers used in this module
const $ = (sel)=> document.querySelector(sel);
const $$ = (sel)=> Array.from(document.querySelectorAll(sel));

// Safe accessors for evaluation helpers exposed on window
const _evalNormalize = (typeof window !== 'undefined' && window.normalizeCounts) ? window.normalizeCounts : (x=>x||{0:0,1:0,2:0,3:0,4:0,5:0});
const _evalFetchCounts = (lvl, run)=>{
  if (typeof window !== 'undefined' && typeof window.fetchStatusCounts === 'function'){
    return window.fetchStatusCounts(lvl, run);
  }
  return Promise.resolve({0:0,1:0,2:0,3:0,4:0,5:0});
};

// _fetchLevelStats function removed - now using cached bulk data instead

function currentTargetLang(){ return (document.getElementById('target-lang')?.value||'en'); }

let LEVEL_SUMMARY_CACHE = null;
let LEVEL_SUMMARY_LANG = null;
let SELECTED_LEVEL_GROUP = null;
let LEVEL_GROUP_DEFS = null;
let LATEST_BULK_RESULT = { language: null, levels: {}, fetchedLevels: new Set() };
let CURRENT_VIEW_WORD_MAP = new Map();
let BULK_STATS_LAST_FETCH = 0;
let BULK_STATS_FETCH_THROTTLE = 2000; // 2 seconds throttle
let GROUPS_LOADING_LOCK = false; // Prevent race conditions in groups loading

// Configuration: Disable standard level groups (they won't be loaded in library)
const DISABLE_STANDARD_LEVEL_GROUPS = true; // Set to false to re-enable standard groups

// Central function to get level score from bulkData (same source as display)
// This ensures unlock logic uses the exact same data source as the UI display
function getLevelScoreFromBulkData(levelElement) {
  if (!levelElement || !levelElement.dataset.bulkData) {
    return 0;
  }
  
  try {
    const data = JSON.parse(levelElement.dataset.bulkData);
    // Use the same logic as the display: prefer user_progress.score, then last_score
    // This ensures we use the same source as the display
    const score = data.user_progress?.score || data.last_score;
    if (score !== null && score !== undefined) {
      // Score is already in 0-1 format, convert to 0-100
      return Math.round(Number(score) * 100);
    }
  } catch (error) {
    console.log('Error parsing bulkData for score:', error);
  }
  
  return 0;
}

// Function to show elegant level locked message
function showLevelLockedMessage(level, prevLevel, prevScore) {
  // Remove any existing message
  hideLevelLockedMessage();
  
  // Create overlay
  const overlay = document.createElement('div');
  overlay.className = 'level-locked-overlay';
  overlay.id = 'level-locked-overlay';
  
  // Create message
  const message = document.createElement('div');
  message.className = 'level-locked-message';
  message.id = 'level-locked-message';
  
  // prevScore is already in percent (0-100), no need to multiply
  const progressPercent = Math.round(prevScore || 0);
  const neededPercent = 60;
  const tt = (key, fallback, vars = {}) => {
    let text = (typeof window.t === 'function') ? window.t(key, fallback) : fallback;
    Object.entries(vars).forEach(([k, v]) => {
      text = text.replace(new RegExp(`\\{${k}\\}`, 'g'), String(v));
    });
    return text;
  };
  const title = tt('levels.locked_title', `Level ${level} is locked`, { level });
  const body = tt('levels.locked_body', `Complete level ${prevLevel} with at least ${neededPercent}% to unlock level ${level}.`, {
    level, prevLevel, percent: neededPercent
  });
  const progressLabel = tt('levels.locked_progress', `Level ${prevLevel} progress: ${progressPercent}%`, {
    prevLevel, percent: progressPercent
  });
  const requiredLabel = tt('levels.locked_required', `Required: ${neededPercent}%`, { percent: neededPercent });
  const continueLabel = tt('levels.continue_previous', `Continue level ${prevLevel}`, { level: prevLevel });
  const closeLabel = tt('buttons.close', 'Close');

  message.innerHTML = `
    <div class="icon">🔒</div>
    <div class="title">${title}</div>
    <div class="message">${body}</div>
    <div class="progress-info">
      <div class="progress-text">${progressLabel}</div>
      <div class="progress-bar">
        <div class="progress-fill" style="width: ${Math.min(progressPercent, 100)}%"></div>
      </div>
      <div class="progress-text">${requiredLabel}</div>
    </div>
    <div class="actions">
      <button class="btn btn-primary" onclick="goToPreviousLevel(${prevLevel})">
        ${continueLabel}
      </button>
      <button class="btn btn-secondary" onclick="hideLevelLockedMessage()">
        ${closeLabel}
      </button>
    </div>
  `;
  
  // Add to DOM
  document.body.appendChild(overlay);
  document.body.appendChild(message);
  
  // Close on overlay click
  overlay.onclick = (e) => {
    if (e.target === overlay) {
      hideLevelLockedMessage();
    }
  };
  
  // Close on Escape key
  const handleEscape = (e) => {
    if (e.key === 'Escape') {
      hideLevelLockedMessage();
      document.removeEventListener('keydown', handleEscape);
    }
  };
  document.addEventListener('keydown', handleEscape);
}

// Function to hide level locked message
function hideLevelLockedMessage() {
  const overlay = document.getElementById('level-locked-overlay');
  const message = document.getElementById('level-locked-message');
  
  if (overlay) overlay.remove();
  if (message) message.remove();
}

// Export getLevelScoreFromBulkData globally for use in other files
window.getLevelScoreFromBulkData = getLevelScoreFromBulkData;

// Function to go to previous level
function goToPreviousLevel(level) {
  hideLevelLockedMessage();
  
  // Start the previous level
  if(typeof window.startLevelWithTopic === 'function'){
    window.startLevelWithTopic(level, `Level ${level}`);
  } else if(typeof window.startLevel === 'function'){
    window.startLevel(level);
  }
}

// Function to unlock words when starting a level
async function unlockLevelWords(level) {
  const lang = currentTargetLang();
  
  // Get auth headers if user is logged in
  const headers = {};
  if (window.authManager && window.authManager.isAuthenticated()) {
    Object.assign(headers, window.authManager.getAuthHeaders());
  }
  
  try {
    const response = await fetch('/api/level/unlock-words', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...headers
      },
      body: JSON.stringify({ 
        level: level, 
        language: lang 
      })
    });
    
    if (response.ok) {
      const result = await response.json();
      console.log('Words unlocked for level', level, ':', result.message);
      return true;
    } else {
      console.error('Failed to unlock words for level', level);
      return false;
    }
  } catch (error) {
    console.error('Error unlocking words for level', level, ':', error);
    return false;
  }
}

// Debouncing for applyLevelStates to prevent multiple calls
let applyLevelStatesTimeout = null;
let isApplyingLevelStates = false;

// Function to refresh level states when user logs in/out
function refreshLevelStates() {
  console.log('Refreshing level states due to auth change...');
  
  // Apply immediate feedback first
  applyImmediateLevelStates();
  
  // Clear existing timeout
  if (applyLevelStatesTimeout) {
    clearTimeout(applyLevelStatesTimeout);
  }
  
  // Debounce the full API call
  applyLevelStatesTimeout = setTimeout(() => {
    applyLevelStates();
    // Group stats will be updated automatically by applyLevelStates
    applyLevelStatesTimeout = null;
  }, 100);
}

// Debounced version of applyLevelStates with immediate feedback
function debouncedApplyLevelStates() {
  // Apply immediate feedback first
  applyImmediateLevelStates();
  
  // Clear existing timeout
  if (applyLevelStatesTimeout) {
    clearTimeout(applyLevelStatesTimeout);
  }
  
  // Debounce the full API call
  applyLevelStatesTimeout = setTimeout(() => {
    applyLevelStates();
    // Group stats will be updated automatically by applyLevelStates
    applyLevelStatesTimeout = null;
  }, 50);
}

// Expose refresh function globally for auth manager
window.refreshLevelStates = refreshLevelStates;

// Function to sync user data
// Note: This endpoint may not exist in all deployments
// Made optional to prevent errors if endpoint is not available
async function syncUserData() {
  try {
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    const response = await fetch('/api/level/sync-data', {
      method: 'POST',
      headers: headers
    });
    
    // Check if response is OK before trying to parse JSON
    if (!response.ok) {
      // 405 Method Not Allowed or 404 Not Found means endpoint doesn't exist
      // This is fine - just log and return success (non-blocking)
      if (response.status === 405 || response.status === 404) {
        console.log('ℹ️ Sync endpoint not available (this is OK)');
        return true; // Return success to not block other operations
      }
      // For other errors, log but don't throw
      console.log('⚠️ Sync endpoint returned status:', response.status);
      return false;
    }
    
    // Try to parse JSON, but handle non-JSON responses gracefully
    let result;
    try {
      const text = await response.text();
      if (!text || text.trim() === '') {
        console.log('ℹ️ Sync endpoint returned empty response');
        return true;
      }
      result = JSON.parse(text);
    } catch (parseError) {
      console.log('⚠️ Sync endpoint returned non-JSON response:', parseError.message);
      return false;
    }
    
    if (result.success) {
      console.log('✅ User data synchronized successfully');
      return true;
    } else {
      console.log('⚠️ Sync returned success=false:', result.error);
      return false;
    }
  } catch (error) {
    // Network errors or other issues - log but don't throw
    // This is a non-critical operation, so we don't want to break the UI
    console.log('ℹ️ Sync skipped (non-critical):', error.message);
    return false;
  }
}

// Expose sync function globally
window.syncUserData = syncUserData;

// Fast path: Apply immediate visual feedback for level states
function applyImmediateLevelStates() {
  try {
    console.log('⚡ Applying immediate level states for fast feedback...');
    
    const nodes = Array.from(document.querySelectorAll('.level-card'));
    if (!nodes.length) return;
    
    const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
    
    // Apply immediate visual feedback based on cached data or defaults
    nodes.forEach(node => {
      const levelNum = parseInt(node.dataset.level || '0', 10);
      if (!levelNum) return;
      
      // Check if we have cached data
      const cachedData = node.dataset.bulkData;
      if (cachedData) {
        try {
          const data = JSON.parse(cachedData);
          applyLevelStateFromCache(node, levelNum, data);
          return;
        } catch (error) {
          console.log('Error parsing cached data for level', levelNum, error);
        }
      }
      
      // Apply default states for immediate feedback
      applyDefaultLevelState(node, levelNum, isUserAuthenticated);
    });
    
    console.log('✅ Immediate level states applied');
    
  } catch (error) {
    console.error('Error applying immediate level states:', error);
  }
}

// Apply level state from cached data
function applyLevelStateFromCache(node, levelNum, data) {
  const status = data.status || 'not_started';
  const score = data.user_progress?.score || data.last_score || 0;
  const scorePercent = Math.round(Number(score) * 100);
  
  // Remove all state classes
  node.classList.remove('locked', 'unlocked', 'done', 'active');
  
  if (status === 'completed' && scorePercent >= 60) {
    node.classList.add('done');
    node.dataset.allowStart = 'true';
  } else if (levelNum === 1) {
    node.classList.add('unlocked');
    node.dataset.allowStart = 'true';
  } else {
    // For other levels, check if previous level has score >= 60 (ready check based on score)
    const prevNode = document.querySelector(`.level-card[data-level="${levelNum - 1}"]`);
    if (prevNode) {
      // Use the same data source as the display: bulkData
      const prevScorePercent = getLevelScoreFromBulkData(prevNode);
      const prevHasScoreAbove60 = prevScorePercent >= 60;
      
      if (prevHasScoreAbove60) {
        node.classList.add('unlocked');
        node.dataset.allowStart = 'true';
      } else {
        node.classList.add('locked');
      }
    } else {
      node.classList.add('locked');
    }
  }
  
  // Update visual indicators
  updateLevelVisualIndicators(node, data);
}

// Apply default level state for immediate feedback
function applyDefaultLevelState(node, levelNum, isUserAuthenticated) {
  // Remove all state classes
  node.classList.remove('locked', 'unlocked', 'done', 'active');
  
  if (!isUserAuthenticated) {
    // For unauthenticated users, only level 1 is available
    if (levelNum === 1) {
      node.classList.add('unlocked');
      node.dataset.allowStart = 'true';
    } else {
      node.classList.add('locked');
    }
  } else {
    // For authenticated users, apply smart defaults
    if (levelNum === 1) {
      node.classList.add('unlocked');
      node.dataset.allowStart = 'true';
    } else {
      // Mark as locked initially, will be updated by API call
      node.classList.add('locked');
    }
  }
  
  // Set default visual indicators
  setDefaultVisualIndicators(node);
}

// Update visual indicators from cached data
function updateLevelVisualIndicators(node, data) {
  const wordsText = node.querySelector('.words-text');
  const learnedText = node.querySelector('.learned-text');
  const completionText = node.querySelector('.completion-circle-text');
  const progressFill = node.querySelector('.level-progress-fill');
  
  if (wordsText && data.total_words) {
    wordsText.textContent = data.total_words;
  }
  
  if (learnedText && data.completed_words !== undefined) {
    learnedText.textContent = data.completed_words;
  }
  
  if (completionText && data.last_score !== undefined) {
    const score = Math.round((data.last_score || 0) * 100);
    completionText.textContent = `${score}%`;
  }
  
  if (progressFill && data.total_words && data.completed_words !== undefined) {
    const progress = data.total_words > 0 ? 
      Math.round((data.completed_words / data.total_words) * 100) : 0;
    progressFill.style.width = `${progress}%`;
  }
}

// Set default visual indicators
function setDefaultVisualIndicators(node) {
  const wordsText = node.querySelector('.words-text');
  const learnedText = node.querySelector('.learned-text');
  const completionText = node.querySelector('.completion-circle-text');
  const progressFill = node.querySelector('.level-progress-fill');
  
  // Set default values for immediate feedback
  if (wordsText && !wordsText.textContent) {
    wordsText.textContent = '0';
  }
  
  if (learnedText && !learnedText.textContent) {
    learnedText.textContent = '0';
  }
  
  if (completionText && !completionText.textContent) {
    completionText.textContent = '0%';
  }
  
  if (progressFill && !progressFill.style.width) {
    progressFill.style.width = '0%';
  }
}

async function applyLevelStates(){
  // Prevent multiple simultaneous calls
  if (isApplyingLevelStates) {
    console.log('⏳ applyLevelStates already in progress, skipping...');
    return;
  }
  
  isApplyingLevelStates = true;
  
  // Fast path: Apply immediate visual feedback first
  applyImmediateLevelStates();
  
  try {
    const nodes = Array.from(document.querySelectorAll('.level-card'));
    if(!nodes.length) {
      // Even if no level cards are present, we should still update group stats
      // This ensures group statistics are updated when showing the groups overview
      updateGroupStatsInOverview();
      return;
    }
  
  // Sync user data when applying level states (for authenticated users)
  // NOTE: Endpoint /api/level/sync-data may not exist - disabled to prevent 405 errors
  // If sync is needed in the future, the endpoint should be created first
  /*
  if (window.authManager && window.authManager.isAuthenticated()) {
    try {
      await syncUserData();
    } catch (error) {
      console.log('Sync skipped:', error);
    }
  }
  */

  // Map Level -> Node
  const map = new Map();
  nodes.forEach(nd=>{
    const n = parseInt(nd.dataset.level || '0', 10);
    if(n) map.set(n, nd);
  });

  // Get all level numbers
  const levelNumbers = Array.from(map.keys()).sort((a, b) => a - b);
  
  // Use bulk API to get all level stats in one call
  try {
    const targetLang = document.getElementById('target-lang')?.value || 'en';
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    headers['X-Native-Language'] = nativeLanguage;
    
    let response;
    
    // Check if we're using custom level groups (from PostgreSQL)
    if (SELECTED_LEVEL_GROUP && SELECTED_LEVEL_GROUP.id) {
      // Use custom level groups endpoint (from PostgreSQL)
      response = await fetch(`/api/custom-levels/${SELECTED_LEVEL_GROUP.id}/bulk-stats`, {
        headers
      });
    } else if (DISABLE_STANDARD_LEVEL_GROUPS) {
      // Standard levels are disabled - skip API call
      console.log('Standard level groups disabled, skipping bulk-stats API call');
      return;
    } else {
      // Fallback to standard levels endpoint (for backwards compatibility)
    const fetchSet = new Set(levelNumbers);
    for(const lvl of levelNumbers){
      if(lvl > 1) fetchSet.add(lvl - 1);
    }
    const sortedLevels = Array.from(fetchSet).sort((a,b)=>a-b);
    const levelsParam = sortedLevels.join(',');
    
      response = await fetch(`/api/levels/bulk-stats?levels=${levelsParam}&language=${encodeURIComponent(targetLang)}`, {
      headers
    });
    }
    
    if (response.ok) {
      const data = await response.json();
      if (data.success && data.levels) {
        mergeBulkLevels(targetLang, data.levels);
        // Update header stats if available
        // Header stats will be recalculated later based on the currently visible levels
        
        // Cache bulk data in localStorage for other modules to use
        const langKey = document.getElementById('target-lang')?.value || 'en';
        localStorage.setItem(`bulk_data_${langKey}`, JSON.stringify(data));
        
        // Process all levels with bulk data
        for (const lvl of levelNumbers) {
      const nd = map.get(lvl);
          if (!nd) continue;
          
          const js = data.levels[lvl] || data.levels[String(lvl)];
          if (!js || !js.success) continue;
          
          // Debug: log title data
          if (lvl <= 3) {
            console.log(`🔍 Level ${lvl} title data:`, {
              hasTitle: !!js.title,
              title: js.title,
              titleType: typeof js.title,
              titleValue: js.title
            });
          }
          
          // Cache the bulk data in the level element for later use
          // Use user-specific score if available, otherwise use global score
          const scoreForBulkData = js?.user_progress?.score || js?.last_score || 0;
          nd.dataset.bulkData = JSON.stringify({
            fam_counts: js.fam_counts,
            status: js.status,
            last_score: scoreForBulkData,  // Use user-specific score if available
            total_words: js.total_words,
            title: js.title || `Level ${lvl}`,
            user_progress: js.user_progress || null  // Include user_progress for consistency
          });
          
          // Update level title if available (for custom levels)
          const titleToUse = js.title || `Level ${lvl}`;
          if (titleToUse && titleToUse !== `Level ${lvl}`) {
            const titleEl = nd.querySelector('.level-title');
            if (titleEl) {
              titleEl.textContent = titleToUse;
              console.log(`✅ Updated level ${lvl} title to: ${titleToUse}`);
            } else {
              console.warn(`⚠️ Level ${lvl}: title element not found for title: ${titleToUse}`);
            }
          } else if (lvl <= 3) {
            console.log(`ℹ️ Level ${lvl}: title is default or missing (titleToUse='${titleToUse}')`);
          }
          
      nd.classList.remove('locked','unlocked','done');
      
      // Use user-specific data if available, otherwise fall back to global data
      const userProgress = js?.user_progress;
      const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
      
      // Determine status and score based on user data or global data
      const status = userProgress?.status || js?.status;
      const score = userProgress?.score || js?.last_score;
      
      // Debug-Ausgabe
      console.log(`Level ${lvl}:`, { 
        status: status,
        score: score,
        total_words: js?.total_words,
        fam_counts: js?.fam_counts
      });
      
      // Update level card elements
      const statusEl = nd.querySelector('.level-status');
      const progressFill = nd.querySelector('.progress-fill');
      const progressText = nd.querySelector('.progress-text');
      
      let statusText = window.t ? window.t('status.locked', 'Locked') : 'Locked';
      let progressPercent = 0;
      
          // Determine if level is unlocked based on completion status
          let isUnlocked = false;
          
      if(status === 'completed' && Number(score || 0) > 0.6){
            // Level abgeschlossen und Score > 0,6
            isUnlocked = true;
        statusText = window.t ? window.t('status.completed', 'Completed') : 'Completed';
        console.log(`Level ${lvl} als 'completed' markiert (Score > 0.6) - User: ${isUserAuthenticated ? 'Yes' : 'No'}`);
      } else if(status === 'completed' && Number(score || 0) <= 0.6){
            // Level abgeschlossen, aber Score < 0,6
            isUnlocked = true;
        statusText = window.t ? window.t('status.available', 'Available') : 'Available';
        console.log(`Level ${lvl} als 'unlocked' markiert (abgeschlossen, aber Score <= 0.6) - User: ${isUserAuthenticated ? 'Yes' : 'No'}`);
      } else if(lvl === 1){
            // Level 1 ist immer verfügbar (erste Lektion)
            isUnlocked = true;
        statusText = window.t ? window.t('status.available', 'Available') : 'Available';
        console.log(`Level ${lvl} als 'unlocked' markiert (Level 1 - erste Lektion) - User: ${isUserAuthenticated ? 'Yes' : 'No'}`);
      } else if(lvl > 1) {
            // Check if previous level has score >= 60 (ready check based on score)
        const prevLevel = lvl - 1;
        // First try to get score from API data (already processed in this loop)
        const prevJs = data.levels[prevLevel] || data.levels[String(prevLevel)];
        let prevScorePercent = 0;
        
        if (prevJs && prevJs.success) {
          // Use the same logic as for current level: user_progress.score or last_score
          const prevUserProgress = prevJs?.user_progress;
          const prevScore = prevUserProgress?.score || prevJs?.last_score;
          if (prevScore !== null && prevScore !== undefined) {
            prevScorePercent = Math.round(Number(prevScore) * 100);
          }
        } else {
          // Fallback: try to get score from bulkData (if already set)
          const prevLevelElement = document.querySelector(`[data-level="${prevLevel}"]`);
          if (prevLevelElement) {
            prevScorePercent = getLevelScoreFromBulkData(prevLevelElement);
          }
        }
        
        const prevHasScoreAbove60 = prevScorePercent >= 60;
        
        console.log(`Level ${lvl} unlock check - Prev Level ${prevLevel}: Score=${prevScorePercent}% (from API data or bulkData), hasScoreAbove60=${prevHasScoreAbove60}`);
    
        if(prevHasScoreAbove60) {
              isUnlocked = true;
          statusText = window.t ? window.t('status.available', 'Available') : 'Available';
          console.log(`Level ${lvl} als 'unlocked' markiert (vorheriges Level ${prevLevel} hat Score >= 60) - User: ${isUserAuthenticated ? 'Yes' : 'No'}`);
        } else {
              isUnlocked = false;
              statusText = window.t ? window.t('status.locked', 'Locked') : 'Locked';
          console.log(`Level ${lvl} als 'locked' markiert (vorheriges Level ${prevLevel} hat Score < 60) - User: ${isUserAuthenticated ? 'Yes' : 'No'}`);
        }
      } else {
        // Fallback: Level verriegelt
            isUnlocked = false;
            statusText = window.t ? window.t('status.locked', 'Locked') : 'Locked';
        console.log(`Level ${lvl} als 'locked' markiert (Fallback) - User: ${isUserAuthenticated ? 'Yes' : 'No'}`);
      }
          
          // Set basic unlock status
          if (isUnlocked) {
            nd.classList.add('unlocked');
            nd.dataset.allowStart = 'true';  // Allow starting unlocked levels
          } else {
            nd.classList.add('locked');
            nd.dataset.allowStart = 'false';  // Prevent starting locked levels
          }
          
          // Store completion status for color logic
          nd.dataset.isCompleted = (status === 'completed') ? 'true' : 'false';
          console.log(`Level ${lvl} dataset.isCompleted set to: "${nd.dataset.isCompleted}" (status: ${status})`);
          
          // Cache bulk data for this level element (include user_progress if available)
          nd.dataset.bulkData = JSON.stringify({
            fam_counts: js.fam_counts,
            status: status,
            last_score: score,
            total_words: js.total_words,
            user_progress: userProgress || null  // Include user_progress for score lookup
          });
          
          // Set color based on learned words percentage (for all levels, not just completed ones)
          // This must be called AFTER dataset.isCompleted is set
          await _setLevelColorBasedOnLearnedWords(nd, lvl);
      
      // Mark this level as having its color set to prevent interference
      nd.dataset.colorSet = 'true';
  
  // Update status and progress elements
  if(statusEl) {
    statusEl.textContent = statusText;
    statusEl.className = `level-status ${nd.classList.contains('done') ? 'done' : nd.classList.contains('unlocked') ? 'unlocked' : 'locked'}`;
  }
  
  // Update group statistics in overview if groups are visible
  updateGroupStatsInOverview();
      
          // Word progress is now handled by _setLevelColorBasedOnLearnedWords
      
      // Update rating display
      updateLevelRatingDisplay(lvl, nd, js);
      
      // Update practice button state
      const practiceBtn = nd.querySelector('.level-btn:not(.primary)');
      if(practiceBtn) {
        if(nd.classList.contains('locked')) {
          practiceBtn.disabled = true;
          practiceBtn.style.opacity = '0.5';
          practiceBtn.style.cursor = 'not-allowed';
        } else {
          practiceBtn.disabled = false;
          practiceBtn.style.opacity = '1';
          practiceBtn.style.cursor = 'pointer';
        }
      }
        }
      }
    } else {
      console.log('Bulk API response not ok:', response.status);
      // Fallback: mark levels as locked, but keep Level 1 unlocked
      for (const lvl of levelNumbers) {
        const nd = map.get(lvl);
        if (nd) {
      nd.classList.remove('locked','unlocked','done');
      if (lvl === 1) {
        nd.classList.add('unlocked');
        nd.dataset.allowStart = 'true';
        console.log(`Level ${lvl} als 'unlocked' markiert (Level 1 - Fallback)`);
      } else {
        nd.classList.add('locked');
      }
        }
      }
    }
  } catch (error) {
    console.log('Error fetching bulk level stats:', error);
    // Fallback: mark levels as locked, but keep Level 1 unlocked
    for (const lvl of levelNumbers) {
      const nd = map.get(lvl);
      if (nd) {
        nd.classList.remove('locked','unlocked','done');
        if (lvl === 1) {
          nd.classList.add('unlocked');
          nd.dataset.allowStart = 'true';
          console.log(`Level ${lvl} als 'unlocked' markiert (Level 1 - Error Fallback)`);
        } else {
          nd.classList.add('locked');
        }
      }
    }
  }
  
  // Update group stats after all level states have been applied
  // This ensures the group statistics reflect the current level completion status
  await updateGroupStatsInOverview();
  
  // Highlight the highest available level after all levels are processed
  // Use setTimeout to ensure DOM is fully updated
  setTimeout(() => {
    highlightHighestAvailableLevel();
  }, 200); // Increased timeout to ensure all levels are fully processed
  
  } finally {
    isApplyingLevelStates = false;
  }
}
// Helper function to check if level color should be protected from interference
function _isLevelColorProtected(levelElement) {
  return levelElement.dataset.colorSet === 'true';
}

// Helper function to safely set level color (prevents interference)
function _safeSetLevelColor(levelElement, className) {
  if (!_isLevelColorProtected(levelElement)) {
    levelElement.classList.add(className);
  }
}

// Helper function to load familiarity data for level card back
async function loadFamiliarityData(levelElement, lvl) {
  try {
    const targetLang = document.getElementById('target-lang')?.value || 'en';
    
    // Use cached data from bulk API instead of making new requests
    let totalWords = 0;
    const familiarityCounts = {};
    
    // Check if this is a custom level first
    const isCustomLevel = levelElement.dataset.customGroupId || levelElement.classList.contains('custom-level');
    
    // For custom levels, always use Progress API instead of cached data
    if (!isCustomLevel) {
      // Check if we have cached data from bulk API (only for standard levels)
      const cachedData = levelElement.dataset.bulkData;
      if (cachedData) {
        try {
          const data = JSON.parse(cachedData);
          if (data.fam_counts) {
            // Copy the fam_counts to familiarityCounts
            Object.assign(familiarityCounts, data.fam_counts);
            // Sum all familiarity counts to get total words
            totalWords = Object.values(data.fam_counts).reduce((sum, count) => sum + count, 0);
          } else {
            // Fallback: set all counts to 0
            for (let familiarity = 0; familiarity <= 5; familiarity++) {
              familiarityCounts[familiarity] = 0;
            }
          }
        } catch (error) {
          console.log('Error parsing cached bulk data for familiarity:', error);
          // Fallback: set all counts to 0
          for (let familiarity = 0; familiarity <= 5; familiarity++) {
            familiarityCounts[familiarity] = 0;
          }
        }
      }
    }
    
    // If no data loaded yet (either no cached data for standard levels, or custom levels), fetch from API
    if (Object.keys(familiarityCounts).length === 0) {
      console.log(`Fetching familiarity data from API for level ${lvl}`);
      
      if (isCustomLevel) {
        // For custom levels, use the progress API to get accurate word counts
        try {
          const groupId = levelElement.dataset.customGroupId;
          if (groupId) {
            const headers = {};
            if (window.authManager && window.authManager.isAuthenticated()) {
              Object.assign(headers, window.authManager.getAuthHeaders());
            }
            
            const response = await fetch(`/api/custom-levels/${groupId}/${lvl}/progress`, {
              headers: headers
            });
            if (response.ok) {
              const progressData = await response.json();
              if (progressData.success) {
                totalWords = progressData.total_words || 0;
                console.log(`Custom level ${lvl} familiarity data: ${totalWords} words`);
                
                // Use real familiarity counts from progress API if available
                if (progressData.fam_counts) {
                  // Convert string keys to numbers and populate familiarityCounts
                  for (let familiarity = 0; familiarity <= 5; familiarity++) {
                    familiarityCounts[familiarity] = progressData.fam_counts[familiarity.toString()] || 0;
                  }
                  console.log(`Custom level ${lvl} real familiarity counts:`, familiarityCounts);
                } else {
                  // Fallback: Initialize familiarity counts with all words as unknown (level 0)
                  for (let familiarity = 0; familiarity <= 5; familiarity++) {
                    familiarityCounts[familiarity] = familiarity === 0 ? totalWords : 0;
                  }
                }
              }
            }
          }
        } catch (error) {
          console.log('Error fetching custom level progress for familiarity:', error);
        }
      } else {
        // For standard levels, try to get word count from level API
        try {
          const response = await fetch(`/api/level/${lvl}/words?language=${encodeURIComponent(targetLang)}`);
          if (response.ok) {
            const data = await response.json();
            if (data.success && data.words) {
              totalWords = data.words.length;
              console.log(`Standard level ${lvl} has ${totalWords} words for familiarity data`);
            }
          }
        } catch (error) {
          console.log('Error fetching standard level word count for familiarity:', error);
        }
      }
      
      // Fallback: Set familiarity counts only if not already set from Progress API
      if (Object.keys(familiarityCounts).length === 0) {
        for (let familiarity = 0; familiarity <= 5; familiarity++) {
          if (familiarity === 0) {
            familiarityCounts[familiarity] = totalWords; // All words start as unknown
          } else {
            familiarityCounts[familiarity] = 0;
          }
        }
      }
    }
    
    // Update the familiarity list in the card
    const familiarityItems = levelElement.querySelectorAll('.familiarity-item');
    familiarityItems.forEach(item => {
      const level = parseInt(item.dataset.familiarityLevel);
      const countElement = item.querySelector('.familiarity-count');
      if (countElement) {
        // Show 0 if user is not logged in, otherwise show user-specific count
        countElement.textContent = familiarityCounts[level] || 0;
      }
    });
    
    console.log(`Loaded USER-SPECIFIC familiarity data for level ${lvl}:`, familiarityCounts);
    
  } catch(error) {
    console.log('Error loading familiarity data:', error);
  }
}

// Helper function to set level color based on learned words percentage
async function _setLevelColorBasedOnLearnedWords(levelElement, lvl) {
  try {
    const targetLang = document.getElementById('target-lang')?.value || 'en';
    
    // Use cached data from bulk API instead of making new requests
    let totalWords = 0;
    let completedWords = 0;
    
    // Check if we have cached data from bulk API
    const cachedData = levelElement.dataset.bulkData;
    if (cachedData) {
      try {
        const data = JSON.parse(cachedData);
        if (data.fam_counts) {
          // Sum all familiarity counts to get total words
          totalWords = Object.values(data.fam_counts).reduce((sum, count) => sum + count, 0);
          // Get learned words (familiarity = 5)
          completedWords = data.fam_counts[5] || 0;
        }
      } catch (error) {
        console.log('Error parsing cached bulk data:', error);
      }
    }
    
    // If no cached data or totalWords is 0, try to get word count from level data
    if (totalWords === 0) {
      console.log(`No cached data for level ${lvl}, trying to get word count from level data`);
      
      // Check if this is a custom level by looking at the level element
      const isCustomLevel = levelElement.dataset.customGroupId || levelElement.classList.contains('custom-level');
      
      if (isCustomLevel) {
        // For custom levels, use the progress API to get accurate word counts
        try {
          const groupId = levelElement.dataset.customGroupId;
          if (groupId) {
            const headers = {};
            if (window.authManager && window.authManager.isAuthenticated()) {
              Object.assign(headers, window.authManager.getAuthHeaders());
            }
            
            const response = await fetch(`/api/custom-levels/${groupId}/${lvl}/progress`, {
              headers: headers
            });
            if (response.ok) {
              const progressData = await response.json();
              if (progressData.success) {
                totalWords = progressData.total_words || 0;
                completedWords = progressData.completed_words || 0;
                console.log(`Custom level ${lvl} progress: ${completedWords}/${totalWords} words`);
                
                // Create and cache the progress data
                const progressCache = {
                  fam_counts: {0: totalWords, 1: 0, 2: 0, 3: 0, 4: 0, 5: completedWords},
                  status: progressData.status || 'not_started',
                  last_score: progressData.level_score || 0,
                  total_words: totalWords
                };
                levelElement.dataset.bulkData = JSON.stringify(progressCache);
                console.log(`Cached custom level ${lvl} progress data:`, progressCache);
              }
            }
          }
        } catch (error) {
          console.log(`Error fetching custom level progress for ${lvl}:`, error);
        }
      } else {
        // For standard levels, try to get word count from level API
        try {
          const response = await fetch(`/api/level/${lvl}/words?language=${encodeURIComponent(targetLang)}`);
          if (response.ok) {
            const data = await response.json();
            if (data.success && data.words) {
              totalWords = data.words.length;
              console.log(`Standard level ${lvl} has ${totalWords} words`);
            }
          }
        } catch (error) {
          console.log('Error fetching standard level word count:', error);
        }
      }
    }
    
    // If still no data, use default values
    if (totalWords === 0 && completedWords === 0) {
      console.log(`No word data found for level ${lvl}, using default values`);
    }
    
    // Calculate progress percentage for learned words (used for progress bar)
    let progressPercent = 0;
    if(totalWords > 0) {
      progressPercent = Math.round((completedWords / totalWords) * 100);
    }
    
    // Get level score for completion circle (USER-SPECIFIC - only for authenticated users)
    // Use the same function as unlock logic to ensure consistency
    const levelScorePercent = getLevelScoreFromBulkData(levelElement);
    
    // Update word statistics on front of card
    const wordsText = levelElement.querySelector('.words-text');
    const learnedText = levelElement.querySelector('.learned-text');
    const progressFill = levelElement.querySelector('.level-progress-fill');
    
    // Total words: GLOBAL (always show total words in level)
    if (wordsText) wordsText.textContent = totalWords.toString();
    
    // Learned words: USER-SPECIFIC (show 0 if not logged in)
    if (learnedText) learnedText.textContent = completedWords.toString();
    
    if (progressFill) {
      progressFill.style.width = `${progressPercent}%`;
    }
    
    // Update completion circle with level score percentage
    updateCompletionCircle(levelElement, levelScorePercent);
    
    // Update icons to match the new design
    const wordsIcon = levelElement.querySelector('.words-icon');
    const learnedIcon = levelElement.querySelector('.learned-icon');
    
    if (wordsIcon) wordsIcon.textContent = '📖';
    if (learnedIcon) learnedIcon.textContent = '💡';
    
    // Remove existing status classes (but preserve unlocked/locked)
    levelElement.classList.remove('done', 'gold');
    
    // Unified color logic based on Familiarity 5:
    // Gold: >90% with Familiarity 5
    // Green: >50% with Familiarity 5
    // Blue/Gray: handled by unlock logic (preserved from existing classes)
    if (progressPercent > 90) {
      levelElement.classList.add('gold');
      console.log(`Level ${lvl} marked as GOLD (>90% Familiarity 5 - ${completedWords}/${totalWords})`);
    } else if (progressPercent > 50) {
      levelElement.classList.add('done');
      console.log(`Level ${lvl} marked as DONE (>50% Familiarity 5 - ${completedWords}/${totalWords})`);
    } else {
      // Level is available but <50% - stays as unlocked/locked (blue/gray)
      const isAvailable = levelElement.classList.contains('unlocked');
      console.log(`Level ${lvl} stays as ${isAvailable ? 'unlocked (blue)' : 'locked (gray)'} (<50% Familiarity 5 - ${completedWords}/${totalWords})`);
    }
    
    // Mark this level as having its color set to prevent interference
    levelElement.dataset.colorSet = 'true';
    
    // Apply button highlighting based on level status and color
    // For Level 1, if it's unlocked and not completed, it should be highlighted
    // We'll let highlightHighestAvailableLevel determine if it's the highest, but ensure it gets highlighted
    const isLevel1 = lvl === 1;
    const isAvailableAndNotCompleted = isAvailable && !actualIsCompleted;
    const isHighestForNow = isLevel1 && isAvailableAndNotCompleted; // Level 1 is highest if it's available and no other levels are completed
    
    applyButtonHighlighting(levelElement, actualIsCompleted, progressPercent, isHighestForNow);
    
  } catch(error) {
    console.log('Error setting level color based on learned words:', error);
    // Fallback: no additional class
  }
}

// Helper function to update completion circle
function updateCompletionCircle(levelElement, progressPercent) {
  try {
    const circleFill = levelElement.querySelector('.completion-circle-fill');
    const circleText = levelElement.querySelector('.completion-circle-text');
    
    if (!circleFill || !circleText) return;
    
    // Calculate stroke-dasharray for the circle (circumference = 2 * π * r, r = 15.9155)
    const circumference = 2 * Math.PI * 15.9155;
    const offset = circumference - (progressPercent / 100) * circumference;
    
    // Update the circle fill
    circleFill.style.strokeDasharray = `${circumference} ${circumference}`;
    circleFill.style.strokeDashoffset = offset;
    
    // Update the text
    circleText.textContent = `${progressPercent}%`;
    
    // Add color based on progress
    circleFill.classList.remove('low', 'medium', 'high');
    if (progressPercent < 30) {
      circleFill.classList.add('low');
    } else if (progressPercent < 70) {
      circleFill.classList.add('medium');
    } else {
      circleFill.classList.add('high');
    }
    
  } catch(error) {
    console.log('Error updating completion circle:', error);
  }
}

// Function to re-localize level group names when language changes
export function updateLevelGroupNames() {
  try {
    const groupTitles = document.querySelectorAll('.level-group-title[data-group-name]');
    groupTitles.forEach(title => {
      const groupName = title.dataset.groupName;
      if (groupName && typeof window !== 'undefined' && typeof window.tSection === 'function') {
        const localizedName = window.tSection(groupName, groupName);
        if (localizedName && !String(localizedName).startsWith('[')) {
          title.textContent = localizedName;
          console.log(`🌍 Updated group name: ${groupName} -> ${localizedName}`);
        }
      }
    });
  } catch (error) {
    console.warn('⚠️ Error updating level group names:', error);
  }
}

// Helper function to apply button highlighting based on level status
// Now uses the same logic as the level number circle - colors are applied via CSS based on level card classes
function applyButtonHighlighting(levelElement, isCompleted, progressPercent, isHighestAvailable = false) {
  try {
    const startBtn = levelElement.querySelector('.level-btn.primary');
    const practiceBtn = levelElement.querySelector('.level-btn:not(.primary)');
    
    if (!startBtn || !practiceBtn) return;
    
    // Remove ALL legacy highlighting classes to prevent interference
    startBtn.classList.remove('highlighted-blue', 'highlighted-green', 'highlighted-gold', 'highlighted-orange');
    practiceBtn.classList.remove('highlighted-blue', 'highlighted-green', 'highlighted-gold', 'highlighted-orange');
    
    // Mark buttons as color-set to prevent legacy code interference
    startBtn.dataset.colorSet = 'true';
    practiceBtn.dataset.colorSet = 'true';
    
    // The button colors are now controlled by CSS based on level card classes:
    // - .level-card.unlocked .level-btn.primary (blue) - matches .level-card.unlocked .level-number
    // - .level-card.done .level-btn.primary (green) - matches .level-card.done .level-number
    // - .level-card.gold .level-btn.primary (gold) - matches .level-card.gold .level-number
    // - .level-card.locked .level-btn.primary (gray) - matches default locked state
    
    // For highest available level, we can add a special pulse effect via CSS class
    if (isHighestAvailable && !isCompleted) {
      levelElement.classList.add('highest-available');
      console.log(`✅ Applied highest-available class to level ${levelElement.dataset.level || 'unknown'} - Start button will match circle color`);
    } else {
      levelElement.classList.remove('highest-available');
    }
    
    // Log for debugging
    const levelNum = levelElement.dataset.level || 'unknown';
    const hasGold = levelElement.classList.contains('gold');
    const hasDone = levelElement.classList.contains('done');
    const hasUnlocked = levelElement.classList.contains('unlocked');
    const hasLocked = levelElement.classList.contains('locked');
    
    // Ensure button doesn't have inline styles that override CSS
    if (startBtn) {
      // Remove any inline background styles that might interfere
      if (startBtn.style.background) {
        console.log(`⚠️ Level ${levelNum}: Removing inline background style from start button: ${startBtn.style.background}`);
        startBtn.style.background = '';
      }
      if (startBtn.style.backgroundColor) {
        console.log(`⚠️ Level ${levelNum}: Removing inline backgroundColor style from start button: ${startBtn.style.backgroundColor}`);
        startBtn.style.backgroundColor = '';
      }
    }
    
    console.log(`✅ Button colors set for level ${levelNum}: gold=${hasGold}, done=${hasDone}, unlocked=${hasUnlocked}, locked=${hasLocked} (matches circle color)`);
    
  } catch(error) {
    console.log('Error applying button highlighting:', error);
  }
}

// Function to find and highlight the highest available (unlocked, not completed) level
function highlightHighestAvailableLevel() {
  try {
    // Get all level elements
    const levelElements = document.querySelectorAll('[data-level]');
    if (!levelElements || levelElements.length === 0) {
      console.log('No level elements found for highest available level detection');
      return;
    }
    
    let highestAvailableLevel = null;
    let highestLevelNumber = 0;
    
    // Find the highest unlocked level that is not completed
    levelElements.forEach(element => {
      const levelNum = parseInt(element.dataset.level, 10);
      if (isNaN(levelNum)) return;
      
      const isUnlocked = element.classList.contains('unlocked');
      const isCompleted = element.dataset.isCompleted === 'true';
      
      // Debug logging
      if (levelNum === 1) {
        console.log(`🔍 Level 1 check: isUnlocked=${isUnlocked}, isCompleted=${isCompleted}, dataset.isCompleted="${element.dataset.isCompleted}"`);
      }
      
      if (isUnlocked && !isCompleted && levelNum > highestLevelNumber) {
        highestLevelNumber = levelNum;
        highestAvailableLevel = element;
      }
    });
    
    // If no highest level found but Level 1 is unlocked and not completed, use Level 1
    if (!highestAvailableLevel) {
      levelElements.forEach(element => {
        const levelNum = parseInt(element.dataset.level, 10);
        if (levelNum === 1) {
          const isUnlocked = element.classList.contains('unlocked');
          const isCompleted = element.dataset.isCompleted === 'true';
          if (isUnlocked && !isCompleted) {
            highestAvailableLevel = element;
            highestLevelNumber = 1;
            console.log('🎯 Using Level 1 as highest available level (fallback)');
          }
        }
      });
    }
    
    if (highestAvailableLevel) {
      console.log(`🎯 Found highest available level: ${highestLevelNumber}`);
      
      // Get progress percent for this level
      let progressPercent = 0;
      try {
        const bulkData = highestAvailableLevel.dataset.bulkData;
        if (bulkData) {
          const data = JSON.parse(bulkData);
          const totalWords = data.total_words || 0;
          const famCounts = data.fam_counts || {};
          
          // Calculate learned words (familiarity >= 1)
          let learnedWords = 0;
          for (let fam = 1; fam <= 5; fam++) {
            learnedWords += parseInt(famCounts[fam] || 0, 10);
          }
          
          if (totalWords > 0) {
            progressPercent = Math.round((learnedWords / totalWords) * 100);
          }
        }
      } catch (error) {
        console.log('Error calculating progress for highest available level:', error);
      }
      
      // Re-apply highlighting with isHighestAvailable flag
      const isCompleted = highestAvailableLevel.dataset.isCompleted === 'true';
      applyButtonHighlighting(highestAvailableLevel, isCompleted, progressPercent, true);
      
      // Also update other available levels to use blue instead of orange
      levelElements.forEach(element => {
        const levelNum = parseInt(element.dataset.level, 10);
        if (isNaN(levelNum)) return;
        
        const isUnlocked = element.classList.contains('unlocked');
        const isCompleted = element.dataset.isCompleted === 'true';
        
        // Skip the highest available level (already handled above)
        if (element === highestAvailableLevel) return;
        
        // Re-apply highlighting for other available levels (with blue, not orange)
        if (isUnlocked && !isCompleted) {
          let progressPercent = 0;
          try {
            const bulkData = element.dataset.bulkData;
            if (bulkData) {
              const data = JSON.parse(bulkData);
              const totalWords = data.total_words || 0;
              const famCounts = data.fam_counts || {};
              
              let learnedWords = 0;
              for (let fam = 1; fam <= 5; fam++) {
                learnedWords += parseInt(famCounts[fam] || 0, 10);
              }
              
              if (totalWords > 0) {
                progressPercent = Math.round((learnedWords / totalWords) * 100);
              }
            }
          } catch (error) {
            // Ignore errors
          }
          
          applyButtonHighlighting(element, false, progressPercent, false);
        }
      });
    } else {
      console.log('No highest available level found (all levels are either locked or completed)');
    }
    
  } catch(error) {
    console.log('Error highlighting highest available level:', error);
  }
}

if(typeof window!=='undefined'){ 
  window.applyLevelStates = applyLevelStates;
  window.updateGroupStatsInOverview = updateGroupStatsInOverview;
  window.applyImmediateLevelStates = applyImmediateLevelStates;
  window.applyLevelStateFromCache = applyLevelStateFromCache;
  window.applyDefaultLevelState = applyDefaultLevelState;
  window.highlightHighestAvailableLevel = highlightHighestAvailableLevel;
}


// ---- Curriculum utilities ----
function readCurriculum(){
  const el = document.getElementById('curriculum-spec');
  if(!el) return null;
  try{ return JSON.parse(el.textContent||'{}'); }catch(_){ return null; }
}
function sectionForLevel(lvl, spec){
  for(const s of (spec?.sections||[])){
    const a = s.range?.[0]||1, b = s.range?.[1]||1;
    if(lvl>=a && lvl<=b) return s;
  }
  return { name:'Foundations', themes:[], range:[1,10] };
}

function cefrRank(c){ return ['A0','A1','A2','B1','B2','C1','C2'].indexOf(String(c||'A0').toUpperCase()); }
function normalizeGoal(raw){
  const spec = readCurriculum(); const s = String(raw||'').toLowerCase();
  const ali = (spec?.goalAliases?.[s]) || s; return (spec?.goals||[]).includes(ali) ? ali : 'everyday';
}
function stageForLevel(lvl, startCEFR){
  const spec = readCurriculum(); const stages = spec?.cefrStagesDefault || [[1,10,'A1'],[11,20,'A2'],[21,30,'B1'],[31,40,'B2'],[41,45,'C1'],[46,50,'C2']];
  const startRank = Math.max(0, cefrRank(startCEFR));
  for(const [a,b,tag] of stages){
    if(lvl>=a && lvl<=b){
      const baseRank = cefrRank(tag), diff = Math.max(0, baseRank - cefrRank('A1'));
      return ['A0','A1','A2','B1','B2','C1','C2'][Math.min(6, startRank + diff)];
    }
  }
  return 'A1';
}
function personalizedSectionAndTheme(lvl, goalRaw, startCEFR){
  const spec = readCurriculum()||{}; const goal = normalizeGoal(goalRaw);
  const order = spec.sectionOrderByGoal?.[goal] || (spec.sections||[]).map(s=>s.name);
  const idx = Math.floor((lvl-1)/10); const sectionName = order[Math.min(idx, order.length-1)] || (spec.sections?.[0]?.name||'Foundations');
  const real = (spec.sections||[]).find(s=> s.name===sectionName) || spec.sections?.[0];
  const within = (lvl-1)%10;
  let theme = real?.themes?.[within] || '';
  const goalMap = spec.goalThemes?.[sectionName]?.[goal]; if(goalMap && goalMap[within]) theme = goalMap[within];
  const min = spec.sectionMinCEFR?.[sectionName] || 'A0';
  if(cefrRank(startCEFR) < cefrRank(min)){
    const firstAllowed = order.find(n=> cefrRank(startCEFR) >= cefrRank(spec.sectionMinCEFR?.[n]||'A0')) || order[0];
    const s2 = (spec.sections||[]).find(s=> s.name===firstAllowed) || real;
    return { section:s2.name, theme:(s2.themes||[])[within]||theme };
  }
  return { section:sectionName, theme };
}

function ensureLevelGroups(){
  if(Array.isArray(LEVEL_GROUP_DEFS) && LEVEL_GROUP_DEFS.length){
    return LEVEL_GROUP_DEFS;
  }
  
  // If standard groups are disabled, return empty array
  if (DISABLE_STANDARD_LEVEL_GROUPS) {
    console.log('🚫 Standard level groups are disabled - only custom groups will be shown');
    LEVEL_GROUP_DEFS = [];
    return LEVEL_GROUP_DEFS;
  }
  
  const spec = readCurriculum() || {};
  const icons = ['🎯','🎬','🧭','🌍','🏛️','🚀','📚'];
  LEVEL_GROUP_DEFS = (spec.sections || []).map((section, idx) => {
    const range = section?.range || [];
    const start = Number(range?.[0] ?? (idx * 10 + 1));
    const end = Number(range?.[1] ?? (start + 9));
    return {
      id: section?.name || `group_${idx+1}`,
      name: section?.name || `Group ${idx+1}`,
      start,
      end,
      icon: icons[idx % icons.length],
      label: section?.name || `Group ${idx+1}`,
      completed: 0,
      total: Math.max(0, end - start + 1)
    };
  });
  return LEVEL_GROUP_DEFS;
}

function getLevelGroupForLevel(levelNumber){
  const groups = ensureLevelGroups();
  const lvl = Number(levelNumber);
  if(!Number.isFinite(lvl)) return null;
  return groups.find(gr => lvl >= gr.start && lvl <= gr.end) || null;
}

function isLevelCompletedFromSummary(item){
  if(!item) return false;
  const progress = item.user_progress || {};
  const status = progress.status || item.status;
  if(status !== 'completed') return false;
  const score = progress.score ?? item.last_score;
  if(score === null || score === undefined) return true;
  return Number(score || 0) >= 0.0;
}

function levelEntryForAggregation(level, summaryMap){
  const lang = currentTargetLang();
  if(LATEST_BULK_RESULT.language === lang){
    const payload = LATEST_BULK_RESULT.levels[level] || LATEST_BULK_RESULT.levels[String(level)];
    if(payload){
      const status = payload.user_progress?.status ?? payload.status;
      const score = payload.user_progress?.score ?? payload.last_score ?? payload.score;
      return {
        status,
        last_score: score,
        user_progress: payload.user_progress || null
      };
    }
  }
  if(summaryMap instanceof Map){
    return summaryMap.get(level);
  }
  return undefined;
}

async function ensureLevelSummary(force = false){
  const lang = currentTargetLang();
  if(!lang){
    LEVEL_SUMMARY_CACHE = { byLevel: new Map(), raw: null, header: null };
    LEVEL_SUMMARY_LANG = null;
    return LEVEL_SUMMARY_CACHE;
  }
  // Standard levels are disabled - return empty cache
  if (DISABLE_STANDARD_LEVEL_GROUPS) {
    LEVEL_SUMMARY_CACHE = { byLevel: new Map(), raw: null, header: null };
    LEVEL_SUMMARY_LANG = lang;
    return LEVEL_SUMMARY_CACHE;
  }
  if(force || !LEVEL_SUMMARY_CACHE || LEVEL_SUMMARY_LANG !== lang){
    try{
      const response = await fetch(`/api/levels/summary?language=${encodeURIComponent(lang)}`);
      const js = await response.json();
      if(js && js.success){
        const byLevel = new Map((js.levels || []).map(entry => [Number(entry.level), entry]));
        LEVEL_SUMMARY_CACHE = { byLevel, raw: js, header: js.header_stats || null };
        LEVEL_SUMMARY_LANG = lang;
      }else{
        LEVEL_SUMMARY_CACHE = { byLevel: new Map(), raw: null, header: null };
        LEVEL_SUMMARY_LANG = lang;
      }
    }catch(err){
      console.error('Failed to load level summary:', err);
      LEVEL_SUMMARY_CACHE = { byLevel: new Map(), raw: null, header: null };
      LEVEL_SUMMARY_LANG = lang;
    }
  }
  return LEVEL_SUMMARY_CACHE;
}

function mergeBulkLevels(lang, responseLevels){
  if(LATEST_BULK_RESULT.language !== lang){
    LATEST_BULK_RESULT = { language: lang, levels: {}, fetchedLevels: new Set() };
  }
  const store = LATEST_BULK_RESULT.levels;
  Object.entries(responseLevels || {}).forEach(([lvl, payload]) => {
    const numLevel = Number(lvl);
    store[numLevel] = payload;
    LATEST_BULK_RESULT.fetchedLevels.add(numLevel);
  });
}

async function ensureBulkDataForLevels(levels){
  const lang = currentTargetLang();
  if(!lang || !Array.isArray(levels) || !levels.length){
    return LATEST_BULK_RESULT;
  }
  // Standard levels are disabled - return empty result
  if (DISABLE_STANDARD_LEVEL_GROUPS) {
    return LATEST_BULK_RESULT;
  }
  const pending = [];
  if(LATEST_BULK_RESULT.language === lang){
    for(const lvl of levels){
      if(!LATEST_BULK_RESULT.fetchedLevels.has(Number(lvl))){
        pending.push(Number(lvl));
      }
    }
  }else{
    pending.push(...levels.map(Number));
  }

  if(!pending.length){
    return LATEST_BULK_RESULT;
  }

  // Throttle bulk-stats requests to prevent excessive API calls
  const now = Date.now();
  if (now - BULK_STATS_LAST_FETCH < BULK_STATS_FETCH_THROTTLE) {
    console.log('🕐 Throttling bulk-stats request to prevent excessive API calls');
    return LATEST_BULK_RESULT;
  }
  BULK_STATS_LAST_FETCH = now;

  try{
    const qs = pending.sort((a,b)=>a-b).join(',');
    const response = await fetch(`/api/levels/bulk-stats?language=${encodeURIComponent(lang)}&levels=${qs}`, {
      headers: {
        'Content-Type': 'application/json',
        'X-Requested-With': 'XMLHttpRequest'
      }
    });
    
    if (!response.ok) {
      console.warn(`Bulk-stats API returned ${response.status}: ${response.statusText}`);
      return LATEST_BULK_RESULT;
    }
    
    const data = await response.json();
    if(data && data.success && data.levels){
      mergeBulkLevels(lang, data.levels);
    } else {
      console.warn('Bulk-stats API returned invalid data:', data);
    }
  }catch(error){
    console.warn('ensureBulkDataForLevels failed:', error);
    // Don't spam the console with repeated errors
    if (!LATEST_BULK_RESULT._errorLogged) {
      console.error('Bulk-stats API error details:', error.message);
      LATEST_BULK_RESULT._errorLogged = true;
    }
  }

  return LATEST_BULK_RESULT;
}

function normalizeWordKeyForLang(word, lang){
  return `${lang}:${String(word || '').trim().toLowerCase()}`;
}

function computeWordStatsForLevels(levels, levelDataMap){
  const lang = currentTargetLang();
  const statsSource = levelDataMap || (LATEST_BULK_RESULT.language === lang ? LATEST_BULK_RESULT.levels : {});
  const allKeys = new Set();
  const memorizedKeys = new Set();
  const wordMap = new Map();

  levels.forEach((lvl) => {
    const entry = statsSource[Number(lvl)] || statsSource[String(lvl)] || {};
    const words = entry.words || [];
    const hashes = entry.word_hashes || [];
    const familiarityData = entry.familiarity_data || {};

    const maxLen = Math.max(words.length, hashes.length);
    for(let i = 0; i < maxLen; i += 1){
      const word = words[i] !== undefined ? String(words[i]) : '';
      const rawHash = hashes[i];
      const hash = rawHash ? String(rawHash) : normalizeWordKeyForLang(word, lang);

      if(!hash){
        continue;
      }

      allKeys.add(hash);

      let familiarityValue = 0;
      const famEntry = familiarityData[hash];
      if(typeof famEntry === 'object' && famEntry !== null){
        familiarityValue = Number(famEntry.familiarity ?? famEntry.familiarity_level ?? 0);
      }else if(famEntry !== undefined){
        familiarityValue = Number(famEntry) || 0;
      }

      if(familiarityValue >= 5){
        memorizedKeys.add(hash);
      }

      if(word && !wordMap.has(hash)){
        wordMap.set(hash, {
          word,
          familiarity: familiarityValue
        });
      }else if(word && familiarityValue > 0){
        const existing = wordMap.get(hash);
        if(existing && familiarityValue > Number(existing.familiarity || 0)){
          existing.familiarity = familiarityValue;
        }
      }
    }
  });

  return {
    totalWords: allKeys.size,
    memorizedWords: memorizedKeys.size,
    wordMap
  };
}

async function updateHeaderStatsForLevelSet(levels){
  if(!Array.isArray(levels) || !levels.length){
  // For authenticated users, use the more accurate words data (async, non-blocking)
  if (window.authManager && window.authManager.isAuthenticated()) {
    // Load header stats in background without blocking level rendering
    setTimeout(() => {
      window.headerStats?.updateFromWordsData?.();
    }, 0);
  } else {
    // For unauthenticated users, use bulk data
    window.headerStats?.updateFromBulkData?.({ total_words: 0, memorized_words: 0 });
  }
    CURRENT_VIEW_WORD_MAP = new Map();
    updatePracticeButtonState();
    return;
  }

  await ensureBulkDataForLevels(levels);
  const { totalWords, memorizedWords, wordMap } = computeWordStatsForLevels(levels);
  CURRENT_VIEW_WORD_MAP = wordMap;
  updatePracticeButtonState();
  bindPracticeActionButtons(); // Ensure buttons are bound
  
  // For authenticated users, use the more accurate words data
  if (window.authManager && window.authManager.isAuthenticated()) {
    window.headerStats?.updateFromWordsData?.();
  } else {
    // For unauthenticated users, use bulk data
    window.headerStats?.updateFromBulkData?.({ total_words: totalWords, memorized_words: memorizedWords });
  }
}

function updatePracticeButtonState(){
  const practiceBtn = document.getElementById('smart-practice-btn');
  if(!practiceBtn) {
    console.log('⚠️ updatePracticeButtonState: practice button not found');
    return;
  }
  
  // Check if we're in a custom level group context (stories)
  // In that case, don't disable the button - startSmartPractice will handle word collection
  const groupsContainer = document.getElementById('custom-level-groups-container');
  const isStoryOverview = groupsContainer && getComputedStyle(groupsContainer).display !== 'none';
  const levelsContainer = document.getElementById('levels-container');
  const isCustomLevelView = levelsContainer && getComputedStyle(levelsContainer).display !== 'none';
  
  if(isStoryOverview || isCustomLevelView){
    // In story/custom level context, always enable the button
    // startSmartPractice will collect words from the appropriate context
    practiceBtn.disabled = false;
    console.log(`🔗 Practice button enabled (story/custom level context)`);
    return;
  }
  
  // For standard level groups, check if words are available
  let available = false;
  CURRENT_VIEW_WORD_MAP.forEach((info) => {
    const fam = Number(info?.familiarity ?? 0);
    if(fam < 5) available = true;
  });
  practiceBtn.disabled = !available;
  console.log(`🔗 Practice button state updated: disabled=${practiceBtn.disabled}, available=${available}, wordMapSize=${CURRENT_VIEW_WORD_MAP.size}`);
}

function updatePracticeActionLabels(){
  const alphabetBtn = document.getElementById('alphabet-practice-btn');
  if(alphabetBtn){
    const alphabetLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('navigation.alphabet', 'Alphabet')
      : 'Alphabet';
    const practiceLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('buttons.practice', 'Practice')
      : 'Practice';
    const labelNode = alphabetBtn.querySelector('.btn-label');
    if(labelNode){
      labelNode.textContent = `${alphabetLabel} • ${practiceLabel}`;
    }
  }

  const practiceBtn = document.getElementById('smart-practice-btn');
  if(practiceBtn){
    const practiceLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('buttons.practice', 'Practice')
      : 'Practice';
    const labelNode = practiceBtn.querySelector('.btn-label');
    if(labelNode){
      labelNode.textContent = practiceLabel;
    }
  }
}

export function bindPracticeActionButtons(){
  console.log('🔗 Binding practice action buttons...');
  console.log('🔗 Button binding stack trace:', new Error().stack);
  updatePracticeActionLabels();
  const alphabetBtn = document.getElementById('alphabet-practice-btn');
  if(alphabetBtn && !alphabetBtn.dataset.bound){
    alphabetBtn.addEventListener('click', () => {
      try{
        // Importiere startAlphabet aus dem alphabet Modul
        import('./alphabet.js').then(module => {
          if(module.startAlphabet){
            module.startAlphabet();
          }
        }).catch(err => {
          console.warn('Failed to import alphabet module:', err);
          // Fallback: versuche window.startAlphabet
          if(typeof window.startAlphabet === 'function'){
            window.startAlphabet();
          }
        });
      }catch(err){
        console.warn('Alphabet practice failed:', err);
      }
    });
    alphabetBtn.dataset.bound = 'true';
    console.log('✅ Alphabet button bound');
  } else {
    console.log('⚠️ Alphabet button not found or already bound:', alphabetBtn ? (alphabetBtn.dataset.bound ? 'already bound' : 'found but not bound') : 'not found');
  }

  const practiceBtn = document.getElementById('smart-practice-btn');
  console.log('🔗 Practice button element:', practiceBtn);
  console.log('🔗 Practice button dataset.bound:', practiceBtn?.dataset.bound);
  console.log('🔗 Practice button disabled:', practiceBtn?.disabled);
  console.log('🔗 Practice button style.display:', practiceBtn ? getComputedStyle(practiceBtn).display : 'N/A');
  console.log('🔗 Practice button onclick:', practiceBtn?.onclick);
  console.log('🔗 Practice button event listeners:', practiceBtn ? (practiceBtn.onclick ? 'has onclick' : 'no onclick') : 'N/A');
  
  if(practiceBtn && !practiceBtn.dataset.bound){
    console.log('🔗 Adding click listener to practice button...');
    // Remove any existing onclick handler first
    practiceBtn.onclick = null;
    // Use capture phase to ensure we catch the event early
    practiceBtn.addEventListener('click', (e) => {
      console.log('🔗 Practice button clicked!', e);
      e.preventDefault();
      e.stopPropagation();
      startSmartPractice();
    }, true); // Use capture phase
    practiceBtn.dataset.bound = 'true';
    console.log('✅ Practice button bound successfully');
  } else {
    console.log('⚠️ Practice button not found or already bound:', practiceBtn ? (practiceBtn.dataset.bound ? 'already bound' : 'found but not bound') : 'not found');
    // If already bound, try to rebind anyway (in case binding failed)
    if(practiceBtn && practiceBtn.dataset.bound){
      console.log('🔄 Button already bound, but checking if click handler works...');
      // Test if click handler exists
      const testClick = () => {
        console.log('🔗 Test click triggered - handler exists');
        startSmartPractice();
      };
      practiceBtn.onclick = testClick;
      practiceBtn.addEventListener('click', testClick, true);
      console.log('🔄 Added additional click handler');
    }
  }

  updatePracticeButtonState();
}

// Helper function to extract words from custom level content
// CRITICAL: This function must use the SAME normalization as the server:
// - lowercase conversion
// - trailing punctuation removal
// - only use item.words (no fallback to text_target for consistency)
function extractWordsFromLevelContent(levelContent) {
  const words = new Set();
  if(levelContent && levelContent.items) {
    for(const item of levelContent.items) {
      // Extract from item.words array (preferred, already tokenized)
      // This matches the server-side logic in calculate_word_count_from_content
      if(item.words && Array.isArray(item.words)) {
        for(const word of item.words) {
          if(word && word.trim()) {
            // CRITICAL: Use same normalization as server (lowercase + trailing punctuation removal)
            // This ensures consistency with server-side word counting
            const cleanWord = word.trim().toLowerCase().replace(/[.!?,;:—–-]+$/, '');
            if(cleanWord) {
              words.add(cleanWord);
            }
          }
        }
      } else {
        // Log warning if item.words is missing (should not happen in normal flow)
        console.warn('⚠️ extractWordsFromLevelContent: item.words is missing or empty for item:', item);
      }
      // NOTE: Removed fallback to text_target to ensure consistency with server-side logic
      // Server only uses item.words, so client should too
    }
  }
  return Array.from(words);
}

// Helper function to filter words by familiarity < 5 (all words that are not fully learned)
async function filterWordsByFamiliarity(words, language, nativeLanguage, headers) {
  if(!words || words.length === 0) return [];
  
  const filteredWords = [];
  const nativeLang = nativeLanguage || localStorage.getItem('siluma_native') || 'en';
  
  // Fetch familiarities for all words in parallel for better performance
  // CRITICAL: Try both original case and lowercase for compatibility
  const familiarityPromises = words.map(async (word) => {
    try {
      // Try original case first
      let url = `/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(language)}&native_language=${encodeURIComponent(nativeLang)}`;
      let response = await fetch(url, { headers });
      let js = await response.json();
      
      // Check both js.data.familiarity and js.familiarity for compatibility
      // CRITICAL: API returns data directly in response object, not in js.data
      let familiarity = null;
      if(js && js.success) {
        // API returns: {success: true, word: "...", familiarity: 0, ...}
        if(js.familiarity !== undefined) {
          familiarity = Number(js.familiarity || 0);
        } else if(js.data && js.data.familiarity !== undefined) {
          familiarity = Number(js.data.familiarity || 0);
        } else {
          // If no familiarity found, treat as 0 (unknown word)
          familiarity = 0;
        }
      } else {
        // API returned success: false, treat as unknown (0)
        familiarity = 0;
      }
      
      // If not found with original case, try lowercase
      if(familiarity === null && word !== word.toLowerCase()) {
        url = `/api/word?word=${encodeURIComponent(word.toLowerCase())}&language=${encodeURIComponent(language)}&native_language=${encodeURIComponent(nativeLang)}`;
        response = await fetch(url, { headers });
        js = await response.json();
        
        if(js && js.success) {
          if(js.familiarity !== undefined) {
            familiarity = Number(js.familiarity || 0);
          } else if(js.data && js.data.familiarity !== undefined) {
            familiarity = Number(js.data.familiarity || 0);
          } else {
            familiarity = 0;
          }
        } else {
          familiarity = 0;
        }
      }
      
      // Log for debugging
      if(familiarity === null) {
        console.warn(`⚠️ Could not determine familiarity for word "${word}", treating as 0`);
        familiarity = 0;
      }
      
      return { word, familiarity };
    } catch(e) {
      console.warn(`Failed to get familiarity for word "${word}":`, e);
      // Treat errors as unknown (0) - include in practice
      return { word, familiarity: 0 };
    }
  });
  
  // Wait for all requests to complete
  const results = await Promise.all(familiarityPromises);
  
  // Debug: Log all familiarity results
  const familiarityBreakdown = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, null: 0};
  results.forEach(({ word, familiarity }) => {
    const famKey = familiarity !== null ? familiarity : 'null';
    familiarityBreakdown[famKey] = (familiarityBreakdown[famKey] || 0) + 1;
  });
  console.log(`📊 Familiarity breakdown for ${words.length} words:`, familiarityBreakdown);
  
  // Filter: all words with familiarity < 5 (not fully learned)
  // This includes: 0 (unknown), 1 (seen), 2 (learning), 3 (familiar), 4 (strong)
  // Excludes: 5 (memorized/fully learned)
  results.forEach(({ word, familiarity }) => {
    // CRITICAL: Treat null as 0 (unknown word, should be included)
    const famValue = familiarity !== null ? familiarity : 0;
    
    if(famValue < 5) {
      filteredWords.push(word);
    } else {
      console.log(`⏭️ Excluding word "${word}" with familiarity ${famValue} (fully learned)`);
    }
  });
  
  console.log(`📊 Filtered ${filteredWords.length} words with familiarity < 5 from ${words.length} total words`);
  console.log(`📊 Excluded ${words.length - filteredWords.length} words with familiarity = 5 (fully learned)`);
  return filteredWords;
}

// Guard to prevent multiple simultaneous practice starts
let isStartingPractice = false;

async function startSmartPractice(fromLevelContainer = false){
  // Prevent multiple simultaneous calls
  if(isStartingPractice){
    console.log('⚠️ Practice already starting, ignoring duplicate call');
    return;
  }
  
  console.log('🎯 startSmartPractice called', fromLevelContainer ? 'from level container' : 'from quick access bar');
  console.log('🎯 Stack trace:', new Error().stack);
  
  // Only set loading state on quick access bar button if NOT called from level container
  if(!fromLevelContainer) {
    const practiceBtn = document.getElementById('smart-practice-btn');
    if(practiceBtn){
      practiceBtn.disabled = true;
      // Show loading state on button - update label node if it exists, otherwise update textContent
      const labelNode = practiceBtn.querySelector('.btn-label');
      if(labelNode){
        const originalText = labelNode.textContent;
        labelNode.textContent = window.t ? window.t('ui.loading', 'Loading...') : 'Loading...';
        practiceBtn.dataset.originalText = originalText;
      } else {
        const originalText = practiceBtn.textContent;
        practiceBtn.textContent = window.t ? window.t('ui.loading', 'Loading...') : 'Loading...';
        practiceBtn.dataset.originalText = originalText;
      }
      console.log('✅ Practice button found and disabled');
    } else {
      console.warn('⚠️ Practice button not found!');
    }
  } else {
    console.log('✅ Loading state set on level container button, skipping quick access bar button');
  }
  
  // Ensure practice UI exists and show loading indicator
  if(typeof window.ensurePracticeUI === 'function') {
    window.ensurePracticeUI();
  }
  const practiceCard = document.getElementById('practice-card');
  if(practiceCard) {
    practiceCard.style.display = '';
    // Switch to practice tab to show loading state
    if(typeof window.showTab === 'function') {
      window.showTab('practice');
    }
    const practiceInner = document.getElementById('practice-inner');
    if(practiceInner) {
      const preparingText = window.t ? window.t('practice.preparing_session', 'Preparing practice session...') : 'Preparing practice session...';
      practiceInner.innerHTML = `<div style="text-align:center;padding:40px;color:var(--fg);opacity:0.8"><div>${preparingText}</div></div>`;
    }
  }
  
  isStartingPractice = true;

  try{
    console.log('🎯 Checking if startPracticeWithWordList is available...');
    console.log('🎯 typeof window.startPracticeWithWordList:', typeof window.startPracticeWithWordList);
    if(typeof window.startPracticeWithWordList !== 'function'){
      console.error('❌ startPracticeWithWordList is not a function!');
      console.error('❌ window.startPracticeWithWordList:', window.startPracticeWithWordList);
      alert('Practice-Modul nicht initialisiert. Bitte Seite neu laden.');
      if(practiceBtn) practiceBtn.disabled = false;
      return;
    }
    let practiceCandidates = [];
    let scopeLabel = 'course';
    
    // Detect context: Check if we're in a custom level group context
    const levelsContainer = document.getElementById('levels-container');
    const groupsContainer = document.getElementById('custom-level-groups-container');
    // Check visibility using getComputedStyle for accurate detection
    const isCustomLevelView = levelsContainer && getComputedStyle(levelsContainer).display !== 'none';
    const isStoryOverview = groupsContainer && getComputedStyle(groupsContainer).display !== 'none';
    
    console.log('🔍 Container visibility check:');
    console.log('  - levelsContainer:', levelsContainer ? 'found' : 'not found');
    console.log('  - groupsContainer:', groupsContainer ? 'found' : 'not found');
    if(levelsContainer) {
      console.log('  - levelsContainer display:', getComputedStyle(levelsContainer).display);
    }
    if(groupsContainer) {
      console.log('  - groupsContainer display:', getComputedStyle(groupsContainer).display);
    }
    console.log('  - isCustomLevelView:', isCustomLevelView);
    console.log('  - isStoryOverview:', isStoryOverview);
    
    // Check for specific custom level (level card clicked or practice button clicked)
    const activeLevelCard = document.querySelector('.level-card.active[data-custom-group-id]');
    
    const targetLang = $('#target-lang')?.value || 'en';
    const headers = { 'Content-Type': 'application/json' };
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
    
    // Determine scope label and collect words based on context
    if(activeLevelCard){
      // Context: Specific level - only practice words from that level with familiarity 1-4
      const groupId = activeLevelCard.dataset.customGroupId;
      const levelNumber = activeLevelCard.dataset.level;
      scopeLabel = levelNumber ? `Level ${levelNumber}` : 'Level';
      
      // CRITICAL: Set custom level context for enrichment API
      if (groupId && levelNumber) {
        window.SELECTED_CUSTOM_GROUP = groupId;
        window.SELECTED_CUSTOM_LEVEL = levelNumber;
        console.log(`🔧 Set custom level context for practice: group ${groupId}, level ${levelNumber}`);
      }
      
      console.log(`🎯 Context: Specific level (group: ${groupId}, level: ${levelNumber})`);
      
      try {
        // Fetch the specific level data
        const levelResponse = await fetch(`/api/custom-level-groups/${groupId}/levels/${levelNumber}`, { headers });
        const levelData = await levelResponse.json();
        
        if(levelData && levelData.success && levelData.level) {
          // Extract words from level content
          const levelWords = extractWordsFromLevelContent(levelData.level.content);
          console.log(`✅ Extracted ${levelWords.length} words from level ${levelNumber}`);
          console.log(`📝 Extracted words:`, levelWords);
          
          // Get total words from progress data for comparison
          if(levelData.level.progress) {
            const totalWordsFromProgress = levelData.level.progress.total_words || 0;
            console.log(`📊 Total words from progress data: ${totalWordsFromProgress}`);
            if(totalWordsFromProgress !== levelWords.length) {
              console.warn(`⚠️ DISCREPANCY: Extracted ${levelWords.length} words but progress shows ${totalWordsFromProgress} words`);
            }
          }
          
          // Filter by familiarity < 5 (all words that are not fully learned)
          practiceCandidates = await filterWordsByFamiliarity(levelWords, targetLang, nativeLanguage, headers);
          console.log(`✅ Filtered to ${practiceCandidates.length} words with familiarity < 5 (not fully learned)`);
          console.log(`📝 Practice candidates:`, practiceCandidates);
          
          if(practiceCandidates.length === 0 && levelWords.length > 0) {
            console.warn(`⚠️ No practice candidates found, but ${levelWords.length} words were extracted. All words might have familiarity 5.`);
          }
        } else {
          console.warn('⚠️ Failed to fetch level data:', levelData);
        }
      } catch(e) {
        console.error('Error fetching level data:', e);
      }
    } else if(isCustomLevelView){
      // Context: Story view (10 levels visible) - practice words from that story group with familiarity 1-4
      scopeLabel = 'Story';
      
      // Get the current story group ID from the levels container
      const firstLevelCard = document.querySelector('.level-card[data-custom-group-id]');
      const groupId = firstLevelCard?.dataset.customGroupId;
      
      console.log(`🎯 Context: Story view (group: ${groupId})`);
      
      if(groupId) {
        try {
          // Fetch bulk stats for all levels in the group
          const bulkResponse = await fetch(`/api/custom-levels/${groupId}/bulk-stats`, { headers });
          const bulkData = await bulkResponse.json();
          
          if(bulkData && bulkData.success && bulkData.levels) {
            const allStoryWords = new Set();
            
            // Extract words from all levels in the story (fetch in parallel for better performance)
            const levelPromises = [];
            for(const levelNum in bulkData.levels) {
              levelPromises.push(
                fetch(`/api/custom-level-groups/${groupId}/levels/${levelNum}`, { headers })
                  .then(response => response.json())
                  .then(levelData => {
                    if(levelData && levelData.success && levelData.level) {
                      const levelWords = extractWordsFromLevelContent(levelData.level.content);
                      return levelWords;
                    }
                    return [];
                  })
                  .catch(e => {
                    console.warn(`Failed to fetch level ${levelNum}:`, e);
                    return [];
                  })
              );
            }
            
            // Wait for all level fetches to complete
            const allLevelWordsArrays = await Promise.all(levelPromises);
            allLevelWordsArrays.forEach(levelWords => {
              levelWords.forEach(word => allStoryWords.add(word));
            });
            
            const storyWordsArray = Array.from(allStoryWords);
            console.log(`✅ Extracted ${storyWordsArray.length} unique words from story group ${groupId}`);
            
            // Filter by familiarity 1-4
            practiceCandidates = await filterWordsByFamiliarity(storyWordsArray, targetLang, nativeLanguage, headers);
            console.log(`✅ Filtered to ${practiceCandidates.length} words with familiarity 1-4`);
          } else {
            console.warn('⚠️ Failed to fetch bulk stats:', bulkData);
          }
        } catch(e) {
          console.error('Error fetching story group data:', e);
        }
      }
    } else if(isStoryOverview){
      // Context: Story overview - practice all words currently learning (familiarity 1-4)
      scopeLabel = 'Stories';
      
      console.log(`🎯 Context: Story overview - all learning words`);
      
      try{
        // Fetch words with familiarity 1-4 directly from API
        const response = await fetch(`/api/words/learning?language=${encodeURIComponent(targetLang)}&min_familiarity=1&max_familiarity=4&limit=1000`, { headers });
        const js = await response.json();
        if(js && js.success && Array.isArray(js.words)){
          practiceCandidates = js.words.map(w => w.word || w).filter(Boolean);
          console.log(`✅ Found ${practiceCandidates.length} words with familiarity 1-4 from API`);
        } else {
          console.warn('⚠️ API did not return words:', js);
        }
      }catch(e){
        console.error('Error fetching words from API:', e);
      }
    } else {
      // Context: Course overview - practice all words currently learning (familiarity 1-4)
      scopeLabel = 'Course';
      
      console.log(`🎯 Context: Course overview - all learning words`);
      
      try{
        // Fetch words with familiarity 1-4 directly from API
        const response = await fetch(`/api/words/learning?language=${encodeURIComponent(targetLang)}&min_familiarity=1&max_familiarity=4&limit=1000`, { headers });
        const js = await response.json();
        if(js && js.success && Array.isArray(js.words)){
          practiceCandidates = js.words.map(w => w.word || w).filter(Boolean);
          console.log(`✅ Found ${practiceCandidates.length} words with familiarity 1-4 from API`);
        } else {
          console.warn('⚠️ API did not return words:', js);
        }
      }catch(e){
        console.error('Error fetching words from API:', e);
      }
      
      // Fallback: Standard level logic (only if no words found and in level group view)
      if(practiceCandidates.length === 0 && SELECTED_LEVEL_GROUP){
        console.log(`🔍 No words from API, using standard level group logic`);
        const levels = [];
        if(SELECTED_LEVEL_GROUP){
          console.log(`🔍 Using selected level group:`, SELECTED_LEVEL_GROUP);
          for(let lvl = SELECTED_LEVEL_GROUP.start; lvl <= SELECTED_LEVEL_GROUP.end; lvl += 1){
            levels.push(lvl);
          }
          scopeLabel = SELECTED_LEVEL_GROUP.name || 'group';
        }

        console.log(`🔍 Collected ${levels.length} levels for practice`);

        if(!levels.length){
          console.warn('⚠️ No levels found for practice');
          const msg = (typeof window !== 'undefined' && typeof window.t === 'function')
            ? window.t('practice.no_completed_level', 'Kein abgeschlossenes Level gefunden')
            : 'Kein abgeschlossenes Level gefunden';
          alert(msg);
          if(practiceBtn) practiceBtn.disabled = false;
          return;
        }

        console.log(`🔍 Loading bulk data for ${levels.length} levels...`);
        await ensureBulkDataForLevels(levels);
        const { wordMap } = computeWordStatsForLevels(levels);
        CURRENT_VIEW_WORD_MAP = wordMap;
        updatePracticeButtonState();

        console.log(`🔍 Word map contains ${wordMap.size} words`);
        let checkedWords = 0;
        CURRENT_VIEW_WORD_MAP.forEach(({ word, familiarity }) => {
          if(!word) return;
          checkedWords++;
          const fam = Number(familiarity ?? 0);
          // Filter: only familiarity 1-4 (learning words, not unknown or memorized)
          if(fam >= 1 && fam <= 4){
            practiceCandidates.push(word);
          }
        });
        console.log(`🔍 Checked ${checkedWords} words, found ${practiceCandidates.length} with familiarity 1-4`);
      }
    }

    console.log(`🎯 Practice candidates collected: ${practiceCandidates.length} words (scope: ${scopeLabel})`);
    
    if(!practiceCandidates.length){
      console.warn('⚠️ No practice candidates found');
      // Provide a more accurate message based on context
      let msg = '';
      if(activeLevelCard || isCustomLevelView) {
        // For specific level or story view, words might all be unknown (familiarity 0) or memorized (familiarity 5)
        msg = (typeof window !== 'undefined' && typeof window.t === 'function')
          ? window.t('practice.no_words_to_practice', 'Keine Wörter zum Üben verfügbar (alle Wörter sind unbekannt oder bereits gelernt)')
          : 'Keine Wörter zum Üben verfügbar (alle Wörter sind unbekannt oder bereits gelernt)';
      } else {
        // For overview, all words might be memorized
        msg = (typeof window !== 'undefined' && typeof window.t === 'function')
          ? window.t('levels.no_remaining_words', 'Keine übrig gebliebenen Wörter (max. Stufe erreicht)')
          : 'Keine übrig gebliebenen Wörter (max. Stufe erreicht)';
      }
      alert(msg);
      if(practiceBtn){
        practiceBtn.disabled = false;
      }
      return;
    }

    console.log(`🎯 Starting practice with ${practiceCandidates.length} words (scope: ${scopeLabel})`);
    console.log(`🎯 First 5 words:`, practiceCandidates.slice(0, 5));
    
    // Double-check that function exists before calling
    if(typeof window.startPracticeWithWordList !== 'function'){
      console.error('❌ startPracticeWithWordList helper is not available. Practice module may not be initialized.');
      console.error('❌ Available window functions:', Object.keys(window).filter(k => k.includes('Practice')));
      console.error('❌ window.startPracticeWithWordList value:', window.startPracticeWithWordList);
      alert('Practice-Modul nicht verfügbar. Bitte Seite neu laden.');
      if(practiceBtn) practiceBtn.disabled = false;
      return;
    }
    
    console.log('✅ Calling startPracticeWithWordList...');
    try {
      await window.startPracticeWithWordList(practiceCandidates, scopeLabel);
      console.log('✅ startPracticeWithWordList completed successfully');
    } catch (practiceError) {
      console.error('❌ Error in startPracticeWithWordList:', practiceError);
      console.error('❌ Error stack:', practiceError.stack);
      alert('Fehler beim Starten der Übung: ' + (practiceError?.message || practiceError));
      throw practiceError; // Re-throw to be caught by outer catch
    }
  }catch(error){
    console.error('Error starting smart practice:', error);
    alert('Practice-Start fehlgeschlagen: ' + (error?.message || error));
  }finally{
    isStartingPractice = false;
    
    // Restore quick access bar button if it was modified
    if(!fromLevelContainer) {
      const practiceBtn = document.getElementById('smart-practice-btn');
      if(practiceBtn){
        practiceBtn.disabled = false;
        // Restore original button text - update label node if it exists
        if(practiceBtn.dataset.originalText) {
          const labelNode = practiceBtn.querySelector('.btn-label');
          if(labelNode){
            labelNode.textContent = practiceBtn.dataset.originalText;
          } else {
            practiceBtn.textContent = practiceBtn.dataset.originalText;
          }
          delete practiceBtn.dataset.originalText;
        }
      }
    }
    
    // Restore level container button if it was modified
    if(fromLevelContainer) {
      const activeLevelCard = document.querySelector('.level-card.active[data-custom-group-id]');
      if(activeLevelCard) {
        const practiceBtn = activeLevelCard.querySelector('.level-btn[data-i18n="buttons.practice"]');
        if(practiceBtn && practiceBtn.dataset.originalText) {
          practiceBtn.disabled = false;
          const labelNode = practiceBtn.querySelector('.btn-label');
          if(labelNode){
            labelNode.textContent = practiceBtn.dataset.originalText;
          } else {
            practiceBtn.textContent = practiceBtn.dataset.originalText;
          }
          delete practiceBtn.dataset.originalText;
        }
      }
    }
  }
}

// Helper function to get word familiarity
async function getWordFamiliarity(word, language, nativeLanguage){
  try{
    const headers = {};
    if (window.authManager && window.authManager.isAuthenticated()) {
      Object.assign(headers, window.authManager.getAuthHeaders());
    }
    
    const r = await fetch(`/api/word?word=${encodeURIComponent(word)}&language=${encodeURIComponent(language)}&native_language=${encodeURIComponent(nativeLanguage)}`, { headers });
    const js = await r.json();
    if(js && js.success && js.data && js.data.familiarity !== undefined){
      return Number(js.data.familiarity || 0);
    }
  }catch(_){}
  return 0;
}

async function recomputeLevelGroupStats(byLevel){
  const groups = ensureLevelGroups();
  console.log('🔍 recomputeLevelGroupStats called with byLevel:', byLevel);
  
  // Get all level numbers from all groups
  const allLevels = [];
  groups.forEach(group => {
    for(let lvl = group.start; lvl <= group.end; lvl += 1){
      allLevels.push(lvl);
    }
  });
  
  // Use the same logic as applyLevelStates - fetch bulk data directly
  if (allLevels.length > 0) {
    try {
      const targetLang = document.getElementById('target-lang')?.value || 'en';
      const headers = {};
      if (window.authManager && window.authManager.isAuthenticated()) {
        Object.assign(headers, window.authManager.getAuthHeaders());
      }
      const nativeLanguage = localStorage.getItem('siluma_native') || 'en';
      headers['X-Native-Language'] = nativeLanguage;
      
      // Create levels parameter string (same logic as applyLevelStates)
      const fetchSet = new Set(allLevels);
      for(const lvl of allLevels){
        if(lvl > 1) fetchSet.add(lvl - 1);
      }
      const sortedLevels = Array.from(fetchSet).sort((a,b)=>a-b);
      const levelsParam = sortedLevels.join(',');
      
      const response = await fetch(`/api/levels/bulk-stats?levels=${levelsParam}&language=${encodeURIComponent(targetLang)}`, {
        headers: {
          ...headers,
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        }
      });
      
      if (!response.ok) {
        console.warn(`Bulk-stats API returned ${response.status}: ${response.statusText}`);
        return groups; // Return groups with default values
      }
      
      const data = await response.json();
      if (data.success && data.levels) {
        // Use the same logic as applyLevelStates to determine completion
        groups.forEach(group => {
          const label = (typeof window !== 'undefined' && typeof window.tSection === 'function')
            ? window.tSection(group.name, group.name)
            : group.name;
          group.label = label && !String(label).startsWith('[') ? label : group.name;
          let completed = 0;
          for(let lvl = group.start; lvl <= group.end; lvl += 1){
            const payload = data.levels[lvl] || data.levels[String(lvl)];
            if (payload) {
              const status = payload.user_progress?.status ?? payload.status;
              const score = payload.user_progress?.score ?? payload.last_score ?? payload.score;
              const isCompleted = status === 'completed' && (score === null || score === undefined || Number(score || 0) >= 0.0);
              if (isCompleted) {
                completed += 1;
                // Reduced logging - only log summary
              } else {
                // Reduced logging - only log summary
              }
            } else {
              // Reduced logging - only log summary
            }
          }
          group.completed = completed;
          group.total = Math.max(0, group.end - group.start + 1);
          console.log(`📊 Group ${group.name}: ${completed}/${group.total} completed`);
        });
      } else {
        console.warn('Bulk-stats API returned invalid data:', data);
      }
    } catch (error) {
      console.warn('Failed to fetch bulk data for group stats:', error);
      // Don't spam the console with repeated errors
      if (!groups._errorLogged) {
        console.error('Bulk-stats API error details:', error.message);
        groups._errorLogged = true;
      }
    }
  }
  
  return groups;
}

/**
 * Update group statistics in the groups overview when level states change
 */
async function updateGroupStatsInOverview() {
  // Always recompute the group statistics, but only update UI if visible
  const groupsEl = document.getElementById('level-groups');
  const isGroupsVisible = groupsEl && groupsEl.style.display !== 'none';
  
  // Recompute and update the group statistics
  const groups = await recomputeLevelGroupStats();
  
  // Only update the UI if groups overview is visible
  if (isGroupsVisible) {
    groups.forEach(group => {
      const groupCard = document.querySelector(`[data-group-id="${group.id}"]`);
      if (groupCard) {
        // Update the completed count display (only the completed stat, not the total)
        const statCompletedValue = groupCard.querySelector('.level-group-stat-completed');
        if (statCompletedValue && statCompletedValue.textContent !== `${group.completed}`) {
          statCompletedValue.textContent = `${group.completed}`;
        }
        
        // Update the progress bar
        const progressBar = groupCard.querySelector('.level-group-progress-bar');
        if (progressBar) {
          const pct = group.total ? Math.round((group.completed / group.total) * 100) : 0;
          progressBar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
        }
        
        // Update the subtitle in the header if this group is selected
        if (SELECTED_LEVEL_GROUP && SELECTED_LEVEL_GROUP.id === group.id) {
          updateSelectedGroupHeader();
        }
      }
    });
    console.log('📊 Group stats updated in overview UI:', groups.map(g => `${g.id}: ${g.completed}/${g.total}`));
  } else {
    console.log('📊 Group stats updated (UI not visible):', groups.map(g => `${g.id}: ${g.completed}/${g.total}`));
  }
}

async function showGroupsContainer(){
  // Only manipulate groups if we're on the library tab
  // This prevents conflicts when user is on browse/courses/settings/words tabs
  const libraryTab = document.getElementById('library-tab');
  if (!libraryTab || !libraryTab.classList.contains('active')) {
    console.log('⏭️ Skipping showGroupsContainer - not on library tab');
    return;
  }
  
  // Prevent race conditions with loading lock
  if (GROUPS_LOADING_LOCK) {
    console.log('🔄 Groups loading already in progress, skipping...');
    return;
  }
  
  GROUPS_LOADING_LOCK = true;
  
  try {
    const groupsEl = document.getElementById('level-groups');
    const levelsEl = document.getElementById('levels');
    const headerEl = document.getElementById('levels-group-header');
    const customGroupsSection = document.getElementById('custom-level-groups-section');
    const standardGroupsSection = document.getElementById('standard-level-groups-section');
    
    if(groupsEl) groupsEl.style.display = '';
    if(levelsEl) levelsEl.style.display = 'none';
    if(headerEl) headerEl.style.display = 'none';
    
    // Show both custom and standard level groups sections when showing groups
    if(customGroupsSection) customGroupsSection.style.display = '';
    if(standardGroupsSection) standardGroupsSection.style.display = '';
    
    // Ensure both standard and custom groups are loaded synchronously
    try {
      console.log('🔄 Synchronizing groups loading...');
      
      // Load standard groups first
      if (typeof window.renderLevels === 'function') {
        await window.renderLevels();
      }
      
    // Then load custom groups if user is authenticated
    if (window.authManager && window.authManager.isAuthenticated()) {
      console.log('🔍 User is authenticated, loading custom groups...');
      if (typeof window.showCustomLevelGroupsInLibrary === 'function') {
        console.log('✅ showCustomLevelGroupsInLibrary function found, calling...');
        await window.showCustomLevelGroupsInLibrary();
      } else {
        console.warn('❌ showCustomLevelGroupsInLibrary function not found');
      }
      if (typeof window.loadCustomLevelGroups === 'function') {
        console.log('✅ loadCustomLevelGroups function found, calling...');
        await window.loadCustomLevelGroups();
      } else {
        console.warn('❌ loadCustomLevelGroups function not found');
      }
    } else {
      console.log('🔍 User not authenticated, skipping custom groups');
    }
      
      console.log('✅ Groups loading synchronized');
    } catch (error) {
      console.warn('Error synchronizing groups loading:', error);
    }
    
    // Remove group management buttons from quick access (if function exists)
    if (typeof window.removeGroupManagementFromQuickAccess === 'function') {
      console.log('🔄 Calling removeGroupManagementFromQuickAccess from levels.js');
      window.removeGroupManagementFromQuickAccess();
    } else {
      console.log('⚠️ removeGroupManagementFromQuickAccess function not available');
    }
    
    // Hide edit button when switching away from custom group
    const editBtn = document.getElementById('levels-group-edit-btn');
    const dropdown = document.getElementById('levels-group-edit-dropdown');
    if (editBtn) editBtn.style.display = 'none';
    if (dropdown) dropdown.style.display = 'none';
  } finally {
    GROUPS_LOADING_LOCK = false;
  }
}

function showLevelsContainer(){
  const groupsEl = document.getElementById('level-groups');
  const levelsEl = document.getElementById('levels');
  const headerEl = document.getElementById('levels-group-header');
  const customGroupsSection = document.getElementById('custom-level-groups-section');
  const standardGroupsSection = document.getElementById('standard-level-groups-section');
  
  if(groupsEl) groupsEl.style.display = 'none';
  if(levelsEl) levelsEl.style.display = '';
  if(headerEl) headerEl.style.display = '';
  
  // Hide both custom and standard level groups sections when showing levels
  if(customGroupsSection) customGroupsSection.style.display = 'none';
  if(standardGroupsSection) standardGroupsSection.style.display = 'none';
}

function updateSelectedGroupHeader(){
  const headerEl = document.getElementById('levels-group-header');
  const titleEl = document.getElementById('levels-group-title');
  const subtitleEl = document.getElementById('levels-group-subtitle');
  if(!SELECTED_LEVEL_GROUP){
    if(headerEl) headerEl.style.display = 'none';
    return;
  }
  if(headerEl) headerEl.style.display = '';
  const icon = SELECTED_LEVEL_GROUP.icon || '🎯';
  if(titleEl){
    titleEl.textContent = `${icon} ${SELECTED_LEVEL_GROUP.label || SELECTED_LEVEL_GROUP.name}`;
  }
  if(subtitleEl){
    const completedLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('status.completed', 'Completed')
      : 'Completed';
    const levelLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('labels.level', 'Level')
      : 'Level';
    subtitleEl.textContent = `${SELECTED_LEVEL_GROUP.start}–${SELECTED_LEVEL_GROUP.end} • ${SELECTED_LEVEL_GROUP.completed}/${SELECTED_LEVEL_GROUP.total} ${completedLabel}`;
    subtitleEl.title = `${SELECTED_LEVEL_GROUP.total} ${levelLabel}`;
  }
}

async function renderLevelGroupsView(byLevel){
  const host = document.getElementById('level-groups');
  if(!host) return;
  
  // First, ensure we have all the level data we need
  let allLevels = [];
  const groups = ensureLevelGroups();
  groups.forEach(group => {
    for(let lvl = group.start; lvl <= group.end; lvl += 1){
      allLevels.push(lvl);
    }
  });

  // Load bulk data for all levels first (only if there are standard levels)
  if(allLevels.length){
    await ensureBulkDataForLevels(allLevels);
  } else {
    console.log('📝 No standard level groups to load - only custom groups will be displayed');
  }
  
  // Now recompute group stats with the loaded data
  let groupsWithStats = await recomputeLevelGroupStats(byLevel);
  
  // Update header stats
  if(allLevels.length){
    await updateHeaderStatsForLevelSet(allLevels);
  }else{
  // For authenticated users, use the more accurate words data (async, non-blocking)
  if (window.authManager && window.authManager.isAuthenticated()) {
    // Load header stats in background without blocking level rendering
    setTimeout(() => {
      window.headerStats?.updateFromWordsData?.();
    }, 0);
  } else {
    // For unauthenticated users, use bulk data
    window.headerStats?.updateFromBulkData?.({ total_words: 0, memorized_words: 0 });
  }
    CURRENT_VIEW_WORD_MAP = new Map();
    updatePracticeButtonState();
  }

  host.innerHTML = '';
  groupsWithStats.forEach(group => {
    const card = document.createElement('article');
    card.className = 'level-group-card';
    if(SELECTED_LEVEL_GROUP && SELECTED_LEVEL_GROUP.id === group.id){
      card.classList.add('active');
    }
    card.dataset.groupId = group.id;
    card.dataset.start = String(group.start);
    card.dataset.end = String(group.end);
    card.tabIndex = 0;

    const thumb = document.createElement('div');
    thumb.className = 'level-group-thumb';
    const title = document.createElement('div');
    title.className = 'level-group-title';
    title.textContent = group.label || group.name;
    // Store the group name for later re-localization
    title.dataset.groupName = group.name;
    const range = document.createElement('div');
    range.className = 'level-group-range';
    // Remove redundant number display - keep empty for cleaner look
    range.textContent = '';
    
    // Define levelLabel for use in stats below
    const levelLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('labels.level', 'Level')
      : 'Level';
    const progress = document.createElement('div');
    progress.className = 'level-group-progress';
    const bar = document.createElement('div');
    bar.className = 'level-group-progress-bar';
    const pct = group.total ? Math.round((group.completed / group.total) * 100) : 0;
    bar.style.width = `${Math.min(100, Math.max(0, pct))}%`;
    progress.appendChild(bar);

    thumb.appendChild(title);
    thumb.appendChild(range);
    thumb.appendChild(progress);

    const meta = document.createElement('div');
    meta.className = 'level-group-meta';

    const statTotal = document.createElement('div');
    statTotal.className = 'level-group-stat';
    const statTotalLabel = document.createElement('div');
    statTotalLabel.textContent = levelLabel;
    const statTotalValue = document.createElement('div');
    statTotalValue.className = 'level-group-stat-value level-group-stat-total';
    statTotalValue.textContent = String(group.total);
    statTotal.appendChild(statTotalLabel);
    statTotal.appendChild(statTotalValue);

    const statCompleted = document.createElement('div');
    statCompleted.className = 'level-group-stat';
    const completedLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('status.completed', 'Completed')
      : 'Completed';
    const statCompletedLabel = document.createElement('div');
    statCompletedLabel.textContent = completedLabel;
    const statCompletedValue = document.createElement('div');
    statCompletedValue.className = 'level-group-stat-value level-group-stat-completed';
    statCompletedValue.textContent = `${group.completed}`;
    statCompleted.appendChild(statCompletedLabel);
    statCompleted.appendChild(statCompletedValue);

    meta.appendChild(statTotal);
    meta.appendChild(statCompleted);

    const footer = document.createElement('div');
    footer.className = 'level-group-footer';
    const footerAction = document.createElement('div');
    footerAction.className = 'level-group-action';
    const openLabel = (typeof window !== 'undefined' && typeof window.t === 'function')
      ? window.t('buttons.open', 'Open')
      : 'Open';
    footerAction.innerHTML = `<span class="action-icon">▶</span><span class="action-label" data-i18n="buttons.open">${openLabel}</span>`;
    footerAction.addEventListener('click', (e) => {
      e.stopPropagation();
    });
    footer.appendChild(footerAction);

    card.appendChild(thumb);
    card.appendChild(meta);
    card.appendChild(footer);

    card.addEventListener('click', () => {
      selectLevelGroup(group.id);
    });
    card.addEventListener('keydown', (evt) => {
      if(evt.key === 'Enter' || evt.key === ' ' || evt.key === 'Spacebar' || evt.key === 'Space'){
        evt.preventDefault();
        selectLevelGroup(group.id);
      }
    });

    host.appendChild(card);
  });
  
  // Update group stats after rendering all groups
  // This ensures the group statistics are displayed correctly
  await updateGroupStatsInOverview();
}

function selectLevelGroup(groupId){
  const groups = ensureLevelGroups();
  const target = typeof groupId === 'object' ? groupId : groups.find(g => g.id === groupId);
  if(!target) return;
  SELECTED_LEVEL_GROUP = target;
  showLevelsContainer();
  renderLevels();
  try{
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }catch(_){ }
}

export function showLevelGroupsHome(){
  console.log('🏠 showLevelGroupsHome called');
  
  // Clear selection first
  SELECTED_LEVEL_GROUP = null;
  
  // Show groups container immediately
  showGroupsContainer();
  
  // Force update the dataset to ensure UI reflects the change
  const levelsHost = document.getElementById('levels');
  if(levelsHost) {
    levelsHost.dataset.groupId = '';
  }
  
  // Render levels asynchronously to avoid race conditions
  setTimeout(() => {
    console.log('🔄 Rendering levels after timeout');
    renderLevels();
  }, 0);
  
  // If standard groups are disabled and user is authenticated, ensure custom groups are loaded
  if (DISABLE_STANDARD_LEVEL_GROUPS && window.authManager && window.authManager.isAuthenticated()) {
    setTimeout(() => {
      if (typeof window.showCustomLevelGroupsInLibrary === 'function') {
        console.log('🔄 Loading custom groups for authenticated user');
        window.showCustomLevelGroupsInLibrary();
      }
    }, 100);
  }
  
  try{
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }catch(_){ }
}

function _levelGroupInfo(level){
  const lvl = Number(level);
  if(!Number.isFinite(lvl) || lvl <= 0) return { section:'', label:'General' };
  let sectionLabel = '';
  const goal = document.getElementById('topic')?.value || 'everyday';
  const cefr = document.getElementById('cefr')?.value || 'A1';
  let sectionName = '';
  try{
    const info = personalizedSectionAndTheme(lvl, goal, cefr) || {};
    sectionName = info.section || '';
  }catch(_){ sectionName = ''; }

  if(sectionName){
    if(typeof window !== 'undefined' && typeof window.tSection === 'function'){
      sectionLabel = window.tSection(sectionName, sectionName) || sectionName;
    }else if(typeof window !== 'undefined' && typeof window.t === 'function'){
      const candidate = window.t(`sections.${sectionName}`, sectionName);
      if(candidate && candidate.trim() && !candidate.startsWith('[')) sectionLabel = candidate;
    }
    if(sectionLabel && sectionLabel.startsWith('[')) sectionLabel = sectionName;
  }

  if(!sectionLabel) sectionLabel = sectionName || 'General';
  return { section: sectionName, label: sectionLabel };
}

export function buildLevelPrompt(lvl, { target_lang='en', native_lang='de', cefr='A1', topic='' }={}){
  const spec = readCurriculum()||{};
  const goal = normalizeGoal(topic||'everyday');
  const stg = stageForLevel(+lvl||1, cefr||'A1');
  const pt  = personalizedSectionAndTheme(+lvl||1, goal, cefr||'A1');
  const tmpl = spec.defaultTemplate || '';
  const hint = spec.sectionHints?.[pt.section] || '';
  const goalLine = (spec.promptGoalLine||'').replaceAll('{{goal}}', goal);
  const cefrLine = (spec.promptCEFRPolicy||'').replaceAll('{{cefr_stage}}', stg).replaceAll('{{start_cefr}}', cefr||'A1');
  const fill = (s)=> s
    .replaceAll('{{target_lang}}', String(target_lang))
    .replaceAll('{{native_lang}}', String(native_lang))
    .replaceAll('{{cefr}}', String(cefr))
    .replaceAll('{{topic}}', String(topic||''))
    .replaceAll('{{section_name}}', String(pt.section))
    .replaceAll('{{level}}', String(lvl))
    .replaceAll('{{theme}}', String(pt.theme||''));
  let out = fill(tmpl);
  if(hint) out += `\nSection focus: ${hint}`;
  if(goalLine) out += `\n${goalLine}`;
  if(cefrLine) out += `\n${cefrLine}`;
  return out;
}

// Expose globally for other modules
if(typeof window !== 'undefined'){
  window.buildLevelPrompt = buildLevelPrompt;
}

export function showLoader(txt){
  const el = document.getElementById('loader');
  if(!el) return;
  const t = el.querySelector('.loader-text');
  if(t && typeof txt === 'string') t.textContent = txt;
  el.style.display = 'flex';
}
export function hideLoader(){ const el = document.getElementById('loader'); if(el) el.style.display = 'none'; }
export function setDebug(txt){ const el = document.getElementById('dbg'); if(el) el.textContent = String(txt||''); }
export function showProgress(on){ const blk = document.getElementById('progress-block'); if(blk) blk.style.display = on ? '' : 'none'; }

// Toggle visibility of the native language dropdown
export function setNativeDropdownVisible(on){
    const host = document.querySelector('.topbar-right');
    if(!host) return;
    host.style.display = on ? '' : 'none';
}

// Control visibility of topbar buttons based on current page
export function setTopbarButtonsVisible(tab){
    const settingsBtn = document.getElementById('settings-btn');
    const logoutBtn = document.getElementById('logout-btn');
    const loginBtn = document.getElementById('login-btn');
    
    // Show buttons only on home page (levels)
    const showButtons = tab === 'levels';
    
    if(settingsBtn) settingsBtn.style.display = showButtons ? '' : 'none';
    if(logoutBtn) logoutBtn.style.display = showButtons ? '' : 'none';
    if(loginBtn) loginBtn.style.display = showButtons ? '' : 'none';
}
// Unified tab switcher: 'levels' | 'lesson' | 'words' | 'evaluation' | 'practice'
export function showTab(tab){
    const ids = {
    levels: '#levels-card',
    lesson: '#lesson',
    evaluation: '#evaluation-card',
    practice: '#practice-card',
    library: '#library-tab',
    browse: '#browse-tab',
    settings: '#settings-tab',
    courses: '#courses-tab'
    };
    
    // Handle new navigation tabs
    if (['library', 'browse', 'settings', 'courses', 'words'].includes(tab)) {
        // Completely reset level UI when switching away from lesson
        if (typeof window.resetLevelUI === 'function') {
            window.resetLevelUI();
        } else {
            // Fallback: Hide legacy single-view screens
            ['#lesson','#lesson-container','#evaluation-card','#practice-card','#alphabet-card'].forEach(id=>{ 
                const el=$(id); 
                if(el) el.style.display='none'; 
            });
            // Reset Word Details Panel
            const wordDetailsPanel = document.getElementById('word-details-panel');
            if(wordDetailsPanel) {
                wordDetailsPanel.innerHTML = '';
            }
        }
        
        // Stop alphabet practice when switching tabs
        if (typeof window.stopAlphabetPractice === 'function') {
            window.stopAlphabetPractice();
        }
        
        const levelsCard = document.getElementById('levels-card');
        if(levelsCard) levelsCard.style.display='';
        
        // Hide all tab contents
        const tabContents = document.querySelectorAll('.tab-content');
        tabContents.forEach((content) => {
          content.classList.remove('active');
          content.setAttribute('aria-hidden', 'true');
        });
        
        // Remove active class from all tabs
        const tabs = document.querySelectorAll('.nav-tab');
        tabs.forEach(tabEl => tabEl.classList.remove('active'));
        
        // Show selected tab content
        const selectedContent = document.getElementById(`${tab}-tab`);
        if (selectedContent) {
            selectedContent.classList.add('active');
            selectedContent.setAttribute('aria-hidden', 'false');
        } else {
            console.warn(`⚠️ Tab content not found: #${tab}-tab`);
        }
        
        // Add active class to selected tab
        const selectedTab = document.querySelector(`[data-tab="${tab}"]`);
        if (selectedTab) {
            selectedTab.classList.add('active');
            console.log(`✅ Activated tab button: [data-tab="${tab}"]`);
        } else {
            console.warn(`⚠️ Tab button not found: [data-tab="${tab}"]`);
        }
        
        if (tab === 'words') {
            console.log('📝 Calling words tab callback...');
            if (window.wordsTabManager && typeof window.wordsTabManager.activate === 'function') {
                window.wordsTabManager.activate();
            }
        }
        
        // Call specific tab activation functions
        if (tab === 'library') {
            console.log('📚 Calling library callback...');
            if (typeof window.onLibraryTabActivated === 'function') {
                window.onLibraryTabActivated();
            }
        } else if (tab === 'browse') {
            console.log('🔍 Calling browse callback...');
            if (typeof window.initMarketplace === 'function') {
                window.initMarketplace();
            }
        } else if (tab === 'settings') {
            console.log('⚙️ Calling settings callback...');
            if (typeof window.loadSettings === 'function') {
                window.loadSettings();
            }
            // Show admin section when settings tab is activated
            setTimeout(() => {
                const adminSection = document.getElementById('admin-section');
                if (adminSection) {
                    adminSection.style.display = 'block';
                    adminSection.style.visibility = 'visible';
                    console.log('✅ Admin section shown when settings tab activated');
                }
            }, 100);
        } else if (tab === 'courses') {
            console.log('🌍 Calling courses callback...');
            if (typeof window.loadCourseCards === 'function') {
                window.loadCourseCards();
            }
        }
        
        return;
    }
    
    // Original tab handling for legacy tabs
    // Completely reset level UI when switching away from lesson
    if(tab !== 'lesson' && typeof window.resetLevelUI === 'function') {
        window.resetLevelUI();
    }
    
    // Stop alphabet practice if switching away from it
    if(tab !== 'alphabet' && typeof window.stopAlphabetPractice === 'function') {
        window.stopAlphabetPractice();
    }
    
    // hide all views including practice (words-card removed - now a modern tab)
    ['#levels-card','#lesson','#lesson-container','#evaluation-card','#practice-card','#alphabet-card'].forEach(id=>{ const el=$(id); if(el) el.style.display='none'; });
    // hide level tooltip as well
    const lt = document.getElementById('level-tip'); if(lt) lt.style.display='none';
    // progress only in lesson
    showProgress(tab==='lesson');
    // show target view
    const sel = ids[tab]; if(sel){ const el=$(sel); if(el) el.style.display=''; }
    // Show lesson container when lesson tab is active
    if(tab==='lesson'){
      const lessonContainer=document.getElementById('lesson-container'); 
      if(lessonContainer) lessonContainer.style.display='flex';
    }
    if(tab==='lesson' || tab==='evaluation'){
      const abEntry=document.getElementById('alphabet-entry'); if(abEntry) abEntry.style.display='none';
      const abCard=document.getElementById('alphabet-card'); if(abCard) abCard.style.display='none';
    }
    
    // Focus the input field when lesson starts
    if(tab === 'lesson'){
        setTimeout(()=>{
            const ta = document.getElementById('user-translation');
            if(ta){ ta.focus(); }
        }, 50);
    }

    // nav active state: only for legacy tabs
    // Note: words is now a modern tab, handled by the modern tab system above
    $$('.nav button').forEach(b=> b.classList.remove('active'));
    if(['levels', 'lesson', 'evaluation', 'practice'].includes(tab)) {
    // Use library tab instead of home button
    const libraryTab = document.querySelector('[data-tab="library"]');
    if(libraryTab) libraryTab.classList.add('active');
    }
    // Show language dropdown only outside of lesson and practice
    setNativeDropdownVisible(!(tab==='lesson' || tab==='practice'));
    
    // Control visibility of topbar buttons based on current page
    setTopbarButtonsVisible(tab);
}
// Re-show right header whenever Levels view becomes visible (after lesson/practice end)
export function observeLevelsVisible(){
    const el = document.getElementById('levels-card');
    if(!el) return;
    const isShown = () => window.getComputedStyle(el).display !== 'none';
    let prev = isShown();
    const obs = new MutationObserver(()=>{
    const now = isShown();
    if(!prev && now){ setNativeDropdownVisible(true); }
    prev = now;
    });
    obs.observe(el, { attributes:true, attributeFilter:['style','class'] });
}
// Re-show right header whenever Evaluation view becomes visible & populate score
export function observeEvaluationVisible(){
  const el = document.getElementById('evaluation-card');
  if(!el) return;
  const isShown = () => window.getComputedStyle(el).display !== 'none';
  let prev = isShown();
  const obs = new MutationObserver(()=>{
    const now = isShown();
    if(!prev && now){
      setNativeDropdownVisible(true);
      try{ if(typeof window.populateEvaluationScore === 'function') window.populateEvaluationScore(); }catch(_){}
      try{ if(typeof window.populateEvaluationStatus === 'function') window.populateEvaluationStatus(); }catch(_){}
      const t = document.querySelector('#evaluation-card .eval-title');
      if(t){ 
        const practiceText = window.t ? window.t('status.practice_completed', 'Übung abgeschlossen 🎉') : 'Übung abgeschlossen 🎉';
        const levelText = window.t ? window.t('status.level_completed', 'Level abgeschlossen 🎉') : 'Level abgeschlossen 🎉';
        t.textContent = (window._eval_context === 'practice') ? practiceText : levelText; 
      }
      const card = document.getElementById('evaluation-card');
      if(card){ card.classList.remove('reveal'); void card.offsetWidth; card.classList.add('reveal'); }
    }
    prev = now;
  });
  obs.observe(el, { attributes:true, attributeFilter:['style','class'] });
}
// Add an "Üben" button to the level tooltip and wire it to the exact run of that level
export function ensureLtPractice(){
    // Function disabled - buttons removed from tooltip
    // const tip = document.getElementById('level-tip');
    // if(!tip) return;
    // const obs = new MutationObserver(()=>{
    // if(tip.style.display !== 'none'){
    //     // Buttons removed - no longer needed
    //     // const rep = document.getElementById('lt-repeat');
    //     // if(rep && !document.getElementById('lt-practice')){
    //     // const btn = document.createElement('button');
    //     // btn.id = 'lt-practice';
    //     // btn.className = rep.className; // same style as Wiederholen
    //     // btn.style.marginLeft = '8px';
    //     // btn.textContent = window.t ? window.t('buttons.practice', 'Üben') : 'Üben';
    //     // rep.parentNode.insertBefore(btn, rep.nextSibling);
    //     // btn.addEventListener('click', async ()=>{
    //     //     // Hide topbar-right when Üben is clicked
    //     //     const host = document.querySelector('.topbar-right');
    //     //     if(host) host.style.display='none';
    //     //     const lvl = Number(window._lt_level||0) || 1;
    //     //     // Resolve latest run_id for this exact level
    //     //     let run_id = null;
    //     //     try{
    //     //     const r = await fetch(`/api/levels/summary?language=${encodeURIComponent(currentTargetLang())}`);
    //     //     const js = await r.json();
    //     //     if(js && js.success && Array.isArray(js.levels)){
    //     //         const rows = js.levels.filter(x=>Number(x.level)===lvl && Number(x.run_id||0)>0);
    //     //         if(rows.length){ run_id = rows.sort((a,b)=>Number(b.run_id)-Number(a.run_id))[0].run_id; }
    //     //     }
    //     //     }catch(_){}
    //     //     if(!run_id){ try{ const v = localStorage.getItem('siluma_last_run_'+String(lvl)); if(v) run_id = parseInt(v,10)||null; }catch(_){} }
    //     //     window._last_run_id = run_id || null;
    //     //     await startPracticeForLevel(lvl, run_id||null);
    //     //     tip.style.display = 'none';
    //     // });
    //     // }
    // // }
    // // });
    // // obs.observe(tip, {attributes:true, attributeFilter:['style']});
    // }
}
// --- Evaluation actions ---
export function highlightLevel(lvl){
    const nd = document.querySelector(`.level-node[data-level="${lvl}"]`);
    if(nd){ nd.classList.add('pulse'); setTimeout(()=> nd.classList.remove('pulse'), 1500); }
}

// --- Topic utilities (moved from index.html) ---------------------------------

// Track last clicked level bubble
if (typeof document !== 'undefined'){
  document.addEventListener('click', (e)=>{
    const nd = e.target.closest && e.target.closest('.level-node');
    if(nd){
      const txt = (nd.textContent||'').trim();
      const n = parseInt(txt, 10);
      if(!isNaN(n)) window._lt_level = n;
    }
  });
}

let LEVELS_REQ = 0;

function topicKey(level){
  const sel = document.getElementById('target-lang');
  const lang = sel && sel.value ? sel.value : 'en';
  return `siluma_topic_lvl_${lang}_${level}`;
}
function saveLevelTopic(level, topic){ try{ localStorage.setItem(topicKey(level), topic||''); }catch(_){} }

function loadLevelTopic(level){ try{ return localStorage.getItem(topicKey(level))||''; }catch(_){ return ''; } }


export async function ensureTopicsForVisibleLevels(){
  if(window._ensuringTopics) return;
  window._ensuringTopics = true;
  try{
    const waitForLevelNodes = async (timeout=1500)=>{
      const start = Date.now();
      while(Date.now()-start < timeout){
        if(document.querySelector('.level-node')) return true;
        await new Promise(r=>setTimeout(r, 50));
      }
      return false;
    };
    await waitForLevelNodes();
    const nodes = Array.from(document.querySelectorAll('.level-node'));
    if(!nodes.length) return;
    const tgt = document.getElementById('target-lang')?.value || 'en';
    const nat = localStorage.getItem('siluma_native') || 'de';
    const cef = document.getElementById('cefr')?.value || 'A1';
    const base = document.getElementById('topic')?.value || '';
    await Promise.all(nodes.map(async nd=>{
      const n = parseInt((nd.textContent||'').trim(),10); if(!n) return;
      const existing = loadLevelTopic(n) || '';
      try{
        const r = await fetch('/api/level/ensure_topic', {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ level:n, target_lang:tgt, native_lang:nat, cefr:cef, base_topic:base })
        });
        const js = await r.json();
        const t = (js && js.success && js.topic) ? String(js.topic).trim() : '';
        if(t && !existing){ saveLevelTopic(n, t); }
      }catch(_){}
    }));
  } finally { window._ensuringTopics = false; }
  try{ await debouncedApplyLevelStates(); }catch(_){}
}

function positionLevelTip(anchor){
  const r = anchor.getBoundingClientRect();
  const tip = document.getElementById('level-tip');
  const pad = 20;
  
  // Check if we're on mobile (768px or less)
  const isMobile = window.innerWidth <= 768;
  
  // Get shell element to determine the right edge of the content area
  const shell = document.querySelector('.shell');
  const shellRect = shell ? shell.getBoundingClientRect() : null;
  
  // Calculate the right edge of the content area (shell right edge)
  const contentRightEdge = shellRect ? shellRect.right : window.innerWidth;
  
  // Position tooltip in the right margin area, centered vertically
  const w = tip.offsetWidth || 320;
  const h = tip.offsetHeight || 200;
  
  let x, y;
  
  if (isMobile) {
    // On mobile, position tooltip centered horizontally and above/below anchor
    x = (window.innerWidth - w) / 2;
    
    // Try to position above the anchor first
    y = r.top + window.scrollY - h - pad;
    
    // If it doesn't fit above, position below
    if (y < window.scrollY + pad) {
      y = r.bottom + window.scrollY + pad;
    }
    
    // Ensure it stays within viewport
    if (y + h > window.scrollY + window.innerHeight - pad) {
      y = window.scrollY + window.innerHeight - h - pad;
    }
  } else {
    // Desktop: position in right margin area
    // X position: right edge of content + some padding, but ensure it fits in viewport
    x = contentRightEdge + pad;
    if (x + w > window.innerWidth) {
      x = window.innerWidth - w - pad;
    }
    
    // Y position: center vertically relative to the anchor, but keep within viewport
    y = r.top + window.scrollY + (r.height / 2) - (h / 2);
    
    // Ensure tooltip stays within viewport bounds
    if (y < window.scrollY + pad) {
      y = window.scrollY + pad;
    } else if (y + h > window.scrollY + window.innerHeight - pad) {
      y = window.scrollY + window.innerHeight - h - pad;
    }
  }
  
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}

// Cache for preloaded tooltip data
const TOOLTIP_DATA_CACHE = new Map();

// Preload tooltip data for a level (called when cards are rendered or on hover)
async function preloadTooltipData(lvl) {
  // Skip if already cached or loading
  if (TOOLTIP_DATA_CACHE.has(lvl)) {
    return TOOLTIP_DATA_CACHE.get(lvl);
  }
  
  // Mark as loading
  const loadingPromise = (async () => {
    const levelElement = document.querySelector(`[data-level="${lvl}"]`);
    const tooltipData = {
      totalWords: 0,
      completedWords: 0,
      practiceAvailable: false,
      loaded: false
    };
    
    // Get level data from cached bulk data
    let levelData = null;
    if (levelElement && levelElement.dataset.bulkData) {
      try {
        levelData = JSON.parse(levelElement.dataset.bulkData);
      } catch (error) {
        if (window.DEBUG) console.log('Error parsing cached bulk data for tooltip preload:', error);
      }
    }
    
    // Extract word counts from bulk data if available
    if (levelData) {
      // Try to get word count from familiarity array
      if (levelData.familiarity && Array.isArray(levelData.familiarity)) {
        tooltipData.totalWords = levelData.familiarity.reduce((a, b) => a + (Number(b) || 0), 0);
        tooltipData.completedWords = Number(levelData.familiarity[5] || 0);
      } else if (levelData.fam_counts && typeof levelData.fam_counts === 'object') {
        const counts = levelData.fam_counts;
        tooltipData.totalWords = [0,1,2,3,4,5].reduce((sum, i) => sum + (Number(counts[i] ?? counts[String(i)] ?? 0)), 0);
        tooltipData.completedWords = Number(counts[5] ?? counts['5'] ?? 0);
      } else if (levelData.words_count) {
        tooltipData.totalWords = Number(levelData.words_count) || 0;
      }
    }
    
    // Prefetch practice availability (non-blocking)
    const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
    if (isUserAuthenticated) {
      try {
        const targetLang = document.getElementById('target-lang')?.value || 'en';
        const pr = await fetch('/api/practice/start', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ level:lvl, peek:true, exclude_max:true, language: targetLang })
        });
        const pj = await pr.json();
        if(pj && pj.success){ 
          const remaining = Number(pj.remaining||pj.total||0); 
          tooltipData.practiceAvailable = remaining > 0; 
        }
      } catch(_) {
        // Ignore errors - practice availability is optional
      }
    }
    
    tooltipData.loaded = true;
    return tooltipData;
  })();
  
  TOOLTIP_DATA_CACHE.set(lvl, loadingPromise);
  return loadingPromise;
}

async function updateLevelTipContent(lvl, isDone){
  // Get level data from cached bulk data
  const levelElement = document.querySelector(`[data-level="${lvl}"]`);
  let levelData = null;
  
  if (levelElement && levelElement.dataset.bulkData) {
    try {
      levelData = JSON.parse(levelElement.dataset.bulkData);
    } catch (error) {
      if (window.DEBUG) console.log('Error parsing cached bulk data for tooltip:', error);
    }
  }
  
  // Update status
  const statusEl = document.getElementById('lt-status');
  const wordsCount = document.getElementById('lt-words-count');
  const completedCount = document.getElementById('lt-completed-count');
  
  let status = window.t ? window.t('status.locked', 'Locked') : 'Locked';
  let progress = 0;
  let score = 0;
  let words = 0;
  let completed = 0;
  
  // Use the same logic as applyLevelStates for consistency
  if(levelData?.status === 'completed' && Number(levelData.last_score || 0) > 0.6){
    // Level abgeschlossen und Score > 0,6 -> Completed
    status = window.t ? window.t('status.completed', 'Completed') : 'Completed';
    progress = Math.round((levelData.last_score || 0) * 100);
    score = progress;
  } else if(levelData?.status === 'completed' && Number(levelData.last_score || 0) <= 0.6){
    // Level abgeschlossen, aber Score <= 0,6 -> Available
    status = window.t ? window.t('status.available', 'Available') : 'Available';
    progress = Math.round((levelData.last_score || 0) * 100);
    score = progress;
  } else if(lvl === 1){
    // Level 1 ist immer verfügbar (erste Lektion) - nur wenn nicht abgeschlossen
    status = window.t ? window.t('status.available', 'Available') : 'Available';
  } else if(lvl > 1) {
    // Prüfe ob vorheriges Level verfügbar oder abgeschlossen ist
    const prevLevelElement = document.querySelector(`[data-level="${lvl - 1}"]`);
    let prevLevelData = null;
    
    if (prevLevelElement && prevLevelElement.dataset.bulkData) {
      try {
        prevLevelData = JSON.parse(prevLevelElement.dataset.bulkData);
      } catch (error) {
        if (window.DEBUG) console.log('Error parsing cached bulk data for previous level tooltip:', error);
      }
    }
    
      // Check if previous level has score >= 60 (ready check based on score)
      // Use the same data source as the display: bulkData from the level element
      let prevScorePercent = 0;
      if (prevLevelElement) {
        prevScorePercent = getLevelScoreFromBulkData(prevLevelElement);
      }
      const isPrevCompleted = prevScorePercent >= 60;
      
      if(isPrevCompleted) {
        status = window.t ? window.t('status.available', 'Available') : 'Available';
      } else {
      status = window.t ? window.t('status.locked', 'Locked') : 'Locked';
    }
  }
  
  // Update elements
  if(statusEl) statusEl.textContent = status;
  
  // Get theme information (section/group)
  const themeEl = document.getElementById('lt-theme');
  const difficultyEl = document.getElementById('lt-difficulty');
  
  // Get section name for theme/group display
  let secName = '';
  try{
    const goal = document.getElementById('topic')?.value || 'everyday';
    const cef  = document.getElementById('cefr')?.value || 'A1';
    const pt = personalizedSectionAndTheme(lvl, goal, cef);
    secName = pt.section||'';
  }catch(_){}
  
  let theme = secName || 'General';
  
  // Try to translate section name
  if(theme && typeof window.t === 'function') {
    try {
      const translated = window.t(`sections.${theme}`, theme);
      if(translated && translated.trim()) theme = translated;
    } catch(_) {}
  }
  
  if(themeEl) themeEl.textContent = theme;
  if(difficultyEl) {
    const difficulty = lvl <= 2 ? 'Beginner' : lvl <= 4 ? 'Intermediate' : 'Advanced';
    difficultyEl.textContent = difficulty;
  }
  
  // Use preloaded tooltip data if available, otherwise try to get from bulk data
  let totalWords = 0;
  let completedWords = 0;
  
  // Check preloaded cache first
  const cachedData = await preloadTooltipData(lvl).catch(() => null);
  if (cachedData && cachedData.loaded) {
    totalWords = cachedData.totalWords || 0;
    completedWords = cachedData.completedWords || 0;
  } else if (levelData) {
    // Fallback to bulk data
    if (levelData.familiarity && Array.isArray(levelData.familiarity)) {
      totalWords = levelData.familiarity.reduce((a, b) => a + (Number(b) || 0), 0);
      completedWords = Number(levelData.familiarity[5] || 0);
    } else if (levelData.fam_counts && typeof levelData.fam_counts === 'object') {
      const counts = levelData.fam_counts;
      totalWords = [0,1,2,3,4,5].reduce((sum, i) => sum + (Number(counts[i] ?? counts[String(i)] ?? 0)), 0);
      completedWords = Number(counts[5] ?? counts['5'] ?? 0);
    } else if (levelData.words_count) {
      totalWords = Number(levelData.words_count) || 0;
    }
  }
  
  // Get score from level data (user-specific if authenticated, 0 if not)
  const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
  let levelScore = 0;
  if (isUserAuthenticated && levelData?.user_progress?.score !== undefined) {
    levelScore = Math.round((levelData.user_progress.score || 0) * 100);
  } else if (!isUserAuthenticated && levelData?.last_score !== undefined) {
    // For unauthenticated users, show global score
    levelScore = Math.round((levelData.last_score || 0) * 100);
  } else {
    // For authenticated users without progress, show 0%
    levelScore = 0;
  }
  
  // Calculate progress based on completed words / total words for this level
  let wordProgressPercent = 0;
  if(totalWords > 0) {
    wordProgressPercent = Math.round((completedWords / totalWords) * 100);
  }
  
  // Update elements with correct data
  if(wordsCount) wordsCount.textContent = totalWords.toString();
  if(completedCount) completedCount.textContent = completedWords.toString();
}

// updateLevelCardProgress function removed - now handled by _setLevelColorBasedOnLearnedWords

async function updateLevelRatingDisplay(lvl, levelCard, stats) {
  const ratingElement = levelCard.querySelector('.level-rating');
  const ratingText = levelCard.querySelector('.rating-text');
  const ratingIcon = levelCard.querySelector('.level-rating span');
  
  if (!ratingElement || !ratingText || !ratingIcon) return;
  
  try {
    // Get rating stats from the level stats response
    const ratingStats = stats?.rating_stats;
    
    if (ratingStats && ratingStats.total_ratings > 0) {
      const { positive_ratings, total_ratings, positive_percentage } = ratingStats;
      
      // Update rating text
      ratingText.textContent = `${positive_percentage}% (${total_ratings})`;
      
      // Update icon based on rating
      if (positive_percentage >= 70) {
        ratingIcon.textContent = '👍';
        ratingIcon.style.color = '#10b981';
      } else if (positive_percentage >= 50) {
        ratingIcon.textContent = '👍';
        ratingIcon.style.color = '#f59e0b';
      } else {
        ratingIcon.textContent = '👎';
        ratingIcon.style.color = '#ef4444';
      }
      
      // Show rating element
      ratingElement.style.display = 'flex';
    } else {
      // No ratings yet
      ratingText.textContent = window.t ? window.t('rating.no_ratings', 'Keine Bewertungen') : 'Keine Bewertungen';
      ratingIcon.textContent = '👍';
      ratingIcon.style.color = 'var(--text-secondary)';
      ratingElement.style.display = 'flex';
    }
  } catch (error) {
    console.log('Error updating rating display:', error);
    // Fallback
    ratingText.textContent = window.t ? window.t('rating.no_ratings', 'Keine Bewertungen') : 'Keine Bewertungen';
    ratingIcon.textContent = '👍';
    ratingIcon.style.color = 'var(--text-secondary)';
    ratingElement.style.display = 'flex';
  }
}

async function openLevelTip(anchor, lvl, isDone){
  // Check if level is locked - don't open tooltip for locked levels (except Level 1)
  const levelCard = document.querySelector(`[data-level="${lvl}"]`);
  if (levelCard && levelCard.classList.contains('locked') && lvl !== 1) {
    return; // Don't open tooltip for locked levels (except Level 1)
  }
  
  const _ltTitle = document.getElementById('lt-title');
  if (_ltTitle) { 
    _ltTitle.innerHTML = ''; 
    _ltTitle.textContent = `Level ${lvl}`; 
    // Keep the fixed title attribute to prevent modifications
    _ltTitle.setAttribute('data-fixed-title', 'true');
  }
  
  // Update tooltip content with level information
  updateLevelTipContent(lvl, isDone);
  try{
    const tgt = (document.getElementById('target-lang')?.value||'en');
    const nat = localStorage.getItem('siluma_native') || 'de';
    const cef = (document.getElementById('cefr')?.value||'none');
    let previewTheme = (typeof window.buildLevelPrompt==='function') ? (function(){
      const spec = document.getElementById('curriculum-spec');
      if(!spec) return '';
      const js = JSON.parse(spec.textContent||'{}');
      const sec = (js.sections||[]).find(s=> lvl>=s.range[0] && lvl<=s.range[1]);
      if(!sec) return '';
      const idx = lvl - sec.range[0];
      return (sec.themes||[])[idx]||'';
    })() : '';
    // Disabled: Don't add theme chip to title
    // if(previewTheme){
    //   const chip3 = document.createElement('span'); chip3.className='pill'; chip3.style.marginLeft='8px';
    //   chip3.textContent = String(previewTheme||''); // Set initial text
    //   _ltTitle.appendChild(chip3);
      
      // Disabled: Don't load translated topic
      // (async ()=>{
        let txt = String(previewTheme||'');
        try{
          if(typeof window.t==='function'){
            // Map common theme names to existing topic keys
            const themeMapping = {
              'daily life': 'topics.daily_life',
              'travel': 'topics.travel', 
              'work': 'topics.work',
              'academic': 'topics.academic',
              'family': 'topics.family',
              'immigration': 'topics.immigration',
              'culture': 'topics.culture',
              'hobbies': 'topics.hobbies',
              'healthcare': 'topics.healthcare',
              'technology': 'topics.technology',
              'food': 'topics.food',
              'romance': 'topics.romance',
              'media': 'topics.media',
              'sich vorstellen': 'topics.daily_life', // Map to daily life
              'introduction': 'topics.daily_life',
              'greetings': 'topics.daily_life'
            };
            
            // Try to find a mapping for the theme
            const lowerTheme = txt.toLowerCase().trim();
            let topicKey = themeMapping[lowerTheme];
            
            if(!topicKey) {
              // Try to match partial themes
              for(const [key, value] of Object.entries(themeMapping)) {
                if(lowerTheme.includes(key) || key.includes(lowerTheme)) {
                  topicKey = value;
                  break;
                }
              }
            }
            
            if(topicKey) {
              const translatedText = window.t(topicKey, '');
              if(translatedText && translatedText.trim()) {
                txt = translatedText;
              }
            } else {
              // Fallback: try level-specific name
              const levelName = window.t(`level.${lvl}.name`, '');
              if(levelName && levelName.trim()) {
                txt = levelName;
              }
            }
          }
        }catch(_){ }
        // Disabled: Don't update chip
        // if(chip3 && chip3.textContent !== txt) {
        //   chip3.textContent = txt;
        // }
      // })();
    // }
  }catch(_){}
  const oldTbl = document.querySelector('#lt-fam-table'); if(oldTbl) oldTbl.remove();
  document.getElementById('level-tip').style.display='block';
  positionLevelTip(anchor);
  // Removed per-level topic input and suggest logic.
  document.getElementById('lt-close').onclick = ()=>{
    document.getElementById('level-tip').style.display='none';
    renderLevels();
  };
  // Buttons removed - no longer needed
  // document.getElementById('lt-start').style.display = '';
  // document.getElementById('lt-repeat').style.display = 'none';
  // Check if level is completed using cached bulk data
  let isCompleted = false;
  const levelElement = document.querySelector(`[data-level="${lvl}"]`);
  if (levelElement && levelElement.dataset.bulkData) {
  try {
      const levelData = JSON.parse(levelElement.dataset.bulkData);
    if(levelData?.status === 'completed' && Number(levelData.last_score || 0) > 0.6){
      isCompleted = true;
    }
    } catch (error) {
      console.log('Error parsing cached bulk data for completion check:', error);
    }
  }
  
  
  // Standard levels disabled - skip API call and use default values
    let prevOk = (lvl===1);
    let score = null; let words = null;
  
  if (!DISABLE_STANDARD_LEVEL_GROUPS) {
    // Only fetch if standard levels are enabled (they're not, but keeping for completeness)
    try {
      const response = await fetch(`/api/levels/summary?language=${encodeURIComponent(currentTargetLang())}`);
      const js = await response.json();
    if(js && js.success){
      const byLevel = new Map((js.levels||[]).map(x=>[x.level, x]));
      const cur = byLevel.get(lvl);
      if(cur && (cur.status==='completed' || cur.score != null)){
        score = (cur.last_score!=null?cur.last_score:cur.score); words = cur.words_count;
      }
    }
    } catch(err) {
      // API endpoint removed - ignore error
    }
  }
  
    // bevorzugt: per-Level-Stats des VORHERIGEN Levels
    if(lvl>1){
      const prevLevelElement = document.querySelector(`[data-level="${lvl - 1}"]`);
      if (prevLevelElement && prevLevelElement.dataset.bulkData) {
      try{
          const prevJs = JSON.parse(prevLevelElement.dataset.bulkData);
        prevOk = !!(prevJs && Number(prevJs.last_score||0) > 0.6);
        } catch (error) {
          console.log('Error parsing cached bulk data for previous level:', error);
        }
      }
    }
  // Use preloaded tooltip data for practice availability if available
    let practiceAvailable = true;
  const cachedTooltipData = await preloadTooltipData(lvl).catch(() => null);
  if (cachedTooltipData && cachedTooltipData.loaded) {
    practiceAvailable = cachedTooltipData.practiceAvailable;
  } else {
    // Fallback to checking bulk data
    const currentLevelElement = document.querySelector(`[data-level="${lvl}"]`);
    if (currentLevelElement && currentLevelElement.dataset.bulkData) {
      try {
        const sj = JSON.parse(currentLevelElement.dataset.bulkData);
        let famArr = null;

        if (Array.isArray(sj?.familiarity)) {
          famArr = sj.familiarity;
        } else if (Array.isArray(sj?.data?.familiarity)) {
          famArr = sj.data.familiarity;
        } else if (Array.isArray(sj?.dist)) {
          famArr = sj.dist;
        } else if (sj?.familiarity && typeof sj.familiarity === 'object') {
          famArr = [0,1,2,3,4,5].map(i => Number(sj.familiarity[i] ?? sj.familiarity[String(i)] ?? 0));
        } else if (sj?.counts && typeof sj.counts === 'object') {
          famArr = [0,1,2,3,4,5].map(i => Number(sj.counts[i] ?? sj.counts[String(i)] ?? 0));
        } else if (sj?.data && typeof sj.data === 'object') {
          famArr = [0,1,2,3,4,5].map(i => Number(sj.data[i] ?? sj.data[String(i)] ?? 0));
        }

        if (Array.isArray(famArr) && famArr.length) {
          const remaining = famArr.slice(0, 5).reduce((a, b) => a + (Number(b) || 0), 0);
          practiceAvailable = remaining > 0;
        }
      } catch(e) {
        if (window.DEBUG) console.warn('Failed to parse cached level stats', e);
      }
    }
    
    // If still not determined and user is authenticated, fetch practice availability
    if (practiceAvailable === true && window.authManager && window.authManager.isAuthenticated()) {
    try{
        const pr = await fetch('/api/practice/start', {
          method:'POST',
          headers:{'Content-Type':'application/json'},
          body: JSON.stringify({ level:lvl, peek:true, exclude_max:true, language: currentTargetLang() })
        });
        const pj = await pr.json();
        if(pj && pj.success){ const remaining = Number(pj.remaining||pj.total||0); practiceAvailable = remaining > 0; }
    }catch(_){}
    }
  }
    const title = document.getElementById('lt-title');
    // title.textContent = `Level ${lvl}`; // already set above
    // Only add score chip if title is not fixed
    if(isCompleted && typeof score === 'number' && !title?.getAttribute('data-fixed-title')){
      const chip = document.createElement('span'); chip.className='pill ok'; chip.style.marginLeft='8px'; chip.textContent = `Score ${score.toFixed(2)}`; title.appendChild(chip);
    }
    if(typeof words === 'number' && !title?.getAttribute('data-fixed-title')){
      const chip2 = document.createElement('span'); chip2.className='pill'; chip2.style.marginLeft='8px'; chip2.textContent = `Wörter ${words}`; title.appendChild(chip2);
    }
    // Buttons removed - no longer needed
    // if(isCompleted){ document.getElementById('lt-start').style.display='none'; document.getElementById('lt-repeat').style.display=''; }
    // Buttons removed - no longer needed
    // const rep = document.getElementById('lt-repeat');
    // let pbtn = document.getElementById('lt-practice');
    // if(rep && !pbtn){
    //   pbtn = document.createElement('button');
    //   pbtn.id = 'lt-practice';
    //   pbtn.className = rep.className;
    //   pbtn.style.marginLeft = '8px';
    //   pbtn.textContent = window.t ? window.t('buttons.practice', 'Üben') : 'Üben';
    //   rep.parentNode.insertBefore(pbtn, rep.nextSibling);
    // }
    // Buttons removed - no longer needed
    // if(pbtn){
    //   pbtn.style.display = isCompleted ? '' : 'none';
    //  const gatePrev = (!prevOk && lvl>1);
    //  const gateItems = !practiceAvailable;
    //  pbtn.disabled = gatePrev || gateItems;
    //  if(gatePrev) pbtn.title = 'Vorheriges Level mit > 0,6 abschließen';
    //  else if(gateItems) pbtn.title = window.t ? window.t('levels.no_remaining_words', 'Keine übrig gebliebenen Wörter (max. Stufe erreicht)') : 'Keine übrig gebliebenen Wörter (max. Stufe erreicht)';
    //  else pbtn.title = '';
    //   pbtn.onclick = ()=>{
    //     const t = (document.getElementById('lt-topic')?.value||'').trim();
    //     saveLevelTopic(lvl, t);
    //     document.getElementById('level-tip').style.display='none';
    //     if(typeof window.startPracticeForLevel === 'function'){
    //       window.startPracticeForLevel(lvl);
    //     } else {
    //       try{ window.showTab && window.showTab('practice'); }catch(_){}
    //     }
    //   };
    // }
    // Buttons removed - no longer needed
    // const startBtn = document.getElementById('lt-start');
    // const repBtn   = document.getElementById('lt-repeat');
    // if(!prevOk && lvl>1 && !(anchor && anchor.dataset && anchor.dataset.allowStart==='true')){
    //   if(startBtn){ startBtn.disabled = true; startBtn.title = 'Vorheriges Level mit > 0,6 abschließen'; }
    //   if(repBtn){   repBtn.disabled   = true; repBtn.title   = 'Vorheriges Level mit > 0,6 abschließen'; }
    // } else {
    //   if(startBtn){ startBtn.disabled = false; startBtn.title = ''; }
    //   if(repBtn){   repBtn.disabled   = false; repBtn.title   = ''; }
    // }
  // Buttons removed - no longer needed
  // document.getElementById('lt-repeat').onclick = ()=>{
  //   const t = (document.getElementById('topic')?.value||'').trim();
  //   document.getElementById('level-tip').style.display='none';
  //   if(typeof window.startLevelWithTopic === 'function'){
  //     window.startLevelWithTopic(lvl, t, true);
  //   }
  // };
  
  // Buttons removed - no longer needed
  // 
  // if(detailsBtn) {
  //   detailsBtn.onclick = (e) => {
  //     e.stopPropagation();
  //     // Show detailed level information (could open a modal or navigate to details page)
  //     console.log(`Show details for level ${lvl}`);
  //     // For now, just show an alert - could be enhanced later
  //     alert(`Level ${lvl} Details:\nStatus: ${document.getElementById('lt-status')?.textContent || 'Unknown'}\nTheme: ${document.getElementById('lt-theme')?.textContent || 'Unknown'}\nProgress: ${document.getElementById('lt-progress-percent')?.textContent || '0%'}`);
  //   };
  // }
}

// Helper function to create flip card structure
function createFlipCard(level, isAlphabet = false) {
  const node = document.createElement('div');
  node.className = 'level-card';
  node.dataset.level = level;

  // Create flip container
  const inner = document.createElement('div');
  inner.className = 'level-card-inner';

  // Front side
  const front = document.createElement('div');
  front.className = 'level-card-front';
  
  const cardContent = document.createElement('div');
  cardContent.className = 'level-card-content';
  
  // Level number circle
  const levelNumber = document.createElement('div');
  levelNumber.className = 'level-number';
  levelNumber.textContent = isAlphabet ? '🔤' : level;
  
  // Card info section
  const cardInfo = document.createElement('div');
  cardInfo.className = 'level-card-info';
  
  const status = document.createElement('div');
  status.className = 'level-status';
  status.textContent = window.t ? window.t('status.locked', 'Locked') : 'Locked';
  
  const title = document.createElement('div');
  title.className = 'level-title';
  title.textContent = isAlphabet ? 
    (window.t ? window.t('navigation.alphabet', 'Alphabet') : 'Alphabet') :
    `Level ${level}`;
  
  const theme = document.createElement('div');
  theme.className = 'level-theme';
  if(isAlphabet){
    theme.textContent = 'Grundlagen';
  }else{
    const info = _levelGroupInfo(level);
    theme.textContent = info.label;
    node.dataset.section = info.section || '';
  }
  
  // Actions
  const actions = document.createElement('div');
  actions.className = 'level-actions';
  
  if (isAlphabet) {
    actions.style.display = 'none';
  } else {
    // Normal level cards have "Start" and "Practice" buttons
    const startBtn = document.createElement('button');
    startBtn.className = 'level-btn primary';
    startBtn.setAttribute('data-i18n', 'buttons.start');
    startBtn.textContent = window.t ? window.t('buttons.start', 'Start') : 'Start';
    startBtn.onclick = async (e) => {
      e.stopPropagation();
      
      // Unlock words for this level if user is authenticated
      if (window.authManager && window.authManager.isAuthenticated()) {
        const unlocked = await unlockLevelWords(level);
        if (!unlocked) {
          console.warn('Failed to unlock words for level', level);
        }
      }
      
      // Start level - try different function names
      // Level will be automatically user-specific based on authentication
      if(typeof window.startLevelWithTopic === 'function'){
        window.startLevelWithTopic(level, `Level ${level}`);
      } else if(typeof window.startLevel === 'function'){
        window.startLevel(level);
      } else {
        console.log(`Starting user-specific level ${level}`);
        // Fallback: show level details or start practice
        if(typeof window.showTab === 'function'){
          window.showTab('practice');
        }
      }
    };
    
    const practiceBtn = document.createElement('button');
    practiceBtn.className = 'level-btn';
    practiceBtn.setAttribute('data-i18n', 'buttons.practice');
    practiceBtn.textContent = window.t ? window.t('buttons.practice', 'Practice') : 'Practice';
    practiceBtn.onclick = (e) => {
      e.stopPropagation();
      // Start practice for this level
      if(typeof window.startPracticeForLevel === 'function'){
        window.startPracticeForLevel(level);
      } else if(typeof window.showTab === 'function'){
        window.showTab('practice');
      } else {
        console.log(`Starting practice for level ${level}`);
      }
    };
    
    // Store button references for later highlighting
    node.dataset.startBtn = 'startBtn';
    node.dataset.practiceBtn = 'practiceBtn';
    
    actions.appendChild(startBtn);
    actions.appendChild(practiceBtn);
  }
  
  // Assemble front side
  cardInfo.appendChild(status);
  cardInfo.appendChild(title);
  cardInfo.appendChild(theme);
  
  // Word statistics section (only for non-alphabet cards) - positioned after theme
  if (!isAlphabet) {
    const wordStats = document.createElement('div');
    wordStats.className = 'level-word-stats';
    
    // Main container for words/circle layout
    const wordStatsMain = document.createElement('div');
    wordStatsMain.className = 'level-word-stats-main';
    
    // Left side: Words and Learned counts
    const wordStatsLeft = document.createElement('div');
    wordStatsLeft.className = 'level-word-stats-left';
    
    const wordsCount = document.createElement('div');
    wordsCount.className = 'level-words-count';
    wordsCount.innerHTML = '<span class="words-icon">📖</span><span class="words-text">0</span>';
    
    const learnedCount = document.createElement('div');
    learnedCount.className = 'level-learned-count';
    learnedCount.innerHTML = '<span class="learned-icon">💡</span><span class="learned-text">0</span>';
    
    wordStatsLeft.appendChild(wordsCount);
    wordStatsLeft.appendChild(learnedCount);
    
    // Right side: Completion circle
    const wordStatsRight = document.createElement('div');
    wordStatsRight.className = 'level-word-stats-right';
    
    const completionCircle = document.createElement('div');
    completionCircle.className = 'level-completion-circle';
    completionCircle.innerHTML = `
      <svg class="completion-circle-svg" viewBox="0 0 36 36">
        <path class="completion-circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
        <path class="completion-circle-fill" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
      </svg>
      <div class="completion-circle-text">0%</div>
    `;
    
    wordStatsRight.appendChild(completionCircle);
    
    // Progress bar
    const progressBar = document.createElement('div');
    progressBar.className = 'level-progress-bar';
    const progressFill = document.createElement('div');
    progressFill.className = 'level-progress-fill';
    progressBar.appendChild(progressFill);
    
    wordStatsMain.appendChild(wordStatsLeft);
    wordStatsMain.appendChild(wordStatsRight);
    
    wordStats.appendChild(wordStatsMain);
    wordStats.appendChild(progressBar);
    
    cardInfo.appendChild(wordStats);
  }
  
  cardContent.appendChild(levelNumber);
  cardContent.appendChild(cardInfo);
  cardContent.appendChild(actions);
  
  front.appendChild(cardContent);

  // Back side (tooltip info)
  const back = document.createElement('div');
  back.className = 'level-card-back';
  
  const backContent = document.createElement('div');
  backContent.className = 'level-card-back-content';
  
  // Header
  const backHeader = document.createElement('div');
  backHeader.className = 'level-card-back-header';
  
  const backTitle = document.createElement('div');
  backTitle.className = 'level-card-back-title';
  backTitle.textContent = isAlphabet ? 
    (window.t ? window.t('navigation.alphabet', 'Alphabet') : 'Alphabet') :
    `Level ${level}`;
  
  const backClose = document.createElement('div');
  backClose.className = 'level-card-back-close';
  backClose.textContent = '×';
  backClose.onclick = (e) => {
    e.stopPropagation();
    node.classList.remove('flipped');
  };
  
  backHeader.appendChild(backTitle);
  backHeader.appendChild(backClose);
  
  // Familiarity overview
  const backInfo = document.createElement('div');
  backInfo.className = 'level-card-back-info';
  
  // Title for familiarity overview
  const overviewTitle = document.createElement('div');
  overviewTitle.className = 'familiarity-overview-title';
  overviewTitle.setAttribute('data-i18n', 'familiarity.title');
  overviewTitle.textContent = window.t ? window.t('familiarity.title', 'Familiarity of Words') : 'Familiarity of Words';
  
  // Familiarity list container
  const familiarityList = document.createElement('div');
  familiarityList.className = 'familiarity-list';
  
  // Create familiarity items (will be populated when data is loaded)
  const familiarityLevels = [
    { level: 0, symbol: '❌', labelKey: 'familiarity.unknown', count: 0 },
    { level: 1, symbol: '🔴', labelKey: 'familiarity.seen', count: 0 },
    { level: 2, symbol: '🟠', labelKey: 'familiarity.learning', count: 0 },
    { level: 3, symbol: '🟡', labelKey: 'familiarity.familiar', count: 0 },
    { level: 4, symbol: '🟢', labelKey: 'familiarity.strong', count: 0 },
    { level: 5, symbol: '💡', labelKey: 'familiarity.memorized', count: 0 }
  ];
  
  familiarityLevels.forEach(fam => {
    const item = document.createElement('div');
    item.className = 'familiarity-item';
    item.dataset.familiarityLevel = fam.level;
    
    const symbol = document.createElement('div');
    symbol.className = 'familiarity-symbol';
    symbol.textContent = fam.symbol;
    
    const label = document.createElement('div');
    label.className = 'familiarity-label';
    label.setAttribute('data-i18n', fam.labelKey);
    label.textContent = window.t ? window.t(fam.labelKey, fam.labelKey) : fam.labelKey;
    
    const count = document.createElement('div');
    count.className = 'familiarity-count';
    count.textContent = '0';
    
    item.appendChild(symbol);
    item.appendChild(label);
    item.appendChild(count);
    familiarityList.appendChild(item);
  });
  
  backInfo.appendChild(overviewTitle);
  backInfo.appendChild(familiarityList);
  
  backContent.appendChild(backHeader);
  backContent.appendChild(backInfo);
  back.appendChild(backContent);

  // Assemble flip card
  inner.appendChild(front);
  inner.appendChild(back);
  node.appendChild(inner);
  
  // Add click handler for flipping
  node.onclick = (e) => {
    if (!e.target.closest('.level-btn') && !e.target.closest('.level-card-back-close')) {
      const wasFlipped = node.classList.contains('flipped');
      node.classList.toggle('flipped');
      
      // If flipping to back side, load familiarity data
      if (!wasFlipped && !isAlphabet) {
        loadFamiliarityData(node, level);
      }
    }
  };
  
  return node;
}

export async function renderLevels(){
  const host = document.getElementById('levels'); if(!host) return;
  const my = ++LEVELS_REQ;
  const pc = document.getElementById('practice-card'); if(pc) pc.style.display = 'none';
  bindPracticeActionButtons();

  const summary = await ensureLevelSummary(true);
  if(my !== LEVELS_REQ) return;
  const byLevel = summary?.byLevel || new Map();

  // First render the groups view
  await renderLevelGroupsView(byLevel);

  host.dataset.groupId = SELECTED_LEVEL_GROUP ? SELECTED_LEVEL_GROUP.id : '';

  if(!SELECTED_LEVEL_GROUP){
    showGroupsContainer();
    updateSelectedGroupHeader();
    // Don't update group stats here - they will be updated after applyLevelStates
    return;
  }

  showLevelsContainer();
  updateSelectedGroupHeader();
  host.replaceChildren();

  const rangeStart = Math.max(1, Number(SELECTED_LEVEL_GROUP.start || 1));
  const rangeEnd = Math.max(rangeStart, Number(SELECTED_LEVEL_GROUP.end || rangeStart));

  const levelsToRender = new Set();
  for(let i = rangeStart; i <= rangeEnd; i += 1){
    levelsToRender.add(i);
  }
  for(const lvl of byLevel.keys()){
    if(lvl >= rangeStart && lvl <= rangeEnd){
      levelsToRender.add(lvl);
    }
  }

  const sortedLevels = Array.from(levelsToRender).sort((a, b) => a - b);
  console.log('Levels to render (sorted):', sortedLevels);

  // Alphabet card removed - now handled by separate "Alphabet Übung" button

  for(const levelNumber of sortedLevels){
    const node = createFlipCard(levelNumber, false);
    node.classList.add('locked');
    node.dataset.allowStart = 'false';

    const levelData = byLevel.get(levelNumber);
    // Don't set unlock status here - let applyLevelStates() handle it
    // This ensures consistent unlock logic based on score >= 60
    // Initial state is locked, applyLevelStates() will update it correctly

    host.appendChild(node);
    
    // Preload tooltip data in background (non-blocking)
    preloadTooltipData(levelNumber).catch(() => {});
    
    // Prefetch on hover for instant tooltip display
    let hoverTimeout = null;
    node.addEventListener('mouseenter', () => {
      // Clear any existing timeout
      if (hoverTimeout) clearTimeout(hoverTimeout);
      // Prefetch after a short delay (100ms) to avoid unnecessary requests on quick mouse movements
      hoverTimeout = setTimeout(() => {
        preloadTooltipData(levelNumber).catch(() => {});
      }, 100);
    });
    node.addEventListener('mouseleave', () => {
      if (hoverTimeout) {
        clearTimeout(hoverTimeout);
        hoverTimeout = null;
      }
    });
  }

  try{ await debouncedApplyLevelStates(); }catch(_){ }
  
  updateLevelNames();
  updateLevelGroupLabels();
  updateSelectedGroupHeader();

  await updateHeaderStatsForLevelSet(sortedLevels);

  const topicSelect = document.getElementById('topic');
  if(topicSelect && !topicSelect.dataset.levelGroupBound){
    topicSelect.addEventListener('change', ()=> updateLevelGroupLabels());
    topicSelect.dataset.levelGroupBound = 'true';
  }
  const cefrSelect = document.getElementById('cefr');
  if(cefrSelect && !cefrSelect.dataset.levelGroupBound){
    cefrSelect.addEventListener('change', ()=> updateLevelGroupLabels());
    cefrSelect.dataset.levelGroupBound = 'true';
  }

  const backBtn = document.getElementById('levels-group-back');
  if(backBtn && !backBtn.dataset.bound){
    backBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      console.log('🔙 Back button clicked, navigating to groups home');
      showLevelGroupsHome();
    });
    backBtn.dataset.bound = 'true';
  }
}

// Function to update level names with proper localization
function updateLevelNames() {
  console.log('🔄 Updating level names...');
  
  const levelCards = document.querySelectorAll('.level-card');
  levelCards.forEach(card => {
    const levelNum = parseInt(card.dataset.level);
    const titleElement = card.querySelector('.level-title');
    
    if (!titleElement) return;
    
    if (levelNum === 'alphabet' || card.dataset.level === 'alphabet') {
      titleElement.textContent = window.t ? window.t('navigation.alphabet', 'Alphabet') : 'Alphabet';
      return;
    }
    
    if (!levelNum || isNaN(levelNum)) return;
    
    // Map level numbers to their corresponding theme keys (matching CSV entries)
    const levelThemeMap = {
      1: 'Sich vorstellen',
      2: 'Begrüßungen', 
      3: 'Familie & Freunde',
      4: 'Zahlen & Zeit',
      5: 'Alltagswörter & Farben',
      6: 'Höflichkeit & Etikette',
      7: 'Fragen & Antworten',
      8: 'Orientierung & Transport',
      9: 'Einkaufen (Markt)',
      10: 'Wiederholung I',
      11: 'Essen & Trinken (Restaurant)',
      12: 'Unterkunft',
      13: 'Einkaufen (Kleidung)',
      14: 'Arbeit & Schule',
      15: 'Gesundheit',
      16: 'Freizeit & Hobbys',
      17: 'Reisen',
      18: 'Notfälle',
      19: 'Digitale Welt',
      20: 'Wiederholung II',
      21: 'Essen & Trinken (Restaurant)',  // Repeat themes for higher levels
      22: 'Unterkunft',
      23: 'Einkaufen (Kleidung)',
      24: 'Arbeit & Schule',
      25: 'Gesundheit',
      26: 'Freizeit & Hobbys',
      27: 'Reisen',
      28: 'Notfälle',
      29: 'Digitale Welt',
      30: 'Wiederholung III',
      31: 'Essen & Trinken (Restaurant)',
      32: 'Unterkunft',
      33: 'Einkaufen (Kleidung)',
      34: 'Arbeit & Schule',
      35: 'Gesundheit',
      36: 'Freizeit & Hobbys',
      37: 'Reisen',
      38: 'Notfälle',
      39: 'Digitale Welt',
      40: 'Wiederholung IV',
      41: 'Essen & Trinken (Restaurant)',
      42: 'Unterkunft',
      43: 'Einkaufen (Kleidung)',
      44: 'Arbeit & Schule',
      45: 'Gesundheit',
      46: 'Freizeit & Hobbys',
      47: 'Reisen',
      48: 'Notfälle',
      49: 'Digitale Welt',
      50: 'Wiederholung V'
    };
    
    const themeKey = levelThemeMap[levelNum];
    console.log(`Level ${levelNum}: themeKey = "${themeKey}"`);
    
    let levelName = '';
    if(themeKey && typeof window.t === 'function'){
      const csvKey = `level_themes.${themeKey}`;
      levelName = window.t(csvKey, '');
      console.log(`Level ${levelNum}: CSV key = "${csvKey}", result = "${levelName}"`);
    }
    
    // Set title to level name (or fallback to "Level X")
    if(levelName && !levelName.includes('[') && !levelName.includes('level.') && levelName.trim()){
      titleElement.textContent = levelName;
      console.log(`Level ${levelNum}: Using localized name: "${levelName}"`);
    } else {
      titleElement.textContent = `Level ${levelNum}`;
      console.log(`Level ${levelNum}: Using fallback: "Level ${levelNum}"`);
    }
  });
}

function updateLevelGroupLabels(){
  const cards = document.querySelectorAll('.level-card[data-level]');
  cards.forEach(card => {
    if(card.dataset.level === 'alphabet') return;
    const lvl = Number(card.dataset.level);
    if(!Number.isFinite(lvl) || lvl <= 0) return;
    const info = _levelGroupInfo(lvl);
    card.dataset.section = info.section || '';
    const el = card.querySelector('.level-theme');
    if(el){
      el.textContent = info.label;
    }
  });
}

// Word count functions removed - now handled by _setLevelColorBasedOnLearnedWords

// Function removed - word statistics now handled on front of cards

// Function to refresh all level colors (prevents interference)
export async function refreshAllLevelColors() {
  const levelCards = document.querySelectorAll('.level-card[data-level]');
  for (const card of levelCards) {
    const level = parseInt(card.dataset.level);
    if (level && !isNaN(level)) {
      // Reset color protection
      card.dataset.colorSet = 'false';
      
      // Check if this is a custom level
      const isCustomLevel = card.dataset.customGroupId || card.classList.contains('custom-level');
      
      if (isCustomLevel) {
        // For custom levels, use the custom level progress function
        const groupId = card.dataset.customGroupId;
        if (groupId && typeof window.applyCustomLevelProgress === 'function') {
          await window.applyCustomLevelProgress(card, level, groupId);
        }
      } else {
        // For standard levels, use the standard function
        await _setLevelColorBasedOnLearnedWords(card, level);
      }
    }
  }
}

// Expose for legacy inline code
if (typeof window !== 'undefined'){
  window.renderLevels = renderLevels;
  window.saveLevelTopic = saveLevelTopic;
  window.loadLevelTopic = loadLevelTopic;
  window.ensureTopicsForVisibleLevels = ensureTopicsForVisibleLevels;
  window.showTab = showTab;
  window.showLoader = showLoader;
  window.updateLevelGroupNames = updateLevelGroupNames;
  window.hideLoader = hideLoader;
  window.setDebug = setDebug;
  window.showProgress = showProgress;
  window.refreshAllLevelColors = refreshAllLevelColors;
  window.updateLevelGroupLabels = updateLevelGroupLabels;
  window.showLevelGroupsHome = showLevelGroupsHome;
  window.updatePracticeActionLabels = updatePracticeActionLabels;
  window.bindPracticeActionButtons = bindPracticeActionButtons;
  window.startSmartPractice = startSmartPractice;
  window.showLevelLockedMessage = showLevelLockedMessage;
  window.hideLevelLockedMessage = hideLevelLockedMessage;
  window.goToPreviousLevel = goToPreviousLevel;
  window.renderLevels = renderLevels;
  // updateLevelCardBackData removed - no longer needed
}
