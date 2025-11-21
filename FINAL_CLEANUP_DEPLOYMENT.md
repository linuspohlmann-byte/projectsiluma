# 🚀 Cleanup Service - Finale Deployment-Anleitung

## ✅ Was bereits gemacht wurde:

1. ✅ Code ist bereit (`cleanup_service.py`)
2. ✅ `CLEANUP_SERVICE_URL` ist in Hauptapp gesetzt: `http://cleanup_serivce.railway.internal`
3. ✅ Alle Code-Änderungen sind committed
4. ✅ `railway.json` wurde erstellt (für automatisches Deployment)

## 🎯 Was du JETZT im Railway Dashboard machen musst:

### Schritt 1: Service finden und konfigurieren

1. **Öffne Railway Dashboard:** https://railway.app/dashboard
2. **Finde den Service mit ID:** `841598ff-e5ee-48bd-82c1-43b1533d8cb5`
   - Falls du den Service nicht findest, suche nach "cleanup" oder "cleanup_service"
3. **Klicke auf den Service**

### Schritt 2: Start Command setzen

1. **Gehe zu:** Settings → Deploy
2. **Setze "Start Command":** `python cleanup_service.py`
3. **Speichere**

### Schritt 3: DATABASE_URL verbinden

1. **Gehe zu:** Variables Tab
2. **Klicke:** "Add Variable from Service"
3. **Wähle:** Deinen PostgreSQL-Service
4. **Wähle:** `DATABASE_URL`
5. **Klicke:** "Add"

### Schritt 4: Deploy triggern

**Option A: Automatisch (wenn GitHub verbunden)**
- Pushe den Code zu GitHub
- Railway deployed automatisch

**Option B: Manuell**
- Klicke auf "Deploy" Button
- Oder: Settings → Deploy → "Redeploy"

## ✅ Verifizierung

Nach dem Deployment:

1. **Prüfe Logs:**
   - Im Service → Logs Tab
   - Sollte zeigen:
     ```
     🧹 Word Duplicate Cleanup Service
     🚀 Starting cleanup service on 0.0.0.0:XXXX
     ```

2. **Teste Health Endpoint:**
   - Im Service → Settings → Domains
   - Kopiere die private Domain
   - Teste: `curl http://cleanup_service.railway.internal/health`
   - Sollte zurückgeben: `{"status": "ok", "service": "cleanup-service"}`

3. **Teste von UI:**
   - Als Admin (User ID 2) einloggen
   - Settings → Admin Tools
   - "🔍 Dry Run" klicken
   - Sollte funktionieren!

## 🐛 Troubleshooting

### Service startet nicht
- Prüfe Railway Logs für Fehlermeldungen
- Verifiziere, dass `cleanup_service.py` im Root-Verzeichnis ist
- Prüfe, ob alle Dependencies in `requirements.txt` sind

### "Failed to connect to cleanup service"
- Prüfe, ob `CLEANUP_SERVICE_URL` korrekt gesetzt ist
- Verifiziere, dass der Service-Name in der URL mit dem Railway-Service-Namen übereinstimmt
- Prüfe, ob beide Services im selben Railway-Projekt sind

### "Database connection error"
- Prüfe, ob `DATABASE_URL` im cleanup_service gesetzt ist
- Verifiziere, dass es derselbe `DATABASE_URL` wie in der Hauptapp ist

## 📝 Wichtige Hinweise

1. **Service-Name:** Der Service-Name in Railway muss mit dem in `CLEANUP_SERVICE_URL` übereinstimmen
2. **Private Domain:** Verwende immer `.railway.internal`, nie die öffentliche URL
3. **DATABASE_URL:** Beide Services (Hauptapp und Cleanup) müssen auf dieselbe PostgreSQL-Datenbank zugreifen
4. **Start Command:** Muss `python cleanup_service.py` sein

