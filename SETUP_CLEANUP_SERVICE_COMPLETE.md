# ✅ Cleanup Service - Komplette Konfiguration

## Was wurde gemacht:

1. ✅ Code ist bereit (`cleanup_service.py`)
2. ✅ `CLEANUP_SERVICE_URL` ist in Hauptapp gesetzt: `http://cleanup_serivce.railway.internal`
3. ✅ Code wurde zu GitHub gepusht

## Was du jetzt im Railway Dashboard machen musst:

### 1. Cleanup Service konfigurieren (Service ID: 841598ff-e5ee-48bd-82c1-43b1533d8cb5)

1. **Gehe zu Railway Dashboard**
2. **Finde den Service mit ID:** `841598ff-e5ee-48bd-82c1-43b1533d8cb5`
3. **Setze Start Command:**
   - Settings → Deploy → Start Command
   - Wert: `python cleanup_service.py`
4. **Setze DATABASE_URL:**
   - Variables → Add Variable from Service
   - Wähle deinen PostgreSQL-Service
   - Wähle `DATABASE_URL`
5. **Deploy:**
   - Klicke "Deploy" oder pushe zu GitHub

### 2. Verifizierung

Nach dem Deployment sollten die Logs zeigen:
```
🧹 Word Duplicate Cleanup Service
🚀 Starting cleanup service on 0.0.0.0:XXXX
```

### 3. Testen

1. Als Admin (User ID 2) einloggen
2. Settings → Admin Tools
3. "🔍 Dry Run" klicken
4. Sollte funktionieren!

## Falls der Service nicht deployed wird:

1. Prüfe, ob der Service im Railway Dashboard existiert
2. Prüfe, ob "Start Command" gesetzt ist
3. Prüfe Railway Logs für Fehlermeldungen
4. Stelle sicher, dass `cleanup_service.py` im Root-Verzeichnis ist

