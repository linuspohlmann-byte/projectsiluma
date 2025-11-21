# 🧹 Cleanup Service - Quick Reference

## ⚡ Schnellstart

### Cleanup auslösen (UI)
1. Als Admin (User ID 2) einloggen
2. Settings → Admin Tools
3. "🔍 Dry Run" oder "🧹 Run Cleanup" klicken

### Cleanup auslösen (CLI)
```bash
# Dry Run
./trigger_cleanup.sh dry-run

# Echter Cleanup
./trigger_cleanup.sh run
```

### Monitoring
```bash
# Status prüfen
./monitor_cleanup.sh

# Live-Logs
railway logs --service cleanup_serivce --follow
```

## 📊 Monitoring-Befehle

### Railway Logs
```bash
# Cleanup-Service Logs (letzte 50 Zeilen)
railway logs --service cleanup_serivce --tail 50

# Live-Logs (folgt neuen Einträgen)
railway logs --service cleanup_serivce --follow

# Hauptapp Logs
railway logs --service projectsiluma --tail 50
```

### Health Check
```bash
# Prüfe ob Service läuft
curl http://cleanup_serivce.railway.internal/health
```

### Status prüfen
```bash
# Kompletter Status
./monitor_cleanup.sh

# Nur Konfiguration
railway variables --service projectsiluma | grep CLEANUP
railway variables --service cleanup_serivce | grep DATABASE
```

## 🔍 Was wird bereinigt?

1. **Duplikate identifizieren:**
   - Wörter mit identischer Normalisierung
   - Gleiche `language` und `native_language`
   - Beispiel: "ávexti" und "ávexti." → Duplikat

2. **Referenzen aktualisieren:**
   - `user_word_familiarity.word_id` → zeigt auf kanonischen Eintrag
   - Duplikate in `user_word_familiarity` werden gemerged

3. **Duplikate entfernen:**
   - Nur kanonischer Eintrag bleibt erhalten
   - Duplikate werden gelöscht

## 📈 Erwartete Ergebnisse

### Vor Cleanup:
- X Duplikat-Gruppen
- Y Duplikat-Einträge
- Z Referenzen in `user_word_familiarity`

### Nach Cleanup:
- 0 Duplikat-Gruppen
- 0 Duplikat-Einträge
- Alle Referenzen zeigen auf kanonische Einträge

## ⚠️ Wichtige Hinweise

1. **Immer zuerst Dry Run:** Zeigt was passieren würde
2. **Backup:** Railway macht automatische Backups
3. **Dauer:** Cleanup kann 1-5 Minuten dauern (je nach Datenmenge)
4. **Keine Downtime:** Cleanup läuft im Hintergrund

## 🆘 Bei Problemen

```bash
# 1. Prüfe Service-Status
./monitor_cleanup.sh

# 2. Prüfe Logs
railway logs --service cleanup_serivce --tail 100

# 3. Prüfe Konfiguration
railway variables --service projectsiluma | grep CLEANUP
railway variables --service cleanup_serivce | grep DATABASE

# 4. Teste Health Check
curl http://cleanup_serivce.railway.internal/health
```

