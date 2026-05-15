# 🧹 Word Duplicate Cleanup - Komplette Anleitung

## Übersicht

Das Cleanup-System verhindert und bereinigt Duplikate in der `words` Tabelle durch:
1. **Normalisierung** bei der Erstellung (verhindert neue Duplikate)
2. **Automatisches Cleanup** (bereinigt bestehende Duplikate)

## 🚀 Cleanup auslösen

### Methode 1: Über die UI (Empfohlen)

1. **Als Admin einloggen** (User ID = 2)
2. **Settings öffnen** (⚙️ Button)
3. **Admin-Bereich** (unten in Settings)
4. **"🔍 Dry Run"** klicken (zeigt was passieren würde)
5. **"🧹 Run Cleanup"** klicken (führt Cleanup aus)

### Methode 2: Über CLI

```bash
# Dry Run (empfohlen zuerst)
./trigger_cleanup.sh dry-run

# Echter Cleanup
./trigger_cleanup.sh run
```

### Methode 3: Direkt über API

```bash
# Mit Session Token (als Admin)
curl -X POST https://polo-lingua.de/api/admin/cleanup-duplicates \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"dry_run": false}'
```

## 📊 Monitoring

### Live-Monitoring

```bash
# Kompletter Status-Check
./monitor_cleanup.sh

# Live-Logs (folgt neuen Einträgen)
railway logs --service cleanup_serivce --follow

# Beide Services gleichzeitig
railway logs --service projectsiluma --follow &
railway logs --service cleanup_serivce --follow &
```

### UI-Monitoring

Nach dem Klicken auf "Run Cleanup":
- Status wird in Echtzeit angezeigt
- Zeigt detaillierte Statistiken
- Zeigt Dauer der Operation
- Zeigt eventuelle Fehler

### Health Check

```bash
# Prüfe ob Service läuft
curl http://cleanup_serivce.railway.internal/health
```

Sollte zurückgeben:
```json
{"status": "ok", "service": "cleanup-service"}
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

## 🔍 Was wird bereinigt?

### Duplikat-Erkennung:
- Wörter mit identischer Normalisierung
- Gleiche `language` und `native_language`
- Beispiel: "ávexti" und "ávexti." → werden als Duplikat erkannt

### Bereinigung:
1. **Kanonischer Eintrag** wird identifiziert (ältester/vollständigster)
2. **Referenzen aktualisiert:** `user_word_familiarity.word_id` zeigt auf kanonischen Eintrag
3. **Duplikate gemerged:** Wenn mehrere `user_word_familiarity` Einträge existieren
4. **Duplikate gelöscht:** Nur kanonischer Eintrag bleibt

## 📅 Empfohlene Häufigkeit

- **Nach großen Imports:** Sofort
- **Wöchentlich:** Regelmäßige Wartung
- **Bei Problemen:** Bei Bedarf

## 🎯 Best Practices

1. ✅ **Immer zuerst Dry Run:** Zeigt was passieren würde
2. ✅ **Nach Cleanup prüfen:** Verifiziere Statistiken
3. ✅ **Backup:** Railway macht automatische Backups
4. ✅ **Monitoring:** Prüfe Logs nach Cleanup

## 🆘 Troubleshooting

### "Failed to connect to cleanup service"
```bash
# Prüfe Konfiguration
railway variables --service projectsiluma | grep CLEANUP_SERVICE_URL

# Prüfe ob Service läuft
railway logs --service cleanup_serivce --tail 20
```

### "Database connection error"
```bash
# Prüfe Database-Verbindung
railway variables --service cleanup_serivce | grep DATABASE_URL
```

### Cleanup dauert sehr lange
- Normal bei großen Datenmengen
- Prüfe Logs für Fortschritt
- Timeout ist auf 5 Minuten gesetzt

## 📚 Weitere Dokumentation

- `CLEANUP_USAGE.md` - Detaillierte Verwendungsanleitung
- `CLEANUP_QUICK_REFERENCE.md` - Schnellreferenz
- `RAILWAY_CLEANUP_SETUP.md` - Setup-Anleitung

