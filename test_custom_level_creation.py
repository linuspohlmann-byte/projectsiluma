#!/usr/bin/env python3
"""
Test script to create a custom level group and check if levels are created
"""

import os
import sys
import json
from datetime import datetime, UTC

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_custom_level_creation():
    """Test creating a custom level group"""
    print("🧪 Testing custom level creation...")
    
    try:
        from server.services.custom_levels import create_custom_level_group, generate_custom_levels
        
        # Test parameters
        user_id = 1  # Assuming user ID 1 exists
        language = "de"
        native_language = "en"
        group_name = "Test Supermarkt Gruppe"
        context_description = "Im Supermarkt einkaufen"
        cefr_level = "A1"
        num_levels = 5  # Small number for testing
        
        print(f"📝 Creating group: {group_name}")
        print(f"   Language: {language} -> {native_language}")
        print(f"   CEFR: {cefr_level}, Levels: {num_levels}")
        
        # Create the group
        group_id = create_custom_level_group(
            user_id=user_id,
            language=language,
            native_language=native_language,
            group_name=group_name,
            context_description=context_description,
            cefr_level=cefr_level,
            num_levels=num_levels
        )
        
        if not group_id:
            print("❌ Failed to create custom level group")
            return False
        
        print(f"✅ Created group with ID: {group_id}")
        
        # Generate levels
        print(f"🚀 Generating {num_levels} levels...")
        success = generate_custom_levels(
            group_id=group_id,
            language=language,
            native_language=native_language,
            context_description=context_description,
            cefr_level=cefr_level,
            num_levels=num_levels
        )
        
        if not success:
            print("❌ Failed to generate levels")
            return False
        
        print(f"✅ Successfully generated levels for group {group_id}")
        
        # Check if levels were created
        from server.db_config import get_database_config, get_db_connection, execute_query
        config = get_database_config()
        conn = get_db_connection()
        
        try:
            if config['type'] == 'postgresql':
                result = execute_query(conn, '''
                    SELECT level_number, title, topic, word_count
                    FROM custom_levels 
                    WHERE group_id = %s 
                    ORDER BY level_number
                ''', (group_id,))
                levels = [dict(row) for row in result.fetchall()]
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT level_number, title, topic, word_count
                    FROM custom_levels 
                    WHERE group_id = ? 
                    ORDER BY level_number
                ''', (group_id,))
                levels = [{'level_number': row[0], 'title': row[1], 'topic': row[2], 'word_count': row[3]} for row in cursor.fetchall()]
            
            print(f"📖 Created {len(levels)} levels:")
            for level in levels:
                print(f"  - Level {level['level_number']}: {level['title']} (words: {level['word_count']})")
            
            if len(levels) == num_levels:
                print("🎉 SUCCESS: All levels created correctly!")
                return True
            else:
                print(f"⚠️ WARNING: Expected {num_levels} levels, but found {len(levels)}")
                return False
                
        finally:
            conn.close()
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_custom_level_creation()
    if success:
        print("\n✅ Test passed!")
        sys.exit(0)
    else:
        print("\n❌ Test failed!")
        sys.exit(1)
