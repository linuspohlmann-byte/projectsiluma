"""
Marketplace Notifications System
Handles tracking downloads and notifying users when marketplace content is removed
"""

from datetime import datetime, UTC
from typing import List, Dict, Optional
from server.db_config import get_database_config, get_db_connection, execute_query
from server.db import _coerce_row_to_dict


def create_marketplace_tables():
    """Create tables for tracking downloads and notifications"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            # Marketplace downloads table
            execute_query(conn, """
                CREATE TABLE IF NOT EXISTS marketplace_downloads (
                    id SERIAL PRIMARY KEY,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, user_id),
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            
            # Create index for faster lookups
            execute_query(conn, """
                CREATE INDEX IF NOT EXISTS idx_marketplace_downloads_group_id 
                ON marketplace_downloads(group_id);
            """)
            
            execute_query(conn, """
                CREATE INDEX IF NOT EXISTS idx_marketplace_downloads_user_id 
                ON marketplace_downloads(user_id);
            """)
            
            # User notifications table
            execute_query(conn, """
                CREATE TABLE IF NOT EXISTS user_notifications (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    group_id INTEGER,
                    group_name VARCHAR(255),
                    is_read BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            
            # Create index for faster lookups
            execute_query(conn, """
                CREATE INDEX IF NOT EXISTS idx_user_notifications_user_id 
                ON user_notifications(user_id, is_read);
            """)
            
        else:
            # SQLite version
            cursor = conn.cursor()
            
            # Marketplace downloads table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS marketplace_downloads (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, user_id),
                    FOREIGN KEY (group_id) REFERENCES custom_level_groups(id) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_marketplace_downloads_group_id 
                ON marketplace_downloads(group_id);
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_marketplace_downloads_user_id 
                ON marketplace_downloads(user_id);
            """)
            
            # User notifications table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_notifications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    notification_type VARCHAR(50) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    message TEXT NOT NULL,
                    group_id INTEGER,
                    group_name VARCHAR(255),
                    is_read INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_user_notifications_user_id 
                ON user_notifications(user_id, is_read);
            """)
            
            conn.commit()
            cursor.close()
        
        conn.commit()
        print("✅ Marketplace tables created successfully")
        
    except Exception as e:
        print(f"❌ Error creating marketplace tables: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def track_marketplace_download(group_id: int, user_id: int) -> bool:
    """Track when a user downloads content from marketplace"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            execute_query(conn, """
                INSERT INTO marketplace_downloads (group_id, user_id, downloaded_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (group_id, user_id) DO UPDATE
                SET downloaded_at = CURRENT_TIMESTAMP
            """, (group_id, user_id, datetime.now(UTC).isoformat()))
        else:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO marketplace_downloads (group_id, user_id, downloaded_at)
                VALUES (?, ?, ?)
            """, (group_id, user_id, datetime.now(UTC).isoformat()))
            cursor.close()
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error tracking marketplace download: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_downloaders_for_group(group_id: int) -> List[int]:
    """Get list of user IDs who have downloaded a specific group"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT DISTINCT user_id 
                FROM marketplace_downloads 
                WHERE group_id = %s
            """, (group_id,))
            return [row['user_id'] for row in result.fetchall()]
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT DISTINCT user_id 
                FROM marketplace_downloads 
                WHERE group_id = ?
            """, (group_id,))
            return [row[0] for row in cursor.fetchall()]
            
    except Exception as e:
        print(f"❌ Error getting downloaders for group: {e}")
        return []
    finally:
        conn.close()


def create_notification(
    user_id: int,
    notification_type: str,
    title: str,
    message: str,
    group_id: Optional[int] = None,
    group_name: Optional[str] = None
) -> bool:
    """Create a notification for a user"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            execute_query(conn, """
                INSERT INTO user_notifications 
                (user_id, notification_type, title, message, group_id, group_name, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                user_id,
                notification_type,
                title,
                message,
                group_id,
                group_name,
                datetime.now(UTC).isoformat()
            ))
        else:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO user_notifications 
                (user_id, notification_type, title, message, group_id, group_name, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                notification_type,
                title,
                message,
                group_id,
                group_name,
                datetime.now(UTC).isoformat()
            ))
            cursor.close()
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error creating notification: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def notify_content_removed(group_id: int, group_name: str) -> int:
    """Notify all users who downloaded content that it has been removed"""
    downloaders = get_downloaders_for_group(group_id)
    
    if not downloaders:
        return 0
    
    notification_count = 0
    for user_id in downloaders:
        success = create_notification(
            user_id=user_id,
            notification_type='content_removed',
            title='Content No Longer Available',
            message=f'The content "{group_name}" you downloaded from the marketplace is no longer available. The creator has removed it from their library.',
            group_id=group_id,
            group_name=group_name
        )
        if success:
            notification_count += 1
    
    print(f"✅ Created {notification_count} notifications for {len(downloaders)} users")
    return notification_count


def get_user_notifications(user_id: int, unread_only: bool = False, limit: int = 50) -> List[Dict]:
    """Get notifications for a user"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            if unread_only:
                result = execute_query(conn, """
                    SELECT * FROM user_notifications
                    WHERE user_id = %s AND is_read = FALSE
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, limit))
            else:
                result = execute_query(conn, """
                    SELECT * FROM user_notifications
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                """, (user_id, limit))
            
            notifications = []
            for row in result.fetchall():
                if isinstance(row, dict):
                    notifications.append(row)
                else:
                    notifications.append(_coerce_row_to_dict(row, result.description))
            
            return notifications
        else:
            cursor = conn.cursor()
            if unread_only:
                cursor.execute("""
                    SELECT * FROM user_notifications
                    WHERE user_id = ? AND is_read = 0
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (user_id, limit))
            else:
                cursor.execute("""
                    SELECT * FROM user_notifications
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """, (user_id, limit))
            
            columns = [desc[0] for desc in cursor.description]
            notifications = []
            for row in cursor.fetchall():
                notifications.append(dict(zip(columns, row)))
            
            cursor.close()
            return notifications
            
    except Exception as e:
        print(f"❌ Error getting user notifications: {e}")
        return []
    finally:
        conn.close()


def mark_notification_read(notification_id: int, user_id: int) -> bool:
    """Mark a notification as read"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            execute_query(conn, """
                UPDATE user_notifications
                SET is_read = TRUE
                WHERE id = %s AND user_id = %s
            """, (notification_id, user_id))
        else:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_notifications
                SET is_read = 1
                WHERE id = ? AND user_id = ?
            """, (notification_id, user_id))
            cursor.close()
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error marking notification as read: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def mark_all_notifications_read(user_id: int) -> bool:
    """Mark all notifications as read for a user"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            execute_query(conn, """
                UPDATE user_notifications
                SET is_read = TRUE
                WHERE user_id = %s AND is_read = FALSE
            """, (user_id,))
        else:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE user_notifications
                SET is_read = 1
                WHERE user_id = ? AND is_read = 0
            """, (user_id,))
            cursor.close()
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ Error marking all notifications as read: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


def get_unread_notification_count(user_id: int) -> int:
    """Get count of unread notifications for a user"""
    config = get_database_config()
    conn = get_db_connection()
    
    try:
        if config['type'] == 'postgresql':
            result = execute_query(conn, """
                SELECT COUNT(*) as count FROM user_notifications
                WHERE user_id = %s AND is_read = FALSE
            """, (user_id,))
            row = result.fetchone()
            return row['count'] if isinstance(row, dict) else row[0]
        else:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) FROM user_notifications
                WHERE user_id = ? AND is_read = 0
            """, (user_id,))
            count = cursor.fetchone()[0]
            cursor.close()
            return count
            
    except Exception as e:
        print(f"❌ Error getting unread notification count: {e}")
        return 0
    finally:
        conn.close()

