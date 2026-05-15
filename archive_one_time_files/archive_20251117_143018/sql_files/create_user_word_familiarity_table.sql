-- Create user_word_familiarity table for PostgreSQL
CREATE TABLE IF NOT EXISTS user_word_familiarity (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    word_hash TEXT NOT NULL,
    native_language TEXT NOT NULL,
    familiarity INTEGER DEFAULT 0,
    seen_count INTEGER DEFAULT 0,
    correct_count INTEGER DEFAULT 0,
    unlocked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, word_hash, native_language)
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_user_hash ON user_word_familiarity(user_id, word_hash);
CREATE INDEX IF NOT EXISTS idx_user_word_familiarity_native_lang ON user_word_familiarity(native_language);
