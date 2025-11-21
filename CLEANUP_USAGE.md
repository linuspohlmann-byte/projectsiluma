# 🧹 Cleanup Service - Verwendung und Monitoring

## 🚀 Cleanup auslösen

### Methode 1: Über die UI (Empfohlen)

1. **Als Admin einloggen:**
   - User ID muss `2` sein
   - Falls nicht vorhanden, erstelle einen Admin-User

2. **Settings öffnen:**
   - Klicke auf den Settings-Button (⚙️)
   - Scroll nach unten zum Admin-Bereich

3. **Dry Run testen (empfohlen):**
   - Klicke auf "🔍 Dry Run"
   - Zeigt eine Zusammenfassung ohne Änderungen
   - Prüfe die Statistiken

4. **Cleanup ausführen:**
   - Klicke auf "🧹 Run Cleanup"
   - Warte auf die Erfolgsmeldung
   - Prüfe die Statistiken (Duplikate gefunden, entfernt, etc.)

### Methode 2: Über API (für Automatisierung)

```bash
# Dry Run
curl -X POST https://polo-lingua.de/api/admin/cleanup-duplicates \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Echter Cleanup
curl -X POST https://polo-lingua.de/api/admin/cleanup-duplicates \
  -H "Authorization: Bearer YOUR_SESSION_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

### Methode 3: Direkt über Cleanup-Service

```bash
# Dry Run
curl -X POST http://cleanup_serivce.railway.internal/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": true}'

# Echter Cleanup
curl -X POST http://cleanup_serivce.railway.internal/cleanup \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

## 📊 Monitoring

### 1. Railway Logs (Echtzeit)

#### Hauptapp-Service Logs:
```bash
railway logs --service projectsiluma
```

#### Cleanup-Service Logs:
```bash
railway logs --service cleanup_serivce
```

#### Beide Services gleichzeitig:
```bash
railway logs --service projectsiluma --follow &
railway logs --service cleanup_serivce --follow &
```

### 2. UI-Status (In-App)

Nach dem Klicken auf "Run Cleanup" oder "Dry Run":
- Status wird im Admin-Bereich angezeigt
- Zeigt:
  - Anzahl gefundener Duplikate
  - Aktualisierte Referenzen
  - Gelöschte Einträge
  - Eventuelle Fehler

### 3. Health Check

```bash
# Prüfe ob Cleanup-Service läuft
curl http://cleanup_serivce.railway.internal/health

# Sollte zurückgeben:
# {"status": "ok", "service": "cleanup-service"}
```

### 4. Database-Query (Manuelle Prüfung)

```sql
-- Prüfe auf Duplikate (vor Cleanup)
WITH normalized_words AS (
  SELECT id, word, language, native_language,
         regexp_replace(regexp_replace(lower(trim(word)), '^[.!?,;:—–\-]+', ''), '[.!?,;:—–\-]+$', '') as normalized_word
  FROM words
),
duplicates AS (
  SELECT normalized_word, language, native_language, count(*) as count
  FROM normalized_words
  GROUP BY normalized_word, language, native_language
  HAVING count(*) > 1
)
SELECT count(*) as duplicate_groups, sum(count - 1) as total_duplicates
FROM duplicates;

-- Prüfe user_word_familiarity Referenzen
SELECT COUNT(*) as total_references
FROM user_word_familiarity;
```

## 📈 Erwartete Log-Ausgaben

### Erfolgreicher Cleanup:

```
🔄 Cleanup requested (dry_run=False)
🔍 Scanning for duplicate words...
📊 Found 1234 total words in database
🔍 Found 5 duplicate groups
📋 Summary:
   - 5 duplicate groups
   - 8 duplicate entries to remove
🔄 Updating user_word_familiarity references...
✅ Updated 12 references, merged 3 duplicate entries
🗑️  Removing duplicate word entries...
✅ Deleted 8 duplicate word entries
✅ Cleanup completed successfully!
```

### Dry Run:

```
🔄 Cleanup requested (dry_run=True)
🔍 Scanning for duplicate words...
📊 Found 1234 total words in database
🔍 Found 5 duplicate groups
📋 Summary:
   - 5 duplicate groups
   - 8 duplicate entries to remove
🔍 DRY RUN - No changes will be made
```

## 🔍 Troubleshooting

### Cleanup schlägt fehl

1. **Prüfe Logs:**
   ```bash
   railway logs --service cleanup_serivce --tail 100
   ```

2. **Prüfe Database-Verbindung:**
   ```bash
   railway variables --service cleanup_serivce | grep DATABASE_URL
   ```

3. **Prüfe Service-Status:**
   ```bash
   curl http://cleanup_serivce.railway.internal/health
   ```

### Keine Duplikate gefunden

- Das ist normal, wenn bereits alle Duplikate bereinigt wurden
- Prüfe mit SQL-Query (siehe oben)

### "Failed to connect to cleanup service"

1. Prüfe `CLEANUP_SERVICE_URL`:
   ```bash
   railway variables --service projectsiluma | grep CLEANUP_SERVICE_URL
   ```

2. Prüfe ob cleanup_serivce läuft:
   ```bash
   railway logs --service cleanup_serivce --tail 20
   ```

## 📅 Empfohlene Cleanup-Häufigkeit

- **Täglich:** Automatisch (kann später eingerichtet werden)
- **Wöchentlich:** Manuell über UI
- **Nach großen Imports:** Sofort nach dem Import

## 🎯 Best Practices

1. **Immer zuerst Dry Run:**
   - Zeigt was passieren würde
   - Keine Risiken

2. **Nach Cleanup prüfen:**
   - Prüfe Statistiken
   - Verifiziere dass keine Daten verloren gingen

3. **Backup vor großem Cleanup:**
   - Railway macht automatische Backups
   - Bei Bedarf manuelles Backup erstellen

