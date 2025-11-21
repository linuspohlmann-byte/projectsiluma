#!/usr/bin/env python3
"""Query custom level group 46, level 1 data from all PostgreSQL tables"""

import json
from server.db_config import get_db_connection, execute_query, get_database_config

def format_value(value):
    """Format value for display"""
    if value is None:
        return "NULL"
    if isinstance(value, (dict, list)):
        return json.dumps(value, indent=2, ensure_ascii=False)
    return str(value)

def print_table_data(title, rows, columns):
    """Print table data in a formatted way"""
    print(f"\n{'='*80}")
    print(f"{title}")
    print(f"{'='*80}")
    
    if not rows:
        print("No data found")
        return
    
    # Print column headers
    print("\nColumns:", ", ".join(columns))
    print(f"\nRows found: {len(rows)}")
    print("-" * 80)
    
    for idx, row in enumerate(rows, 1):
        print(f"\nRow {idx}:")
        if isinstance(row, dict):
            for col in columns:
                value = row.get(col, "N/A")
                print(f"  {col:30} = {format_value(value)}")
        else:
            # Tuple/list row
            for i, col in enumerate(columns):
                value = row[i] if i < len(row) else "N/A"
                print(f"  {col:30} = {format_value(value)}")

def main():
    group_id = 46
    level_number = 1
    
    print(f"Querying data for Custom Level Group {group_id}, Level {level_number}")
    print(f"Database type: {get_database_config()['type']}")
    
    conn = get_db_connection()
    
    try:
        config = get_database_config()
        is_postgres = config['type'] == 'postgresql'
        param_placeholder = '%s' if is_postgres else '?'
        
        # 1. Query custom_level_groups
        print("\n" + "="*80)
        print("1. CUSTOM_LEVEL_GROUPS TABLE")
        print("="*80)
        query1 = f"""
            SELECT id, user_id, language, native_language, group_name, 
                   context_description, topic, cefr_level, num_levels, 
                   status, created_at, updated_at
            FROM custom_level_groups
            WHERE id = {param_placeholder}
        """
        cursor1 = execute_query(conn, query1, (group_id,))
        rows1 = cursor1.fetchall()
        
        if rows1:
            row = rows1[0]
            if isinstance(row, dict):
                columns1 = list(row.keys())
            else:
                columns1 = [desc[0] for desc in cursor1.description]
            print_table_data(f"Custom Level Group {group_id}", rows1, columns1)
        else:
            print(f"No group found with id = {group_id}")
        
        # 2. Query custom_levels
        print("\n" + "="*80)
        print("2. CUSTOM_LEVELS TABLE")
        print("="*80)
        if is_postgres:
            query2 = f"""
                SELECT id, group_id, level_number, title, topic, 
                       word_count, created_at, updated_at,
                       CASE 
                           WHEN content IS NULL THEN 'NULL'
                           WHEN jsonb_typeof(content::jsonb) = 'object' THEN 'JSON Object'
                           WHEN jsonb_typeof(content::jsonb) = 'array' THEN 'JSON Array'
                           ELSE 'Other'
                       END as content_type,
                       CASE 
                           WHEN content IS NULL THEN 0
                           WHEN jsonb_typeof(content::jsonb) = 'array' THEN jsonb_array_length(content::jsonb)
                           ELSE 1
                       END as content_items_count
                FROM custom_levels
                WHERE group_id = {param_placeholder} AND level_number = {param_placeholder}
            """
        else:
            query2 = f"""
                SELECT id, group_id, level_number, title, topic, 
                       word_count, created_at, updated_at,
                       CASE 
                           WHEN content IS NULL THEN 'NULL'
                           WHEN typeof(content) = 'text' THEN 'JSON Text'
                           ELSE 'Other'
                       END as content_type,
                       CASE 
                           WHEN content IS NULL THEN 0
                           ELSE 1
                       END as content_items_count
                FROM custom_levels
                WHERE group_id = {param_placeholder} AND level_number = {param_placeholder}
            """
        cursor2 = execute_query(conn, query2, (group_id, level_number))
        rows2 = cursor2.fetchall()
        
        if rows2:
            row = rows2[0]
            if isinstance(row, dict):
                columns2 = list(row.keys())
            else:
                columns2 = [desc[0] for desc in cursor2.description]
            print_table_data(f"Custom Level {group_id}/{level_number}", rows2, columns2)
            
            # Also get a sample of the content if it exists
            query2_content = f"""
                SELECT content
                FROM custom_levels
                WHERE group_id = {param_placeholder} AND level_number = {param_placeholder}
            """
            cursor2_content = execute_query(conn, query2_content, (group_id, level_number))
            content_row = cursor2_content.fetchone()
            if content_row:
                content = content_row[0] if isinstance(content_row, dict) else content_row[0]
                if content:
                    print("\n" + "-"*80)
                    print("Content Sample (first 500 chars):")
                    print("-"*80)
                    content_str = json.dumps(content, indent=2, ensure_ascii=False) if isinstance(content, (dict, list)) else str(content)
                    print(content_str[:500] + ("..." if len(content_str) > 500 else ""))
        else:
            print(f"No level found with group_id = {group_id} AND level_number = {level_number}")
        
        # 3. Query custom_level_progress (for all users)
        print("\n" + "="*80)
        print("3. CUSTOM_LEVEL_PROGRESS TABLE")
        print("="*80)
        try:
            query3 = f"""
                SELECT id, user_id, group_id, level_number,
                       total_words, familiarity_0, familiarity_1, familiarity_2,
                       familiarity_3, familiarity_4, familiarity_5,
                       score, status, completed_at, last_updated, created_at
                FROM custom_level_progress
                WHERE group_id = {param_placeholder} AND level_number = {param_placeholder}
                ORDER BY user_id
            """
            cursor3 = execute_query(conn, query3, (group_id, level_number))
            rows3 = cursor3.fetchall()
        except Exception as e:
            print(f"Error querying custom_level_progress: {e}")
            print("Note: This table may not exist in SQLite. Data is only available in PostgreSQL on Railway.")
            rows3 = []
            cursor3 = None
        
        if rows3:
            row = rows3[0]
            if isinstance(row, dict):
                columns3 = list(row.keys())
            else:
                columns3 = [desc[0] for desc in cursor3.description]
            print_table_data(f"Custom Level Progress for Group {group_id}, Level {level_number}", rows3, columns3)
        else:
            print(f"No progress entries found for group_id = {group_id} AND level_number = {level_number}")
        
        # 4. Get user information for progress entries
        if rows3:
            print("\n" + "="*80)
            print("4. USER INFORMATION (for progress entries)")
            print("="*80)
            user_ids = []
            for row in rows3:
                user_id = row.get('user_id') if isinstance(row, dict) else row[1]
                if user_id and user_id not in user_ids:
                    user_ids.append(user_id)
            
            if user_ids:
                placeholders = ','.join([param_placeholder] * len(user_ids))
                query4 = f"""
                    SELECT id, username, email, created_at
                    FROM users
                    WHERE id IN ({placeholders})
                    ORDER BY id
                """
                cursor4 = execute_query(conn, query4, tuple(user_ids))
                rows4 = cursor4.fetchall()
                
                if rows4:
                    row = rows4[0]
                    if isinstance(row, dict):
                        columns4 = list(row.keys())
                    else:
                        columns4 = [desc[0] for desc in cursor4.description]
                    print_table_data("Users with progress entries", rows4, columns4)
        
        # 5. Summary statistics
        print("\n" + "="*80)
        print("5. SUMMARY STATISTICS")
        print("="*80)
        
        # Count words in user_word_familiarity for this level
        # Note: This query is complex and may not work with SQLite
        if is_postgres:
            query5 = f"""
                SELECT COUNT(DISTINCT word) as word_count,
                       COUNT(*) as total_entries
                FROM user_word_familiarity uwf
                WHERE EXISTS (
                    SELECT 1 FROM custom_levels cl
                    WHERE cl.group_id = {param_placeholder} 
                    AND cl.level_number = {param_placeholder}
                    AND uwf.word = ANY(
                        SELECT jsonb_array_elements_text(
                            jsonb_path_query_array(
                                cl.content::jsonb, 
                                '$[*].words[*]'
                            )
                        )
                    )
                )
            """
        else:
            query5 = f"""
                SELECT COUNT(DISTINCT word) as word_count,
                       COUNT(*) as total_entries
                FROM user_word_familiarity uwf
                WHERE EXISTS (
                    SELECT 1 FROM custom_levels cl
                    WHERE cl.group_id = {param_placeholder} 
                    AND cl.level_number = {param_placeholder}
                )
            """
        try:
            cursor5 = execute_query(conn, query5, (group_id, level_number))
            stats = cursor5.fetchone()
            if stats:
                print(f"Words in user_word_familiarity for this level:")
                if isinstance(stats, dict):
                    print(f"  Distinct words: {stats.get('word_count', 0)}")
                    print(f"  Total entries: {stats.get('total_entries', 0)}")
                else:
                    print(f"  Distinct words: {stats[0] if len(stats) > 0 else 0}")
                    print(f"  Total entries: {stats[1] if len(stats) > 1 else 0}")
        except Exception as e:
            print(f"Could not query user_word_familiarity stats: {e}")
        
    finally:
        conn.close()
    
    print("\n" + "="*80)
    print("Query completed!")
    print("="*80)

if __name__ == "__main__":
    main()

