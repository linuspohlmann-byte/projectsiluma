/**
 * Custom Level Groups UI
 * Handles creation and management of user-defined level groups
 */

let customLevelGroups = [];
let currentLanguage = 'en';
let currentNativeLanguage = 'de';

// --- Helpers ---------------------------------------------------------------
function normalizeScoreValue(raw) {
    if (raw === null || raw === undefined) return 0;
    let num = Number(raw);
    if (!Number.isFinite(num)) return 0;
    if (num > 1.0001) {
        num = num / 100;
    }
    if (num < 0) num = 0;
    if (num > 1 && num < 1.0001) num = 1; // guard against floating errors
    if (num > 1) num = 1;
    return num;
}

function normalizeFamCounts(rawCounts) {
    const counts = {0:0,1:0,2:0,3:0,4:0,5:0};
    if (!rawCounts) return counts;
    if (Array.isArray(rawCounts)) {
        rawCounts.forEach((val, idx) => {
            if (idx >= 0 && idx <= 5) counts[idx] = Number(val) || 0;
        });
        return counts;
    }
    const mappings = {
        unfamiliar: 0, unknown: 0, '0': 0, familiarity_0: 0,
        seen: 1, '1': 1, familiarity_1: 1,
        learning: 2, '2': 2, familiarity_2: 2,
        familiar: 3, '3': 3, familiarity_3: 3,
        strong: 4, '4': 4, familiarity_4: 4,
        memorized: 5, mastered: 5, learned: 5, '5': 5, familiarity_5: 5
    };
    Object.entries(rawCounts).forEach(([key, value]) => {
        const mappedKey = mappings.hasOwnProperty(key) ? mappings[key] : Number(key);
        if (Number.isInteger(mappedKey) && mappedKey >= 0 && mappedKey <= 5) {
            counts[mappedKey] = Number(value) || 0;
        }
    });
    return counts;
}

function normalizeProgressPayload(progressData) {
    const payload = progressData || {};
    const famCounts = normalizeFamCounts(payload.fam_counts || payload.famCounts || payload.familiarity_counts);
    const fallbackTotal = Object.values(famCounts).reduce((sum, val) => sum + Number(val || 0), 0);
    const totalWords = Number(payload.total_words !== undefined ? payload.total_words : fallbackTotal) || fallbackTotal || 0;
    const completedWords = Number(famCounts[5] || 0);
    const scoreRatio = normalizeScoreValue(payload.score);
    const scorePercent = Math.round(scoreRatio * 100);
    const progressPercent = totalWords > 0 ? Math.round((completedWords / totalWords) * 100) : 0;
    
    // Determine status based on PROGRESS (familiarity counts), not score
    // Level is "completed" if ≥80% of words are at familiarity ≥3 (familiar or better)
    const learnedWords = (
        (famCounts[5] || 0) +  // Memorized
        (famCounts[4] || 0) +  // Strong
        (famCounts[3] || 0)    // Familiar
    );
    const learnedPercent = totalWords > 0 ? (learnedWords / totalWords * 100) : 0;
    const status = payload.status || (learnedPercent >= 80 ? 'completed' : (learnedPercent > 0 ? 'in_progress' : 'not_started'));
    
    return {
        success: payload.success !== false,
        fam_counts: famCounts,
        total_words: totalWords,
        completed_words: completedWords,
        progress_percent: progressPercent,
        score: scoreRatio,
        score_percent: scorePercent,
        score_raw: payload.score !== undefined ? payload.score : scorePercent,
        status,
        completed_at: payload.completed_at || null,
        last_updated: payload.last_updated || null,
        group_id: payload.group_id,
        level_number: payload.level_number
    };
}

function applyCustomLevelProgressData(levelElement, progressData) {
    const normalized = normalizeProgressPayload(progressData);

    if (!levelElement) {
        return normalized;
    }

    try {
        if (levelElement.dataset.famCounts) {
            const existing = JSON.parse(levelElement.dataset.famCounts);
            const existingSum = Object.values(existing).reduce((sum, val) => sum + Number(val || 0), 0);
            const incomingSum = Object.values(normalized.fam_counts).reduce((sum, val) => sum + Number(val || 0), 0);
            if (incomingSum === 0 && existingSum > 0) {
                normalized.fam_counts = existing;
                normalized.total_words = existingSum;
                normalized.completed_words = Number(existing[5] || 0);
                normalized.progress_percent = existingSum > 0 ? Math.round((normalized.completed_words / existingSum) * 100) : 0;
            }
        }
    } catch (_e) { /* ignore */ }

    // Cache normalized data on element for reuse
    try {
        levelElement.dataset.cachedProgressData = JSON.stringify(normalized);
        levelElement.dataset.famCounts = JSON.stringify(normalized.fam_counts);
        levelElement.dataset.scorePercent = String(normalized.score_percent);
        levelElement.dataset.bulkData = JSON.stringify({
            fam_counts: normalized.fam_counts,
            status: normalized.status,
            last_score: normalized.score,
            total_words: normalized.total_words
        });
    } catch (_e) { /* ignore dataset serialization errors */ }

    const wordsText = levelElement.querySelector('.words-text');
    if (wordsText) wordsText.textContent = normalized.total_words;

    const learnedText = levelElement.querySelector('.learned-text');
    if (learnedText) learnedText.textContent = normalized.completed_words;

    const progressFill = levelElement.querySelector('.level-progress-fill');
    // Progress bar: Familiarity 5 / Total words
    if (progressFill) progressFill.style.width = `${normalized.progress_percent}%`;
    
    // Score circle: Score from custom_level_progress.score (0-100)
    // This is the session score stored in the database
    updateCustomLevelCompletionCircle(levelElement, normalized.score_percent);
    
    // Only update familiarity UI if card is flipped (backside visible)
    // This prevents overwriting correct values before user flips the card
    if (levelElement.classList.contains('flipped')) {
        updateFamiliarityUI(levelElement, normalized.fam_counts);
    }

    try {
        levelElement.classList.remove('done', 'gold');
        
        // Calculate Familiarity 5 percentage (unified logic)
        const fam5Percent = getFamiliarity5Percent(normalized);
        
        // Unified color logic based on Familiarity 5:
        // Gold: >90% with Familiarity 5
        // Green: >50% with Familiarity 5
        // Blue/Gray: handled by unlock logic
        if (hasFamiliarity5Above90(normalized)) {
            levelElement.classList.add('gold');
        } else if (hasFamiliarity5Above50(normalized)) {
            levelElement.classList.add('done');
        }
        // If <50%, no color class (stays blue/gray based on unlock status)
    } catch (_e) { /* ignore */ }

    // Remove legacy highlighting classes from buttons to prevent interference
    // Button colors are now controlled by CSS based on level card classes (same as circle)
    try {
        const startBtn = levelElement.querySelector('.level-btn.primary');
        const practiceBtn = levelElement.querySelector('.level-btn:not(.primary)');
        if (startBtn) {
            startBtn.classList.remove('highlighted-blue', 'highlighted-green', 'highlighted-gold', 'highlighted-orange');
            startBtn.dataset.colorSet = 'true'; // Prevent legacy code interference
        }
        if (practiceBtn) {
            practiceBtn.classList.remove('highlighted-blue', 'highlighted-green', 'highlighted-gold', 'highlighted-orange');
            practiceBtn.dataset.colorSet = 'true'; // Prevent legacy code interference
        }
    } catch (_e) { /* ignore */ }

    levelElement.dataset.colorSet = 'true';
    return normalized;
}

function updateCustomLevelCardProgress(groupId, levelNumber, progressData) {
    const levelCard = document.querySelector(`.level-card[data-level="${levelNumber}"][data-custom-group-id="${groupId}"]`);
    const normalized = applyCustomLevelProgressData(levelCard, progressData);
    if (!window.cachedGroupProgress) window.cachedGroupProgress = {};
    try {
        const existing = window.cachedGroupProgress[levelNumber];
        if (existing) {
            const existingTotal = Number(existing.total_words || 0);
            const incomingTotal = Number(normalized.total_words || 0);
            const existingSum = Object.values(existing.fam_counts || {}).reduce((sum, val) => sum + Number(val || 0), 0);
            const incomingSum = Object.values(normalized.fam_counts || {}).reduce((sum, val) => sum + Number(val || 0), 0);
            if ((incomingTotal === 0 && existingTotal > 0) || (incomingSum === 0 && existingSum > 0)) {
                window.cachedGroupProgress[levelNumber] = existing;
                return existing;
            }
        }
    } catch (_e) { /* ignore */ }
    window.cachedGroupProgress[levelNumber] = normalized;
    return normalized;
}

window.updateCustomLevelCardProgress = updateCustomLevelCardProgress;

// Initialize custom level groups (called when library tab is activated)
async function initCustomLevelGroups() {
    try {
        await loadCustomLevelGroups();
        // Don't render here - will be called from library tab
    } catch (error) {
        console.error('Error initializing custom level groups:', error);
    }
}

// Show custom level groups in library section
function showCustomLevelGroupsInLibrary() {
    const libraryContent = document.querySelector('#library-tab .library-content');
    if (!libraryContent) return;
    
    // Check if user is authenticated
    if (!window.authManager || !window.authManager.isAuthenticated()) {
        // Don't show custom groups section for unauthenticated users
        const existingSection = document.getElementById('custom-level-groups-section');
        if (existingSection) {
            existingSection.remove();
        }
        return;
    }
    
    // Check if custom groups section already exists
    let customGroupsSection = document.getElementById('custom-level-groups-section');
    if (!customGroupsSection) {
        // Create custom groups section
        customGroupsSection = document.createElement('div');
        customGroupsSection.id = 'custom-level-groups-section';
        customGroupsSection.className = 'library-section';
        customGroupsSection.innerHTML = `
            <div id="custom-level-groups-container">
                <!-- Custom level groups will be loaded here -->
            </div>
        `;
        
        // Insert after quick actions
        const quickActions = libraryContent.querySelector('.library-quick-actions');
        if (quickActions) {
            quickActions.insertAdjacentElement('afterend', customGroupsSection);
        } else {
            libraryContent.appendChild(customGroupsSection);
        }
    }
    
    // Load and render custom groups
    loadCustomLevelGroups().then(() => {
        renderCustomLevelGroups();
        // Ensure practice buttons are bound after custom groups are rendered
        if (typeof window.bindPracticeActionButtons === 'function') {
            window.bindPracticeActionButtons();
            console.log('✅ Practice buttons bound after showing custom groups');
        }
    });
}

// Load custom level groups from API - optimized with summary endpoint
async function loadCustomLevelGroups() {
    try {
        // Check if user is authenticated first
        if (!window.authManager || !window.authManager.isAuthenticated()) {
            console.log('User not authenticated, skipping custom level groups load');
            customLevelGroups = [];
            return;
        }
        
        const headers = {};
        Object.assign(headers, window.authManager.getAuthHeaders());
        
        // Use optimized summary endpoint for faster loading (only metadata, no full content)
        const startTime = performance.now();
        const response = await fetch('/api/custom-levels/groups/summary', {
            headers: headers
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                console.log('User not authenticated for custom level groups');
                customLevelGroups = [];
                return;
            }
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        const loadTime = performance.now() - startTime;
        
        if (result.success) {
            // Preserve any placeholders that are currently generating
            const existingPlaceholders = customLevelGroups.filter(g => g._isPlaceholder);
            
            // Map summary data to expected format
            const loadedGroups = result.groups.map(group => ({
                id: group.id,
                group_name: group.name,
                context_description: group.context_description || '',
                motivation: group.motivation || '',
                language: group.language,
                native_language: group.native_language,
                cefr_level: group.cefr_level || 'A1',
                level_count: group.level_count,
                total_words: group.total_words,
                completed_levels: group.completed_levels,
                num_levels: group.level_count,
                created_at: new Date().toISOString()
            }));
            
            // Combine: placeholders first, then loaded groups (but exclude placeholders that match loaded groups by ID)
            const placeholderIds = new Set(existingPlaceholders.map(p => p.id).filter(Boolean));
            const loadedGroupIds = new Set(loadedGroups.map(g => g.id));
            
            // Keep placeholders that don't have a matching loaded group yet
            const activePlaceholders = existingPlaceholders.filter(p => {
                const pId = p.id || p._realId;
                return pId && !loadedGroupIds.has(pId);
            });
            
            customLevelGroups = [...activePlaceholders, ...loadedGroups];
            console.log(`✅ Loaded ${loadedGroups.length} custom level groups from summary API in ${loadTime.toFixed(0)}ms (${activePlaceholders.length} active placeholders preserved)`);
        } else {
            console.error('Failed to load custom level groups:', result.error);
            customLevelGroups = [];
        }
    } catch (error) {
        console.error('Error loading custom level groups:', error);
        // Fallback: Try old endpoint if summary endpoint fails
        try {
            const targetLanguage = localStorage.getItem('siluma_target') || 'en';
            const nativeLanguage = localStorage.getItem('siluma_native') || 'de';
            const headers = {};
            Object.assign(headers, window.authManager.getAuthHeaders());
            
            const fallbackResponse = await fetch(`/api/custom-level-groups?language=${targetLanguage}&native_language=${nativeLanguage}`, {
                headers: headers
            });
            
            if (fallbackResponse.ok) {
                const fallbackResult = await fallbackResponse.json();
                if (fallbackResult.success) {
                    customLevelGroups = fallbackResult.groups;
                    console.log(`✅ Loaded ${customLevelGroups.length} custom level groups from fallback API`);
                    return;
                }
            }
        } catch (fallbackError) {
            console.error('Fallback API also failed:', fallbackError);
        }
        
        // Last resort: empty array
        customLevelGroups = [];
    }
}

// Render custom level groups
function renderCustomLevelGroups() {
    console.log('🎨 renderCustomLevelGroups called, groups:', customLevelGroups.length);
    const container = document.getElementById('custom-level-groups-container');
    if (!container) {
        console.error('❌ custom-level-groups-container not found!');
        return;
    }
    
    // Always show "Level Gruppe erstellen" as first option
    const createGroupCardHTML = `
        <div class="level-group-card create-group-card" onclick="showCreateCustomGroupModal()" style="cursor: pointer; border: 2px dashed var(--border); background: var(--surface);">
            <div class="level-group-thumb">
                <div class="level-group-title" style="color: var(--accent); font-weight: 600;">📖 Level Gruppe erstellen</div>
                <div class="level-group-range" style="margin-top: 8px; font-size: 13px; color: var(--text-secondary);">
                    Erstelle eine neue Story mit KI-generierten Lektionen
                </div>
            </div>
            <div class="level-group-meta" style="opacity: 0.6;">
                <div class="level-group-stat">
                    <div class="level-group-stat-value">+</div>
                    <div>Neu</div>
                </div>
            </div>
            <div class="level-group-footer">
                <div class="level-group-action" onclick="event.stopPropagation(); showCreateCustomGroupModal()">
                    <span class="action-icon">✨</span>
                    <span class="action-label">Erstellen</span>
                </div>
            </div>
        </div>
    `;
    
    console.log(`🎨 Rendering ${customLevelGroups.length} custom groups + create card`);
    
    // Filter stories by topic/motivation and CEFR level
    const topicSelect = document.getElementById('topic');
    const cefrSelect = document.getElementById('cefr');
    const selectedTopic = topicSelect ? (topicSelect.value || '').trim() : '';
    const selectedCefr = cefrSelect ? (cefrSelect.value || '').trim() : '';
    
    // Filter groups based on selected filters
    const filteredGroups = customLevelGroups.filter(group => {
        // Filter by motivation/topic if selected
        if (selectedTopic) {
            const groupMotivation = (group.motivation || '').trim();
            if (groupMotivation !== selectedTopic) {
                return false;
            }
        }
        
        // Filter by CEFR level if selected
        if (selectedCefr) {
            const groupCefr = (group.cefr_level || 'A1').trim();
            if (groupCefr !== selectedCefr) {
                return false;
            }
        }
        
        return true;
    });
    
    console.log(`📊 Filtered ${filteredGroups.length} groups from ${customLevelGroups.length} (topic: ${selectedTopic || 'any'}, cefr: ${selectedCefr || 'any'})`);
    
    // Build HTML with filtered stories (no grouping)
    const groupsHTML = filteredGroups.map(group => renderCustomGroupCard(group)).join('');
    
    console.log('📝 First group card HTML length:', groupsHTML.substring(0, 200).length, 'chars');
    
    container.innerHTML = `
        <div class="level-groups-grid">
            ${createGroupCardHTML}
            ${groupsHTML}
        </div>
    `;
    console.log('✅ Custom groups rendered successfully');
    
    // Setup filter listeners after rendering
    setupCustomGroupsFilterListeners();
    
    // Debug: Check the grid element
    const grid = container.querySelector('.level-groups-grid');
    if (grid) {
        const gridRect = grid.getBoundingClientRect();
        const gridStyles = window.getComputedStyle(grid);
        console.log('📊 Grid element check:', {
            display: gridStyles.display,
            gridTemplateColumns: gridStyles.gridTemplateColumns,
            width: gridRect.width,
            height: gridRect.height,
            childCount: grid.children.length
        });
    }
    
    // Debug: Check if container is visible
    const containerStyles = window.getComputedStyle(container);
    console.log('📊 Container visibility check:', {
        display: containerStyles.display,
        visibility: containerStyles.visibility,
        opacity: containerStyles.opacity,
        height: containerStyles.height,
        childElementCount: container.childElementCount
    });
    
    // Debug: Check positioning
    const rect = container.getBoundingClientRect();
    console.log('📐 Container position:', {
        top: rect.top,
        left: rect.left,
        bottom: rect.bottom,
        right: rect.right,
        width: rect.width,
        height: rect.height,
        isInViewport: rect.top >= 0 && rect.bottom <= window.innerHeight
    });
    
    // Debug: Check parent chain
    let parent = container.parentElement;
    let parentChain = [];
    while (parent && parentChain.length < 5) {
        const pRect = parent.getBoundingClientRect();
        const pStyles = window.getComputedStyle(parent);
        parentChain.push({
            tag: parent.tagName,
            id: parent.id,
            class: parent.className,
            display: pStyles.display,
            width: pRect.width,
            height: pRect.height,
            overflow: pStyles.overflow
        });
        parent = parent.parentElement;
    }
    console.log('🔍 Parent chain:', parentChain);
    
    // Force scroll into view if not visible
    if (rect.top < 0 || rect.bottom > window.innerHeight) {
        console.log('⚠️ Container not in viewport, scrolling...');
        setTimeout(() => {
            container.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }, 100);
    }
}

// Render individual custom group card
function renderCustomGroupCard(group) {
    const createdDate = new Date(group.created_at);
    const now = new Date();
    const diffTime = Math.abs(now - createdDate);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    let timeAgo;
    if (diffDays === 1) {
        timeAgo = 'Heute';
    } else if (diffDays === 2) {
        timeAgo = 'Gestern';
    } else if (diffDays <= 7) {
        timeAgo = `vor ${diffDays - 1} Tagen`;
    } else if (diffDays <= 30) {
        const weeks = Math.floor((diffDays - 1) / 7);
        timeAgo = `vor ${weeks} Woche${weeks > 1 ? 'n' : ''}`;
    } else {
        timeAgo = createdDate.toLocaleDateString('de-DE', { 
            day: '2-digit', 
            month: '2-digit', 
            year: '2-digit' 
        });
    }
    
    // Check if this is a placeholder with generation status
    const isPlaceholder = group._isPlaceholder || group.status === 'generating';
    const genStatus = group._generationStatus;
    
    // Show placeholder if it's marked as placeholder, even without status (will show initial state)
    if (isPlaceholder) {
        // Render placeholder with progress
        const progress = Math.round((genStatus?.progress || 0) * 100);
        const stepMessages = {
            'starting': 'Starte Story-Erstellung...',
            'enriching': 'Bereichere Input mit KI...',
            'creating_group': 'Erstelle Story-Gruppe...',
            'topics': 'Generiere Topics...',
            'titles': 'Generiere Titles...',
            'saving': 'Speichere Level...',
            'completed': 'Fertig!',
            'failed': 'Fehler'
        };
        const stepMessage = genStatus?.message || stepMessages[genStatus?.step] || 'Wird erstellt...';
        
        return `
            <div class="level-group-card custom-level-group generating-placeholder" data-group-id="${group.id}" style="opacity: 0.8; cursor: wait;">
                <div class="level-group-thumb">
                    <div class="level-group-title">${escapeHtml(group.group_name)}</div>
                    <div class="level-group-range" style="margin-top: 12px;">
                        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                            <div class="spinner-small" style="width: 16px; height: 16px; border: 2px solid var(--border); border-top: 2px solid var(--accent); border-radius: 50%; animation: spin 1s linear infinite;"></div>
                            <span style="font-size: 13px; color: var(--text-secondary);">${escapeHtml(stepMessage)}</span>
                        </div>
                        <div style="width: 100%; height: 4px; background: var(--surface); border-radius: 2px; overflow: hidden;">
                            <div style="width: ${progress}%; height: 100%; background: var(--accent); transition: width 0.3s ease; border-radius: 2px;"></div>
                        </div>
                        <div style="margin-top: 4px; font-size: 11px; color: var(--text-secondary); text-align: right;">
                            ${progress}%
                        </div>
                    </div>
                </div>
                <div class="level-group-meta" style="opacity: 0.5;">
                    <div class="level-group-stat">
                        <div class="level-group-stat-value">-</div>
                        <div>Wörter</div>
                    </div>
                    <div class="level-group-stat">
                        <div class="level-group-stat-value">-</div>
                        <div>Abgeschlossen</div>
                    </div>
                </div>
                <div class="level-group-footer">
                    <div class="level-group-action" style="opacity: 0.5; cursor: not-allowed;">
                        <span class="action-icon">⏳</span>
                        <span class="action-label">Wird erstellt...</span>
                    </div>
                </div>
            </div>
        `;
    }
    
    // Normal card rendering
    return `
        <div class="level-group-card custom-level-group" data-group-id="${group.id}" onclick="startCustomGroup(${group.id})" style="cursor: pointer;">
            <div class="level-group-thumb">
                <div class="level-group-title">${escapeHtml(group.group_name)}</div>
                <div class="level-group-date">
                    Erstellt ${timeAgo}
                </div>
            </div>
            <div class="level-group-meta">
                <div class="level-group-stat">
                    <div class="level-group-stat-value">${group.total_words || 0}</div>
                    <div>Wörter</div>
                </div>
                <div class="level-group-stat">
                    <div class="level-group-stat-value">${group.completed_levels || 0}</div>
                    <div>Abgeschlossen</div>
                </div>
            </div>
            <div class="level-group-footer">
                <div class="level-group-action" onclick="event.stopPropagation(); startCustomGroup(${group.id})">
                    <span class="action-icon">▶</span>
                    <span class="action-label" data-i18n="buttons.open">Öffnen</span>
                </div>
                ${group.status === 'published' ? `
                    <div class="level-group-action published" onclick="event.stopPropagation(); unpublishCustomGroup(${group.id})" title="Vom Marketplace entfernen">
                        <span class="action-icon">🌐</span>
                        <span class="action-label">Publisht</span>
                    </div>
                ` : ''}
            </div>
        </div>
    `;
}

// Show edit custom group modal
function showEditCustomGroupModal(group) {
    // Remove any existing edit modal first
    const existingModal = document.getElementById('edit-custom-group-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modalHtml = `
        <div class="modal-overlay" id="edit-custom-group-modal">
            <div class="modal-content">
                <div class="modal-header">
                    <h2>📖 Story bearbeiten</h2>
                    <button class="modal-close" onclick="console.log('🔴 Close button clicked'); closeEditModal();">×</button>
                </div>
                <div class="modal-body">
                    <form id="edit-custom-group-form">
                        <div class="form-group">
                            <label for="edit-group-name">
                                <span style="font-weight: 600;">Titel der Story</span>
                            </label>
                            <input type="text" id="edit-group-name" name="group_name" required 
                                   value="${escapeHtml(group.group_name)}"
                                   placeholder="z.B. 'Geschäftsreisen nach London' oder 'Kaffee bestellen in Italien'"
                                   style="margin-top: 8px;">
                        </div>
                        
                        <div class="form-group" style="margin-top: 24px;">
                            <label for="edit-context-description">
                                <span style="font-weight: 600;">Thema & Kontext</span>
                            </label>
                            <textarea id="edit-context-description" name="context_description" required 
                                      rows="5"
                                      placeholder="Beschreibe, worum es in deiner Story gehen soll. Je detaillierter, desto besser!"
                                      style="margin-top: 8px; resize: vertical;">${escapeHtml(group.context_description)}</textarea>
                        </div>
                        
                        <div class="form-group">
                            <label for="edit-cefr-level">CEFR-Level</label>
                            <select id="edit-cefr-level" name="cefr_level">
                                <option value="A1" ${group.cefr_level === 'A1' ? 'selected' : ''}>A1 - Anfänger</option>
                                <option value="A2" ${group.cefr_level === 'A2' ? 'selected' : ''}>A2 - Grundkenntnisse</option>
                                <option value="B1" ${group.cefr_level === 'B1' ? 'selected' : ''}>B1 - Mittelstufe</option>
                                <option value="B2" ${group.cefr_level === 'B2' ? 'selected' : ''}>B2 - Fortgeschritten</option>
                                <option value="C1" ${group.cefr_level === 'C1' ? 'selected' : ''}>C1 - Sehr fortgeschritten</option>
                                <option value="C2" ${group.cefr_level === 'C2' ? 'selected' : ''}>C2 - Muttersprachler</option>
                            </select>
                        </div>
                        
                    </form>
                </div>
                <div class="modal-footer">
                    <div class="modal-footer-actions">
                        <button type="button" class="btn btn-danger" onclick="deleteCustomGroupFromModal(${group.id})" title="Story löschen">
                            🗑️ Löschen
                        </button>
                        ${group.status === 'published' ? `
                            <button type="button" class="btn btn-warning" onclick="unpublishCustomGroup(${group.id})" title="Story vom Marketplace entfernen">
                                🌐 Unpublishen
                            </button>
                        ` : `
                            <button type="button" class="btn btn-warning" onclick="publishCustomGroup(${group.id})" title="Story publishen">
                                🌐 Publishen
                            </button>
                        `}
                    </div>
                    <div class="modal-footer-controls">
                        <button type="button" class="btn btn-secondary" onclick="console.log('🔴 Cancel button clicked'); closeEditModal();">
                            Abbrechen
                        </button>
                        <button type="button" class="btn btn-primary" onclick="updateCustomGroup(${group.id})">
                            Speichern
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    console.log('📝 Edit modal created and added to DOM');
    
    // Add event listeners for modal closing
    const modal = document.getElementById('edit-custom-group-modal');
    console.log('🔍 Modal element found:', modal);
    if (modal) {
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeEditModal();
            }
        });
        
        // Close on ESC key
        const handleEscKey = (e) => {
            if (e.key === 'Escape') {
                closeEditModal();
                document.removeEventListener('keydown', handleEscKey);
            }
        };
        document.addEventListener('keydown', handleEscKey);
    }
    
    // Focus on first input
    setTimeout(() => {
        const firstInput = document.getElementById('edit-group-name');
        if (firstInput) firstInput.focus();
    }, 100);
}

// Show create custom group modal
async function showCreateCustomGroupModal() {
    // Check if modal already exists
    const existingModal = document.getElementById('create-custom-group-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modal = document.createElement('div');
    modal.id = 'create-custom-group-modal';
    modal.className = 'modal-overlay';
    modal.innerHTML = `
        <div class="modal-content create-custom-group-modal" style="max-width: 600px;">
            <div class="modal-header">
                <h2>📖 Neue Story erstellen</h2>
                <button class="btn-close" onclick="closeModal(this)">×</button>
            </div>
            <div class="modal-body">
                <div class="story-creation-intro" style="margin-bottom: 24px; padding: 16px; background: var(--surface); border-radius: 8px; border-left: 3px solid var(--accent);">
                    <p style="margin: 0; font-size: 14px; color: var(--text-secondary); line-height: 1.6;">
                        <strong>Was ist eine Story?</strong><br>
                        Eine Story ist eine Sammlung von Lektionen zu einem bestimmten Thema. Die KI erstellt automatisch passende Sätze und Wörter basierend auf deinem Thema.
                    </p>
                </div>
                <form id="create-custom-group-form">
                    <div class="form-group">
                        <label for="group-name">
                            <span style="font-weight: 600;">Titel der Story</span>
                            <span style="color: var(--text-secondary); font-size: 13px; font-weight: normal; display: block; margin-top: 4px;">
                                Gib deiner Story einen aussagekräftigen Namen
                            </span>
                        </label>
                        <input type="text" id="group-name" name="group_name" required 
                               placeholder="z.B. 'Geschäftsreisen nach London' oder 'Kaffee bestellen in Italien'"
                               style="margin-top: 8px;">
                    </div>
                    
                    <div class="form-group" style="margin-top: 24px;">
                        <label for="context-description">
                            <span style="font-weight: 600;">Thema & Kontext</span>
                            <span style="color: var(--text-secondary); font-size: 13px; font-weight: normal; display: block; margin-top: 4px;">
                                Beschreibe, worum es in deiner Story gehen soll. Je detaillierter, desto besser!
                            </span>
                        </label>
                        <textarea id="context-description" name="context_description" required 
                                  rows="5"
                                  placeholder="Beispiel: 'Ich möchte eine Story über Geschäftsmeetings auf Englisch lernen. Die Story soll Situationen wie Vorstellungsrunden, Präsentationen und Verhandlungen abdecken. Der Fokus liegt auf professioneller Kommunikation und Business-Vokabular.'"
                                  style="margin-top: 8px; resize: vertical;"></textarea>
                        <div style="margin-top: 8px; font-size: 12px; color: var(--text-secondary);">
                            💡 <strong>Tipp:</strong> Erzähle eine kleine Geschichte oder beschreibe konkrete Situationen, die du lernen möchtest.
                        </div>
                    </div>
                    
                    <div class="form-group" style="margin-top: 24px; padding: 16px; background: var(--surface); border-radius: 8px; border: 1px solid var(--border);">
                        <label style="display: flex; align-items: center; gap: 12px; cursor: pointer; margin: 0;">
                            <input type="checkbox" id="publish-immediately" name="publish_immediately" checked style="width: 18px; height: 18px; cursor: pointer; accent-color: var(--accent);">
                            <div style="flex: 1;">
                                <span style="font-weight: 600; display: block; margin-bottom: 4px;">🌐 Sofort publishen</span>
                                <span style="font-size: 13px; color: var(--text-secondary);">
                                    Deine Story wird direkt nach der Erstellung im Marketplace verfügbar sein
                                </span>
                            </div>
                        </label>
                    </div>
                    
                </form>
            </div>
            <div class="modal-footer" style="display: flex; justify-content: flex-end; gap: 12px; padding-top: 20px; border-top: 1px solid var(--border);">
                <button class="btn btn-secondary" onclick="closeModal(this)">Abbrechen</button>
                <button class="btn btn-primary" onclick="createCustomGroup()" id="create-group-btn" style="min-width: 160px;">
                    ✨ Story erstellen
                </button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Load current settings from localStorage and user preferences for use in createCustomGroup
    await loadCurrentSettings();
}

// Load current settings from localStorage and user preferences for use in createCustomGroup
async function loadCurrentSettings() {
    try {
        // Get current settings from localStorage
        const targetLanguage = localStorage.getItem('siluma_target') || 'en';
        let nativeLanguage = localStorage.getItem('siluma_native') || 'de';
        
        // For authenticated users, try to get native language from user settings
        if (window.authManager && window.authManager.isAuthenticated()) {
            try {
                const headers = window.authManager.getAuthHeaders();
                const response = await fetch('/api/user/settings', { headers });
                if (response.ok) {
                    const result = await response.json();
                    if (result.success && result.settings && result.settings.native_language) {
                        nativeLanguage = result.settings.native_language;
                        console.log('🔧 Using native language from user settings:', nativeLanguage);
                    }
                }
            } catch (error) {
                console.log('Could not load user settings, using localStorage fallback:', error);
            }
        }
        
        // Update global variables for use in createCustomGroup
        currentLanguage = targetLanguage;
        currentNativeLanguage = nativeLanguage;
        
        console.log('🔧 Loaded settings - Target:', currentLanguage, 'Native:', currentNativeLanguage);
        
    } catch (error) {
        console.error('Error loading current settings:', error);
        // Fallback to localStorage values
        currentLanguage = localStorage.getItem('siluma_target') || 'en';
        currentNativeLanguage = localStorage.getItem('siluma_native') || 'de';
    }
}

// Update custom group
async function updateCustomGroup(groupId) {
    try {
        console.log('💾 Updating custom group:', groupId);
        
        const form = document.getElementById('edit-custom-group-form');
        if (!form) {
            showNotification('Formular nicht gefunden.', 'error');
            return;
        }
        
        const formData = new FormData(form);
        const groupName = formData.get('group_name');
        const contextDescription = formData.get('context_description');
        const cefrLevel = formData.get('cefr_level');
        
        // Validate
        if (!groupName || !contextDescription) {
            showNotification('Bitte fülle alle Pflichtfelder aus.', 'error');
            return;
        }
        
        // Show loading state
        if (window.showLoader) {
            window.showLoader();
        }
        
        // Prepare update data
        const updateData = {
            group_name: groupName,
            context_description: contextDescription,
            cefr_level: cefrLevel
        };
        
        // Call API
        const response = await fetch(`/api/custom-level-groups/${groupId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            },
            body: JSON.stringify(updateData)
        });
        
        if (!response.ok) {
            throw new Error('Failed to update group');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to update group');
        }
        
        // Update local data
        const groupIndex = customLevelGroups.findIndex(g => g.id === groupId);
        if (groupIndex !== -1) {
            customLevelGroups[groupIndex] = {
                ...customLevelGroups[groupIndex],
                ...updateData,
                updated_at: new Date().toISOString()
            };
        }
        
        // Close modal
        closeEditModal();
        
        // If we're currently viewing this group, refresh it
        if (window.currentCustomGroup && window.currentCustomGroup.id === groupId) {
            await refreshCurrentGroup(groupId);
        }
        
        // Reload custom level groups to get updated data
        await loadCustomLevelGroups();
        
        // Refresh the display
        await showCustomLevelGroupsInLibrary();
        
        // Also refresh if we're on the library tab
        const libraryTab = document.getElementById('library-tab');
        if (libraryTab && libraryTab.classList.contains('active')) {
            renderCustomLevelGroups();
        }
        
        showNotification('Story erfolgreich aktualisiert!', 'success');
        
    } catch (error) {
        console.error('❌ Error updating custom group:', error);
        showNotification('Fehler beim Aktualisieren der Story: ' + error.message, 'error');
    } finally {
        // Hide loading state
        if (window.hideLoader) {
            window.hideLoader();
        }
    }
}

// Create custom group
async function createCustomGroup() {
    const form = document.getElementById('create-custom-group-form');
    const formData = new FormData(form);
    
    // Use the group name as provided by the user
    const groupName = formData.get('group_name');
    
    // Get topic from the dropdown (motivation)
    const topicSelect = document.getElementById('topic');
    const motivation = topicSelect ? (topicSelect.value || '').trim() : '';
    
    const data = {
        group_name: groupName,
        context_description: formData.get('context_description'),
        motivation: motivation,
        language: currentLanguage,
        native_language: currentNativeLanguage,
        cefr_level: localStorage.getItem('siluma_cefr_' + currentLanguage) || 'A1',
        num_levels: 10
    };
    
    // Validate
    if (!groupName || !data.context_description) {
        showNotification('Bitte fülle alle Pflichtfelder aus.', 'error');
        return;
    }
    
    const createBtn = document.getElementById('create-group-btn');
    const originalText = createBtn.textContent;
    createBtn.textContent = 'Erstelle...';
    createBtn.disabled = true;
    
    // Close modal immediately and show placeholder card
    closeModal(createBtn.closest('.modal-overlay'));
    
    // Create placeholder card immediately
    const placeholderId = `placeholder-${Date.now()}`;
    const placeholderGroup = {
        id: placeholderId,
        group_name: groupName,
        context_description: data.context_description,
        motivation: data.motivation || '',
        level_count: 0,
        total_words: 0,
        completed_levels: 0,
        status: 'generating',
        _isPlaceholder: true,
        _generationStatus: {
            status: 'generating',
            step: 'starting',
            progress: 0.0,
            message: 'Starte Story-Erstellung...'
        }
    };
    
    // Add placeholder to the beginning of the list
    customLevelGroups.unshift(placeholderGroup);
    
    // Render immediately with placeholder
    renderCustomLevelGroups();
    
    // Navigate to library tab to show placeholder
    if (window.showTab) {
        window.showTab('library');
    }
    
    // Start polling for status updates
    let statusPollInterval = null;
    let groupId = null;
    
    try {
        const headers = {
            'Content-Type': 'application/json'
        };
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        let response;
        try {
            response = await fetch('/api/custom-level-groups/create', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(data)
            });
        } catch (fetchError) {
            // Handle network errors (fetch completely failed)
            console.error('Fetch error:', fetchError);
            throw new Error('Netzwerkfehler: Bitte überprüfe deine Internetverbindung und versuche es erneut.');
        }
        
        // Check if response is ok before parsing JSON
        if (!response.ok) {
            let errorMessage = `HTTP error! status: ${response.status}`;
            try {
                const errorData = await response.json();
                errorMessage = errorData.error || errorMessage;
            } catch (e) {
                // If response is not JSON, use status text
                errorMessage = response.statusText || errorMessage;
            }
            throw new Error(errorMessage);
        }
        
        let result;
        try {
            result = await response.json();
        } catch (jsonError) {
            console.error('JSON parse error:', jsonError);
            throw new Error('Ungültige Antwort vom Server. Bitte versuche es erneut.');
        }
        
        if (result.success) {
            groupId = result.group_id || result.id;
            
            // Update placeholder with real group_id
            const placeholderIndex = customLevelGroups.findIndex(g => g.id === placeholderId);
            if (placeholderIndex !== -1) {
                customLevelGroups[placeholderIndex].id = groupId;
                customLevelGroups[placeholderIndex]._realId = groupId;
            }
            
            // Start polling for generation status
            statusPollInterval = startStatusPolling(groupId, placeholderId);
            
            const publishImmediately = formData.get('publish_immediately') === 'on';
            
            // Store publish flag for later (after generation completes)
            if (publishImmediately && groupId) {
                const placeholderIndex = customLevelGroups.findIndex(g => g.id === groupId || g._realId === groupId);
                if (placeholderIndex !== -1) {
                    customLevelGroups[placeholderIndex]._publishAfterGeneration = true;
                }
            }
            
            // Note: Publishing will happen after generation completes via status polling
            // The status polling will handle completion and publishing
            // Status polling will handle completion
            // Don't reload here - let polling handle it
        } else {
            // Stop polling if it was started
            if (statusPollInterval) {
                clearInterval(statusPollInterval);
            }
            
            // Remove placeholder on error
            const placeholderIndex = customLevelGroups.findIndex(g => g.id === placeholderId || g._isPlaceholder);
            if (placeholderIndex !== -1) {
                customLevelGroups.splice(placeholderIndex, 1);
                renderCustomLevelGroups();
            }
            
            let errorMessage = result.error || 'Fehler beim Erstellen der Story';
            
            // Handle specific error cases
            if (errorMessage.includes('UNIQUE constraint') || errorMessage.includes('already exists')) {
                errorMessage = 'Eine Story mit diesem Namen existiert bereits in dieser Sprache. Bitte wähle einen anderen Namen.';
            }
            
            showNotification(errorMessage, 'error');
        }
    } catch (error) {
        console.error('Error creating custom group:', error);
        
        // Stop polling if it was started
        if (statusPollInterval) {
            clearInterval(statusPollInterval);
        }
        
        // Remove placeholder on error
        const placeholderIndex = customLevelGroups.findIndex(g => g.id === placeholderId || g._isPlaceholder);
        if (placeholderIndex !== -1) {
            customLevelGroups.splice(placeholderIndex, 1);
            renderCustomLevelGroups();
        }
        
        // Provide more specific error message
        let errorMessage = 'Fehler beim Erstellen der Level-Gruppe';
        if (error.message) {
            if (error.message.includes('Failed to fetch') || error.message.includes('Load failed')) {
                errorMessage = 'Netzwerkfehler: Bitte überprüfe deine Internetverbindung und versuche es erneut.';
            } else if (error.message.includes('HTTP error')) {
                errorMessage = `Serverfehler: ${error.message}`;
            } else {
                errorMessage = error.message;
            }
        }
        
        showNotification(errorMessage, 'error');
    } finally {
        createBtn.textContent = originalText;
        createBtn.disabled = false;
    }
}

// Start polling for generation status
function startStatusPolling(groupId, placeholderId) {
    console.log('🔄 Starting status polling for group:', groupId, 'placeholder:', placeholderId);
    let pollCount = 0;
    const maxPolls = 120; // Max 2 minutes (120 * 1 second)
    
    // Start polling immediately (don't wait 1 second for first poll)
    const pollOnce = async () => {
        pollCount++;
        
        try {
            const headers = {};
            if (window.authManager && window.authManager.isAuthenticated()) {
                Object.assign(headers, window.authManager.getAuthHeaders());
            }
            
            const response = await fetch(`/api/custom-level-groups/${groupId}/generation-status`, { headers });
            
            if (!response.ok) {
                if (pollCount >= maxPolls) {
                    clearInterval(pollInterval);
                    handleGenerationComplete(groupId, placeholderId, false, 'Timeout beim Abrufen des Status');
                }
                return;
            }
            
            let statusData;
            try {
                statusData = await response.json();
            } catch (e) {
                console.error('Error parsing status response:', e);
                if (pollCount >= maxPolls) {
                    clearInterval(pollInterval);
                    handleGenerationComplete(groupId, placeholderId, false, 'Fehler beim Abrufen des Status');
                }
                return;
            }
            
            if (statusData.success) {
                const status = statusData.status;
                const step = statusData.step || '';
                const progress = statusData.progress || 0;
                const message = statusData.message || '';
                const error = statusData.error;
                
                // Update placeholder card with status
                updatePlaceholderStatus(groupId, placeholderId, {
                    status,
                    step,
                    progress,
                    message,
                    error
                });
                
                if (status === 'completed') {
                    clearInterval(pollInterval);
                    await handleGenerationComplete(groupId, placeholderId, true);
                } else if (status === 'failed') {
                    clearInterval(pollInterval);
                    await handleGenerationComplete(groupId, placeholderId, false, error || message);
                }
            } else {
                // If status endpoint fails, check if group exists (might be completed)
                if (pollCount > 5) {
                    // After 5 polls, check if group exists
                    const groupExists = await checkGroupExists(groupId);
                    if (groupExists) {
                        clearInterval(pollInterval);
                        await handleGenerationComplete(groupId, placeholderId, true);
                    }
                }
            }
        } catch (error) {
            console.error('Error polling generation status:', error);
            // Only fail after max polls to allow for temporary network issues
            if (pollCount >= maxPolls) {
                clearInterval(pollInterval);
                let errorMsg = 'Fehler beim Abrufen des Status';
                if (error.message && error.message.includes('Failed to fetch')) {
                    errorMsg = 'Netzwerkfehler beim Abrufen des Status. Die Story wird möglicherweise trotzdem erstellt.';
                }
                handleGenerationComplete(groupId, placeholderId, false, errorMsg);
            }
        }
        
        if (pollCount >= maxPolls) {
            clearInterval(pollInterval);
            handleGenerationComplete(groupId, placeholderId, false, 'Timeout beim Abrufen des Status');
        }
    };
    
    // Poll immediately, then every second
    pollOnce();
    const pollInterval = setInterval(pollOnce, 1000);
    
    return pollInterval;
}

// Update placeholder card with status
function updatePlaceholderStatus(groupId, placeholderId, statusData) {
    const placeholderIndex = customLevelGroups.findIndex(g => 
        g.id === groupId || g.id === placeholderId || g._realId === groupId || (g._isPlaceholder && (g.id === placeholderId || g._realId === groupId))
    );
    
    if (placeholderIndex !== -1) {
        const placeholder = customLevelGroups[placeholderIndex];
        placeholder._generationStatus = statusData;
        
        // Ensure placeholder is still marked
        placeholder._isPlaceholder = true;
        placeholder.status = 'generating';
        
        // Re-render to show updated status
        renderCustomLevelGroups();
    } else {
        console.warn('⚠️ Placeholder not found for status update:', { groupId, placeholderId, customLevelGroupsLength: customLevelGroups.length });
    }
}

// Handle generation completion
async function handleGenerationComplete(groupId, placeholderId, success, errorMessage = null) {
    const placeholderIndex = customLevelGroups.findIndex(g => 
        g.id === groupId || g.id === placeholderId || g._realId === groupId || g._isPlaceholder
    );
    
    if (placeholderIndex !== -1) {
        const placeholder = customLevelGroups[placeholderIndex];
        const shouldPublish = placeholder._publishAfterGeneration;
        
        if (success) {
            // Reload groups to get real data
            await loadCustomLevelGroups();
            
            // If publish was requested, do it now
            if (shouldPublish && groupId) {
                try {
                    const publishHeaders = {
                        'Content-Type': 'application/json'
                    };
                    if (window.authManager && window.authManager.isAuthenticated()) {
                        Object.assign(publishHeaders, window.authManager.getAuthHeaders());
                    }
                    
                    const publishResponse = await fetch(`/api/custom-level-groups/${groupId}/publish`, {
                        method: 'POST',
                        headers: publishHeaders
                    });
                    
                    const publishResult = await publishResponse.json();
                    if (publishResult.success) {
                        showNotification('Story erfolgreich erstellt und publisht! Sie ist jetzt im Marketplace verfügbar.', 'success');
                    } else {
                        showNotification('Story erfolgreich erstellt, aber Fehler beim Publishen: ' + (publishResult.error || 'Unbekannter Fehler'), 'warning');
                    }
                } catch (publishError) {
                    console.error('❌ Error publishing story after creation:', publishError);
                    showNotification('Story erfolgreich erstellt, aber Fehler beim Publishen: ' + publishError.message, 'warning');
                }
            } else {
                showNotification('Story erfolgreich erstellt!', 'success');
            }
            
            // Refresh display
            if (typeof window.showCustomLevelGroupsInLibrary === 'function') {
                await window.showCustomLevelGroupsInLibrary();
            }
            
            renderCustomLevelGroups();
        } else {
            // Remove placeholder on error
            customLevelGroups.splice(placeholderIndex, 1);
            renderCustomLevelGroups();
            showNotification(errorMessage || 'Fehler bei der Story-Generierung', 'error');
        }
    }
}

// Check if group exists (fallback for status polling)
async function checkGroupExists(groupId) {
    try {
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        const response = await fetch(`/api/custom-level-groups/${groupId}`, { headers });
        return response.ok;
    } catch (error) {
        return false;
    }
}

// Publish custom group
async function publishCustomGroup(groupId) {
    try {
        console.log('🌐 Publishing custom group:', groupId);
        
        // Get current group data
        const group = customLevelGroups.find(g => g.id === groupId);
        if (!group) {
            showNotification('Story nicht gefunden.', 'error');
            return;
        }
        
        // Show confirmation dialog
        const confirmed = confirm(
            `Möchtest du die Level-Gruppe "${group.group_name}" wirklich publishen?\n\n` +
            `Diese Gruppe wird dann für alle Nutzer im Marketplace verfügbar sein. ` +
            `Du kannst sie jederzeit wieder unpublishen.`
        );
        
        if (!confirmed) {
            return;
        }
        
        // Show loading state
        if (window.showLoader) {
            window.showLoader();
        }
        
        // Call API to publish group
        const response = await fetch(`/api/custom-level-groups/${groupId}/publish`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to publish group');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to publish group');
        }
        
        // Update local data
        const groupIndex = customLevelGroups.findIndex(g => g.id === groupId);
        if (groupIndex !== -1) {
            customLevelGroups[groupIndex] = {
                ...customLevelGroups[groupIndex],
                status: 'published',
                published_at: new Date().toISOString()
            };
        }
        
        // Close modal
        closeEditModal();
        
        // Reload custom level groups to get updated data
        await loadCustomLevelGroups();
        
        // Refresh the display
        await showCustomLevelGroupsInLibrary();
        
        // Also refresh if we're on the library tab
        const libraryTab = document.getElementById('library-tab');
        if (libraryTab && libraryTab.classList.contains('active')) {
            renderCustomLevelGroups();
        }
        
        showNotification('Story erfolgreich publisht! Sie ist jetzt im Marketplace verfügbar.', 'success');
        
    } catch (error) {
        console.error('❌ Error publishing custom group:', error);
        showNotification('Fehler beim Publishen der Story: ' + error.message, 'error');
    } finally {
        // Hide loading state
        if (window.hideLoader) {
            window.hideLoader();
        }
    }
}

// Unpublish custom group
async function unpublishCustomGroup(groupId) {
    try {
        console.log('🔒 Unpublishing custom group:', groupId);
        
        // Get current group data
        const group = customLevelGroups.find(g => g.id === groupId);
        if (!group) {
            showNotification('Story nicht gefunden.', 'error');
            return;
        }
        
        // Show confirmation dialog
        const confirmed = confirm(
            `Möchtest du die Story "${group.group_name}" wirklich unpublishen?\n\n` +
            `Diese Story wird dann nicht mehr im Marketplace verfügbar sein. ` +
            `Du kannst sie jederzeit wieder publishen.`
        );
        
        if (!confirmed) {
            return;
        }
        
        // Show loading state
        if (window.showLoader) {
            window.showLoader();
        }
        
        // Call API to unpublish group
        const response = await fetch(`/api/custom-level-groups/${groupId}/unpublish`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to unpublish group');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to unpublish group');
        }
        
        // Update local data
        const groupIndex = customLevelGroups.findIndex(g => g.id === groupId);
        if (groupIndex !== -1) {
            customLevelGroups[groupIndex] = {
                ...customLevelGroups[groupIndex],
                status: 'active',
                published_at: null
            };
        }
        
        // Close modal if open
        closeEditModal();
        
        // Reload custom level groups to get updated data
        await loadCustomLevelGroups();
        
        // Refresh the display
        await showCustomLevelGroupsInLibrary();
        
        // Also refresh if we're on the library tab
        const libraryTab = document.getElementById('library-tab');
        if (libraryTab && libraryTab.classList.contains('active')) {
            renderCustomLevelGroups();
        }
        
        showNotification('Story erfolgreich unpublisht! Sie ist nicht mehr im Marketplace verfügbar.', 'success');
        
    } catch (error) {
        console.error('❌ Error unpublishing custom group:', error);
        showNotification('Fehler beim Unpublishen der Story: ' + error.message, 'error');
    } finally {
        // Hide loading state
        if (window.hideLoader) {
            window.hideLoader();
        }
    }
}

// Edit custom group
async function editCustomGroup(groupId) {
    try {
        console.log('✏️ Editing custom group:', groupId);
        
        // Get current group data
        const group = customLevelGroups.find(g => g.id === groupId);
        if (!group) {
            showNotification('Gruppe nicht gefunden.', 'error');
            return;
        }
        
        // Show edit modal
        showEditCustomGroupModal(group);
        
    } catch (error) {
        console.error('❌ Error editing custom group:', error);
        showNotification('Fehler beim Laden der Gruppe: ' + error.message, 'error');
    }
}

// Close edit modal
function closeEditModal() {
    console.log('🔒 Closing edit modal...');
    const modal = document.getElementById('edit-custom-group-modal');
    if (modal) {
        console.log('✅ Modal found, removing...');
        modal.remove();
    } else {
        console.log('❌ Modal not found');
        // Fallback: remove all modals
        const allModals = document.querySelectorAll('.modal-overlay');
        allModals.forEach(modal => modal.remove());
    }
}

// Delete custom group from modal
async function deleteCustomGroupFromModal(groupId) {
    // Close the modal first
    closeEditModal();
    
    // Then delete the group
    await deleteCustomGroup(groupId);
}

// Delete custom group
async function deleteCustomGroup(groupId) {
    const group = customLevelGroups.find(g => g.id === groupId);
    if (!group) return;
    
    if (!confirm(`Möchtest du die Story "${group.group_name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`)) {
        return;
    }
    
    try {
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        const response = await fetch(`/api/custom-level-groups/${groupId}`, {
            method: 'DELETE',
            headers: headers
        });
        
        const result = await response.json();
        
        if (result.success) {
            showNotification('Story wurde gelöscht.', 'success');
            
            // Immediately reload custom level groups and refresh overview
            console.log('🔄 Reloading custom level groups after deletion...');
            
            // Hide any modals that might be open
            const modals = document.querySelectorAll('.modal-overlay');
            modals.forEach(modal => {
                if (modal.style.display !== 'none') {
                    modal.style.display = 'none';
                }
            });
            
            // Force reload of custom level groups data immediately
            await loadCustomLevelGroups();
            
            // Refresh the library section to show updated data
            if (typeof window.showCustomLevelGroupsInLibrary === 'function') {
                await window.showCustomLevelGroupsInLibrary();
            }
            
            // Also refresh if we're on the library tab
            const libraryTab = document.getElementById('library-tab');
            if (libraryTab && libraryTab.classList.contains('active')) {
                renderCustomLevelGroups();
            }
            
            // Navigate to library tab if not already there to show updated overview
            if (window.showTab) {
                window.showTab('library');
            }
            
            // Additional refresh operations after navigation
            setTimeout(() => {
                // Force refresh of header stats to update word counts
                if (window.headerStats && window.headerStats.refresh) {
                    window.headerStats.refresh();
                }
                
                // Clear any cached data that might show the deleted group
                if (typeof window.clearLevelCache === 'function') {
                    window.clearLevelCache();
                }
                
                // Force a complete re-render of the levels tab
                const levelsHost = document.getElementById('levels');
                if (levelsHost) {
                    // Trigger a custom event to force re-render
                    levelsHost.dispatchEvent(new CustomEvent('forceRefresh'));
                }
                
                console.log('✅ Homepage and library completely refreshed after group deletion');
            }, 100);
        } else {
            showNotification(result.error || 'Fehler beim Löschen der Level-Gruppe', 'error');
        }
    } catch (error) {
        console.error('Error deleting custom group:', error);
        showNotification('Fehler beim Löschen der Level-Gruppe', 'error');
    }
}

// Start custom group
async function startCustomGroup(groupId) {
    try {
        console.log('🎯 Starting custom group:', groupId);
        const startTime = performance.now();
        
        // Show loading state
        if (window.showLoader) {
            window.showLoader();
        }
        
        const headers = {
            'Authorization': `Bearer ${localStorage.getItem('session_token')}`
        };
        
        // OPTIMIZATION: Load group data and bulk-stats in parallel
        console.log('⚡ Loading group data and bulk-stats in parallel...');
        const [groupResponse, bulkStatsResponse] = await Promise.all([
            fetch(`/api/custom-level-groups/${groupId}`, { headers }),
            fetch(`/api/custom-levels/${groupId}/bulk-stats`, { headers }).catch(() => null) // Don't fail if bulk-stats fails
        ]);
        
        if (!groupResponse.ok) {
            throw new Error('Failed to load custom level group');
        }
        
        const data = await groupResponse.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to load custom level group');
        }
        
        const group = data.group;
        const levels = data.levels;
        
        // Process bulk-stats if available
        if (bulkStatsResponse && bulkStatsResponse.ok) {
            try {
                const bulkData = await bulkStatsResponse.json();
                if (bulkData.success && bulkData.levels) {
                    // Cache bulk stats for immediate use
                    window.cachedGroupProgress = bulkData.levels;
                    console.log('✅ Bulk stats loaded and cached');
                }
            } catch (e) {
                console.log('⚠️ Could not process bulk-stats:', e);
            }
        }
        
        const loadTime = performance.now() - startTime;
        console.log(`📚 Custom group loaded in ${loadTime.toFixed(0)}ms:`, group);
        console.log('📖 Levels found:', levels.length);
        console.log('⚡ Ultra-lazy loading: Levels loaded without content (content loaded on-demand)');
        
        // OPTIMIZATION: Don't block on content generation - show UI immediately
        // Content will be generated on-demand when level is opened
        const levelsNeedingGeneration = levels.filter(level => {
            return !level.content || level.content === null;
        });
        
        // Start content generation in background (non-blocking)
        if (levelsNeedingGeneration.length > 0) {
            console.log(`🚀 ${levelsNeedingGeneration.length} levels need generation - starting in background`);
            
            // Determine which levels to generate (non-blocking)
            determineLevelsToGenerate(groupId, levels, levelsNeedingGeneration).then(levelsToGenerate => {
                if (levelsToGenerate.immediate.length > 0) {
                    // Generate in background without blocking UI
                    generateSpecificCustomLevelsContent(groupId, levelsToGenerate.immediate).catch(err => {
                        console.error('Background generation error:', err);
                    });
                }
            }).catch(err => {
                console.error('Error determining levels to generate:', err);
            });
        }
        
        // Store custom group context for level rendering
        window.currentCustomGroup = {
            id: groupId,
            group: group,
            levels: levels
        };
        
        // Switch to levels tab IMMEDIATELY (don't wait for content generation)
        if (window.showTab) {
            window.showTab('levels');
        }
        
        // Setup edit button immediately after setting currentCustomGroup
        setTimeout(() => {
            if (typeof setupGroupEditButton === 'function') {
                setupGroupEditButton(groupId);
            }
        }, 50);
        
        // Use the same system as standard level groups
        if (window.SELECTED_LEVEL_GROUP !== undefined) {
            window.SELECTED_LEVEL_GROUP = {
                id: `custom-${groupId}`,
                name: group.group_name,
                start: 1,
                end: levels.length,
                total: levels.length,
                completed: 0,
                isCustom: true,
                customGroupId: groupId,
                customLevels: levels
            };
        }
        
        // Show levels container immediately
        showLevelsContainer();
        
        // Load cached progress data (already loaded from bulk-stats if available)
        if (!window.cachedGroupProgress || Object.keys(window.cachedGroupProgress).length === 0) {
            await loadCachedGroupProgress(groupId);
        }
        
        // Render custom levels immediately (don't wait for content generation)
        console.log('🎨 Rendering levels immediately...');
        renderCustomLevels(groupId, levels);
        
        // Apply basic progression immediately (fast path)
        applyBasicCustomLevelProgression(groupId, levels);
        
        // Preload familiarity data with loading screen integration
        if (window.authManager && window.authManager.isAuthenticated()) {
            if (window.showLoader) {
                window.showLoader(window.t ? window.t('ui.loading_familiarity', 'Lade Fortschrittsdaten...') : 'Lade Fortschrittsdaten...');
            }
            
            await preloadFamiliarityDataForAllLevels(groupId, levels, (current, total) => {
                if (window.showLoader) {
                    const progressText = window.t 
                        ? window.t('ui.loading_familiarity_progress', 'Lade Fortschrittsdaten... {current}/{total}')
                        : `Lade Fortschrittsdaten... ${current}/${total}`;
                    window.showLoader(progressText.replace('{current}', current).replace('{total}', total));
                }
            });
            
            // Update frontside of all cards with preloaded data (same logic as backside)
            updateFrontsideWithPreloadedData(groupId, levels);
            
            // Re-apply progression after preloading to unlock levels based on scores
            const levelsContainer = document.getElementById('levels-container') || document.getElementById('levels');
            if (levelsContainer) {
                console.log('🔄 Re-applying progression after preloading familiarity data');
                await applyCustomLevelProgressionBulk(levelsContainer, groupId);
            }
        }
        
        const totalTime = performance.now() - startTime;
        console.log(`✅ Group opened in ${totalTime.toFixed(0)}ms`);
        
    } catch (error) {
        console.error('❌ Error starting custom group:', error);
        showNotification('Fehler beim Laden der Custom-Gruppe: ' + error.message, 'error');
        
        // Fallback to standard levels
        if (window.showTab) {
            window.showTab('levels');
        }
        if (window.renderLevels) {
            window.renderLevels();
        }
    } finally {
        // Hide loading state
        if (window.hideLoader) {
            window.hideLoader();
        }
    }
}

// Generate content for all custom levels that need it
async function generateSpecificCustomLevelsContent(groupId, levelsNeedingGeneration) {
    try {
        console.log(`🚀 Starting specific content generation for ${levelsNeedingGeneration.length} levels`);
        
        // Extract level numbers
        const levelNumbers = levelsNeedingGeneration.map(level => level.level_number);
        
        // Use the new specific API endpoint for immediate generation
        const response = await fetch(`/api/custom-levels/${groupId}/generate-specific-content`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            },
            body: JSON.stringify({
                level_numbers: levelNumbers
            })
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                console.log(`🎉 Specific content generation complete: ${data.successful} successful, ${data.failed} failed`);
                
                if (data.failed > 0) {
                    const failedLevels = data.results.filter(r => !r.success).map(r => r.level_number);
                    console.warn(`⚠️ Failed to generate content for levels: ${failedLevels.join(', ')}`);
                }
                
                return { 
                    successful: data.successful, 
                    failed: data.failed, 
                    results: data.results 
                };
            } else {
                console.error(`❌ Specific generation failed:`, data.error);
                return { successful: 0, failed: levelsNeedingGeneration.length, results: [] };
            }
        } else {
            console.error(`❌ Specific generation request failed: ${response.status}`);
            return { successful: 0, failed: levelsNeedingGeneration.length, results: [] };
        }
        
    } catch (error) {
        console.error(`❌ Error in specific content generation:`, error);
        return { successful: 0, failed: levelsNeedingGeneration.length, results: [] };
    }
}

async function generateAllCustomLevelsContent(groupId, levelsNeedingGeneration) {
    try {
        console.log(`🚀 Starting batch content generation for ${levelsNeedingGeneration.length} levels`);
        
        // Use the new batch API endpoint for optimal performance
        const response = await fetch(`/api/custom-levels/${groupId}/generate-all-content`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                console.log(`🎉 Batch content generation complete: ${data.successful} successful, ${data.failed} failed`);
                
                if (data.failed > 0) {
                    const failedLevels = data.results.filter(r => !r.success).map(r => r.levelNumber);
                    console.warn(`⚠️ Failed to generate content for levels: ${failedLevels.join(', ')}`);
                }
                
                return { 
                    successful: data.successful, 
                    failed: data.failed, 
                    results: data.results 
                };
            } else {
                console.error(`❌ Batch generation failed:`, data.error);
                throw new Error(data.error || 'Batch generation failed');
            }
        } else {
            console.error(`❌ HTTP error in batch generation:`, response.status);
            throw new Error(`HTTP ${response.status}`);
        }
        
    } catch (error) {
        console.error('❌ Error in batch content generation:', error);
        
        // Fallback to individual level generation if batch fails
        console.log('🔄 Falling back to individual level generation...');
        return await generateAllCustomLevelsContentFallback(groupId, levelsNeedingGeneration);
    }
}

// Fallback function for individual level generation
async function generateAllCustomLevelsContentFallback(groupId, levelsNeedingGeneration) {
    try {
        console.log(`🔄 Fallback: Generating content individually for ${levelsNeedingGeneration.length} levels`);
        
        // Generate content for all levels in parallel for optimal performance
        const generationPromises = levelsNeedingGeneration.map(async (level, index) => {
            try {
                console.log(`📝 Generating content for level ${level.level_number} (${index + 1}/${levelsNeedingGeneration.length})`);
                
                const response = await fetch(`/api/custom-levels/${groupId}/${level.level_number}/generate-content`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                    }
                });
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        console.log(`✅ Generated content for level ${level.level_number}`);
                        return { success: true, levelNumber: level.level_number };
                    } else {
                        console.error(`❌ Failed to generate content for level ${level.level_number}:`, data.error);
                        return { success: false, levelNumber: level.level_number, error: data.error };
                    }
                } else {
                    console.error(`❌ HTTP error generating content for level ${level.level_number}:`, response.status);
                    return { success: false, levelNumber: level.level_number, error: `HTTP ${response.status}` };
                }
            } catch (error) {
                console.error(`❌ Error generating content for level ${level.level_number}:`, error);
                return { success: false, levelNumber: level.level_number, error: error.message };
            }
        });
        
        // Wait for all generations to complete
        const results = await Promise.all(generationPromises);
        
        // Count successes and failures
        const successful = results.filter(r => r.success).length;
        const failed = results.filter(r => !r.success).length;
        
        console.log(`🎉 Fallback generation complete: ${successful} successful, ${failed} failed`);
        
        if (failed > 0) {
            const failedLevels = results.filter(r => !r.success).map(r => r.levelNumber);
            console.warn(`⚠️ Failed to generate content for levels: ${failedLevels.join(', ')}`);
        }
        
        return { successful, failed, results };
        
    } catch (error) {
        console.error('❌ Error in fallback content generation:', error);
        throw error;
    }
}

// Close modal
function closeModal(buttonOrModalId) {
    let modal = null;
    
    // Check if it's a button element or modal ID
    if (typeof buttonOrModalId === 'string') {
        // It's a modal ID
        modal = document.getElementById(buttonOrModalId);
    } else if (buttonOrModalId && buttonOrModalId.closest) {
        // It's a button element
        modal = buttonOrModalId.closest('.modal-overlay');
    }
    
    if (modal) {
        modal.remove();
    }
    
    // Also close any other modals that might exist
    const allModals = document.querySelectorAll('.modal-overlay');
    allModals.forEach(modal => modal.remove());
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show levels container (same as standard groups)
function showLevelsContainer() {
    const groupsEl = document.getElementById('level-groups');
    const levelsEl = document.getElementById('levels');
    const headerEl = document.getElementById('levels-group-header');
    const customGroupsSection = document.getElementById('custom-level-groups-section');
    const standardGroupsSection = document.getElementById('standard-level-groups-section');
    
    if (groupsEl) groupsEl.style.display = 'none';
    if (levelsEl) levelsEl.style.display = '';
    if (headerEl) headerEl.style.display = '';
    
    // Hide custom and standard groups sections
    if (customGroupsSection) customGroupsSection.style.display = 'none';
    if (standardGroupsSection) standardGroupsSection.style.display = 'none';
    
    console.log('🎯 Showing levels container, hiding groups');
}

// Show groups container (same as standard groups)
async function showGroupsContainer() {
    const groupsEl = document.getElementById('level-groups');
    const levelsEl = document.getElementById('levels');
    const headerEl = document.getElementById('levels-group-header');
    const customGroupsSection = document.getElementById('custom-level-groups-section');
    const standardGroupsSection = document.getElementById('standard-level-groups-section');
    
    if (groupsEl) groupsEl.style.display = '';
    if (levelsEl) levelsEl.style.display = 'none';
    if (headerEl) headerEl.style.display = 'none';
    
    // Show custom and standard groups sections
    if (customGroupsSection) customGroupsSection.style.display = '';
    if (standardGroupsSection) standardGroupsSection.style.display = '';
    
    // Ensure both groups are loaded synchronously to prevent race conditions
    try {
        console.log('🔄 Custom groups: Synchronizing groups loading...');
        
        // Load standard groups first
        if (typeof window.renderLevels === 'function') {
            console.log('✅ Custom groups: renderLevels function found, calling...');
            await window.renderLevels();
        } else {
            console.warn('❌ Custom groups: renderLevels function not found');
        }
        
        // Then load custom groups
        if (typeof window.showCustomLevelGroupsInLibrary === 'function') {
            console.log('✅ Custom groups: showCustomLevelGroupsInLibrary function found, calling...');
            await window.showCustomLevelGroupsInLibrary();
        } else {
            console.warn('❌ Custom groups: showCustomLevelGroupsInLibrary function not found');
        }
        if (typeof window.loadCustomLevelGroups === 'function') {
            console.log('✅ Custom groups: loadCustomLevelGroups function found, calling...');
            await window.loadCustomLevelGroups();
        } else {
            console.warn('❌ Custom groups: loadCustomLevelGroups function not found');
        }
        
        console.log('✅ Custom groups: Groups loading synchronized');
    } catch (error) {
        console.warn('Custom groups: Error synchronizing groups loading:', error);
    }
    
    // Remove group management buttons from quick access
    removeGroupManagementFromQuickAccess();
    
    console.log('🎯 Showing groups container, hiding levels');
}

// Add group management buttons to existing quick access
// Setup edit button in story header
function setupGroupEditButton(groupId) {
    console.log('🔧 Setting up edit button for group:', groupId);
    
    const editBtn = document.getElementById('levels-group-edit-btn');
    const dropdown = document.getElementById('levels-group-edit-dropdown');
    const editOption = document.getElementById('levels-group-edit-option');
    const publishOption = document.getElementById('levels-group-publish-option');
    const unpublishOption = document.getElementById('levels-group-unpublish-option');
    const deleteOption = document.getElementById('levels-group-delete-option');
    
    if (!editBtn || !dropdown) {
        console.log('⚠️ Edit button or dropdown not found');
        return;
    }
    
    // Get group data - try multiple sources
    let group = window.currentCustomGroup?.group;
    
    // If not found in currentCustomGroup, try to find it in customLevelGroups array
    if (!group && customLevelGroups) {
        const foundGroup = customLevelGroups.find(g => g.id === groupId);
        if (foundGroup) {
            group = foundGroup;
            console.log('✅ Found group in customLevelGroups array');
        }
    }
    
    // If still not found, fetch it
    if (!group) {
        console.log('⚠️ Group data not available, fetching...');
        // Try to fetch group data
        fetch(`/api/custom-level-groups/${groupId}`, {
            headers: window.authManager && window.authManager.isAuthenticated() 
                ? window.authManager.getAuthHeaders() 
                : {}
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.group) {
                // Update currentCustomGroup if it exists
                if (window.currentCustomGroup) {
                    window.currentCustomGroup.group = data.group;
                }
                // Setup button with fetched data
                setupGroupEditButtonWithData(groupId, data.group);
            } else {
                console.log('⚠️ Could not fetch group data');
                editBtn.style.display = 'none';
            }
        })
        .catch(error => {
            console.log('⚠️ Error fetching group:', error);
            editBtn.style.display = 'none';
        });
        return;
    }
    
    setupGroupEditButtonWithData(groupId, group);
}

// Setup edit button with group data
function setupGroupEditButtonWithData(groupId, group) {
    console.log('🔧 Setting up edit button with data for group:', groupId, group);
    
    const editBtn = document.getElementById('levels-group-edit-btn');
    const dropdown = document.getElementById('levels-group-edit-dropdown');
    const editWrapper = editBtn?.closest('.levels-group-edit-wrapper');
    const editOption = document.getElementById('levels-group-edit-option');
    const publishOption = document.getElementById('levels-group-publish-option');
    const unpublishOption = document.getElementById('levels-group-unpublish-option');
    const deleteOption = document.getElementById('levels-group-delete-option');
    
    if (!editBtn || !dropdown) {
        console.log('⚠️ Edit button or dropdown not found');
        return;
    }
    
    // Check if current user owns this group (you may need to add user_id check)
    // For now, show it if group exists
    editBtn.style.display = 'inline-flex';
    console.log('✅ Edit button displayed');
    
    // Remove existing event listeners by cloning elements
    const newEditBtn = editBtn.cloneNode(true);
    editBtn.parentNode.replaceChild(newEditBtn, editBtn);
    
    // Set up dropdown toggle
    let dropdownOpen = false;
    newEditBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        dropdownOpen = !dropdownOpen;
        dropdown.style.display = dropdownOpen ? 'flex' : 'none';
        
        // Position dropdown relative to button (already positioned via CSS relative to wrapper)
        // Just ensure it's visible and properly aligned
        if (dropdownOpen) {
            // Dropdown is already positioned relative to the wrapper via CSS
            // No need to calculate position manually since it's in a relative wrapper
        }
        
        // Close dropdown when clicking outside
        if (dropdownOpen) {
            const closeDropdown = (event) => {
                if (!dropdown.contains(event.target) && !newEditBtn.contains(event.target)) {
                    dropdownOpen = false;
                    dropdown.style.display = 'none';
                    document.removeEventListener('click', closeDropdown);
                }
            };
            setTimeout(() => document.addEventListener('click', closeDropdown), 0);
        }
    });
    
    // Set up edit option
    if (editOption) {
        const newEditOption = editOption.cloneNode(true);
        editOption.parentNode.replaceChild(newEditOption, editOption);
        newEditOption.addEventListener('click', (e) => {
            e.stopPropagation();
            dropdown.style.display = 'none';
            dropdownOpen = false;
            editCustomGroup(groupId);
        });
    }
    
    // Set up publish/unpublish options based on current status
    const isPublished = group.status === 'published';
    if (publishOption) {
        publishOption.style.display = isPublished ? 'none' : 'flex';
        const newPublishOption = publishOption.cloneNode(true);
        publishOption.parentNode.replaceChild(newPublishOption, publishOption);
        newPublishOption.addEventListener('click', async (e) => {
            e.stopPropagation();
            dropdown.style.display = 'none';
            dropdownOpen = false;
            await publishCustomGroup(groupId);
            // Refresh group data and update UI
            await refreshCurrentGroup(groupId);
        });
    }
    
    if (unpublishOption) {
        unpublishOption.style.display = isPublished ? 'flex' : 'none';
        const newUnpublishOption = unpublishOption.cloneNode(true);
        unpublishOption.parentNode.replaceChild(newUnpublishOption, unpublishOption);
        newUnpublishOption.addEventListener('click', async (e) => {
            e.stopPropagation();
            dropdown.style.display = 'none';
            dropdownOpen = false;
            await unpublishCustomGroup(groupId);
            // Refresh group data and update UI
            await refreshCurrentGroup(groupId);
        });
    }
    
    // Set up delete option
    if (deleteOption) {
        const newDeleteOption = deleteOption.cloneNode(true);
        deleteOption.parentNode.replaceChild(newDeleteOption, deleteOption);
        newDeleteOption.addEventListener('click', async (e) => {
            e.stopPropagation();
            dropdown.style.display = 'none';
            dropdownOpen = false;
            await deleteCustomGroup(groupId);
        });
    }
}

// Refresh current group data and update UI
async function refreshCurrentGroup(groupId) {
    try {
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        const response = await fetch(`/api/custom-level-groups/${groupId}`, { headers });
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.group) {
                // Update current group data
                if (window.currentCustomGroup) {
                    window.currentCustomGroup.group = data.group;
                }
                
                // Update edit button dropdown options
                setupGroupEditButton(groupId);
                
                // Update header subtitle if needed
                const subtitleEl = document.getElementById('levels-group-subtitle');
                if (subtitleEl && data.group) {
                    const levels = data.levels || [];
                    subtitleEl.innerHTML = `${levels.length} Level • ${data.group.cefr_level || 'A1'} • ${data.group.context_description || 'Custom Content'}`;
                }
            }
        }
    } catch (error) {
        console.log('Error refreshing group:', error);
    }
}

function addGroupManagementToQuickAccess(groupId) {
    console.log('➕ Adding group management buttons to quick access for group:', groupId);
    
    const quickActions = document.querySelector('.library-quick-actions');
    if (!quickActions) {
        console.log('⚠️ Quick actions container not found');
        return;
    }
    
    // Get buttons container once
    const buttonsContainer = quickActions.querySelector('.quick-actions-buttons');
    if (!buttonsContainer) {
        console.log('⚠️ Quick actions buttons container not found');
        return;
    }
    
    // Remove existing group management buttons if any
    const existingGroupManagementButtons = buttonsContainer.querySelectorAll('button[onclick*="editCustomGroup"]');
    console.log(`🗑️ Removing ${existingGroupManagementButtons.length} existing group management buttons`);
    existingGroupManagementButtons.forEach(button => button.remove());
    
    // Hide "Level erstellen" button in level overview
    const createLevelBtn = buttonsContainer.querySelector('#create-custom-levels-btn');
    if (createLevelBtn) {
        console.log('👁️ Hiding "Level erstellen" button');
        createLevelBtn.style.display = 'none';
    } else {
        console.log('⚠️ "Level erstellen" button not found');
    }
    
    // Note: Edit button is now in the header, so we don't add it to quick access anymore
    // But we keep this function for backwards compatibility
}

// Remove group management buttons from quick access
function removeGroupManagementFromQuickAccess() {
    console.log('🔄 Removing group management buttons from quick access');
    
    const quickActions = document.querySelector('.library-quick-actions');
    if (!quickActions) {
        console.log('⚠️ Quick actions container not found');
        return;
    }
    
    // Remove buttons with group management onclick handlers
    const buttonsContainer = quickActions.querySelector('.quick-actions-buttons');
    if (buttonsContainer) {
        const groupManagementButtons = buttonsContainer.querySelectorAll('button[onclick*="editCustomGroup"]');
        console.log(`🗑️ Removing ${groupManagementButtons.length} group management buttons`);
        groupManagementButtons.forEach(button => button.remove());
        
        // Show "Level erstellen" button again in group overview
        const createLevelBtn = buttonsContainer.querySelector('#create-custom-levels-btn');
        if (createLevelBtn) {
            console.log('✅ Showing "Level erstellen" button');
            createLevelBtn.style.display = '';
        } else {
            console.log('⚠️ "Level erstellen" button not found');
        }
    } else {
        console.log('⚠️ Quick actions buttons container not found');
    }
}

// Show notification
function showNotification(message, type = 'info') {
    // Simple notification system - you can enhance this
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    notification.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 12px 20px;
        border-radius: 8px;
        color: white;
        font-weight: 500;
        z-index: 10000;
        max-width: 400px;
        word-wrap: break-word;
    `;
    
    if (type === 'success') {
        notification.style.background = '#10b981';
    } else if (type === 'error') {
        notification.style.background = '#ef4444';
    } else if (type === 'info') {
        notification.style.background = '#3b82f6';
    } else {
        notification.style.background = '#6b7280';
    }
    
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Render custom levels in the levels tab
async function renderCustomLevels(groupId, levels) {
    console.log('🎨 Rendering custom levels for group:', groupId);
    
    // Find the levels container - same as standard levels
    const levelsContainer = document.getElementById('levels');
    if (!levelsContainer) {
        console.error('❌ Levels container not found');
        return;
    }
    
    // Load cached progress data BEFORE rendering (performance optimization)
    // This ensures all progress data is available when cards are rendered
    if (window.authManager && window.authManager.isAuthenticated()) {
        if (!window.cachedGroupProgress || Object.keys(window.cachedGroupProgress).length === 0) {
            await loadCachedGroupProgress(groupId);
        }
    }
    
    // Clear existing content
    levelsContainer.innerHTML = '';
    
    // Create custom levels HTML using the exact same structure as standard levels
    const levelsHtml = levels.map(level => {
        const levelNumber = level.level_number;
        const levelTitle = level.title || `Level ${levelNumber}`;
        const levelTopic = level.topic || 'Custom Level';
        
        // Check if level needs content generation
        const content = level.content || {};
        const needsGeneration = content.ultra_lazy_loading && !content.sentences_generated;
        const isGenerating = content.ultra_lazy_loading && content.sentences_generated === false;
        
        // Get progress data from preload cache (same source as backside)
        // Use window.cachedFamiliarityData which is populated during preloading
        let totalWords = 0;
        let learnedWords = 0;
        let scorePercent = 0;
        
        // Try to get progress data from preload cache (same as backside uses)
        if (window.cachedFamiliarityData && 
            window.cachedFamiliarityData[groupId] && 
            window.cachedFamiliarityData[groupId][levelNumber]) {
            const cachedFamiliarity = window.cachedFamiliarityData[groupId][levelNumber];
            totalWords = cachedFamiliarity.total_words || 0;
            learnedWords = cachedFamiliarity.fam_counts && cachedFamiliarity.fam_counts[5] ? cachedFamiliarity.fam_counts[5] : 0;
            // Calculate progress percent based on learned words (familiarity 5)
            // This represents actual learning progress, not session score
            if (totalWords > 0) {
                scorePercent = Math.round((learnedWords / totalWords) * 100);
            } else {
                scorePercent = 0;
            }
        }
        
        // Fallback: Try old cache if preload cache not available yet
        if (totalWords === 0 && window.cachedGroupProgress && window.cachedGroupProgress[levelNumber]) {
            const cachedProgress = window.cachedGroupProgress[levelNumber];
            totalWords = cachedProgress.total_words || 0;
            learnedWords = cachedProgress.completed_words || (cachedProgress.fam_counts && cachedProgress.fam_counts[5]) || 0;
            // Calculate progress percent based on learned words, not score_percent
            if (totalWords > 0) {
                scorePercent = Math.round((learnedWords / totalWords) * 100);
            } else {
                scorePercent = 0;
            }
        }
        
        // If no progress data, estimate word count from content
        if (totalWords === 0) {
            if (content.items && content.items.length > 0) {
                // Count words from existing content
                const allWords = new Set();
                content.items.forEach(item => {
                    if (item.words) {
                        item.words.forEach(word => {
                            if (word && word.trim()) {
                                allWords.add(word.trim().toLowerCase());
                            }
                        });
                    }
                });
                totalWords = allWords.size;
            } else if (needsGeneration) {
                // Estimate for levels that need generation
                totalWords = 25; // Typical custom level size
            }
        }
        
        // Determine level status (localized)
        let levelStatus = window.t ? window.t('status.available', 'Available') : 'Available';
        let statusClass = '';
        if (needsGeneration) {
            levelStatus = window.t ? window.t('status.generating', 'Generating...') : 'Generating...';
            statusClass = 'generating';
        } else if (isGenerating) {
            levelStatus = window.t ? window.t('status.generated', 'Generated') : 'Generated';
            statusClass = 'generating';
        }
        
        return `
            <div class="level-card ${statusClass}" data-level="${levelNumber}" data-custom-group-id="${groupId}">
                <div class="level-card-inner">
                    <div class="level-card-front">
                        <div class="level-card-content">
                            <div class="level-number">${levelNumber}</div>
                            <div class="level-card-info">
                                <div class="level-status ${statusClass}" data-i18n="${needsGeneration ? 'status.generating' : (isGenerating ? 'status.generated' : 'status.available')}">${levelStatus}</div>
                                <div class="level-title">${escapeHtml(levelTitle)}</div>
                                
                                <!-- Word statistics section (same as standard levels) -->
                                <div class="level-word-stats">
                                    <div class="level-word-stats-main">
                                        <div class="level-word-stats-left">
                                            <div class="level-words-count">
                                                <span class="words-icon">📖</span>
                                                <span class="words-text">${totalWords}</span>
                                            </div>
                                            <div class="level-learned-count">
                                                <span class="learned-icon">💡</span>
                                                <span class="learned-text">${learnedWords}</span>
                                            </div>
                                        </div>
                                        <div class="level-word-stats-right">
                                            <div class="level-completion-circle">
                                                <svg class="completion-circle-svg" viewBox="0 0 36 36">
                                                    <path class="completion-circle-bg" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
                                                    <path class="completion-circle-fill" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"/>
                                                </svg>
                                                <div class="completion-circle-text">${scorePercent}%</div>
                                            </div>
                                        </div>
                                    </div>
                                    <div class="level-progress-bar">
                                        <div class="level-progress-fill"></div>
                                    </div>
                                </div>
                            </div>
                            
                            <!-- Actions section (same as standard levels) -->
                            <div class="level-actions">
                                <button class="level-btn primary" data-i18n="buttons.start" onclick="handleCustomLevelStart(${groupId}, ${levelNumber})">
                                    ${window.t ? window.t('buttons.start', 'Start') : 'Start'}
                                </button>
                                <button class="level-btn" data-i18n="buttons.practice" onclick="handleCustomLevelPractice(${groupId}, ${levelNumber})">
                                    ${window.t ? window.t('buttons.practice', 'Practice') : 'Practice'}
                                </button>
                            </div>
                        </div>
                    </div>
                    
                    <div class="level-card-back">
                        <div class="level-card-back-content">
                            <div class="level-card-back-header">
                                <div class="level-card-back-title" data-i18n="labels.level">${window.t ? window.t('labels.level', 'Level') : 'Level'} ${levelNumber}</div>
                                <div class="level-card-back-close">×</div>
                            </div>
                            <div class="level-card-back-info">
                                <div class="familiarity-overview-title" data-i18n="familiarity.title">${window.t ? window.t('familiarity.title', 'Familiarity of Words') : 'Familiarity of Words'}</div>
                                <div class="familiarity-list">
                                    <div class="familiarity-item" data-familiarity-level="0">
                                        <div class="familiarity-symbol">❌</div>
                                        <div class="familiarity-label" data-i18n="familiarity.unknown">${window.t ? window.t('familiarity.unknown', 'Unknown') : 'Unknown'}</div>
                                        <div class="familiarity-count">0</div>
                                    </div>
                                    <div class="familiarity-item" data-familiarity-level="1">
                                        <div class="familiarity-symbol">🔴</div>
                                        <div class="familiarity-label" data-i18n="familiarity.seen">${window.t ? window.t('familiarity.seen', 'Seen') : 'Seen'}</div>
                                        <div class="familiarity-count">0</div>
                                    </div>
                                    <div class="familiarity-item" data-familiarity-level="2">
                                        <div class="familiarity-symbol">🟠</div>
                                        <div class="familiarity-label" data-i18n="familiarity.learning">${window.t ? window.t('familiarity.learning', 'Learning') : 'Learning'}</div>
                                        <div class="familiarity-count">0</div>
                                    </div>
                                    <div class="familiarity-item" data-familiarity-level="3">
                                        <div class="familiarity-symbol">🟡</div>
                                        <div class="familiarity-label" data-i18n="familiarity.familiar">${window.t ? window.t('familiarity.familiar', 'Familiar') : 'Familiar'}</div>
                                        <div class="familiarity-count">0</div>
                                    </div>
                                    <div class="familiarity-item" data-familiarity-level="4">
                                        <div class="familiarity-symbol">🟢</div>
                                        <div class="familiarity-label" data-i18n="familiarity.strong">${window.t ? window.t('familiarity.strong', 'Strong') : 'Strong'}</div>
                                        <div class="familiarity-count">0</div>
                                    </div>
                                    <div class="familiarity-item" data-familiarity-level="5">
                                        <div class="familiarity-symbol">💡</div>
                                        <div class="familiarity-label" data-i18n="familiarity.memorized">${window.t ? window.t('familiarity.memorized', 'Memorized') : 'Memorized'}</div>
                                        <div class="familiarity-count">0</div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Update the levels container - use standard header structure
    levelsContainer.innerHTML = levelsHtml;
    
    // Update the standard levels group header
    const headerTitle = document.getElementById('levels-group-title');
    const headerSubtitle = document.getElementById('levels-group-subtitle');
    
    if (headerTitle) {
        headerTitle.innerHTML = `🎯 ${window.currentCustomGroup?.group?.group_name || 'Custom Level Group'}`;
    }
    
    if (headerSubtitle) {
        headerSubtitle.innerHTML = `${levels.length} Level • ${window.currentCustomGroup?.group?.cefr_level || 'A1'} • ${window.currentCustomGroup?.group?.context_description || 'Custom Content'}`;
    }
    
    // Ensure the standard header is visible
    const headerEl = document.getElementById('levels-group-header');
    if (headerEl) {
        headerEl.style.display = '';
    }
    
    // Show edit button in header if user owns this group
    // Use setTimeout to ensure window.currentCustomGroup is set
    setTimeout(() => {
        setupGroupEditButton(groupId);
    }, 100);
    
    // Add group management buttons to existing quick access
    addGroupManagementToQuickAccess(groupId);
    
    
    // Hide edit button when leaving the story view
    const editBtn = document.getElementById('levels-group-edit-btn');
    if (editBtn) {
        editBtn.style.display = 'none';
    }
    const dropdown = document.getElementById('levels-group-edit-dropdown');
    if (dropdown) {
        dropdown.style.display = 'none';
    }
    
    // Bind the standard back button if not already bound
    const backBtn = document.getElementById('levels-group-back');
    if (backBtn && !backBtn.dataset.bound) {
        backBtn.addEventListener('click', () => {
            // Hide edit button
            if (editBtn) editBtn.style.display = 'none';
            if (dropdown) dropdown.style.display = 'none';
            
            // Clear custom group context
            window.currentCustomGroup = null;
            window.currentCustomLevel = null;
            
            // Clear selected level group
            if (window.SELECTED_LEVEL_GROUP !== undefined) {
                window.SELECTED_LEVEL_GROUP = null;
            }
            
            // Show groups container
            showGroupsContainer();
            
            // Restore standard levels view
            if (window.renderLevels) {
                window.renderLevels();
            }
        });
        backBtn.dataset.bound = 'true';
    }
    
    // Apply user-specific level progression logic for all levels at once (performance optimization)
    applyCustomLevelProgressionBulk(levelsContainer, groupId);
    
    // Add click handlers for level cards (same as standard levels)
    levelsContainer.querySelectorAll('.level-card').forEach(card => {
        const levelNumber = parseInt(card.dataset.level);
        
        // Add flip functionality (same as standard levels)
        card.addEventListener('click', function(e) {
            // Don't flip if clicking on buttons or close button
            if (!e.target.closest('.level-btn') && !e.target.closest('.level-card-back-close')) {
                const wasFlipped = this.classList.contains('flipped');
                this.classList.toggle('flipped');
                
                // If flipping to back side, load familiarity data
                if (!wasFlipped) {
                    console.log('🔄 Card flipped to back side, loading familiarity data for level', levelNumber, 'group', groupId);
                    loadCustomLevelFamiliarityData(card, levelNumber, groupId);
                }
            }
        });

        // Ensure buttons stop propagation so clicks don't flip the card
        const btns = card.querySelectorAll('.level-btn');
        btns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
            });
        });
        
        // Add close button functionality for back side
        const closeBtn = card.querySelector('.level-card-back-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                card.classList.remove('flipped');
            });
        }
        
        // Apply progress data from cache (already loaded by applyCustomLevelProgressionBulk)
        // This avoids making individual API calls for each level
        if (window.cachedGroupProgress && window.cachedGroupProgress[levelNumber]) {
            const cachedData = window.cachedGroupProgress[levelNumber];
            card.dataset.cachedProgressData = JSON.stringify(cachedData);
            // Apply progress data directly from cache for immediate UI update
            applyCustomLevelProgressData(card, cachedData);
            
            // Update title from bulk-stats if available
            if (cachedData.title && cachedData.title !== `Level ${levelNumber}`) {
                const titleEl = card.querySelector('.level-title');
                if (titleEl) {
                    titleEl.textContent = cachedData.title;
                    console.log(`✅ Updated custom level ${levelNumber} title to: ${cachedData.title}`);
                }
            }
        } else {
            // Only make individual API call if cache is missing (shouldn't happen normally)
        setTimeout(() => {
            applyCustomLevelProgress(card, levelNumber, groupId);
        }, 100);
        }
        
        // Note: Click handlers are already set via HTML onclick attributes
        // which include proper lock checking via handleCustomLevelStart()
        // No need for additional JavaScript event listeners
    });
    
    console.log('✅ Custom levels rendered successfully');
}

// Start a specific custom level
async function startCustomLevel(groupId, levelNumber) {
    try {
        console.log('🚀 Starting custom level:', groupId, levelNumber);
        
        // Show loading state
        if (window.showLoader) {
            window.showLoader();
        }
        
        // Get custom level data
        const response = await fetch(`/api/custom-level-groups/${groupId}/levels/${levelNumber}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load custom level');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to load custom level');
        }
        
        let level = data.level;
        console.log('📖 Custom level loaded:', level);
        
        // Check if level content needs generation - WAIT for it before starting level
        const levelContent = level.content;
        const isEmpty = !levelContent || !levelContent.items || levelContent.items.length === 0;
        const isUltraLazy = levelContent && levelContent.ultra_lazy_loading && !levelContent.sentences_generated;
        
        if (isEmpty || isUltraLazy) {
            console.log('🚀 Level content is empty or ultra-lazy, generating content...');
            
            // Show loading message
            if (window.showLoader) {
                window.showLoader('Generiere Level-Inhalt...');
            }
            
            // WAIT for content generation before proceeding
            try {
                const generateResponse = await fetch(`/api/custom-levels/${groupId}/${levelNumber}/generate-content`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                    }
                });
                
                if (!generateResponse.ok) {
                    throw new Error('Failed to generate level content');
                }
                
                const generateData = await generateResponse.json();
                if (!generateData.success) {
                    throw new Error(generateData.error || 'Failed to generate level content');
                }
                
                console.log('✅ Level content generated successfully, reloading...');
                
                // Reload level data with generated content
                const reloadResponse = await fetch(`/api/custom-level-groups/${groupId}/levels/${levelNumber}`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                    }
                });
                
                if (!reloadResponse.ok) {
                    throw new Error('Failed to reload level data');
                }
                
                const reloadData = await reloadResponse.json();
                if (!reloadData.success || !reloadData.level) {
                    throw new Error('Failed to reload level data');
                }
                
                // Update level with generated content
                level = reloadData.level;
                console.log('📖 Level content loaded with generated content');
                
            } catch (err) {
                console.error('❌ Error generating level content:', err);
                if (window.hideLoader) {
                    window.hideLoader();
                }
                alert('Fehler beim Generieren des Level-Inhalts. Bitte versuche es erneut.');
                return; // Don't start level if content generation failed
            }
        }
        
        // Store custom level context
        window.currentCustomLevel = {
            groupId: groupId,
            levelNumber: levelNumber,
            level: level
        };
        
        // Start the lesson with custom level using the standard lesson system
        if (window.startLevelWithTopic) {
            // Set global variables for custom level context
            window.SELECTED_CUSTOM_GROUP = groupId;
            window.SELECTED_CUSTOM_LEVEL = levelNumber;
            
            // Convert custom level content to standard format
            let levelContent = level.content;
            const levelTitle = String(level.title || `Custom Level ${levelNumber}`).trim();
            
            // Extract items from custom level content structure
            if (levelContent && typeof levelContent === 'object' && levelContent.items) {
                levelContent = levelContent.items;
            } else if (Array.isArray(levelContent)) {
                // Already an array, use as is
                levelContent = levelContent;
            } else {
                console.warn('Unexpected level content structure:', levelContent);
                levelContent = [];
            }
            
            // Store custom level data in global RUN object for the lesson system
            if (!window.RUN) {
                window.RUN = {
                    id: null,
                    items: [],
                    idx: 0,
                    target: document.getElementById('target-lang')?.value || 'en',
                    native: localStorage.getItem('siluma_native') || 'de',
                    answered: false,
                    queue: [],
                    selectedOption: null,
                    mcCorrect: 0,
                    mcTotal: 0
                };
            }
            
            // Ensure levelContent is an array and in the correct format
            let formattedContent = levelContent;
            if (!Array.isArray(levelContent)) {
                console.warn('Level content is not an array, converting...', levelContent);
                formattedContent = [];
            }
            
            // Ensure each item has the required structure
            formattedContent = formattedContent.map((item, index) => {
                let textTarget = '';
                let words = [];
                
                if (typeof item === 'string') {
                    // If item is just a string, convert to proper format
                    textTarget = item;
                    words = extractWordsFromText(item);
                } else if (item && typeof item === 'object') {
                    // Ensure required fields exist - match custom level format
                    textTarget = item.text_target || item.text || item.sentence || '';
                    words = item.words || extractWordsFromText(textTarget);
                } else {
                    // Fallback for invalid items
                    textTarget = String(item || '');
                    words = extractWordsFromText(textTarget);
                }
                
                return {
                    text_target: textTarget,
                    text_native_ref: item?.text_native_ref || item?.text_native || item?.translation || '',
                    text_native: item?.text_native || item?.translation || item?.text_native_ref || '',
                    translation: item?.translation || item?.text_native || item?.text_native_ref || '',
                    words: words,
                    idx: item?.idx || item?.id || index + 1,
                    ...item // Keep any additional fields
                };
            });
            
            console.log('📝 Formatted custom level content:', formattedContent);
            
            // Log the first item to verify translation data
            if (formattedContent.length > 0) {
                console.log('🔧 First item translation data:', {
                    text_target: formattedContent[0].text_target,
                    text_native_ref: formattedContent[0].text_native_ref,
                    text_native: formattedContent[0].text_native,
                    translation: formattedContent[0].translation,
                    originalItem: level.content.items[0]
                });
            }
            
            // Ensure words are properly extracted for tooltips
            formattedContent.forEach((item, index) => {
                if (!item.words || item.words.length === 0) {
                    item.words = extractWordsFromText(item.text_target);
                    console.log(`🔧 Extracted words for item ${index}:`, item.words);
                }
            });
            
            // Set custom level data
            window.RUN._customLevelData = formattedContent;
            window.RUN._customLevelTitle = levelTitle;
            window.RUN._customGroupId = groupId;
            window.RUN._customLevelNumber = levelNumber;
            
            // Ensure target language is set for tooltips
            window.RUN.target = window.RUN.target || 'en'; // Default to English
            
            console.log('🔧 Custom level context set:', {
                groupId: window.RUN._customGroupId,
                levelNumber: window.RUN._customLevelNumber,
                target: window.RUN.target
            });
            
            // Also set these for API calls (redundant but ensures they're set)
            window.RUN._customGroupId = groupId;
            window.RUN._customLevelNumber = levelNumber;
            
            // OPTIMIZATION: Preload first sentence audio immediately (non-blocking)
            if (formattedContent.length > 0 && formattedContent[0].text_target) {
                const firstSentence = formattedContent[0].text_target;
                // Get language from level, currentCustomGroup, or default
                const lang = level.language || 
                            (window.currentCustomGroup && window.currentCustomGroup.group && window.currentCustomGroup.group.language) ||
                            document.getElementById('target-lang')?.value || 'en';
                // Preload sentence audio in background
                if (window.prewarmSentenceTTS) {
                    window.prewarmSentenceTTS(firstSentence).catch(() => {});
                }
            }
            
            // OPTIMIZATION: Preload first 10 words immediately for instant tooltips
            const firstWords = [];
            for (let i = 0; i < Math.min(10, formattedContent.length); i++) {
                const item = formattedContent[i];
                if (item.words && Array.isArray(item.words)) {
                    firstWords.push(...item.words);
                }
            }
            const uniqueFirstWords = [...new Set(firstWords)].slice(0, 10);
            if (uniqueFirstWords.length > 0 && window.preloadWordsBatch) {
                // Get language from level, currentCustomGroup, or default
                const lang = level.language || 
                            (window.currentCustomGroup && window.currentCustomGroup.group && window.currentCustomGroup.group.language) ||
                            document.getElementById('target-lang')?.value || 'en';
                const nativeLang = level.native_language ||
                                  (window.currentCustomGroup && window.currentCustomGroup.group && window.currentCustomGroup.group.native_language) ||
                                  localStorage.getItem('siluma_native') || 'de';
                window.preloadWordsBatch(uniqueFirstWords, lang, nativeLang).catch(() => {});
            }
            
            // Start lesson with custom data
            window.startLevelWithTopic(levelNumber, levelTitle, false);
        } else {
            showNotification('Lektion-Funktion nicht verfügbar', 'error');
        }
        
    } catch (error) {
        console.error('❌ Error starting custom level:', error);
        showNotification('Fehler beim Laden des Levels: ' + error.message, 'error');
    } finally {
        // Hide loading state
        if (window.hideLoader) {
            window.hideLoader();
        }
    }
}


// Helper function to extract words from text (same as in lesson.js)
function extractWordsFromText(text) {
    if (!text || typeof text !== 'string') return [];
    
    // Extract words using the same regex as in lesson.js
    const words = [];
    const re = /\p{L}+(?:'\p{L}+)?/gu;
    let match;
    while ((match = re.exec(text)) !== null) {
        const word = match[0].toLowerCase();
        if (word && !words.includes(word)) {
            words.push(word);
        }
    }
    return words;
}

// Export functions for global access
window.initCustomLevelGroups = initCustomLevelGroups;
window.showCustomLevelGroupsInLibrary = showCustomLevelGroupsInLibrary;
window.showCreateCustomGroupModal = showCreateCustomGroupModal;
// Apply progress and colors to custom level cards (same as standard levels)
async function applyCustomLevelProgress(levelElement, levelNumber, groupId) {
    try {
        // Get level data
        const level = window.currentCustomGroup?.levels?.find(l => l.level_number === levelNumber);
        if (!level) return;
        
        let normalized = null;

        // Priority 1: Use cached data from window.cachedGroupProgress (fastest, already loaded)
        if (window.cachedGroupProgress && window.cachedGroupProgress[levelNumber]) {
            const cachedData = window.cachedGroupProgress[levelNumber];
            normalized = applyCustomLevelProgressData(levelElement, cachedData);
            levelElement.dataset.cachedProgressData = JSON.stringify(cachedData);
            if (window.DEBUG) console.log(`✅ Applied cached progress for level ${levelNumber} from window.cachedGroupProgress`);
            return; // Early return - no need for API call if cache exists
        }

        // Priority 2: Use cached data from dataset (from previous render)
        if (levelElement.dataset.cachedProgressData) {
            try {
                const cachedData = JSON.parse(levelElement.dataset.cachedProgressData);
                normalized = applyCustomLevelProgressData(levelElement, cachedData);
                if (window.DEBUG) console.log(`✅ Applied cached progress for level ${levelNumber} from dataset`);
                return; // Early return - no need for API call if dataset cache exists
            } catch (error) {
                console.log('⚠️ Error parsing cached progress data:', error);
                normalized = null;
            }
        }

        // Priority 3: Only make API call if no cache exists (fallback)
        try {
            const headers = {};
            if (window.authManager && window.authManager.isAuthenticated()) {
                Object.assign(headers, window.authManager.getAuthHeaders());
            }

            if (window.DEBUG) console.log('🔧 Fetching custom level progress (no cache):', groupId, levelNumber);
            const response = await fetch(`/api/custom-levels/${groupId}/${levelNumber}/progress`, {
                headers
            });

            if (response.ok) {
                const progressData = await response.json();
                if (progressData.success) {
                    const refreshed = applyCustomLevelProgressData(levelElement, progressData);
                    if (refreshed) {
                        normalized = refreshed;
                        // Update cache for future use
                        if (!window.cachedGroupProgress) window.cachedGroupProgress = {};
                        window.cachedGroupProgress[levelNumber] = refreshed;
                        levelElement.dataset.cachedProgressData = JSON.stringify(refreshed);
                        if (window.DEBUG) console.log('✅ Custom level progress loaded from API:', normalized);
                    }
                } else {
                    console.log('⚠️ Progress API returned error:', progressData.error);
                }
            } else {
                console.log('⚠️ Progress API not available for custom level, using defaults. Status:', response.status);
            }
        } catch (error) {
            console.log('⚠️ No progress data available for custom level, using defaults:', error.message);
        }

        if (!normalized) {
            normalized = applyCustomLevelProgressData(levelElement, null);
        }

        // Fallback: if no progress data, try to get word count from level content
        if (normalized && normalized.total_words === 0 && level.content) {
            let fallbackTotal = 0;
            if (Array.isArray(level.content)) {
                fallbackTotal = level.content.length;
            } else if (level.content && Array.isArray(level.content.items)) {
                fallbackTotal = level.content.items.length;
            }
            if (fallbackTotal > 0) {
                normalized = applyCustomLevelProgressData(levelElement, {
                    fam_counts: normalized.fam_counts,
                    total_words: fallbackTotal,
                    score: normalized.score_raw !== undefined ? normalized.score_raw : normalized.score_percent,
                    status: normalized.status,
                    completed_at: normalized.completed_at,
                    last_updated: normalized.last_updated
                });
            }
        }

        if (!window.cachedGroupProgress) window.cachedGroupProgress = {};
        window.cachedGroupProgress[levelNumber] = normalized;
        
    } catch (error) {
        console.log('Error setting custom level color:', error);
    }
}

// Update completion circle for custom levels
function updateCustomLevelCompletionCircle(levelElement, progressPercent) {
    try {
        const circleFill = levelElement.querySelector('.completion-circle-fill');
        const circleText = levelElement.querySelector('.completion-circle-text');
        
        if (!circleFill || !circleText) return;

        const safePercent = Math.max(0, Math.min(100, Number(progressPercent) || 0));
        
        // Calculate stroke-dasharray for the circle
        const circumference = 2 * Math.PI * 15.9155;
        const offset = circumference - (safePercent / 100) * circumference;
        
        // Update the circle fill
        circleFill.style.strokeDasharray = `${circumference} ${circumference}`;
        circleFill.style.strokeDashoffset = offset;
        
        // Update the text
        circleText.textContent = `${safePercent}%`;
        
        // Add color based on progress
        circleFill.classList.remove('low', 'medium', 'high');
        if (safePercent < 30) {
            circleFill.classList.add('low');
        } else if (safePercent < 70) {
            circleFill.classList.add('medium');
        } else {
            circleFill.classList.add('high');
        }
        
    } catch (error) {
        console.log('Error updating custom level completion circle:', error);
    }
}

// Load familiarity data for custom level back side - reads directly from custom_level_progress table
async function loadCustomLevelFamiliarityData(levelElement, levelNumber, groupId) {
    console.log('📊 loadCustomLevelFamiliarityData called:', { levelNumber, groupId, element: levelElement });
    try {
        // Extract identifiers from element if not provided
        const extractedGroupId = groupId || levelElement.dataset.customGroupId;
        const extractedLevelNumber = levelNumber || parseInt(levelElement.dataset.level);
        
        // Get user ID from auth manager with fallback
        let userId = null;
        if (window.authManager && window.authManager.currentUser) {
            userId = window.authManager.currentUser.id;
        } else {
            // Fallback: try to decode from session token
            const sessionToken = localStorage.getItem('session_token');
            if (sessionToken) {
                try {
                    const userInfo = JSON.parse(atob(sessionToken.split('.')[1]));
                    userId = userInfo.user_id || userInfo.id;
                } catch (e) {
                    console.warn('⚠️ Could not decode session token:', e);
                }
            }
        }
        
        if (!userId) {
            console.log('⚠️ No user ID available, cannot fetch progress data');
            // Initialize with zeros
            const familiarityCounts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0};
            updateFamiliarityUI(levelElement, familiarityCounts);
            return;
        }
        
        // Check preloaded cache first (data loaded when story was opened)
        if (window.cachedFamiliarityData && 
            window.cachedFamiliarityData[extractedGroupId] && 
            window.cachedFamiliarityData[extractedGroupId][extractedLevelNumber]) {
            const cachedFamiliarity = window.cachedFamiliarityData[extractedGroupId][extractedLevelNumber];
            console.log('🚀 Using preloaded familiarity data for level', extractedLevelNumber, ':', cachedFamiliarity.fam_counts);
            updateFamiliarityUI(levelElement, cachedFamiliarity.fam_counts);
            
            // Also update card's cached data
            levelElement.dataset.cachedProgressData = JSON.stringify(cachedFamiliarity);
            return;
        }
        
        // Check card's cached data as fallback
        const cachedData = levelElement.dataset.cachedProgressData;
        if (cachedData) {
            try {
                const progressData = JSON.parse(cachedData);
                if (progressData.fam_counts) {
                    console.log('🚀 Using card cached familiarity data for level', extractedLevelNumber, ':', progressData.fam_counts);
                    updateFamiliarityUI(levelElement, progressData.fam_counts);
                    return;
                }
            } catch (error) {
                console.log('⚠️ Error parsing cached data, fetching from API:', error);
            }
        }
        
        // Fetch fresh data from API if cache is not available
        console.log('📊 Fetching familiarity data from API for level', extractedLevelNumber);
        
        // Single API call to read from custom_level_progress table using new direct endpoint
        const familiarityCounts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0};
        
        try {
            const headers = {};
            if (window.authManager && window.authManager.isAuthenticated()) {
                Object.assign(headers, window.authManager.getAuthHeaders());
            }
            
            console.log('🔧 Fetching custom level progress from custom_level_progress table (direct):', extractedGroupId, extractedLevelNumber, userId);
            const response = await fetch(`/api/custom-levels/${extractedGroupId}/${extractedLevelNumber}/progress-direct`, {
                headers: headers
            });
            
            if (response.ok) {
                const progressData = await response.json();
                console.log('📊 API Response for level', extractedLevelNumber, 'group', extractedGroupId, ':', progressData);
                if (progressData.success) {
                    // Extract familiarity counts from direct database fields
                    familiarityCounts[0] = parseInt(progressData.familiarity_0 || 0);
                    familiarityCounts[1] = parseInt(progressData.familiarity_1 || 0);
                    familiarityCounts[2] = parseInt(progressData.familiarity_2 || 0);
                    familiarityCounts[3] = parseInt(progressData.familiarity_3 || 0);
                    familiarityCounts[4] = parseInt(progressData.familiarity_4 || 0);
                    familiarityCounts[5] = parseInt(progressData.familiarity_5 || 0);
                    
                    const totalFromCounts = Object.values(familiarityCounts).reduce((sum, val) => sum + val, 0);
                    console.log('✅ Custom level progress loaded from custom_level_progress table (direct):', {
                        familiarityCounts,
                        total_words_from_api: progressData.total_words,
                        total_from_familiarity_counts: totalFromCounts,
                        match: progressData.total_words === totalFromCounts
                    });
                    
                    // Update cache for future use
                    const cacheData = {
                        fam_counts: familiarityCounts,
                        total_words: progressData.total_words || 0,
                        score: progressData.score,
                        status: progressData.status
                    };
                    
                    // Store in card's dataset
                    levelElement.dataset.cachedProgressData = JSON.stringify(cacheData);
                    
                    // Also store in global preload cache
                    if (!window.cachedFamiliarityData) {
                        window.cachedFamiliarityData = {};
                    }
                    if (!window.cachedFamiliarityData[extractedGroupId]) {
                        window.cachedFamiliarityData[extractedGroupId] = {};
                    }
                    window.cachedFamiliarityData[extractedGroupId][extractedLevelNumber] = cacheData;
                } else {
                    console.log('⚠️ Progress API returned no data:', progressData);
                }
            } else {
                console.log('⚠️ Progress API not available. Status:', response.status);
            }
        } catch (error) {
            console.log('⚠️ Error fetching progress data:', error.message);
        }
        
        updateFamiliarityUI(levelElement, familiarityCounts);
        
    } catch (error) {
        console.log('Error loading custom level familiarity data:', error);
    }
}

// Helper function to update familiarity UI
// Maps all 6 familiarity counts (0-5) from database fields to UI elements
function updateFamiliarityUI(levelElement, familiarityCounts) {
    // Ensure we update all 6 familiarity levels (0-5)
    for (let level = 0; level <= 5; level++) {
        const familiarityItem = levelElement.querySelector(`[data-familiarity-level="${level}"]`);
        if (familiarityItem) {
            const countElement = familiarityItem.querySelector('.familiarity-count');
            if (countElement) {
                // Get count from familiarityCounts object (handles both string and number keys)
                const count = familiarityCounts[level] !== undefined 
                    ? familiarityCounts[level] 
                    : (familiarityCounts[String(level)] !== undefined 
                        ? familiarityCounts[String(level)] 
                        : 0);
                countElement.textContent = parseInt(count) || 0;
            }
        }
    }
}

// Preload familiarity data for all levels in a story (background loading)
// This ensures data is ready when user flips a card
// progressCallback(current, total) is called to update loading screen
async function preloadFamiliarityDataForAllLevels(groupId, levels, progressCallback = null) {
    try {
        // Get user ID
        let userId = null;
        if (window.authManager && window.authManager.currentUser) {
            userId = window.authManager.currentUser.id;
        } else {
            const sessionToken = localStorage.getItem('session_token');
            if (sessionToken) {
                try {
                    const userInfo = JSON.parse(atob(sessionToken.split('.')[1]));
                    userId = userInfo.user_id || userInfo.id;
                } catch (e) {
                    console.warn('⚠️ Could not decode session token for preloading:', e);
                    return;
                }
            }
        }
        
        if (!userId) {
            console.log('⚠️ No user ID available, cannot preload familiarity data');
            return;
        }
        
        // Initialize cache structure if needed
        if (!window.cachedFamiliarityData) {
            window.cachedFamiliarityData = {};
        }
        if (!window.cachedFamiliarityData[groupId]) {
            window.cachedFamiliarityData[groupId] = {};
        }
        
        console.log(`🚀 Preloading familiarity data for ${levels.length} levels in group ${groupId}`);
        
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        // Load all levels sequentially to show progress (better UX)
        let completed = 0;
        const total = levels.length;
        
        for (const level of levels) {
            const levelNumber = level.level_number;
            
            try {
                // Update progress callback
                if (progressCallback) {
                    progressCallback(completed, total);
                }
                
                const response = await fetch(`/api/custom-levels/${groupId}/${levelNumber}/progress-direct`, {
                    headers: headers
                });
                
                if (response.ok) {
                    const progressData = await response.json();
                    if (progressData.success) {
                        // Extract familiarity counts
                        const familiarityCounts = {
                            0: parseInt(progressData.familiarity_0 || 0),
                            1: parseInt(progressData.familiarity_1 || 0),
                            2: parseInt(progressData.familiarity_2 || 0),
                            3: parseInt(progressData.familiarity_3 || 0),
                            4: parseInt(progressData.familiarity_4 || 0),
                            5: parseInt(progressData.familiarity_5 || 0)
                        };
                        
                        // Store in cache
                        window.cachedFamiliarityData[groupId][levelNumber] = {
                            fam_counts: familiarityCounts,
                            total_words: progressData.total_words || 0,
                            score: progressData.score,
                            status: progressData.status
                        };
                        
                        // Also update the card's dataset if it exists
                        const card = document.querySelector(`[data-custom-group-id="${groupId}"][data-level="${levelNumber}"]`);
                        if (card) {
                            card.dataset.cachedProgressData = JSON.stringify({
                                fam_counts: familiarityCounts,
                                total_words: progressData.total_words || 0,
                                score: progressData.score,
                                status: progressData.status
                            });
                        }
                        
                        completed++;
                    }
                }
            } catch (error) {
                console.log(`⚠️ Error preloading familiarity data for level ${levelNumber}:`, error.message);
            }
        }
        
        // Final progress update
        if (progressCallback) {
            progressCallback(completed, total);
        }
        
        console.log(`✅ Preloaded familiarity data for ${completed}/${total} levels`);
        
    } catch (error) {
        console.log('⚠️ Error in preloadFamiliarityDataForAllLevels:', error);
    }
}

// Update frontside of level cards with preloaded familiarity data
// Uses the same data source as backside for consistency
function updateFrontsideWithPreloadedData(groupId, levels) {
    if (!window.cachedFamiliarityData || !window.cachedFamiliarityData[groupId]) {
        return;
    }
    
    levels.forEach(level => {
        const levelNumber = level.level_number;
        const cachedFamiliarity = window.cachedFamiliarityData[groupId][levelNumber];
        
        if (!cachedFamiliarity) {
            return;
        }
        
        // Find the card element
        const card = document.querySelector(`[data-custom-group-id="${groupId}"][data-level="${levelNumber}"]`);
        if (!card) {
            return;
        }
        
        // Extract data (same as backside uses)
        const totalWords = cachedFamiliarity.total_words || 0;
        const learnedWords = cachedFamiliarity.fam_counts && cachedFamiliarity.fam_counts[5] ? cachedFamiliarity.fam_counts[5] : 0;
        // Calculate progress percent based on learned words (familiarity 5)
        // This represents actual learning progress, not session score
        let progressPercent = 0;
        if (totalWords > 0) {
            progressPercent = Math.round((learnedWords / totalWords) * 100);
        }
        
        // Update frontside elements
        const wordsText = card.querySelector('.words-text');
        if (wordsText) {
            wordsText.textContent = totalWords;
        }
        
        const learnedText = card.querySelector('.learned-text');
        if (learnedText) {
            learnedText.textContent = learnedWords;
        }
        
        const completionCircleText = card.querySelector('.completion-circle-text');
        if (completionCircleText) {
            completionCircleText.textContent = `${progressPercent}%`;
        }
        
        // Update completion circle visual (use progress_percent, not score_percent)
        updateCustomLevelCompletionCircle(card, progressPercent);
        
        // Update progress bar
        const progressFill = card.querySelector('.level-progress-fill');
        if (progressFill && totalWords > 0) {
            const progressPercent = Math.round((learnedWords / totalWords) * 100);
            progressFill.style.width = `${progressPercent}%`;
        }
        
        // Store in card's dataset for consistency
        card.dataset.cachedProgressData = JSON.stringify({
            fam_counts: cachedFamiliarity.fam_counts,
            total_words: totalWords,
            score: cachedFamiliarity.score,
            status: cachedFamiliarity.status
        });
    });
    
    console.log(`✅ Updated frontside for ${levels.length} level cards with preloaded data`);
}

// Load cached progress data for all levels in a group (ultra-fast)
async function loadCachedGroupProgress(groupId) {
    try {
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        console.log('🚀 Loading cached progress data for group:', groupId);
        const response = await fetch(`/api/custom-levels/${groupId}/progress-cache`, {
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.progress_data) {
                const normalizedCache = {};
                Object.entries(data.progress_data).forEach(([levelKey, progressValue]) => {
                    normalizedCache[levelKey] = normalizeProgressPayload(progressValue);
                });
                // Store cached progress data globally for use in level cards
                window.cachedGroupProgress = normalizedCache;
                console.log(`✅ Loaded cached progress for ${data.cached_levels} levels`);
                return true;
            }
        } else {
            console.log('⚠️ No cached progress data available, will use individual API calls');
        }
        
        return false;
        
    } catch (error) {
        console.log('⚠️ Error loading cached progress data:', error.message);
        return false;
    }
}

// Start custom level practice
async function startCustomLevelPractice(groupId, levelNumber) {
    try {
        console.log('🎯 Starting custom level practice:', groupId, levelNumber);
        
        // Get custom level data
        const response = await fetch(`/api/custom-level-groups/${groupId}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load custom level group');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to load custom level group');
        }
        
        const level = data.levels.find(l => l.level_number === levelNumber);
        if (!level) {
            throw new Error('Level not found');
        }
        
        // Set global variables for custom level context
        window.SELECTED_CUSTOM_GROUP = groupId;
        window.SELECTED_CUSTOM_LEVEL = levelNumber;
        
        // Start practice with custom level content
        if (window.startPracticeWithContent) {
            const levelTitle = String(level.title || `Custom Level ${levelNumber}`).trim();
            window.startPracticeWithContent(level.content, levelNumber, levelTitle);
        } else {
            showNotification('Übungs-Funktion nicht verfügbar', 'error');
        }
        
    } catch (error) {
        console.error('❌ Error starting custom level practice:', error);
        showNotification('Fehler beim Laden der Übung: ' + error.message, 'error');
    }
}

window.startCustomGroup = startCustomGroup;
window.renderCustomLevels = renderCustomLevels;
window.startCustomLevel = startCustomLevel;
window.startCustomLevelPractice = startCustomLevelPractice;
window.showLevelsContainer = showLevelsContainer;
window.showGroupsContainer = showGroupsContainer;
window.loadCurrentSettings = loadCurrentSettings;
window.createCustomGroup = createCustomGroup;
window.publishCustomGroup = publishCustomGroup;
window.unpublishCustomGroup = unpublishCustomGroup;
window.editCustomGroup = editCustomGroup;
window.updateCustomGroup = updateCustomGroup;
window.showEditCustomGroupModal = showEditCustomGroupModal;
window.closeEditModal = closeEditModal;
window.deleteCustomGroup = deleteCustomGroup;
window.deleteCustomGroupFromModal = deleteCustomGroupFromModal;
window.closeModal = closeModal;
window.startCustomGroup = startCustomGroup;
window.addGroupManagementToQuickAccess = addGroupManagementToQuickAccess;
window.removeGroupManagementFromQuickAccess = removeGroupManagementFromQuickAccess;
window.generateAllCustomLevelsContent = generateAllCustomLevelsContent;
window.generateAllCustomLevelsContentFallback = generateAllCustomLevelsContentFallback;
window.preloadCustomLevelData = preloadCustomLevelData;
window.renderCustomLevelsWithPreloading = renderCustomLevelsWithPreloading;
window.generateRemainingLevelsInBackground = generateRemainingLevelsInBackground;
window.updateLevelGenerationProgress = updateLevelGenerationProgress;
window.applyBasicCustomLevelProgression = applyBasicCustomLevelProgression;
window.updateWordCountsProgressively = updateWordCountsProgressively;
window.updateSingleLevelWordCount = updateSingleLevelWordCount;
window.updateLevelCardWordCount = updateLevelCardWordCount;
window.determineLevelsToGenerate = determineLevelsToGenerate;
window.getUserProgressForGroup = getUserProgressForGroup;
window.determineUnlockedLevels = determineUnlockedLevels;
window.findCurrentActiveLevel = findCurrentActiveLevel;

// Smart level generation: Determine which levels to generate based on user progress
async function determineLevelsToGenerate(groupId, allLevels, levelsNeedingGeneration) {
    try {
        console.log('🧠 Determining smart level generation strategy...');
        
        const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
        
        if (!isUserAuthenticated) {
            // For unauthenticated users, only generate level 1
            const level1 = levelsNeedingGeneration.find(level => level.level_number === 1);
            return {
                immediate: level1 ? [level1] : [],
                background: levelsNeedingGeneration.filter(level => level.level_number !== 1)
            };
        }
        
        // For authenticated users, check their progress
        const userProgress = await getUserProgressForGroup(groupId);
        const unlockedLevels = determineUnlockedLevels(userProgress, allLevels.length);
        
        console.log(`📊 User progress analysis:`, {
            totalLevels: allLevels.length,
            unlockedLevels: unlockedLevels,
            levelsNeedingGeneration: levelsNeedingGeneration.length,
            hasProgressData: Object.keys(userProgress).length > 0
        });
        
        // Determine immediate and background generation
        const immediate = [];
        const background = [];
        
        // For new groups (no progress data), only generate Level 1 immediately
        if (Object.keys(userProgress).length === 0) {
            const firstLevel = levelsNeedingGeneration.find(level => level.level_number === 1);
            if (firstLevel) {
                immediate.push(firstLevel);
                console.log(`🎯 New group detected: generating Level 1 only for immediate play`);
            }
        } else {
            // For existing groups, find the current active level (highest unlocked) that needs generation
            const currentActiveLevel = findCurrentActiveLevel(unlockedLevels, levelsNeedingGeneration);
            
            if (currentActiveLevel) {
                // Generate only the current active level (highest unlocked)
                immediate.push(currentActiveLevel);
                console.log(`🎯 Current active level to generate: Level ${currentActiveLevel.level_number}`);
            } else {
                // If no specific level needs immediate generation, generate first level only
                const firstLevel = levelsNeedingGeneration.find(level => level.level_number === 1);
                if (firstLevel) {
                    immediate.push(firstLevel);
                    console.log(`🎯 No specific level needed, generating Level 1 only`);
                }
            }
        }
        
        // Put remaining levels in background
        const immediateLevelNumbers = immediate.map(l => l.level_number);
        background.push(...levelsNeedingGeneration.filter(level => 
            !immediateLevelNumbers.includes(level.level_number)
        ));
        
        console.log(`📋 Smart generation plan (current active level only):`, {
            immediate: immediate.map(l => l.level_number),
            background: background.map(l => l.level_number),
            strategy: 'Generate only current active level for optimal resource usage'
        });
        
        return { immediate, background };
        
    } catch (error) {
        console.error('Error determining levels to generate:', error);
        // Fallback: generate first 2 levels
        return {
            immediate: levelsNeedingGeneration.slice(0, 2),
            background: levelsNeedingGeneration.slice(2)
        };
    }
}

// Get user progress for a custom level group
async function getUserProgressForGroup(groupId) {
    try {
        const response = await fetch(`/api/custom-levels/${groupId}/bulk-stats`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                return data.levels || {};
            }
        }
    } catch (error) {
        console.log('Could not fetch user progress, using defaults:', error);
    }
    
    return {};
}

// Helper function to check if level is completed based on progress (familiarity counts)
// Helper function to calculate Familiarity 5 percentage
function getFamiliarity5Percent(levelData) {
    if (!levelData) return 0;
    const famCounts = levelData.fam_counts || {};
    const totalWords = levelData.total_words || 0;
    if (totalWords === 0) return 0;
    const fam5Words = famCounts[5] || 0;
    return (fam5Words / totalWords) * 100;
}

// Helper function to check if level has >50% Familiarity 5 (for unlocking next level)
function hasFamiliarity5Above50(levelData) {
    return getFamiliarity5Percent(levelData) > 50;
}

// Helper function to check if level has >90% Familiarity 5 (for gold status)
function hasFamiliarity5Above90(levelData) {
    return getFamiliarity5Percent(levelData) > 90;
}

function isLevelCompletedByProgress(levelData) {
    if (!levelData) return false;
    
    // Check status first
    const status = levelData.user_progress?.status || levelData.status;
    if (status === 'completed') {
        // Verify with familiarity counts: ≥80% words at familiarity ≥3
        const famCounts = levelData.fam_counts || {};
        const totalWords = levelData.total_words || 0;
        if (totalWords === 0) return false;
        
        const learnedWords = (famCounts[5] || 0) + (famCounts[4] || 0) + (famCounts[3] || 0);
        const learnedPercent = (learnedWords / totalWords) * 100;
        return learnedPercent >= 80;
    }
    return false;
}

// Determine which levels should be unlocked based on user progress
function determineUnlockedLevels(userProgress, totalLevels) {
    const unlockedLevels = [];
    
    for (let levelNum = 1; levelNum <= totalLevels; levelNum++) {
        const levelData = userProgress[levelNum];
        
        if (levelNum === 1) {
            // Level 1 is always unlocked
            unlockedLevels.push(levelNum);
        } else {
            // Check if previous level has score >= 60 (ready check based on score)
            const prevLevelData = userProgress[levelNum - 1];
            if (prevLevelData && prevLevelData.success) {
                // Get score from previous level (0-1 or 0-100)
                const prevScore = prevLevelData.user_progress?.score || prevLevelData.last_score || 0;
                // Normalize score to 0-100
                const prevScoreNormalized = normalizeScoreValue(prevScore);
                const prevScorePercent = prevScoreNormalized * 100;
                const prevHasScoreAbove60 = prevScorePercent >= 60;
                
                if (prevHasScoreAbove60) {
                    unlockedLevels.push(levelNum);
                } else {
                    // Stop at first locked level
                    break;
                }
            } else {
                // Stop at first level without data
                break;
            }
        }
    }
    
    return unlockedLevels;
}

// Find the current active level (highest unlocked) that needs generation
function findCurrentActiveLevel(unlockedLevels, levelsNeedingGeneration) {
    // Find the highest unlocked level
    const highestUnlocked = Math.max(...unlockedLevels, 0);
    
    // Find the current active level (highest unlocked) that needs generation
    const currentActiveLevel = levelsNeedingGeneration.find(level => 
        level.level_number === highestUnlocked
    );
    
    return currentActiveLevel;
}

// Progressive word count updates (one level at a time for better UX)
async function updateWordCountsProgressively(groupId, levels) {
    try {
        console.log('📊 Starting progressive word count updates...');
        
        // Only update first 3 levels immediately, others in background
        const immediateLevels = levels.slice(0, 3);
        const backgroundLevels = levels.slice(3);
        
        // Update immediate levels in parallel for faster feedback
        const immediatePromises = immediateLevels.map(level => 
            updateSingleLevelWordCount(groupId, level.level_number)
        );
        await Promise.all(immediatePromises);
        
        // Update remaining levels in background (batched)
        if (backgroundLevels.length > 0) {
            console.log(`🔄 Updating ${backgroundLevels.length} remaining levels in background...`);
            updateRemainingLevelWordCounts(groupId, backgroundLevels);
        }
        
    } catch (error) {
        console.error('Error in progressive word count updates:', error);
    }
}

// Update word count for a single level
async function updateSingleLevelWordCount(groupId, levelNumber) {
    try {
        // Check if we already have cached data from setCustomLevelColor
        const levelCard = document.querySelector(`.level-card[data-level="${levelNumber}"][data-custom-group-id="${groupId}"]`);
        if (levelCard && levelCard.dataset.bulkData) {
            try {
                const cachedData = JSON.parse(levelCard.dataset.bulkData);
                // If we have cached data with valid fam_counts, use it instead of making another API call
                const totalCached = Object.values(cachedData.fam_counts || {}).reduce((sum, count) => sum + (Number(count) || 0), 0);
                if (totalCached > 0) {
                    console.log(`✅ Using cached data for level ${levelNumber}: ${totalCached} words (skipping API call)`);
                    return;
                }
            } catch (e) {
                // If parsing fails, continue with API call
            }
        }
        
        const response = await fetch(`/api/custom-levels/${groupId}/${levelNumber}/progress`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success) {
                updateLevelCardWordCount(groupId, levelNumber, data);
                console.log(`✅ Updated word count for level ${levelNumber}: ${data.total_words} words`);
            }
        }
    } catch (error) {
        console.log(`⚠️ Failed to update word count for level ${levelNumber}:`, error);
    }
}

// Update remaining levels in batches
async function updateRemainingLevelWordCounts(groupId, levels) {
    const batchSize = 4; // Increased from 2 to 4 for faster processing
    const batches = [];
    
    for (let i = 0; i < levels.length; i += batchSize) {
        batches.push(levels.slice(i, i + batchSize));
    }
    
    for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
        const batch = batches[batchIndex];
        
        // Process batch in parallel
        const promises = batch.map(level => updateSingleLevelWordCount(groupId, level.level_number));
        await Promise.all(promises);
        
        // Minimal delay between batches (reduced from 1000ms to 200ms)
        if (batchIndex < batches.length - 1) {
            await new Promise(resolve => setTimeout(resolve, 200));
        }
    }
}

// Update the visual word count on a level card
function updateLevelCardWordCount(groupId, levelNumber, progressData) {
    const normalized = updateCustomLevelCardProgress(groupId, levelNumber, progressData);
    if (normalized) {
        console.log(`📊 Level ${levelNumber} updated: ${normalized.total_words} total, ${normalized.completed_words} learned, ${normalized.score_percent}% score`);
    }
}

// Show creation progress modal
function showCreationProgressModal() {
    // Remove any existing progress modal first
    const existingModal = document.getElementById('creation-progress-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modalHtml = `
        <div class="modal-overlay" id="creation-progress-modal">
            <div class="modal-content creation-progress-modal" style="max-width: 400px; text-align: center;">
                <div class="modal-body">
                    <div style="padding: 2rem;">
                        <div style="font-size: 3rem; margin-bottom: 1rem;">🎯</div>
                        <h2 style="margin-bottom: 1rem; color: #333;">Level werden erstellt...</h2>
                        <div style="color: #666; font-size: 0.9rem; margin-bottom: 1.5rem;">
                            Das dauert nur wenige Sekunden
                            </div>
                        <div class="simple-spinner" style="
                            width: 40px; 
                            height: 40px; 
                            border: 4px solid #f3f3f3; 
                            border-top: 4px solid #007bff; 
                            border-radius: 50%; 
                            animation: spin 1s linear infinite;
                            margin: 0 auto;
                        "></div>
                            </div>
                            </div>
                            </div>
                            </div>
        <style>
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }
            .spinner-small {
                animation: spin 1s linear infinite;
            }
        </style>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
}

// Add CSS styles for generating status
function addGeneratingStatusStyles() {
    const styleId = 'custom-levels-generating-styles';
    if (document.getElementById(styleId)) return; // Already added
    
    const styles = `
        <style id="${styleId}">
            .level-card.generating {
                opacity: 0.8;
                position: relative;
            }
            
            .level-card.generating::before {
                content: '';
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: linear-gradient(45deg, transparent 30%, rgba(0, 123, 255, 0.1) 50%, transparent 70%);
                animation: shimmer 2s infinite;
                pointer-events: none;
                z-index: 1;
            }
            
            .level-status.generating {
                color: #007bff;
                font-weight: 600;
                animation: pulse 1.5s infinite;
            }
            
            @keyframes shimmer {
                0% { transform: translateX(-100%); }
                100% { transform: translateX(100%); }
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.6; }
            }
            
            .level-card.generating .level-btn {
                opacity: 0.9; /* keep visible but allow clicks to start/generate */
            }
            
            .level-status.error {
                color: #dc3545;
                font-weight: 600;
            }
            
            .level-card.error {
                border: 2px solid #dc3545;
                opacity: 0.7;
            }
        </style>
    `;
    
    document.head.insertAdjacentHTML('beforeend', styles);
}

// Initialize styles when the module loads
addGeneratingStatusStyles();

// Preload level data for better performance (optimized - only first few levels)
async function preloadCustomLevelData(groupId, levels) {
    try {
        console.log('🚀 Preloading custom level data for better performance...');
        
        // Only preload first 5 levels to avoid overwhelming the system
        const levelsToPreload = levels.slice(0, 5).filter(level => {
            const content = level.content || {};
            return !content.ultra_lazy_loading || content.sentences_generated;
        });
        
        if (levelsToPreload.length === 0) {
            console.log('📝 No levels to preload');
            return;
        }
        
        console.log(`📦 Preloading data for first ${levelsToPreload.length} levels only`);
        
        // Preload in background without blocking UI (with timeout to prevent hanging)
        const preloadPromises = levelsToPreload.map(async (level) => {
            try {
                // Add timeout to prevent hanging requests
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 10000); // 10 second timeout
                
                const response = await fetch(`/api/custom-levels/${groupId}/${level.level_number}/progress`, {
                    headers: {
                        'Authorization': `Bearer ${localStorage.getItem('session_token')}`
                    },
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    const data = await response.json();
                    if (data.success) {
                        // Cache the progress data for faster rendering
                        const levelCard = document.querySelector(`.level-card[data-level="${level.level_number}"][data-custom-group-id="${groupId}"]`);
                        const totalWords = Number(data.total_words || 0);
                        const completedWords = Number(data.completed_words || 0);
                        const remainingWords = Math.max(0, totalWords - completedWords);
                        const syntheticCounts = {
                            0: remainingWords,
                            1: 0,
                            2: 0,
                            3: 0,
                            4: 0,
                            5: completedWords
                        };
                        const normalized = applyCustomLevelProgressData(
                            levelCard || null,
                            {
                                fam_counts: syntheticCounts,
                                total_words: totalWords,
                                score: data.level_score !== undefined ? data.level_score : data.score,
                                status: data.status || 'not_started',
                                completed_at: data.completed_at,
                                last_updated: data.last_updated
                            }
                        );
                        if (!window.cachedGroupProgress) window.cachedGroupProgress = {};
                        window.cachedGroupProgress[level.level_number] = normalized;
                    }
                }
            } catch (error) {
                if (error.name === 'AbortError') {
                    console.log(`⏰ Preload timeout for level ${level.level_number}`);
                } else {
                    console.log(`⚠️ Failed to preload data for level ${level.level_number}:`, error);
                }
            }
        });
        
        // Fire and forget - don't wait for completion
        Promise.all(preloadPromises).catch(() => {});
        
        console.log(`✅ Started preloading data for ${levelsToPreload.length} levels`);
        
    } catch (error) {
        console.log('⚠️ Error in preloading:', error);
    }
}

// Generate remaining levels in background without blocking UI
async function generateRemainingLevelsInBackground(groupId, remainingLevels) {
    try {
        console.log(`🔄 Background generation started for ${remainingLevels.length} levels`);
        
        // For small numbers of levels, generate all at once for maximum speed
        if (remainingLevels.length <= 6) {
            console.log(`🚀 Generating all ${remainingLevels.length} levels in parallel for maximum speed`);
            
            try {
                const batchResult = await generateAllCustomLevelsContent(groupId, remainingLevels);
                
                if (batchResult.successful > 0) {
                    console.log(`✅ All levels completed: ${batchResult.successful} levels generated`);
                    updateLevelGenerationProgress(groupId, remainingLevels, true);
                }
                
                if (batchResult.failed > 0) {
                    console.warn(`⚠️ ${batchResult.failed} levels failed to generate`);
                    updateLevelGenerationProgress(groupId, remainingLevels, false);
                }
                
            } catch (error) {
                console.error(`❌ Error generating all levels:`, error);
                updateLevelGenerationProgress(groupId, remainingLevels, false);
            }
        } else {
            // For larger numbers, use optimized batching
            const batchSize = 4; // Increased from 3 to 4 for faster generation
            const batches = [];
            
            for (let i = 0; i < remainingLevels.length; i += batchSize) {
                batches.push(remainingLevels.slice(i, i + batchSize));
            }
            
            console.log(`📦 Processing ${batches.length} batches of ${batchSize} levels each`);
            
            // Process batches with minimal delays for faster completion
            for (let batchIndex = 0; batchIndex < batches.length; batchIndex++) {
                const batch = batches[batchIndex];
                console.log(`🔄 Processing batch ${batchIndex + 1}/${batches.length} (${batch.length} levels)`);
                
                try {
                    // Generate batch
                    const batchResult = await generateAllCustomLevelsContent(groupId, batch);
                    
                    if (batchResult.successful > 0) {
                        console.log(`✅ Batch ${batchIndex + 1} completed: ${batchResult.successful} levels generated`);
                        
                        // Update UI to show progress
                        updateLevelGenerationProgress(groupId, batch, true);
                    }
                    
                    if (batchResult.failed > 0) {
                        console.warn(`⚠️ Batch ${batchIndex + 1} had ${batchResult.failed} failures`);
                        updateLevelGenerationProgress(groupId, batch, false);
                    }
                    
                } catch (error) {
                    console.error(`❌ Error in batch ${batchIndex + 1}:`, error);
                    updateLevelGenerationProgress(groupId, batch, false);
                }
                
                // Minimal delay between batches (reduced from 500ms to 200ms)
                if (batchIndex < batches.length - 1) {
                    console.log(`⏳ Waiting 200ms before next batch...`);
                    await new Promise(resolve => setTimeout(resolve, 200));
                }
            }
        }
        
        console.log(`🎉 Background generation completed for all ${remainingLevels.length} levels`);
        
        // Show completion notification
        showNotification(`✅ Alle ${remainingLevels.length} Level wurden im Hintergrund generiert!`, 'success');
        
    } catch (error) {
        console.error('❌ Error in background generation:', error);
        showNotification('⚠️ Einige Level konnten nicht im Hintergrund generiert werden.', 'warning');
    }
}

// Update level generation progress in UI
function updateLevelGenerationProgress(groupId, levels, success) {
    levels.forEach(level => {
        const levelCard = document.querySelector(`.level-card[data-level="${level.level_number}"][data-custom-group-id="${groupId}"]`);
        if (levelCard) {
            if (success) {
                levelCard.classList.remove('generating');
                const statusElement = levelCard.querySelector('.level-status');
                if (statusElement) {
                    statusElement.textContent = window.t ? window.t('status.available', 'Available') : 'Available';
                    statusElement.classList.remove('generating');
                }
            } else {
                const statusElement = levelCard.querySelector('.level-status');
                if (statusElement) {
                    statusElement.textContent = 'Fehler beim Generieren';
                    statusElement.classList.add('error');
                }
            }
        }
    });
}

// Enhanced level rendering with preloading (optimized for speed)
function renderCustomLevelsWithPreloading(groupId, levels) {
    // Render levels first with estimated word counts
    renderCustomLevels(groupId, levels);
    
    // Apply basic progression immediately (fast path)
    applyBasicCustomLevelProgression(groupId, levels);
    
    // Note: Preloading is now handled in startCustomGroup with loading screen integration
    // This function is kept for backward compatibility but preloading happens there
}

// Simple progress animation (no longer needed with ultra-lazy loading)
function startProgressAnimation() {
    // Animation removed - ultra-lazy loading is so fast that complex progress tracking is unnecessary
    // The simple spinner in the modal is sufficient
}

// Close creation progress modal
function closeCreationProgressModal() {
    const modal = document.getElementById('creation-progress-modal');
    if (modal) {
        modal.remove();
    }
}

// Export progress modal functions
window.showCreationProgressModal = showCreationProgressModal;
window.closeCreationProgressModal = closeCreationProgressModal;

// Apply user-specific level progression logic for custom levels
async function applyCustomLevelProgression(levelElement, levelNumber, groupId) {
    try {
        console.log(`🔒 Applying custom level progression for level ${levelNumber} in group ${groupId}`);
        
        // Check if user is authenticated
        const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
        
        if (!isUserAuthenticated) {
            // For unauthenticated users, only level 1 is available
            if (levelNumber === 1) {
                levelElement.classList.add('unlocked');
                levelElement.classList.remove('locked', 'done');
                levelElement.dataset.allowStart = 'true';
                console.log(`Level ${levelNumber} unlocked for unauthenticated user (Level 1)`);
            } else {
                levelElement.classList.add('locked');
                levelElement.classList.remove('unlocked', 'done');
                console.log(`Level ${levelNumber} locked for unauthenticated user`);
            }
            return;
        }
        
        // For authenticated users, fetch bulk stats to determine progression
        const headers = {};
        if (window.authManager && window.authManager.isAuthenticated()) {
            Object.assign(headers, window.authManager.getAuthHeaders());
        }
        
        const response = await fetch(`/api/custom-levels/${groupId}/bulk-stats`, {
            headers: headers
        });
        
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.levels) {
                // Apply the same logic as standard levels
                const levelData = data.levels[levelNumber];
                if (levelData && levelData.success) {
                    const userProgress = levelData.user_progress;
                    const status = userProgress?.status || levelData.status;
                    const score = userProgress?.score || levelData.last_score;
                    
                    let isUnlocked = false;
                    
                    // Normalize score first (handles both 0-1 and 0-100 formats)
                    const normalizedScore = normalizeScoreValue(score);
                    
                    if (status === 'completed' && normalizedScore > 0.6) {
                        // Level completed with good score
                        isUnlocked = true;
                        levelElement.classList.add('done');
                        levelElement.classList.remove('locked', 'unlocked');
                        console.log(`Custom level ${levelNumber} marked as completed (Score > 0.6)`);
                    } else if (status === 'completed' && normalizedScore <= 0.6) {
                        // Level completed but low score
                        isUnlocked = true;
                        levelElement.classList.add('unlocked');
                        levelElement.classList.remove('locked', 'done');
                        console.log(`Custom level ${levelNumber} marked as unlocked (completed but low score)`);
                    } else if (levelNumber === 1) {
                        // Level 1 is always available
                        isUnlocked = true;
                        levelElement.classList.add('unlocked');
                        levelElement.classList.remove('locked', 'done');
                        console.log(`Custom level ${levelNumber} marked as unlocked (Level 1)`);
                    } else if (levelNumber > 1) {
                        // Check if previous level has score >= 60 (ready check based on score)
                        const prevLevel = levelNumber - 1;
                        const prevLevelData = data.levels[prevLevel];
                        if (prevLevelData && prevLevelData.success) {
                            // Get score from previous level (0-1 or 0-100)
                            const prevScore = prevLevelData.user_progress?.score || prevLevelData.last_score || 0;
                            // Normalize score to 0-100
                            const prevScoreNormalized = normalizeScoreValue(prevScore);
                            const prevScorePercent = prevScoreNormalized * 100;
                            const prevHasScoreAbove60 = prevScorePercent >= 60;
                            
                            if (prevHasScoreAbove60) {
                                isUnlocked = true;
                                levelElement.classList.add('unlocked');
                                levelElement.classList.remove('locked', 'done');
                                console.log(`Custom level ${levelNumber} unlocked (previous level ${prevLevel} has Score >= 60)`);
                            } else {
                                levelElement.classList.add('locked');
                                levelElement.classList.remove('unlocked', 'done');
                                console.log(`Custom level ${levelNumber} locked (previous level ${prevLevel} has Score < 60)`);
                            }
                        } else {
                            levelElement.classList.add('locked');
                            levelElement.classList.remove('unlocked', 'done');
                            console.log(`Custom level ${levelNumber} locked (previous level ${prevLevel} data not available)`);
                        }
                    } else {
                        levelElement.classList.add('locked');
                        levelElement.classList.remove('unlocked', 'done');
                        console.log(`Custom level ${levelNumber} locked (fallback)`);
                    }
                    
                    // Set allowStart flag for unlocked levels
                    if (isUnlocked) {
                        levelElement.dataset.allowStart = 'true';
                    } else {
                        levelElement.dataset.allowStart = 'false';
                    }
                    
                    // Cache the data for later use
                    levelElement.dataset.bulkData = JSON.stringify(levelData);
                } else {
                    // Level data not found
                    if (levelNumber === 1) {
                        levelElement.classList.add('unlocked');
                        levelElement.classList.remove('locked', 'done');
                        levelElement.dataset.allowStart = 'true';
                        console.log(`Custom level ${levelNumber} unlocked (Level 1 - no data fallback)`);
                    } else {
                        levelElement.classList.add('locked');
                        levelElement.classList.remove('unlocked', 'done');
                        console.log(`Custom level ${levelNumber} locked (no data)`);
                    }
                }
            } else {
                // API response not successful
                if (levelNumber === 1) {
                    levelElement.classList.add('unlocked');
                    levelElement.classList.remove('locked', 'done');
                    levelElement.dataset.allowStart = 'true';
                    console.log(`Custom level ${levelNumber} unlocked (Level 1 - API error fallback)`);
                } else {
                    levelElement.classList.add('locked');
                    levelElement.classList.remove('unlocked', 'done');
                    console.log(`Custom level ${levelNumber} locked (API error)`);
                }
            }
        } else {
            // API request failed
            if (levelNumber === 1) {
                levelElement.classList.add('unlocked');
                levelElement.classList.remove('locked', 'done');
                levelElement.dataset.allowStart = 'true';
                console.log(`Custom level ${levelNumber} unlocked (Level 1 - request error fallback)`);
            } else {
                levelElement.classList.add('locked');
                levelElement.classList.remove('unlocked', 'done');
                console.log(`Custom level ${levelNumber} locked (request error)`);
            }
        }
        
    } catch (error) {
        console.error(`Error applying custom level progression for level ${levelNumber}:`, error);
        // Fallback: only level 1 unlocked
        if (levelNumber === 1) {
            levelElement.classList.add('unlocked');
            levelElement.classList.remove('locked', 'done');
            levelElement.dataset.allowStart = 'true';
        } else {
            levelElement.classList.add('locked');
            levelElement.classList.remove('unlocked', 'done');
        }
    }
}

// Export the function globally
window.applyCustomLevelProgression = applyCustomLevelProgression;

// Fast basic progression (immediate, no API calls)
function applyBasicCustomLevelProgression(groupId, levels) {
    try {
        console.log('⚡ Applying basic custom level progression (fast path)');
        
        const levelsContainer = document.getElementById('levels');
        if (!levelsContainer) return;
        
        const levelCards = levelsContainer.querySelectorAll('.level-card[data-custom-group-id="' + groupId + '"]');
        const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
        
        levelCards.forEach(card => {
            const levelNumber = parseInt(card.dataset.level);
            
            if (!isUserAuthenticated) {
                // For unauthenticated users, only level 1 is available
                if (levelNumber === 1) {
                    card.classList.add('unlocked');
                    card.classList.remove('locked', 'done');
                    card.dataset.allowStart = 'true';
                } else {
                    card.classList.add('locked');
                    card.classList.remove('unlocked', 'done');
                }
            } else {
                // For authenticated users, unlock level 1 immediately
                // Other levels will be unlocked after bulk stats API call
                if (levelNumber === 1) {
                    card.classList.add('unlocked');
                    card.classList.remove('locked', 'done');
                    card.dataset.allowStart = 'true';
                } else {
                    // Mark as locked initially, will be updated by bulk API
                    card.classList.add('locked');
                    card.classList.remove('unlocked', 'done');
                }
            }
        });
        
        console.log('✅ Basic progression applied - Level 1 unlocked immediately');
        
        // Start detailed progression in background (non-blocking)
        setTimeout(() => {
            applyCustomLevelProgressionBulk(levelsContainer, groupId);
        }, 500);
        
    } catch (error) {
        console.error('Error applying basic custom level progression:', error);
    }
}

// Bulk apply custom level progression (performance optimized)
async function applyCustomLevelProgressionBulk(levelsContainer, groupId) {
    try {
        console.log(`🔒 Applying bulk custom level progression for group ${groupId}`);
        
        // Check if user is authenticated
        const isUserAuthenticated = window.authManager && window.authManager.isAuthenticated();
        
        if (!isUserAuthenticated) {
            // For unauthenticated users, only level 1 is available
            const levelCards = levelsContainer.querySelectorAll('.level-card');
            levelCards.forEach(card => {
                const levelNumber = parseInt(card.dataset.level);
                if (levelNumber === 1) {
                    card.classList.add('unlocked');
                    card.classList.remove('locked', 'done');
                    card.dataset.allowStart = 'true';
                } else {
                    card.classList.add('locked');
                    card.classList.remove('unlocked', 'done');
                }
            });
            console.log(`Applied bulk progression for unauthenticated user - only level 1 unlocked`);
            return;
        }
        
        // For authenticated users, use preloaded familiarity data (same source as score display)
        // Fallback to cachedGroupProgress if familiarity data not available yet
        const familiarityData = window.cachedFamiliarityData && window.cachedFamiliarityData[groupId] 
            ? window.cachedFamiliarityData[groupId] 
            : null;
        
        // Fallback: load cachedGroupProgress if familiarity data not available
        if (!familiarityData) {
            if (!window.cachedGroupProgress || Object.keys(window.cachedGroupProgress).length === 0) {
                await loadCachedGroupProgress(groupId);
            }
        }

        const progressMap = window.cachedGroupProgress || {};
        const levelCards = levelsContainer.querySelectorAll('.level-card');

        levelCards.forEach(card => {
            const levelNumber = parseInt(card.dataset.level);
            
            // Use familiarity data if available (same source as score display), otherwise use progressMap
            let levelData = null;
            let prevLevelData = null;
            
            if (familiarityData && familiarityData[levelNumber]) {
                // Use preloaded familiarity data (same as score display)
                const cachedFamiliarity = familiarityData[levelNumber];
                // Normalize to match progressMap format
                const normalizedScore = normalizeScoreValue(cachedFamiliarity.score);
                levelData = {
                    status: cachedFamiliarity.status,
                    score: normalizedScore,
                    score_percent: Math.round(normalizedScore * 100),
                    total_words: cachedFamiliarity.total_words || 0,
                    completed_words: cachedFamiliarity.fam_counts && cachedFamiliarity.fam_counts[5] ? cachedFamiliarity.fam_counts[5] : 0,
                    fam_counts: cachedFamiliarity.fam_counts || {} // Include full fam_counts for applyCustomLevelProgressData
                };
            } else {
                // Fallback to progressMap
                levelData = progressMap[levelNumber];
            }
            
            // Get previous level data using same logic
            if (familiarityData && familiarityData[levelNumber - 1]) {
                const prevCachedFamiliarity = familiarityData[levelNumber - 1];
                const prevNormalizedScore = normalizeScoreValue(prevCachedFamiliarity.score);
                prevLevelData = {
                    status: prevCachedFamiliarity.status,
                    score: prevNormalizedScore, // Normalized score (0-1) for comparison
                    score_percent: Math.round(prevNormalizedScore * 100) // Percent (0-100) for display
                };
            } else {
                prevLevelData = progressMap[levelNumber - 1];
                // Normalize score if it exists in progressMap
                if (prevLevelData && prevLevelData.score !== undefined) {
                    prevLevelData.score = normalizeScoreValue(prevLevelData.score);
                } else if (prevLevelData && prevLevelData.score_percent !== undefined) {
                    // Convert score_percent to normalized score (0-1)
                    prevLevelData.score = prevLevelData.score_percent / 100;
                }
            }

            card.classList.remove('locked', 'unlocked', 'done', 'gold');

            if (levelData) {
                try {
                    // Apply progress data to update frontside display (total_words, familiarity_5, score)
                    applyCustomLevelProgressData(card, levelData);
                    
                    // Update title from bulk-stats if available
                    if (levelData.title && levelData.title !== `Level ${levelNumber}`) {
                        const titleEl = card.querySelector('.level-title');
                        if (titleEl) {
                            titleEl.textContent = levelData.title;
                            console.log(`✅ Updated custom level ${levelNumber} title in bulk: ${levelData.title}`);
                        }
                    }
                } catch (_e) { /* ignore */ }
            }

            // Calculate Familiarity 5 percentage (unified logic)
            const fam5Percent = getFamiliarity5Percent(levelData);
            const prevFam5Percent = getFamiliarity5Percent(prevLevelData);
            
            // Check if previous level has score >= 60 (ready check based on score)
            let prevHasScoreAbove60 = false;
            if (prevLevelData) {
                // Get score from previous level
                // If prevLevelData comes from familiarityData, it has score/score_percent directly
                // If prevLevelData comes from progressMap, it has user_progress.score or last_score
                let prevScore = 0;
                if (prevLevelData.score !== undefined) {
                    // Already normalized (from familiarityData)
                    prevScore = prevLevelData.score;
                } else if (prevLevelData.score_percent !== undefined) {
                    // Convert percent to normalized (0-1)
                    prevScore = prevLevelData.score_percent / 100;
                } else if (prevLevelData.user_progress?.score !== undefined) {
                    // From progressMap with user_progress
                    prevScore = prevLevelData.user_progress.score;
                } else if (prevLevelData.last_score !== undefined) {
                    // From progressMap with last_score
                    prevScore = prevLevelData.last_score;
                }
                
                // Normalize score to 0-100
                const prevScoreNormalized = normalizeScoreValue(prevScore);
                const prevScorePercent = prevScoreNormalized * 100;
                prevHasScoreAbove60 = prevScorePercent >= 60;
            }
            
            // Debug logging
            if (levelNumber > 1) {
                console.log(`🔓 Level ${levelNumber} unlock check:`, {
                    prevLevel: levelNumber - 1,
                    prevLevelData: prevLevelData,
                    prevFam5Percent: prevFam5Percent,
                    prevHasScoreAbove60: prevHasScoreAbove60,
                    currentFam5Percent: fam5Percent,
                    familiarityDataExists: !!familiarityData,
                    familiarityDataForPrevLevel: familiarityData && familiarityData[levelNumber - 1]
                });
            }

            // Unified unlock logic: Level 1 OR previous level has score >= 60
            let allowStart = false;
            if (levelNumber === 1) {
                allowStart = true;
            } else if (prevHasScoreAbove60) {
                allowStart = true;
            } else if (!prevLevelData) {
                // If no data for previous level, check if it exists in familiarity data
                // Maybe the previous level hasn't been started yet, so it should be locked
                console.log(`⚠️ Level ${levelNumber}: No data for previous level ${levelNumber - 1}`);
            }

            // Unified color logic based on Familiarity 5:
            // Gold: >90% with Familiarity 5
            // Green: >50% with Familiarity 5
            // Blue/Gray: handled by unlock logic below
            card.classList.remove('done', 'gold');
            if (hasFamiliarity5Above90(levelData)) {
                card.classList.add('gold');
            } else if (hasFamiliarity5Above50(levelData)) {
                card.classList.add('done');
            }
            // If <50%, no color class (stays blue/gray based on unlock status)

            if (allowStart) {
                card.classList.add('unlocked');
                card.dataset.allowStart = 'true';
            } else {
                card.classList.add('locked');
                card.dataset.allowStart = 'false';
            }
        });
        
    } catch (error) {
        console.error(`Error applying bulk custom level progression:`, error);
        // Fallback: only level 1 unlocked
        const levelCards = levelsContainer.querySelectorAll('.level-card');
        levelCards.forEach(card => {
            const levelNumber = parseInt(card.dataset.level);
            if (levelNumber === 1) {
                card.classList.add('unlocked');
                card.classList.remove('locked', 'done');
                card.dataset.allowStart = 'true';
            } else {
                card.classList.add('locked');
                card.classList.remove('unlocked', 'done');
            }
        });
    }
}

// Export the bulk function globally
window.applyCustomLevelProgressionBulk = applyCustomLevelProgressionBulk;

// Show custom level locked message (similar to standard levels)
function showCustomLevelLockedMessage(level, prevLevel, prevScore) {
    // Remove any existing message
    hideCustomLevelLockedMessage();
    
    // Create overlay
    const overlay = document.createElement('div');
    overlay.className = 'level-locked-overlay';
    overlay.id = 'custom-level-locked-overlay';
    
    // Create message
    const message = document.createElement('div');
    message.className = 'level-locked-message';
    message.id = 'custom-level-locked-message';
    
    // prevScore is already in percent (0-100), no need to multiply
    const progressPercent = Math.round(prevScore || 0);
    const neededPercent = 60;
    
    message.innerHTML = `
        <div class="icon">🔒</div>
        <div class="title">Level ${level} ist gesperrt</div>
        <div class="message">
            Du musst Level ${prevLevel} mit mindestens ${neededPercent}% abschließen, 
            um Level ${level} freizuschalten.
                        </div>
        <div class="progress-info">
            <div class="progress-text">Level ${prevLevel} Fortschritt: ${progressPercent}%</div>
                        <div class="progress-bar">
                <div class="progress-fill" style="width: ${Math.min(progressPercent, 100)}%"></div>
                        </div>
            <div class="progress-text">Benötigt: ${neededPercent}%</div>
                        </div>
        <div class="actions">
            <button class="btn btn-primary" onclick="goToPreviousCustomLevel(${prevLevel})">
                Level ${prevLevel} fortsetzen
            </button>
            <button class="btn btn-secondary" onclick="hideCustomLevelLockedMessage()">
                Schließen
            </button>
        </div>
    `;
    
    // Add to DOM
    document.body.appendChild(overlay);
    document.body.appendChild(message);
    
    // Close on overlay click
    overlay.onclick = (e) => {
        if (e.target === overlay) {
            hideCustomLevelLockedMessage();
        }
    };
    
    // Close on Escape key
    const handleEscape = (e) => {
        if (e.key === 'Escape') {
            hideCustomLevelLockedMessage();
            document.removeEventListener('keydown', handleEscape);
        }
    };
    document.addEventListener('keydown', handleEscape);
}

// Hide custom level locked message
function hideCustomLevelLockedMessage() {
    const overlay = document.getElementById('custom-level-locked-overlay');
    const message = document.getElementById('custom-level-locked-message');
    
    if (overlay) overlay.remove();
    if (message) message.remove();
}

// Go to previous custom level
function goToPreviousCustomLevel(level) {
    hideCustomLevelLockedMessage();
    
    // Find the current custom group context
    const currentGroupElement = document.querySelector('.custom-level-group[data-group-id]');
    if (currentGroupElement) {
        const groupId = currentGroupElement.dataset.groupId;
        if (groupId) {
            // Start the previous level in the same group
            if (typeof window.startCustomLevel === 'function') {
                window.startCustomLevel(groupId, level);
            }
        }
    }
}

// Export custom level locked message functions globally
window.showCustomLevelLockedMessage = showCustomLevelLockedMessage;
window.hideCustomLevelLockedMessage = hideCustomLevelLockedMessage;
window.goToPreviousCustomLevel = goToPreviousCustomLevel;

// Handle custom level start with lock checking
function handleCustomLevelStart(groupId, levelNumber) {
    try {
        console.log(`🎯 Handling custom level start: group ${groupId}, level ${levelNumber}`);
        
        // Find the level card element
        const levelCard = document.querySelector(`.level-card[data-level="${levelNumber}"][data-custom-group-id="${groupId}"]`);
        if (!levelCard) {
            console.error(`Level card not found for group ${groupId}, level ${levelNumber}`);
            return;
        }
        
        // Check if level is locked
        if (levelCard.classList.contains('locked')) {
            console.log(`Level ${levelNumber} is locked, showing locked message`);
            
            // Get previous level data to show progress (use same data source as score display)
            const prevLevel = levelNumber - 1;
            let prevScore = 0;
            
            // Try to get previous level score from preloaded familiarity data (same as score display)
            const familiarityData = window.cachedFamiliarityData && window.cachedFamiliarityData[groupId] 
                ? window.cachedFamiliarityData[groupId] 
                : null;
            
            if (familiarityData && familiarityData[prevLevel]) {
                const prevCachedFamiliarity = familiarityData[prevLevel];
                const prevNormalizedScore = normalizeScoreValue(prevCachedFamiliarity.score);
                prevScore = Math.round(prevNormalizedScore * 100); // Convert to percent (0-100) for display
            } else {
                // Fallback: try to get from card's cached data
                const prevLevelCard = document.querySelector(`.level-card[data-level="${prevLevel}"][data-custom-group-id="${groupId}"]`);
                if (prevLevelCard && prevLevelCard.dataset.bulkData) {
                    try {
                        const prevData = JSON.parse(prevLevelCard.dataset.bulkData);
                        const rawScore = prevData.user_progress?.score || prevData.last_score || 0;
                        const normalizedScore = normalizeScoreValue(rawScore);
                        prevScore = Math.round(normalizedScore * 100); // Convert to percent (0-100) for display
                    } catch (error) {
                        console.log('Error parsing previous level data:', error);
                    }
                }
            }
            
            // Show locked message (prevScore is already in percent 0-100)
            showCustomLevelLockedMessage(levelNumber, prevLevel, prevScore);
            return;
        }
        
        // Level is unlocked, proceed with starting
        console.log(`Level ${levelNumber} is unlocked, starting level`);
        startCustomLevel(groupId, levelNumber);
        
    } catch (error) {
        console.error(`Error handling custom level start:`, error);
        // Fallback: try to start the level anyway
        startCustomLevel(groupId, levelNumber);
    }
}

// Export the functions globally
// Handle practice button click for custom level
function handleCustomLevelPractice(groupId, levelNumber) {
    try {
        console.log(`🎯 Handling custom level practice: group ${groupId}, level ${levelNumber}`);
        
        // Mark this level card as active for context detection
        const levelCard = document.querySelector(`.level-card[data-level="${levelNumber}"][data-custom-group-id="${groupId}"]`);
        if (levelCard) {
            // Remove active class from all cards
            document.querySelectorAll('.level-card').forEach(card => card.classList.remove('active'));
            // Add active class to this card
            levelCard.classList.add('active');
            
            // Find and set loading state on the practice button in this level card
            const practiceBtn = levelCard.querySelector('.level-btn[data-i18n="buttons.practice"]');
            if (practiceBtn) {
                practiceBtn.disabled = true;
                const originalText = practiceBtn.textContent;
                practiceBtn.dataset.originalText = originalText;
                // Show loading state without emoji
                const labelNode = practiceBtn.querySelector('.btn-label');
                if (labelNode) {
                    labelNode.textContent = window.t ? window.t('ui.loading', 'Loading...') : 'Loading...';
                } else {
                    practiceBtn.textContent = window.t ? window.t('ui.loading', 'Loading...') : 'Loading...';
                }
            }
        }
        
        // Call startSmartPractice with flag to indicate it's from a level container
        if (typeof window.startSmartPractice === 'function') {
            window.startSmartPractice(true); // Pass true to indicate level container context
        } else {
            console.error('startSmartPractice function not available');
            alert('Practice-Funktion nicht verfügbar');
        }
    } catch (error) {
        console.error('Error handling custom level practice:', error);
        alert('Fehler beim Starten der Übung: ' + error.message);
    }
}

// Setup dropdown change listeners for filtering
function setupCustomGroupsFilterListeners() {
    const topicSelect = document.getElementById('topic');
    const cefrSelect = document.getElementById('cefr');
    
    // Remove existing listeners to avoid duplicates
    if (topicSelect && topicSelect.dataset.customGroupsFilterBound !== 'true') {
        topicSelect.addEventListener('change', () => {
            console.log('📊 Topic filter changed, re-rendering custom groups...');
            renderCustomLevelGroups();
        });
        topicSelect.dataset.customGroupsFilterBound = 'true';
    }
    
    if (cefrSelect && cefrSelect.dataset.customGroupsFilterBound !== 'true') {
        cefrSelect.addEventListener('change', () => {
            console.log('📊 CEFR filter changed, re-rendering custom groups...');
            renderCustomLevelGroups();
        });
        cefrSelect.dataset.customGroupsFilterBound = 'true';
    }
}

window.handleCustomLevelStart = handleCustomLevelStart;
window.handleCustomLevelPractice = handleCustomLevelPractice;
window.showCustomLevelGroupsInLibrary = showCustomLevelGroupsInLibrary;
window.loadCustomLevelGroups = loadCustomLevelGroups;
window.renderCustomLevelGroups = renderCustomLevelGroups;
window.showGroupsContainer = showGroupsContainer;
window.setupCustomGroupsFilterListeners = setupCustomGroupsFilterListeners;

