-- Debug-Script für Custom Level Progress Problem
-- Story: "Kleine Gespräche im Alltag"
-- Level: "Im Park spielen und treffen"

-- 1. Finde die Story
SELECT 
    id as group_id,
    user_id,
    group_name,
    language,
    native_language,
    num_levels,
    status as group_status,
    created_at,
    updated_at
FROM custom_level_groups
WHERE LOWER(group_name) LIKE '%kleine gespräche%'
   OR LOWER(group_name) LIKE '%alltag%'
ORDER BY created_at DESC;

-- 2. Finde das spezifische Level (ersetze <group_id> mit ID aus Schritt 1)
-- SELECT 
--     id,
--     group_id,
--     level_number,
--     title,
--     topic,
--     word_count,
--     created_at,
--     updated_at,
--     CASE 
--         WHEN content::text = '{}' THEN 'EMPTY'
--         WHEN content->'items' IS NULL THEN 'NO_ITEMS'
--         WHEN jsonb_array_length(content->'items') = 0 THEN 'ZERO_ITEMS'
--         ELSE 'HAS_ITEMS'
--     END as content_status,
--     jsonb_array_length(COALESCE(content->'items', '[]'::jsonb)) as item_count
-- FROM custom_levels
-- WHERE group_id = <group_id>
--   AND (LOWER(title) LIKE '%park%' OR LOWER(title) LIKE '%spielen%' OR LOWER(title) LIKE '%treffen%')
-- ORDER BY level_number;

-- 3. Prüfe alle Level der Story (ersetze <group_id> mit ID aus Schritt 1)
-- SELECT 
--     level_number,
--     title,
--     word_count,
--     CASE 
--         WHEN content->'items' IS NULL THEN 0
--         ELSE jsonb_array_length(content->'items')
--     END as item_count,
--     CASE 
--         WHEN word_count = 0 THEN '⚠️ NO_WORDS'
--         WHEN content->'items' IS NULL OR jsonb_array_length(content->'items') = 0 THEN '⚠️ NO_ITEMS'
--         ELSE '✅ OK'
--     END as status
-- FROM custom_levels
-- WHERE group_id = <group_id>
-- ORDER BY level_number;

-- 4. Prüfe Progress für alle User (ersetze <group_id> und <level_number>)
-- SELECT 
--     user_id,
--     group_id,
--     level_number,
--     total_words,
--     familiarity_0,
--     familiarity_1,
--     familiarity_2,
--     familiarity_3,
--     familiarity_4,
--     familiarity_5,
--     score,
--     status,
--     completed_at,
--     last_updated,
--     CASE 
--         WHEN status = 'completed' AND total_words = 0 THEN '⚠️ COMPLETED_BUT_NO_WORDS'
--         WHEN status = 'completed' AND (familiarity_0 + familiarity_1 + familiarity_2 + familiarity_3 + familiarity_4 + familiarity_5) = 0 THEN '⚠️ COMPLETED_BUT_NO_COUNTS'
--         WHEN status = 'completed' THEN '✅ COMPLETED_WITH_DATA'
--         WHEN total_words > 0 THEN '✅ HAS_PROGRESS'
--         ELSE '⚠️ NO_PROGRESS'
--     END as progress_status
-- FROM custom_level_progress
-- WHERE group_id = <group_id>
--   AND level_number = <level_number>
-- ORDER BY user_id;

-- 5. Prüfe ob Level Wörter hat (ersetze <group_id> und <level_number>)
-- SELECT 
--     cl.id,
--     cl.group_id,
--     cl.level_number,
--     cl.title,
--     cl.word_count as db_word_count,
--     jsonb_array_length(COALESCE(cl.content->'items', '[]'::jsonb)) as json_item_count,
--     -- Extrahiere Wörter aus items
--     (
--         SELECT COUNT(DISTINCT word)
--         FROM jsonb_array_elements(cl.content->'items') AS item,
--              jsonb_array_elements_text(item->'words') AS word
--     ) as extracted_word_count,
--     -- Zeige Sample-Wörter
--     (
--         SELECT array_agg(DISTINCT word ORDER BY word)
--         FROM (
--             SELECT DISTINCT word
--             FROM jsonb_array_elements(cl.content->'items') AS item,
--                  jsonb_array_elements_text(item->'words') AS word
--             LIMIT 10
--         ) sub
--     ) as sample_words
-- FROM custom_levels cl
-- WHERE cl.group_id = <group_id>
--   AND cl.level_number = <level_number>;

-- 6. Prüfe User Word Familiarity für Level-Wörter (ersetze <user_id>, <group_id>, <level_number>)
-- WITH level_words AS (
--     SELECT DISTINCT word
--     FROM custom_levels cl,
--          jsonb_array_elements(cl.content->'items') AS item,
--          jsonb_array_elements_text(item->'words') AS word
--     WHERE cl.group_id = <group_id>
--       AND cl.level_number = <level_number>
-- )
-- SELECT 
--     w.word,
--     w.id as word_id,
--     COALESCE(uwf.familiarity, 0) as familiarity,
--     COALESCE(uwf.seen_count, 0) as seen_count,
--     COALESCE(uwf.correct_count, 0) as correct_count,
--     CASE 
--         WHEN uwf.word_id IS NULL THEN '⚠️ NOT_IN_USER_FAMILIARITY'
--         ELSE '✅ IN_USER_FAMILIARITY'
--     END as status
-- FROM level_words lw
-- LEFT JOIN words w ON LOWER(w.word) = LOWER(lw.word) AND w.language = (SELECT language FROM custom_level_groups WHERE id = <group_id>)
-- LEFT JOIN user_word_familiarity uwf ON uwf.word_id = w.id AND uwf.user_id = <user_id>
-- ORDER BY COALESCE(uwf.familiarity, 0) DESC, w.word;

-- 7. Vergleich: Level word_count vs. tatsächliche Wörter
-- SELECT 
--     cl.level_number,
--     cl.title,
--     cl.word_count as db_word_count,
--     (
--         SELECT COUNT(DISTINCT LOWER(TRIM(REGEXP_REPLACE(word, '[.!?,;:—–-]+$', ''))))
--         FROM jsonb_array_elements(cl.content->'items') AS item,
--              jsonb_array_elements_text(item->'words') AS word
--         WHERE word IS NOT NULL AND TRIM(word) != ''
--     ) as actual_word_count,
--     CASE 
--         WHEN cl.word_count = 0 THEN '⚠️ DB_COUNT_ZERO'
--         WHEN cl.word_count != (
--             SELECT COUNT(DISTINCT LOWER(TRIM(REGEXP_REPLACE(word, '[.!?,;:—–-]+$', ''))))
--             FROM jsonb_array_elements(cl.content->'items') AS item,
--                  jsonb_array_elements_text(item->'words') AS word
--             WHERE word IS NOT NULL AND TRIM(word) != ''
--         ) THEN '⚠️ MISMATCH'
--         ELSE '✅ MATCH'
--     END as count_status
-- FROM custom_levels cl
-- WHERE cl.group_id = <group_id>
-- ORDER BY cl.level_number;


