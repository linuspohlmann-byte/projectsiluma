/**
 * Localization Management UI
 */

let currentEditingEntry = null;
const tt = (key, fallback) => (typeof window !== 'undefined' && typeof window.t === 'function') ? window.t(key, fallback) : fallback;

// Initialize localization management
export function initLocalization() {
    console.log('Initializing localization management...');
    
    // Navigation button
    const navBtn = document.getElementById('nav-localization');
    if (navBtn) {
        navBtn.addEventListener('click', () => {
            showLocalizationPage();
        });
    }
    
    // Add entry button
    const addBtn = document.getElementById('add-localization-entry');
    if (addBtn) {
        addBtn.addEventListener('click', () => {
            showAddEntryModal();
        });
    }
    
    // Import button
    const importBtn = document.getElementById('import-localization');
    if (importBtn) {
        importBtn.addEventListener('click', () => {
            toggleImportSection();
        });
    }
    
    // Cancel import button
    const cancelImportBtn = document.getElementById('cancel-import');
    if (cancelImportBtn) {
        cancelImportBtn.addEventListener('click', () => {
            hideImportSection();
        });
    }
    
    // Start import button
    const startImportBtn = document.getElementById('start-import');
    if (startImportBtn) {
        startImportBtn.addEventListener('click', () => {
            startImport();
        });
    }
    
    // AI Fill button
    const aiFillBtn = document.getElementById('ai-fill-translations');
    if (aiFillBtn) {
        aiFillBtn.addEventListener('click', () => {
            triggerAiFill();
        });
    }
    
    // Modal buttons
    const cancelEntryBtn = document.getElementById('cancel-entry');
    if (cancelEntryBtn) {
        cancelEntryBtn.addEventListener('click', () => {
            hideModal();
        });
    }
    
    const saveEntryBtn = document.getElementById('save-entry');
    if (saveEntryBtn) {
        saveEntryBtn.addEventListener('click', () => {
            saveEntry();
        });
    }
    
    // Modal close button
    const modalCloseBtn = document.querySelector('.modal-close');
    if (modalCloseBtn) {
        modalCloseBtn.addEventListener('click', () => {
            hideModal();
        });
    }
    
    // Load initial data
    loadLocalizationEntries();
}

function showLocalizationPage() {
    // Hide all pages
    const pages = document.querySelectorAll('.page');
    pages.forEach(page => page.style.display = 'none');
    
    // Show localization page
    const localizationPage = document.getElementById('localization-admin');
    if (localizationPage) {
        localizationPage.style.display = 'block';
    }
    
    // Update navigation
    const navButtons = document.querySelectorAll('.nav button');
    navButtons.forEach(btn => btn.classList.remove('active'));
    
    const navBtn = document.getElementById('nav-localization');
    if (navBtn) {
        navBtn.classList.add('active');
    }
    
    // Load entries
    loadLocalizationEntries();
}

function toggleImportSection() {
    const importSection = document.getElementById('import-section');
    if (importSection) {
        const isVisible = importSection.style.display !== 'none';
        importSection.style.display = isVisible ? 'none' : 'block';
    }
}

function hideImportSection() {
    const importSection = document.getElementById('import-section');
    if (importSection) {
        importSection.style.display = 'none';
    }
    
    // Clear file input
    const fileInput = document.getElementById('localization-file');
    if (fileInput) {
        fileInput.value = '';
    }
    
    // Hide status
    const statusDiv = document.getElementById('import-status');
    if (statusDiv) {
        statusDiv.style.display = 'none';
    }
}

async function startImport() {
    const fileInput = document.getElementById('localization-file');
    if (!fileInput || !fileInput.files[0]) {
        alert('Please select a file to import');
        return;
    }
    
    const file = fileInput.files[0];
    const formData = new FormData();
    formData.append('file', file);
    
    // Show status
    const statusDiv = document.getElementById('import-status');
    const progressDiv = document.getElementById('import-progress');
    if (statusDiv && progressDiv) {
        statusDiv.style.display = 'block';
        progressDiv.innerHTML = 'Uploading and importing file...';
    }
    
    try {
        const response = await fetch('/api/localization/import-excel', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (result.success) {
            progressDiv.innerHTML = '✅ Import completed successfully!';
            // Reload entries
            loadLocalizationEntries();
            // Hide import section after delay
            setTimeout(() => {
                hideImportSection();
            }, 2000);
        } else {
            progressDiv.innerHTML = `❌ Import failed: ${result.error}`;
        }
    } catch (error) {
        console.error('Import error:', error);
        progressDiv.innerHTML = `❌ Import failed: ${error.message}`;
    }
}

async function loadLocalizationEntries() {
    try {
        const response = await fetch('/api/localization/entries');
        const result = await response.json();
        
        if (result.success) {
            renderLocalizationTable(result.entries);
        } else {
            console.error('Failed to load localization entries:', result.error);
        }
    } catch (error) {
        console.error('Error loading localization entries:', error);
    }
}

function renderLocalizationTable(entries) {
    const tbody = document.getElementById('localization-table-body');
    if (!tbody) return;
    
    tbody.innerHTML = '';
    
    // Language mapping for display
    const languageOrder = ['english', 'german', 'french', 'spanish', 'portuguese', 'italian', 
                          'dutch', 'swedish', 'norwegian', 'danish', 'finnish', 'polish', 
                          'czech', 'slovak', 'hungarian', 'romanian', 'bulgarian', 'greek', 
                          'turkish', 'russian', 'ukrainian', 'chinese', 'japanese', 'korean', 
                          'hindi', 'urdu', 'indonesian', 'malay', 'thai', 'vietnamese', 
                          'persian', 'arabic', 'swahili', 'georgian'];
    
    entries.forEach(entry => {
        const row = document.createElement('tr');
        
        // Build language cells
        let languageCells = '';
        languageOrder.forEach(lang => {
            const value = entry[lang] || '';
            languageCells += `<td title="${lang}">${value}</td>`;
        });
        
        row.innerHTML = `
            <td>${entry.reference_key}</td>
            <td>${entry.description || ''}</td>
            ${languageCells}
            <td>
                <button onclick="editEntry(${entry.id})" class="secondary" style="margin-right:8px;" data-i18n="localization.edit_button">Edit</button>
                <button onclick="deleteEntry(${entry.id})" class="secondary" data-i18n="localization.delete_button">Delete</button>
            </td>
        `;
        tbody.appendChild(row);
    });
}

function showAddEntryModal() {
    currentEditingEntry = null;
    showModal('Add Localization Entry');
    clearForm();
}

function showEditEntryModal(entry) {
    currentEditingEntry = entry;
    showModal(window.t ? window.t('localization.edit_entry_title', 'Edit Localization Entry') : 'Edit Localization Entry');
    populateForm(entry);
}

function showModal(title) {
    const modal = document.getElementById('localization-modal');
    const titleElement = document.getElementById('modal-title');
    
    if (modal && titleElement) {
        titleElement.textContent = title;
        modal.style.display = 'block';
    }
}

function hideModal() {
    const modal = document.getElementById('localization-modal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentEditingEntry = null;
}

function clearForm() {
    const form = document.getElementById('localization-form');
    if (form) {
        form.reset();
    }
}

function populateForm(entry) {
    document.getElementById('entry-reference-key').value = entry.reference_key || '';
    document.getElementById('entry-description').value = entry.description || '';
    document.getElementById('entry-german').value = entry.german || '';
    document.getElementById('entry-english').value = entry.english || '';
    document.getElementById('entry-french').value = entry.french || '';
    document.getElementById('entry-italian').value = entry.italian || '';
    document.getElementById('entry-spanish').value = entry.spanish || '';
    document.getElementById('entry-portuguese').value = entry.portuguese || '';
    document.getElementById('entry-russian').value = entry.russian || '';
    document.getElementById('entry-turkish').value = entry.turkish || '';
    document.getElementById('entry-georgian').value = entry.georgian || '';
}

async function saveEntry() {
    const form = document.getElementById('localization-form');
    if (!form) return;
    
    const formData = new FormData(form);
    const entry = {
        reference_key: document.getElementById('entry-reference-key').value,
        description: document.getElementById('entry-description').value,
        german: document.getElementById('entry-german').value,
        english: document.getElementById('entry-english').value,
        french: document.getElementById('entry-french').value,
        italian: document.getElementById('entry-italian').value,
        spanish: document.getElementById('entry-spanish').value,
        portuguese: document.getElementById('entry-portuguese').value,
        russian: document.getElementById('entry-russian').value,
        turkish: document.getElementById('entry-turkish').value,
        georgian: document.getElementById('entry-georgian').value
    };
    
    if (!entry.reference_key) {
        alert('Reference key is required');
        return;
    }
    
    try {
        const response = await fetch('/api/localization/entry', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(entry)
        });
        
        const result = await response.json();
        
        if (result.success) {
            hideModal();
            loadLocalizationEntries();
        } else {
            alert(`Failed to save entry: ${result.error}`);
        }
    } catch (error) {
        console.error('Error saving entry:', error);
        alert(`Error saving entry: ${error.message}`);
    }
}

// Global functions for inline event handlers
window.editEntry = async function(entryId) {
    try {
        const response = await fetch('/api/localization/entries');
        const result = await response.json();
        
        if (result.success) {
            const entry = result.entries.find(e => e.id === entryId);
            if (entry) {
                showEditEntryModal(entry);
            }
        }
    } catch (error) {
        console.error('Error loading entry for edit:', error);
    }
};

window.deleteEntry = async function(entryId) {
    if (!confirm(tt('localization.delete_confirm', 'Are you sure you want to delete this entry?'))) {
        return;
    }
    
    try {
        const response = await fetch(`/api/localization/entry/${entryId}`, {
            method: 'DELETE'
        });
        
        const result = await response.json();
        
        if (result.success) {
            loadLocalizationEntries();
        } else {
            alert(tt('localization.delete_failed', 'Failed to delete entry: {error}').replace('{error}', result.error || ''));
        }
    } catch (error) {
        console.error('Error deleting entry:', error);
        alert(tt('localization.delete_error', 'Error deleting entry: {error}').replace('{error}', error.message || ''));
    }
};

// AI Fill functionality
async function triggerAiFill() {
    const button = document.getElementById('ai-fill-translations');
    if (!button) return;
    
    // Show confirmation dialog
    const confirmed = confirm(tt(
        'localization.ai_fill_confirm',
        'This will use AI to fill missing translations for the top 20 most spoken languages.\n\n'
        + 'This may take a few minutes and will use OpenAI API credits.\n\n'
        + 'Do you want to continue?'
    ));
    
    if (!confirmed) return;
    
    // Show loading state
    const originalText = button.textContent;
    button.textContent = tt('localization.ai_fill_in_progress', '🤖 AI filling...');
    button.disabled = true;
    
    try {
        console.log('🤖 Triggering AI translation filling...');
        
        const response = await fetch('/api/localization/ai-fill', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const result = await response.json();
        
        if (result.success) {
            alert(tt('localization.ai_fill_success', '✅ AI translation filling completed successfully!\n\nPlease refresh the page to see the new translations.'));
            // Reload the localization entries
            loadLocalizationEntries();
        } else {
            alert(tt('localization.ai_fill_error', '❌ AI translation filling failed: {error}').replace('{error}', result.error || ''));
        }
        
    } catch (error) {
        console.error('Error during AI fill:', error);
        alert(tt('localization.ai_fill_error_generic', '❌ Error during AI fill: {error}').replace('{error}', error.message || ''));
    } finally {
        // Restore button state
        button.textContent = originalText;
        button.disabled = false;
    }
}
