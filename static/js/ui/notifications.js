/**
 * Notifications UI
 * Handles display and interaction with user notifications
 */

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

let notifications = [];
let unreadCount = 0;
let notificationsPanel = null;
let notificationIcon = null;
let refreshInterval = null;

/**
 * Initialize notifications system
 */
export async function initNotifications() {
    console.log('🔔 Initializing notifications system...');
    
    // Create notification icon in topbar
    createNotificationIcon();
    
    // Create notifications panel
    createNotificationsPanel();
    
    // Load initial notifications
    await loadNotifications();
    
    // Set up auto-refresh (every 5 minutes)
    refreshInterval = setInterval(() => {
        loadNotifications(true); // Silent refresh
    }, 5 * 60 * 1000);
    
    console.log('✅ Notifications system initialized');
}

/**
 * Create notification icon in topbar
 */
function createNotificationIcon() {
    const topbar = $('.main-navigation') || $('header');
    if (!topbar) {
        console.warn('⚠️ Topbar not found, retrying in 100ms...');
        setTimeout(createNotificationIcon, 100);
        return;
    }
    
    // Check if icon already exists
    if ($('#notification-icon')) {
        return;
    }
    
    // Create notification icon button
    const iconContainer = document.createElement('div');
    iconContainer.id = 'notification-icon-container';
    iconContainer.style.cssText = 'position: relative; margin-left: auto; margin-right: 16px;';
    
    const iconBtn = document.createElement('button');
    iconBtn.id = 'notification-icon';
    iconBtn.className = 'notification-icon-btn';
    iconBtn.innerHTML = `
        <span class="notification-icon">🔔</span>
        <span id="notification-badge" class="notification-badge" style="display: none;">0</span>
    `;
    iconBtn.setAttribute('aria-label', 'Notifications');
    iconBtn.onclick = toggleNotificationsPanel;
    
    iconContainer.appendChild(iconBtn);
    
    // Insert before user tab or at the end
    const userTab = $('.user-tab');
    if (userTab && userTab.parentNode) {
        userTab.parentNode.insertBefore(iconContainer, userTab);
    } else {
        topbar.appendChild(iconContainer);
    }
    
    notificationIcon = iconBtn;
    
    // Add styles
    addNotificationStyles();
}

/**
 * Add CSS styles for notifications
 */
function addNotificationStyles() {
    if ($('#notification-styles')) {
        return;
    }
    
    const style = document.createElement('style');
    style.id = 'notification-styles';
    style.textContent = `
        .notification-icon-btn {
            position: relative;
            background: transparent;
            border: none;
            cursor: pointer;
            padding: 8px;
            border-radius: 8px;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .notification-icon-btn:hover {
            background: var(--surface, #f1f5f9);
        }
        
        .notification-icon {
            font-size: 20px;
            line-height: 1;
        }
        
        .notification-badge {
            position: absolute;
            top: 4px;
            right: 4px;
            background: var(--warn, #ea580c);
            color: white;
            border-radius: 10px;
            min-width: 18px;
            height: 18px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 11px;
            font-weight: 600;
            padding: 0 4px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }
        
        .notifications-panel {
            position: fixed;
            top: 60px;
            right: 20px;
            width: 400px;
            max-width: calc(100vw - 40px);
            max-height: calc(100vh - 100px);
            background: var(--card, #ffffff);
            border: 1px solid var(--border, #e2e8f0);
            border-radius: 12px;
            box-shadow: 0 8px 24px rgba(0,0,0,0.15);
            z-index: 1000;
            display: none;
            flex-direction: column;
            overflow: hidden;
        }
        
        .notifications-panel.open {
            display: flex;
        }
        
        .notifications-header {
            padding: 16px;
            border-bottom: 1px solid var(--border, #e2e8f0);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .notifications-header h3 {
            margin: 0;
            font-size: 16px;
            font-weight: 600;
            color: var(--fg, #0f172a);
        }
        
        .notifications-header-actions {
            display: flex;
            gap: 8px;
        }
        
        .notifications-header-actions button {
            background: transparent;
            border: none;
            color: var(--accent, #2563eb);
            cursor: pointer;
            font-size: 12px;
            padding: 4px 8px;
            border-radius: 4px;
            transition: background 0.2s ease;
        }
        
        .notifications-header-actions button:hover {
            background: var(--surface, #f1f5f9);
        }
        
        .notifications-list {
            flex: 1;
            overflow-y: auto;
            padding: 8px;
        }
        
        .notifications-empty {
            padding: 32px 16px;
            text-align: center;
            color: var(--text-secondary, #64748b);
            font-size: 14px;
        }
        
        .notification-item {
            padding: 12px;
            margin-bottom: 8px;
            border-radius: 8px;
            background: var(--surface, #f1f5f9);
            border-left: 3px solid var(--accent, #2563eb);
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .notification-item:hover {
            background: var(--surface-hover, #e2e8f0);
            transform: translateX(2px);
        }
        
        .notification-item.unread {
            background: var(--card, #ffffff);
            border-left-color: var(--warn, #ea580c);
            font-weight: 500;
        }
        
        .notification-item.unread:hover {
            background: var(--surface, #f1f5f9);
        }
        
        .notification-title {
            font-size: 14px;
            font-weight: 600;
            color: var(--fg, #0f172a);
            margin-bottom: 4px;
        }
        
        .notification-message {
            font-size: 13px;
            color: var(--text-secondary, #64748b);
            line-height: 1.4;
        }
        
        .notification-time {
            font-size: 11px;
            color: var(--text-tertiary, #94a3b8);
            margin-top: 4px;
        }
        
        .notifications-loading {
            padding: 32px;
            text-align: center;
            color: var(--text-secondary, #64748b);
        }
    `;
    
    document.head.appendChild(style);
}

/**
 * Create notifications panel
 */
function createNotificationsPanel() {
    if ($('#notifications-panel')) {
        notificationsPanel = $('#notifications-panel');
        return;
    }
    
    const panel = document.createElement('div');
    panel.id = 'notifications-panel';
    panel.className = 'notifications-panel';
    
    panel.innerHTML = `
        <div class="notifications-header">
            <h3>Benachrichtigungen</h3>
            <div class="notifications-header-actions">
                <button id="mark-all-read-btn">Alle als gelesen</button>
                <button id="close-notifications-btn">✕</button>
            </div>
        </div>
        <div class="notifications-list" id="notifications-list">
            <div class="notifications-loading">Lade Benachrichtigungen...</div>
        </div>
    `;
    
    document.body.appendChild(panel);
    notificationsPanel = panel;
    
    // Bind events
    $('#mark-all-read-btn')?.addEventListener('click', markAllAsRead);
    $('#close-notifications-btn')?.addEventListener('click', closeNotificationsPanel);
    
    // Close on outside click
    document.addEventListener('click', (e) => {
        if (panel.classList.contains('open') && 
            !panel.contains(e.target) && 
            !notificationIcon?.contains(e.target)) {
            closeNotificationsPanel();
        }
    });
}

/**
 * Toggle notifications panel
 */
function toggleNotificationsPanel() {
    if (!notificationsPanel) {
        createNotificationsPanel();
    }
    
    const isOpen = notificationsPanel.classList.contains('open');
    if (isOpen) {
        closeNotificationsPanel();
    } else {
        openNotificationsPanel();
    }
}

/**
 * Open notifications panel
 */
function openNotificationsPanel() {
    if (!notificationsPanel) {
        createNotificationsPanel();
    }
    
    notificationsPanel.classList.add('open');
    loadNotifications(); // Refresh when opening
}

/**
 * Close notifications panel
 */
function closeNotificationsPanel() {
    if (notificationsPanel) {
        notificationsPanel.classList.remove('open');
    }
}

/**
 * Load notifications from API
 */
export async function loadNotifications(silent = false) {
    if (!silent) {
        console.log('📬 Loading notifications...');
    }
    
    try {
        const sessionToken = localStorage.getItem('session_token');
        if (!sessionToken) {
            // User not authenticated, hide notifications
            if (notificationIcon) {
                notificationIcon.style.display = 'none';
            }
            return;
        }
        
        // Show icon if hidden
        if (notificationIcon) {
            notificationIcon.style.display = 'flex';
        }
        
        // Get unread count
        const countResponse = await fetch('/api/notifications/unread-count', {
            headers: {
                'Authorization': `Bearer ${sessionToken}`
            }
        });
        
        if (countResponse.ok) {
            const countData = await countResponse.json();
            unreadCount = countData.count || 0;
            updateNotificationBadge();
        }
        
        // Get notifications if panel is open
        if (notificationsPanel?.classList.contains('open')) {
            const response = await fetch('/api/notifications?limit=50', {
                headers: {
                    'Authorization': `Bearer ${sessionToken}`
                }
            });
            
            if (response.ok) {
                const data = await response.json();
                notifications = data.notifications || [];
                renderNotifications();
            }
        }
        
    } catch (error) {
        console.error('❌ Error loading notifications:', error);
        if (!silent) {
            showNotificationError('Fehler beim Laden der Benachrichtigungen');
        }
    }
}

/**
 * Update notification badge
 */
function updateNotificationBadge() {
    const badge = $('#notification-badge');
    if (!badge) {
        return;
    }
    
    if (unreadCount > 0) {
        badge.textContent = unreadCount > 99 ? '99+' : unreadCount.toString();
        badge.style.display = 'flex';
    } else {
        badge.style.display = 'none';
    }
}

/**
 * Render notifications list
 */
function renderNotifications() {
    const list = $('#notifications-list');
    if (!list) {
        return;
    }
    
    if (notifications.length === 0) {
        list.innerHTML = '<div class="notifications-empty">Keine Benachrichtigungen</div>';
        return;
    }
    
    list.innerHTML = notifications.map(notif => {
        const timeAgo = formatTimeAgo(notif.created_at);
        const unreadClass = notif.is_read ? '' : 'unread';
        
        return `
            <div class="notification-item ${unreadClass}" data-id="${notif.id}" data-read="${notif.is_read}">
                <div class="notification-title">${escapeHtml(notif.title)}</div>
                <div class="notification-message">${escapeHtml(notif.message)}</div>
                <div class="notification-time">${timeAgo}</div>
            </div>
        `;
    }).join('');
    
    // Bind click handlers
    $$('.notification-item').forEach(item => {
        item.addEventListener('click', () => {
            const id = parseInt(item.dataset.id);
            const isRead = item.dataset.read === 'true';
            
            if (!isRead) {
                markAsRead(id);
            }
        });
    });
}

/**
 * Mark notification as read
 */
async function markAsRead(notificationId) {
    try {
        const sessionToken = localStorage.getItem('session_token');
        if (!sessionToken) {
            return;
        }
        
        const response = await fetch(`/api/notifications/${notificationId}/read`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${sessionToken}`
            }
        });
        
        if (response.ok) {
            // Update local state
            const notif = notifications.find(n => n.id === notificationId);
            if (notif) {
                notif.is_read = true;
            }
            
            // Update UI
            const item = $(`.notification-item[data-id="${notificationId}"]`);
            if (item) {
                item.classList.remove('unread');
                item.dataset.read = 'true';
            }
            
            // Update badge
            unreadCount = Math.max(0, unreadCount - 1);
            updateNotificationBadge();
        }
        
    } catch (error) {
        console.error('❌ Error marking notification as read:', error);
    }
}

/**
 * Mark all notifications as read
 */
async function markAllAsRead() {
    try {
        const sessionToken = localStorage.getItem('session_token');
        if (!sessionToken) {
            return;
        }
        
        const response = await fetch('/api/notifications/read-all', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${sessionToken}`
            }
        });
        
        if (response.ok) {
            // Update local state
            notifications.forEach(notif => {
                notif.is_read = true;
            });
            
            // Update UI
            $$('.notification-item').forEach(item => {
                item.classList.remove('unread');
                item.dataset.read = 'true';
            });
            
            // Update badge
            unreadCount = 0;
            updateNotificationBadge();
        }
        
    } catch (error) {
        console.error('❌ Error marking all notifications as read:', error);
    }
}

/**
 * Format time ago
 */
function formatTimeAgo(timestamp) {
    if (!timestamp) {
        return 'Vor kurzem';
    }
    
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) {
        return 'Gerade eben';
    } else if (diffMins < 60) {
        return `Vor ${diffMins} ${diffMins === 1 ? 'Minute' : 'Minuten'}`;
    } else if (diffHours < 24) {
        return `Vor ${diffHours} ${diffHours === 1 ? 'Stunde' : 'Stunden'}`;
    } else if (diffDays < 7) {
        return `Vor ${diffDays} ${diffDays === 1 ? 'Tag' : 'Tagen'}`;
    } else {
        return date.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' });
    }
}

/**
 * Escape HTML
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Show notification error
 */
function showNotificationError(message) {
    const list = $('#notifications-list');
    if (list) {
        list.innerHTML = `<div class="notifications-empty" style="color: var(--warn, #ea580c);">${escapeHtml(message)}</div>`;
    }
}

/**
 * Cleanup on page unload
 */
export function cleanupNotifications() {
    if (refreshInterval) {
        clearInterval(refreshInterval);
        refreshInterval = null;
    }
}

// Auto-initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initNotifications);
} else {
    initNotifications();
}

// Export for manual refresh (e.g., after login)
export function refreshNotifications() {
    loadNotifications();
}

// Listen for auth state changes
if (typeof window !== 'undefined') {
    // Refresh notifications when user logs in
    const originalAuthStateChange = window.onAuthStateChange;
    window.onAuthStateChange = function(isAuthenticated) {
        if (originalAuthStateChange) {
            originalAuthStateChange(isAuthenticated);
        }
        if (isAuthenticated) {
            // User logged in, refresh notifications
            setTimeout(() => {
                loadNotifications();
            }, 1000);
        } else {
            // User logged out, hide notifications
            if (notificationIcon) {
                notificationIcon.style.display = 'none';
            }
            if (notificationsPanel) {
                closeNotificationsPanel();
            }
        }
    };
}

