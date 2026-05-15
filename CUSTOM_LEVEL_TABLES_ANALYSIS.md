# Analyse: Custom Level Tabellen in PostgreSQL

## Tabellen-Übersicht

### 1. `custom_level_groups`
**Zweck:** Speichert die Story/Gruppe-Metadaten (eine Story = eine Gruppe)

**Struktur:**
- `id` (PRIMARY KEY) - Eindeutige Gruppen-ID
- `user_id` - Besitzer der Story
- `language` - Zielsprache (z.B. "de")
- `native_language` - Muttersprache (z.B. "en")
- `group_name` - Name der Story (z.B. "Kleine Gespräche im Alltag")
- `context_description` - Beschreibung/Kontext
- `topic` - Hauptthema
- `cefr_level` - CEFR-Level (A1, A2, etc.)
- `num_levels` - Anzahl der Level in der Story
- `status` - Status (active, published, etc.)
- `created_at`, `updated_at` - Zeitstempel

**Verwendung im Code:**
- `server/services/custom_levels.py`: `create_custom_level_group()`, `get_custom_level_groups()`, `get_custom_level_group()`
- `server/db.py`: `create_custom_level_groups_table()`
- Wird verwendet um Stories zu erstellen, zu laden und zu verwalten

---

### 2. `custom_levels`
**Zweck:** Speichert die einzelnen Level innerhalb einer Story

**Struktur:**
- `id` (PRIMARY KEY) - Eindeutige Level-ID
- `group_id` (FOREIGN KEY → custom_level_groups.id) - Zu welcher Story gehört dieses Level
- `level_number` - Level-Nummer innerhalb der Story (1, 2, 3, ...)
- `title` - Level-Titel (z.B. "Im Park spielen und treffen")
- `topic` - Level-Thema
- `content` (TEXT/JSON) - Vollständiger Level-Inhalt (Sätze, Wörter, etc.) als JSON
- `word_count` - Anzahl der Wörter im Level
- `created_at`, `updated_at` - Zeitstempel
- UNIQUE(group_id, level_number) - Jedes Level ist eindeutig innerhalb einer Story

**Verwendung im Code:**
- `server/services/custom_levels.py`: `save_custom_level()`, `get_custom_level()`, `get_custom_levels_for_group()`
- `server/db.py`: `create_custom_levels_table()`
- Wird verwendet um Level-Inhalte zu speichern und zu laden

---

### 3. `custom_level_progress`
**Zweck:** Cached den Fortschritt eines Users für ein bestimmtes Level (Performance-Optimierung)

**Struktur:**
- `id` (PRIMARY KEY) - Eindeutige Progress-ID
- `user_id` (FOREIGN KEY → users.id) - Welcher User
- `group_id` (FOREIGN KEY → custom_level_groups.id) - Welche Story
- `level_number` - Welches Level
- `total_words` - Gesamtanzahl Wörter im Level
- `familiarity_0` bis `familiarity_5` - Anzahl Wörter pro Familiarity-Level (0=unbekannt, 5=vollständig gelernt)
- `score` - Level-Score (0-100)
- `status` - Status: 'not_started', 'in_progress', 'completed'
- `completed_at` - Wann wurde das Level abgeschlossen
- `last_updated`, `created_at` - Zeitstempel
- UNIQUE(user_id, group_id, level_number) - Ein Progress-Eintrag pro User/Level

**Verwendung im Code:**
- `server/db_progress_cache.py`: `create_custom_level_progress_table()`, `update_custom_level_progress()`, `get_custom_level_progress()`, `refresh_custom_level_progress()`
- `app.py`: `/api/custom-levels/<group_id>/<level_number>/progress` - API-Endpoint
- Wird verwendet um den Fortschritt zu cachen und schnell anzuzeigen

---

## Beziehungen zwischen den Tabellen

```
custom_level_groups (1) ──< (N) custom_levels
     │                              │
     │                              │
     └──< (N) custom_level_progress ─┘
              (pro User/Level)
```

**Erklärung:**
- Eine Story (`custom_level_groups`) hat mehrere Level (`custom_levels`)
- Für jedes Level kann es mehrere Progress-Einträge geben (einer pro User)
- `custom_level_progress` ist ein **Cache** - die echten Daten kommen aus `user_word_familiarity` und `words` Tabellen

---

## Problem: Level zeigt "abgeschlossen" aber kein Progress

### Mögliche Ursachen:

#### 1. **Status gesetzt, aber Progress nicht berechnet**
- `status = 'completed'` wurde in `custom_level_progress` gesetzt (z.B. durch `complete_custom_level()`)
- Aber `total_words`, `familiarity_0-5` wurden nie berechnet oder sind 0
- **Lösung:** `refresh_custom_level_progress()` aufrufen

#### 2. **Level hat keine Wörter (word_count = 0)**
- Level wurde mit "ultra-lazy loading" erstellt (nur Titel/Topic, keine Sätze)
- `content.items` ist leer oder `word_count = 0`
- Progress kann nicht berechnet werden
- **Lösung:** Level muss erst generiert werden (`enrich_custom_level_words_on_demand()`)

#### 3. **Progress Cache veraltet**
- Progress wurde berechnet, aber Level-Inhalt wurde später geändert
- Cache zeigt alte Daten
- **Lösung:** Cache refreshen

#### 4. **Wörter nicht in `user_word_familiarity`**
- Level hat Wörter, aber User hat noch keine Wörter gelernt
- `calculate_familiarity_counts_from_user_words()` findet keine Einträge
- Alle Wörter werden als `familiarity_0` gezählt
- **Lösung:** Normal - User muss erst Wörter lernen

#### 5. **Fehlende Foreign Key Beziehung**
- `group_id` oder `level_number` stimmt nicht überein
- Progress-Eintrag existiert, aber Level existiert nicht oder gehört zu anderer Story
- **Lösung:** Datenintegrität prüfen

---

## Spezifische Analyse: "Kleine Gespräche im Alltag" / "Im Park spielen und treffen"

### Prüfschritte:

1. **Story finden:**
```sql
SELECT id, group_name, user_id, language, native_language, num_levels
FROM custom_level_groups
WHERE group_name LIKE '%Kleine Gespräche%' OR group_name LIKE '%kleine gespräche%';
```

2. **Level finden:**
```sql
SELECT id, group_id, level_number, title, topic, word_count
FROM custom_levels
WHERE group_id = <group_id_from_step_1>
  AND (title LIKE '%Park%' OR title LIKE '%park%');
```

3. **Progress prüfen:**
```sql
SELECT user_id, group_id, level_number, total_words, 
       familiarity_0, familiarity_1, familiarity_2, 
       familiarity_3, familiarity_4, familiarity_5,
       score, status, completed_at
FROM custom_level_progress
WHERE group_id = <group_id>
  AND level_number = <level_number>;
```

4. **Level-Inhalt prüfen:**
```sql
SELECT id, word_count, 
       jsonb_array_length(content->'items') as item_count,
       content->'items' as items_sample
FROM custom_levels
WHERE group_id = <group_id>
  AND level_number = <level_number>;
```

### Typische Probleme:

**Problem A: Level hat `word_count = 0`**
- Level wurde nie vollständig generiert
- `content.items` ist leer oder fehlt
- **Fix:** Level muss generiert werden

**Problem B: Progress existiert mit `status = 'completed'` aber `total_words = 0`**
- Level wurde als "completed" markiert, bevor Progress berechnet wurde
- **Fix:** `refresh_custom_level_progress(user_id, group_id, level_number)` aufrufen

**Problem C: Progress fehlt komplett**
- Level wurde nie gestartet oder Progress wurde nie initialisiert
- **Fix:** Progress initialisieren oder refreshen

---

## Code-Stellen für Debugging

### 1. Progress berechnen/refreshen:
```python
# server/db_progress_cache.py
refresh_custom_level_progress(user_id, group_id, level_number)
```

### 2. Level generieren (falls fehlt):
```python
# server/services/custom_levels.py
enrich_custom_level_words_on_demand(group_id, level_number, language, native_language)
```

### 3. Progress abrufen:
```python
# server/db_progress_cache.py
get_custom_level_progress(user_id, group_id, level_number)
```

### 4. API-Endpoint:
```
GET /api/custom-levels/<group_id>/<level_number>/progress
```

---

## Empfohlene Lösung

1. **Prüfe ob Level vollständig generiert ist:**
   - `word_count > 0` in `custom_levels`
   - `content.items` ist nicht leer

2. **Prüfe Progress-Cache:**
   - Existiert ein Eintrag in `custom_level_progress`?
   - Ist `total_words > 0`?

3. **Falls Progress fehlt oder falsch:**
   - `refresh_custom_level_progress()` aufrufen
   - Dies berechnet `familiarity_0-5` aus `user_word_familiarity` Tabelle

4. **Falls Level nicht generiert:**
   - `enrich_custom_level_words_on_demand()` aufrufen
   - Dies generiert Sätze und Wörter für das Level

---

## Zusammenfassung

- **custom_level_groups**: Story-Metadaten
- **custom_levels**: Level-Inhalte (Sätze, Wörter als JSON)
- **custom_level_progress**: Gecachter User-Fortschritt pro Level

**Problem:** Level zeigt "completed" aber kein Progress
- Meistens: `status = 'completed'` gesetzt, aber `total_words = 0` oder Progress nie berechnet
- Lösung: `refresh_custom_level_progress()` aufrufen oder Level erst generieren


