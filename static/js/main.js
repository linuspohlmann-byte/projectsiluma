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
import { loadWords, returnToLibraryHome } from './ui/words.js';
import './auth.js';
import './settings.js';
import './ui/marketplace.js';
import './ui/custom-level-groups.js';

// Initialize clickable statistics functionality
function initClickableStats() {
  // Words stat card - show all words for current course
  const wordsStatCard = document.getElementById('words-stat-card');
  if (wordsStatCard) {
    wordsStatCard.addEventListener('click', async () => {
      // Switch to words tab
      showTab('words');
      // Load all words for current course
      await loadWords();
    });
  }

  // Learned words stat card - show only learned words for current course
  const learnedStatCard = document.getElementById('learned-stat-card');
  if (learnedStatCard) {
    learnedStatCard.addEventListener('click', async () => {
      // Switch to words tab
      showTab('words');
      // Load words and filter to show only learned ones
      await loadWords();
      // Apply filter for learned words (familiarity = 5)
      filterWordsByFamiliarity(5);
    });
  }
}

// Filter words by familiarity level
function filterWordsByFamiliarity(familiarityLevel) {
  // Get the filter input field
  const filterInput = document.getElementById('wb-filter-q');
  if (filterInput) {
    // Set filter to show only words with specific familiarity
    filterInput.value = String(familiarityLevel);
    // Trigger filter update
    filterInput.dispatchEvent(new Event('input'));
  }
  
  // Also set the filter column to familiarity
  const filterColumn = document.getElementById('wb-filter-col');
  if (filterColumn) {
    filterColumn.value = 'familiarity';
    filterColumn.dispatchEvent(new Event('change'));
  }
}

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

  // Initialize clickable statistics
  initClickableStats();
  
  // Initialize navigation tabs to return to library home
  initNavigationHomeButtons();

  // Legacy-API for inline code
  if(typeof window !== 'undefined'){
    window.showTab = showTab;
    window.setNativeDropdownVisible = setNativeDropdownVisible;
  }
});

// Initialize navigation buttons (Polo logo and Browse) to return to library home
function initNavigationHomeButtons() {
  // Get all navigation tabs that should return to library home
  const libraryTab = document.querySelector('[data-tab="library"]'); // Polo logo
  const browseTab = document.querySelector('[data-tab="browse"]'); // Durchsuchen
  
  // Polo logo - return to library home
  if (libraryTab && !libraryTab.dataset.homebound) {
    libraryTab.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      console.log('🎓 Polo logo clicked - returning to library home');
      returnToLibraryHome();
    });
    libraryTab.dataset.homebound = 'true';
    console.log('✅ Polo logo navigation initialized');
  }
  
  // Browse button - return to library home
  if (browseTab && !browseTab.dataset.homebound) {
    browseTab.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      console.log('🔍 Browse button clicked - returning to library home');
      returnToLibraryHome();
    });
    browseTab.dataset.homebound = 'true';
    console.log('✅ Browse button navigation initialized');
  }
}