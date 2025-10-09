// Main bootstrapping for ES modules
import { setupTooltipSaveClose, observeTooltipClose } from './ui/tooltip.js';
import { setNativeDropdownVisible, showTab, observeLevelsVisible, observeEvaluationVisible, ensureLtPractice, renderLevels, showLoader, hideLoader } from './ui/levels.js';
import { initLesson } from './ui/lesson.js';
import { initTopbar } from './ui/topbar.js';
import { initPractice } from './ui/practice.js';
import { wireEvaluationButtons, populateEvaluationScore, populateEvaluationStatus } from './ui/evaluation.js';
import { initAlphabet } from './ui/alphabet.js';
import { initLocalization } from './ui/localization.js';
import { initHeaderStats } from './ui/header-stats.js';
import { returnToLibraryHome } from './ui/words.js';
import './auth.js';
import './settings.js';
import './ui/marketplace.js';
import './ui/custom-level-groups.js';

// Statistics cards are now non-clickable - just display stats

document.addEventListener('DOMContentLoaded', async () => {
  // Tooltip
  setupTooltipSaveClose();
  observeTooltipClose();

  // Topbar (nav + prefs) - wait for completion
  await initTopbar();
  
  // Initialize header statistics
  initHeaderStats();

  // Lessons
  initLesson();

  // Practice
  initPractice();

  // Alphabet pre-level
  initAlphabet();
  
  // Localization management
  initLocalization();

  // Evaluation UI bindings and metrics
  wireEvaluationButtons();
  // Prime score/status once on boot in case evaluation is shown early
  try{ populateEvaluationScore(); }catch(_){ }
  try{ populateEvaluationStatus(); }catch(_){ }

  // Levels/Evaluation observers
  observeLevelsVisible();
  observeEvaluationVisible();
  ensureLtPractice();
  
  console.log('🎯 Calling renderLevels...');
  try {
    renderLevels();
  } catch (error) {
    console.error('❌ Error calling renderLevels:', error);
  }
  
  showLoader();
  hideLoader();

  // Apply localization to all elements
  try {
    const { applyI18n } = await import('./i18n.js');
    applyI18n();
    console.log('✅ Localization applied');
  } catch (error) {
    console.warn('⚠️ Could not apply localization:', error);
  }

  // Check if we need to open create custom group modal (after onboarding)
  setTimeout(() => {
    const shouldCreateGroup = localStorage.getItem('siluma_onboarding_create_group');
    if (shouldCreateGroup === 'true') {
      console.log('🎯 Onboarding requested custom group creation, opening modal...');
      localStorage.removeItem('siluma_onboarding_create_group');
      
      if (typeof window.showCreateCustomGroupModal === 'function') {
        window.showCreateCustomGroupModal();
        console.log('✅ Create custom group modal opened after onboarding');
      } else {
        console.warn('⚠️ showCreateCustomGroupModal not available yet');
      }
    }
  }, 2000); // Wait 2 seconds for everything to load

  // Initialize navigation tabs to return to library home
  initNavigationHomeButtons();

  // Legacy-API for inline code
  if(typeof window !== 'undefined'){
    window.showTab = showTab;
    window.setNativeDropdownVisible = setNativeDropdownVisible;
  }
});

// Initialize navigation buttons to handle special cases
function initNavigationHomeButtons() {
  // Only the Polo logo should return to library home
  const libraryTab = document.querySelector('[data-tab="library"]'); // Polo logo
  
  // Polo logo - return to library home (override default tab behavior)
  if (libraryTab && !libraryTab.dataset.homebound) {
    libraryTab.addEventListener('click', (e) => {
      // Check if we're already on the library tab - if so, return to home
      const libraryTabContent = document.getElementById('library-tab');
      const isLibraryActive = libraryTabContent && libraryTabContent.classList.contains('active');
      
      if (isLibraryActive) {
        // Already on library tab - ensure we're showing the home view
        e.preventDefault();
        e.stopPropagation();
        console.log('🎓 Polo logo clicked - ensuring library home view');
        returnToLibraryHome();
      } else {
        // Not on library tab - let default tab switching happen, but then show home
        console.log('🎓 Polo logo clicked - switching to library tab');
        // Don't prevent default - let the normal tab switching happen
        // But add a listener to show home after tab switch
        setTimeout(() => {
          returnToLibraryHome();
        }, 50);
      }
    });
    libraryTab.dataset.homebound = 'true';
    console.log('✅ Polo logo navigation initialized');
  }
  
  // Note: Browse, Courses, Settings tabs use their default behavior from showTab()
  // No special handling needed - they work correctly with the standard tab system
}