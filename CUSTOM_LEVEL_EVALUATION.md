# Custom Level Evaluation über PostgreSQL

## Übersicht

Die Custom Level Evaluation wurde vollständig auf PostgreSQL umgestellt. Alle Evaluations-Daten werden nun in der `custom_level_progress` Tabelle gespeichert.

## Datenbankschema

### `custom_level_progress` Tabelle

```sql
CREATE TABLE custom_level_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    group_id INTEGER NOT NULL,
    level_number INTEGER NOT NULL,
    total_words INTEGER DEFAULT 0,
    familiarity_0 INTEGER DEFAULT 0,
    familiarity_1 INTEGER DEFAULT 0,
    familiarity_2 INTEGER DEFAULT 0,
    familiarity_3 INTEGER DEFAULT 0,
    familiarity_4 INTEGER DEFAULT 0,
    familiarity_5 INTEGER DEFAULT 0,
    score REAL,                          -- NEU: Level Score (0.0 - 1.0)
    status VARCHAR(50) DEFAULT 'not_started',  -- NEU: 'not_started', 'in_progress', 'completed'
    completed_at TIMESTAMP,              -- NEU: Zeitstempel des Abschlusses
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    FOREIGN KEY (group_id) REFERENCES custom_level_groups (id) ON DELETE CASCADE,
    UNIQUE(user_id, group_id, level_number)
);
```

## API-Endpoints

### 1. Level abschließen

**POST** `/api/custom-levels/{group_id}/{level_number}/finish`

**Request Body:**
```json
{
  "run_id": 123,
  "score": 0.85
}
```

**Response:**
```json
{
  "success": true,
  "message": "Custom level completed",
  "score": 0.85,
  "status": "completed",
  "fam_counts": {
    "0": 2,
    "1": 3,
    "2": 5,
    "3": 8,
    "4": 10,
    "5": 12
  },
  "total_words": 40
}
```

**Logik:**
- Score >= 0.6 → Status = 'completed'
- Score < 0.6 → Status = 'in_progress'
- `completed_at` wird auf aktuellen Timestamp gesetzt
- Familiarity Counts werden neu berechnet

### 2. Level-Progress abrufen

**GET** `/api/custom-levels/{group_id}/{level_number}/progress`

**Response:**
```json
{
  "success": true,
  "score": 0.85,
  "status": "completed",
  "fam_counts": {
    "0": 2,
    "1": 3,
    "2": 5,
    "3": 8,
    "4": 10,
    "5": 12
  },
  "total_words": 40,
  "completed_at": "2025-10-09T12:34:56.789Z",
  "last_updated": "2025-10-09T12:34:56.789Z"
}
```

### 3. Gruppen-Progress abrufen

**GET** `/api/custom-levels/{group_id}/progress`

**Response:**
```json
{
  "success": true,
  "levels": [
    {
      "level": 1,
      "score": 0.85,
      "status": "completed",
      "fam_counts": {...},
      "total_words": 40,
      "completed_at": "2025-10-09T12:34:56.789Z",
      "last_updated": "2025-10-09T12:34:56.789Z"
    },
    {
      "level": 2,
      "score": 0.72,
      "status": "completed",
      "fam_counts": {...},
      "total_words": 38,
      "completed_at": "2025-10-09T13:45:12.345Z",
      "last_updated": "2025-10-09T13:45:12.345Z"
    }
  ]
}
```

## Backend-Funktionen

### `complete_custom_level(user_id, group_id, level_number, score)`

Markiert ein Custom Level als abgeschlossen:
- Speichert den Score
- Setzt den Status ('completed' oder 'in_progress')
- Setzt `completed_at` Timestamp
- Aktualisiert Familiarity Counts

```python
from server.db_progress_cache import complete_custom_level

success = complete_custom_level(
    user_id=1,
    group_id=5,
    level_number=3,
    score=0.85
)
```

### `get_custom_level_progress(user_id, group_id, level_number)`

Ruft Progress-Daten für ein einzelnes Level ab:

```python
from server.db_progress_cache import get_custom_level_progress

progress = get_custom_level_progress(
    user_id=1,
    group_id=5,
    level_number=3
)

# Returns:
# {
#   'total_words': 40,
#   'fam_counts': {0: 2, 1: 3, 2: 5, 3: 8, 4: 10, 5: 12},
#   'score': 0.85,
#   'status': 'completed',
#   'completed_at': '2025-10-09T12:34:56.789Z',
#   'last_updated': '2025-10-09T12:34:56.789Z'
# }
```

### `get_custom_level_group_progress(user_id, group_id)`

Ruft Progress-Daten für alle Levels einer Gruppe ab:

```python
from server.db_progress_cache import get_custom_level_group_progress

progress = get_custom_level_group_progress(
    user_id=1,
    group_id=5
)

# Returns:
# {
#   1: {...},  # Level 1 data
#   2: {...},  # Level 2 data
#   3: {...}   # Level 3 data
# }
```

## Migration

### Bestehende Tabellen aktualisieren

Um bestehende `custom_level_progress` Tabellen zu aktualisieren, führen Sie das Migrations-Skript aus:

```bash
python migrate_custom_level_progress.py
```

Das Skript:
- Prüft, ob die Spalten `score`, `status`, `completed_at` existieren
- Fügt fehlende Spalten hinzu
- Funktioniert mit PostgreSQL und SQLite
- Ist idempotent (kann mehrmals ausgeführt werden)

### Manuelle Migration (PostgreSQL)

```sql
-- Spalten hinzufügen, falls nicht vorhanden
ALTER TABLE custom_level_progress 
ADD COLUMN IF NOT EXISTS score REAL;

ALTER TABLE custom_level_progress 
ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'not_started';

ALTER TABLE custom_level_progress 
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP;
```

### Manuelle Migration (SQLite)

```sql
-- Spalten hinzufügen
ALTER TABLE custom_level_progress ADD COLUMN score REAL;
ALTER TABLE custom_level_progress ADD COLUMN status TEXT DEFAULT 'not_started';
ALTER TABLE custom_level_progress ADD COLUMN completed_at TEXT;
```

## Frontend-Integration

Das Frontend ruft beim Abschluss eines Custom Levels automatisch den `/finish` Endpoint auf:

```javascript
// In lesson.js, nach Level-Abschluss
if (RUN._customGroupId && RUN._customLevelNumber) {
  await fetch(`/api/custom-levels/${RUN._customGroupId}/${RUN._customLevelNumber}/finish`, { 
    method:'POST', 
    headers, 
    body: JSON.stringify({ 
      run_id: RUN.id, 
      language: targetLang,
      score: score
    }) 
  });
}
```

Für die Evaluation werden die Daten aus dem Backend geladen:

```javascript
// In evaluation.js
const response = await fetch(
  `/api/custom-levels/${groupId}/${levelNumber}/progress`,
  { headers: authHeaders }
);
const data = await response.json();

// Verwende data.score, data.fam_counts, data.status für Anzeige
```

## Evaluations-Metriken

Die Evaluation zeigt folgende Daten aus `custom_level_progress`:

1. **Score** (Progress Ring)
   - Quelle: `custom_level_progress.score`
   - Anzeige: Als Prozentsatz (0.85 → 85%)

2. **Wörter gesamt**
   - Quelle: `custom_level_progress.total_words`
   - Oder: Summe aller familiarity Counts

3. **Gelernte Wörter**
   - Quelle: `custom_level_progress.familiarity_5`
   - Anzahl der Wörter mit Familiarity = 5

4. **Genauigkeit**
   - Berechnung: `(familiarity_5 / total_words) * 100`

5. **Familiarity Breakdown**
   - Quelle: `familiarity_0` bis `familiarity_5`
   - 6 Balken für die Verteilung

## Unterschiede zu normalen Levels

### Normale Levels
- Verwenden `user_progress` Tabelle
- Endpoint: `/api/level/finish`
- Speichert: `user_id`, `language`, `level`, `score`, `status`

### Custom Levels
- Verwenden `custom_level_progress` Tabelle
- Endpoint: `/api/custom-levels/{group_id}/{level_number}/finish`
- Speichert: `user_id`, `group_id`, `level_number`, `score`, `status`, `fam_counts`

## Troubleshooting

### Problem: Spalten fehlen
```
ERROR: column "score" of relation "custom_level_progress" does not exist
```

**Lösung:** Migrations-Skript ausführen
```bash
python migrate_custom_level_progress.py
```

### Problem: Progress wird nicht gespeichert
- Prüfen Sie, ob der Benutzer authentifiziert ist
- Prüfen Sie die Console-Logs für Fehler
- Verifizieren Sie, dass `group_id` und `level_number` korrekt sind

### Problem: Familiarity Counts sind alle 0
- Die Counts werden asynchron berechnet
- Rufen Sie `refresh_custom_level_progress()` auf, um sie neu zu berechnen

## Performance-Überlegungen

- Die Tabelle hat Indizes auf `(user_id, group_id)` für schnelle Abfragen
- Familiarity Counts werden gecacht, um wiederholte JOIN-Abfragen zu vermeiden
- `COALESCE` in UPDATE-Statements verhindert das Überschreiben von Daten

## Zukünftige Erweiterungen

Mögliche zukünftige Features:
- Zeit-Tracking (wie lange hat das Level gedauert?)
- Versuch-Zähler (wie oft wurde das Level gespielt?)
- Best Score (höchster Score für dieses Level)
- Achievements/Badges basierend auf Performance

