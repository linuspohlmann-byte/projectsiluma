# 🚀 Cleanup Service - Komplettes Setup

## ⚡ Schnellstart (1 Befehl)

```bash
./SETUP_CLEANUP_NOW.sh
```

Das Script führt dich durch alle Schritte!

## 📋 Was wird konfiguriert?

1. ✅ Railway CLI Installation (falls nötig)
2. ✅ Projekt-Verlinkung
3. ✅ Environment Variable `CLEANUP_SERVICE_URL`
4. ✅ PostgreSQL-Verbindung für cleanup_serivce

## 🔧 Manuelle Konfiguration

Falls das automatische Script nicht funktioniert:

### 1. Environment Variable setzen

**Im Railway Dashboard:**
- Gehe zu deinem **Hauptapp-Service** (nicht cleanup_serivce!)
- Variables → New Variable
- Name: `CLEANUP_SERVICE_URL`
- Value: `http://cleanup_serivce.railway.internal`
- Add

### 2. PostgreSQL verbinden

**Im Railway Dashboard:**
- Gehe zu `cleanup_serivce` Service
- Variables → Add Variable from Service
- Wähle deinen PostgreSQL-Service
- Wähle `DATABASE_URL`
- Add

## ✅ Verifizierung

Nach dem Setup:

1. **Service Logs prüfen:**
   ```bash
   railway logs --service cleanup_serivce
   ```
   Sollte zeigen: `🧹 Word Duplicate Cleanup Service`

2. **Von UI testen:**
   - Als Admin (User ID 2) einloggen
   - Settings öffnen
   - Admin-Bereich sollte sichtbar sein
   - "🔍 Dry Run" klicken

## 🆘 Troubleshooting

### "Failed to connect to cleanup service"
- Prüfe: `CLEANUP_SERVICE_URL` ist gesetzt
- Prüfe: cleanup_serivce Service läuft
- Prüfe: Beide Services im selben Projekt

### "Database connection error"
- Prüfe: PostgreSQL ist mit cleanup_serivce verbunden
- Prüfe: `DATABASE_URL` ist in cleanup_serivce gesetzt

### Admin-Bereich nicht sichtbar
- Prüfe: Du bist als User ID 2 eingeloggt
- Prüfe: Browser-Konsole für Fehler

## 📚 Weitere Dokumentation

- `RAILWAY_CLEANUP_SETUP.md` - Detaillierte Anleitung
- `CLEANUP_SERVICE_SETUP.md` - Technische Details
- `QUICK_SETUP.md` - Schnellreferenz

