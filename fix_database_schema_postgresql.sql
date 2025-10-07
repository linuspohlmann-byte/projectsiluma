-- PostgreSQL Database Schema Fix for Railway
-- Fix database schema for user_word_familiarity table
-- This script should be run on Railway PostgreSQL to fix the missing word_hash column

-- First, check if the table exists and what columns it has
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'user_word_familiarity' 
ORDER BY ordinal_position;

-- If the table doesn't exist or is missing the word_hash column, recreate it
DROP TABLE IF EXISTS user_word_familiarity CASCADE;

-- Create the user_word_familiarity table with the correct schema
CREATE TABLE user_word_familiarity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    word_hash VARCHAR(32) NOT NULL,
    native_language VARCHAR(10) NOT NULL,
    familiarity INTEGER NOT NULL DEFAULT 0 CHECK (familiarity >= 0 AND familiarity <= 5),
    seen_count INTEGER NOT NULL DEFAULT 0,
    correct_count INTEGER NOT NULL DEFAULT 0,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, word_hash, native_language)
);

-- Create indexes for better performance
CREATE INDEX idx_user_word_familiarity_user_hash 
ON user_word_familiarity(user_id, word_hash);

CREATE INDEX idx_user_word_familiarity_native_lang 
ON user_word_familiarity(native_language);

CREATE INDEX idx_user_word_familiarity_familiarity 
ON user_word_familiarity(familiarity);

-- Verify the table was created correctly
SELECT column_name, data_type, is_nullable 
FROM information_schema.columns 
WHERE table_name = 'user_word_familiarity' 
ORDER BY ordinal_position;

-- Show the table structure (PostgreSQL specific)
\d user_word_familiarity;
