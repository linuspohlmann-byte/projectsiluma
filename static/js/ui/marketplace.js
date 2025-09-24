/**
 * Marketplace UI
 * Handles display and interaction with published custom level groups
 */

let marketplaceGroups = [];
let currentMarketplacePage = 1;
let marketplacePageSize = 12;
let marketplaceTotalPages = 1;
let marketplaceFilters = {
    language: 'en',
    native_language: 'de',
    cefr_level: ''
};

// Initialize marketplace when browse tab is activated
async function initMarketplace() {
    try {
        console.log('🌐 Initializing marketplace...');
        
        // Set up filters based on current user settings
        const targetLanguage = document.getElementById('target-lang')?.value || localStorage.getItem('siluma_target') || 'en';
        const nativeLanguage = localStorage.getItem('siluma_native') || 'de';
        
        marketplaceFilters.language = targetLanguage;
        marketplaceFilters.native_language = nativeLanguage;
        
        // Load marketplace groups
        await loadMarketplaceGroups();
        
    } catch (error) {
        console.error('Error initializing marketplace:', error);
        showMarketplaceError('Fehler beim Laden des Marketplaces');
    }
}

// Load marketplace groups from API
async function loadMarketplaceGroups(direction = null) {
    try {
        console.log('📚 Loading marketplace groups...', marketplaceFilters);
        
        // Update page based on direction
        if (direction === 'next' && currentMarketplacePage < marketplaceTotalPages) {
            currentMarketplacePage++;
        } else if (direction === 'prev' && currentMarketplacePage > 1) {
            currentMarketplacePage--;
        } else if (direction === null) {
            currentMarketplacePage = 1; // Reset to first page
        }
        
        const offset = (currentMarketplacePage - 1) * marketplacePageSize;
        
        // Show loading state
        showMarketplaceLoading();
        
        // Build query parameters
        const params = new URLSearchParams({
            language: marketplaceFilters.language,
            native_language: marketplaceFilters.native_language,
            limit: marketplacePageSize,
            offset: offset
        });
        
        if (marketplaceFilters.cefr_level) {
            params.append('cefr_level', marketplaceFilters.cefr_level);
        }
        
        // Call API
        const response = await fetch(`/api/marketplace/custom-level-groups?${params}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        
        if (result.success) {
            marketplaceGroups = result.groups;
            marketplaceTotalPages = Math.ceil(result.total / marketplacePageSize);
            
            console.log(`✅ Loaded ${marketplaceGroups.length} marketplace groups (page ${currentMarketplacePage}/${marketplaceTotalPages})`);
            
            // Render groups
            renderMarketplaceGroups();
            updateMarketplacePagination();
            
        } else {
            throw new Error(result.error || 'Failed to load marketplace groups');
        }
        
    } catch (error) {
        console.error('Error loading marketplace groups:', error);
        showMarketplaceError('Fehler beim Laden der Marketplace-Inhalte: ' + error.message);
    }
}

// Render marketplace groups
function renderMarketplaceGroups() {
    const container = document.getElementById('marketplace-groups-container');
    if (!container) return;
    
    if (marketplaceGroups.length === 0) {
        container.innerHTML = `
            <div class="marketplace-empty">
                <div class="marketplace-empty-icon">📚</div>
                <h3 class="marketplace-empty-title">Keine Level-Gruppen gefunden</h3>
                <p class="marketplace-empty-text">
                    Es wurden keine publishten Level-Gruppen für die gewählten Filter gefunden.
                    <br>Versuche andere Filter oder erstelle deine eigene Level-Gruppe!
                </p>
            </div>
        `;
        return;
    }
    
    container.innerHTML = `
        <div class="marketplace-groups-grid">
            ${marketplaceGroups.map(group => renderMarketplaceGroupCard(group)).join('')}
        </div>
    `;
    
    // Add click handlers for group cards
    container.querySelectorAll('.marketplace-group-card').forEach(card => {
        const groupId = card.dataset.groupId;
        
        // Main card click - start group
        card.addEventListener('click', (e) => {
            if (!e.target.closest('.marketplace-group-btn')) {
                startMarketplaceGroup(groupId);
            }
        });
        
        // Button click handlers
        const startBtn = card.querySelector('.marketplace-group-btn.primary');
        const previewBtn = card.querySelector('.marketplace-group-btn:not(.primary)');
        
        if (startBtn) {
            startBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                startMarketplaceGroup(groupId);
            });
        }
        
        if (previewBtn) {
            previewBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                previewMarketplaceGroup(groupId);
            });
        }
    });
}

// Render individual marketplace group card
function renderMarketplaceGroupCard(group) {
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
    
    return `
        <div class="marketplace-group-card" data-group-id="${group.id}">
            <div class="marketplace-group-header">
                <h3 class="marketplace-group-title">${escapeHtml(group.group_name)}</h3>
                <p class="marketplace-group-description">${escapeHtml(group.context_description)}</p>
                <p class="marketplace-group-author">von ${escapeHtml(group.author_name || 'Unbekannt')} • ${timeAgo}</p>
            </div>
            
            <div class="marketplace-group-meta">
                <div class="marketplace-group-stat">
                    <div class="marketplace-group-stat-value">${group.num_levels}</div>
                    <div class="marketplace-group-stat-label">Level</div>
                </div>
                <div class="marketplace-group-stat">
                    <div class="marketplace-group-stat-value">${group.cefr_level}</div>
                    <div class="marketplace-group-stat-label">CEFR</div>
                </div>
                <div class="marketplace-group-stat">
                    <div class="marketplace-group-stat-value">${group.language.toUpperCase()}</div>
                    <div class="marketplace-group-stat-label">Sprache</div>
                </div>
            </div>
            
            <div class="marketplace-group-actions">
                <button class="marketplace-group-btn primary">
                    Start
                </button>
                <button class="marketplace-group-btn">
                    Vorschau
                </button>
            </div>
        </div>
    `;
}

// Start a marketplace group (import it to user's library)
async function startMarketplaceGroup(groupId) {
    try {
        console.log('🚀 Starting marketplace group:', groupId);
        
        // Check if user is authenticated
        if (!window.authManager || !window.authManager.isAuthenticated()) {
            showNotification('Du musst angemeldet sein, um Level-Gruppen zu importieren.', 'error');
            return;
        }
        
        // Show loading state
        if (window.showLoader) {
            window.showLoader();
        }
        
        // Import the group
        const response = await fetch(`/api/marketplace/custom-level-groups/${groupId}/import`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to import group');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to import group');
        }
        
        showNotification('Level-Gruppe erfolgreich importiert! Du findest sie jetzt in deiner Bibliothek.', 'success');
        
        // Switch to library tab to show the imported group
        if (window.showTab) {
            window.showTab('library');
        }
        
    } catch (error) {
        console.error('❌ Error starting marketplace group:', error);
        showNotification('Fehler beim Importieren der Gruppe: ' + error.message, 'error');
    } finally {
        // Hide loading state
        if (window.hideLoader) {
            window.hideLoader();
        }
    }
}

// Preview a marketplace group
async function previewMarketplaceGroup(groupId) {
    try {
        console.log('👁️ Previewing marketplace group:', groupId);
        
        // Get group details
        const response = await fetch(`/api/marketplace/custom-level-groups/${groupId}`, {
            headers: {
                'Authorization': `Bearer ${localStorage.getItem('session_token')}`
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to load group details');
        }
        
        const data = await response.json();
        if (!data.success) {
            throw new Error(data.error || 'Failed to load group details');
        }
        
        const group = data.group;
        const levels = data.levels;
        
        // Show preview modal
        showMarketplacePreviewModal(group, levels);
        
    } catch (error) {
        console.error('❌ Error previewing marketplace group:', error);
        showNotification('Fehler beim Laden der Vorschau: ' + error.message, 'error');
    }
}

// Show marketplace preview modal
function showMarketplacePreviewModal(group, levels) {
    // Remove any existing preview modal
    const existingModal = document.getElementById('marketplace-preview-modal');
    if (existingModal) {
        existingModal.remove();
    }
    
    const modalHtml = `
        <div class="modal-overlay" id="marketplace-preview-modal">
            <div class="modal-content marketplace-preview-modal">
                <div class="modal-header">
                    <h2>👁️ Vorschau: ${escapeHtml(group.group_name)}</h2>
                    <button class="modal-close" onclick="closeMarketplacePreviewModal()">×</button>
                </div>
                <div class="modal-body">
                    <div class="preview-group-info">
                        <div class="preview-group-description">
                            <h4>Beschreibung</h4>
                            <p>${escapeHtml(group.context_description)}</p>
                        </div>
                        
                        <div class="preview-group-meta">
                            <div class="preview-meta-item">
                                <strong>Sprache:</strong> ${group.language.toUpperCase()}
                            </div>
                            <div class="preview-meta-item">
                                <strong>CEFR-Level:</strong> ${group.cefr_level}
                            </div>
                            <div class="preview-meta-item">
                                <strong>Anzahl Level:</strong> ${levels.length}
                            </div>
                            <div class="preview-meta-item">
                                <strong>Autor:</strong> ${escapeHtml(group.author_name || 'Unbekannt')}
                            </div>
                        </div>
                    </div>
                    
                    <div class="preview-levels">
                        <h4>Level-Übersicht</h4>
                        <div class="preview-levels-list">
                            ${levels.slice(0, 5).map(level => `
                                <div class="preview-level-item">
                                    <div class="preview-level-number">${level.level_number}</div>
                                    <div class="preview-level-info">
                                        <div class="preview-level-title">${escapeHtml(level.title || `Level ${level.level_number}`)}</div>
                                        <div class="preview-level-topic">${escapeHtml(level.topic || '')}</div>
                                    </div>
                                </div>
                            `).join('')}
                            ${levels.length > 5 ? `<div class="preview-level-more">... und ${levels.length - 5} weitere Level</div>` : ''}
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button type="button" class="btn btn-secondary" onclick="closeMarketplacePreviewModal()">
                        Schließen
                    </button>
                    <button type="button" class="btn btn-primary" onclick="startMarketplaceGroup(${group.id}); closeMarketplacePreviewModal();">
                        Importieren
                    </button>
                </div>
            </div>
        </div>
    `;
    
    document.body.insertAdjacentHTML('beforeend', modalHtml);
    
    // Add event listeners for modal closing
    const modal = document.getElementById('marketplace-preview-modal');
    if (modal) {
        // Close on overlay click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeMarketplacePreviewModal();
            }
        });
        
        // Close on ESC key
        const handleEscKey = (e) => {
            if (e.key === 'Escape') {
                closeMarketplacePreviewModal();
                document.removeEventListener('keydown', handleEscKey);
            }
        };
        document.addEventListener('keydown', handleEscKey);
    }
}

// Close marketplace preview modal
function closeMarketplacePreviewModal() {
    const modal = document.getElementById('marketplace-preview-modal');
    if (modal) {
        modal.remove();
    }
}

// Refresh marketplace groups when language changes
function refreshMarketplaceGroups() {
    // Update filters based on current settings
    const targetLanguage = document.getElementById('target-lang')?.value || localStorage.getItem('siluma_target') || 'en';
    const nativeLanguage = localStorage.getItem('siluma_native') || 'de';
    
    marketplaceFilters.language = targetLanguage;
    marketplaceFilters.native_language = nativeLanguage;
    
    // Reset to first page and reload
    currentMarketplacePage = 1;
    loadMarketplaceGroups();
}

// Update marketplace pagination
function updateMarketplacePagination() {
    const pagination = document.getElementById('marketplace-pagination');
    const prevBtn = document.getElementById('marketplace-prev-btn');
    const nextBtn = document.getElementById('marketplace-next-btn');
    const pageInfo = document.getElementById('marketplace-page-info');
    
    if (!pagination || !prevBtn || !nextBtn || !pageInfo) return;
    
    // Show pagination if there are multiple pages
    if (marketplaceTotalPages > 1) {
        pagination.style.display = 'flex';
        
        // Update button states
        prevBtn.disabled = currentMarketplacePage <= 1;
        nextBtn.disabled = currentMarketplacePage >= marketplaceTotalPages;
        
        // Update page info
        pageInfo.textContent = `Seite ${currentMarketplacePage} von ${marketplaceTotalPages}`;
    } else {
        pagination.style.display = 'none';
    }
}

// Show marketplace loading state
function showMarketplaceLoading() {
    const container = document.getElementById('marketplace-groups-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="marketplace-loading">
            <div class="loading-spinner"></div>
            <p>Lade Marketplace-Inhalte...</p>
        </div>
    `;
}

// Show marketplace error state
function showMarketplaceError(message) {
    const container = document.getElementById('marketplace-groups-container');
    if (!container) return;
    
    container.innerHTML = `
        <div class="marketplace-empty">
            <div class="marketplace-empty-icon">❌</div>
            <h3 class="marketplace-empty-title">Fehler</h3>
            <p class="marketplace-empty-text">${escapeHtml(message)}</p>
        </div>
    `;
}

// Utility function to escape HTML
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Export functions for global access
window.initMarketplace = initMarketplace;
window.loadMarketplaceGroups = loadMarketplaceGroups;
window.refreshMarketplaceGroups = refreshMarketplaceGroups;
window.startMarketplaceGroup = startMarketplaceGroup;
window.previewMarketplaceGroup = previewMarketplaceGroup;
window.closeMarketplacePreviewModal = closeMarketplacePreviewModal;
