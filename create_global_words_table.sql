-- Create global words table for PostgreSQL
-- This table stores word tooltip data globally (not per user)
-- Each word is stored once per language pair (target_language + native_language)

CREATE TABLE IF NOT EXISTS global_words (
    id SERIAL PRIMARY KEY,
    word VARCHAR(255) NOT NULL,
    target_language VARCHAR(10) NOT NULL,
    native_language VARCHAR(10) NOT NULL,
    translation TEXT,
    example TEXT,
    example_native TEXT,
    lemma VARCHAR(255),
    pos VARCHAR(50),
    ipa VARCHAR(255),
    audio_url TEXT,
    gender VARCHAR(20) DEFAULT 'none',
    plural VARCHAR(255),
    conj JSONB,
    comp JSONB,
    synonyms JSONB,
    collocations JSONB,
    cefr VARCHAR(10),
    freq_rank INTEGER,
    tags JSONB,
    note TEXT,
    word_hash VARCHAR(64) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique word per language pair
    UNIQUE(word, target_language, native_language)
);

-- Create indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_global_words_word_hash ON global_words(word_hash);
CREATE INDEX IF NOT EXISTS idx_global_words_word_lang ON global_words(word, target_language);
CREATE INDEX IF NOT EXISTS idx_global_words_native_lang ON global_words(native_language);
CREATE INDEX IF NOT EXISTS idx_global_words_target_lang ON global_words(target_language);
CREATE INDEX IF NOT EXISTS idx_global_words_created_at ON global_words(created_at);

-- Create function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_global_words_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Create trigger to automatically update updated_at
DROP TRIGGER IF EXISTS trigger_update_global_words_updated_at ON global_words;
CREATE TRIGGER trigger_update_global_words_updated_at
    BEFORE UPDATE ON global_words
    FOR EACH ROW
    EXECUTE FUNCTION update_global_words_updated_at();
