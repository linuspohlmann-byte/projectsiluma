# 🚀 Cleanup Service auf Railway deployen

## Problem
Der Cleanup-Service ist noch nicht auf Railway deployed. Railway verwendet standardmäßig nur ein `Procfile` im Root-Verzeichnis.

## Lösung: Separater Service im Railway Dashboard

### Schritt 1: Service im Railway Dashboard erstellen

1. **Gehe zu Railway Dashboard:**
   - Öffne https://railway.app/dashboard
   - Wähle dein Projekt aus

2. **Erstelle neuen Service:**
   - Klicke auf "**New Service**" (oder "+" Button)
   - Wähle "**GitHub Repo**"
   - Wähle dasselbe Repository wie deine Hauptapp

3. **Service konfigurieren:**
   - **Service Name:** `cleanup_service` (oder wie du ihn nennen willst)
   - **Root Directory:** `.` (aktuelles Verzeichnis)
   - **Start Command:** `python cleanup_service.py`
   - **Build Command:** (leer lassen, Railway erkennt Python automatisch)

### Schritt 2: Environment Variables setzen

Im neuen `cleanup_service` Service:

1. **Gehe zu "Variables" Tab**
2. **Füge hinzu:**
   - `DATABASE_URL` - Kopiere von deinem PostgreSQL-Service
     - Klicke "Add Variable from Service"
     - Wähle deinen PostgreSQL-Service
     - Wähle `DATABASE_URL`
   - `RAILWAY_SERVICE_NAME` = `cleanup_service` (optional, für Logging)
   - `RAILWAY_PRIVATE_DOMAIN` wird automatisch gesetzt

### Schritt 3: Hauptapp konfigurieren

Im **Hauptapp-Service** (nicht cleanup_service!):

1. **Gehe zu "Variables" Tab**
2. **Füge hinzu:**
   - `CLEANUP_SERVICE_URL` = `http://cleanup_service.railway.internal`
     - **Wichtig:** Verwende die private Domain (`.railway.internal`), nicht die öffentliche URL!
     - Der Service-Name muss mit dem Namen übereinstimmen, den du in Schritt 1 gewählt hast

### Schritt 4: Verifizierung

1. **Prüfe Cleanup-Service Logs:**
   ```
   Im Railway Dashboard → cleanup_service → Logs
   ```
   Sollte zeigen:
   ```
   🧹 Word Duplicate Cleanup Service
   🚀 Starting cleanup service on 0.0.0.0:XXXX
   ```

2. **Teste Health Endpoint:**
   - Im Cleanup-Service → Settings → Domains
   - Kopiere die private Domain
   - Teste: `curl http://cleanup_service.railway.internal/health`
   - Sollte zurückgeben: `{"status": "ok", "service": "cleanup-service"}`

3. **Teste von Hauptapp:**
   - Als Admin (User ID 2) einloggen
   - Settings → Admin Tools
   - "🔍 Dry Run" klicken
   - Sollte funktionieren!

## Alternative: Railway CLI

Falls du Railway CLI bevorzugst:

```bash
# 1. Service erstellen (muss im Dashboard gemacht werden)
# 2. Service auswählen
railway service cleanup_service

# 3. Environment Variables setzen
railway variables set DATABASE_URL="<von-postgres-service>"

# 4. Deployen
railway up
```

## Wichtige Hinweise

1. **Service-Name:** Der Service-Name in Railway muss mit dem in `CLEANUP_SERVICE_URL` übereinstimmen
2. **Private Domain:** Verwende immer `.railway.internal`, nie die öffentliche URL
3. **DATABASE_URL:** Beide Services (Hauptapp und Cleanup) müssen auf dieselbe PostgreSQL-Datenbank zugreifen
4. **Procfile:** Railway ignoriert `Procfile.cleanup` - verwende stattdessen "Start Command" im Dashboard

## Troubleshooting

### Problem: Service startet nicht
- Prüfe Railway Logs für Fehlermeldungen
- Verifiziere, dass `cleanup_service.py` im Root-Verzeichnis ist
- Prüfe, ob alle Dependencies in `requirements.txt` sind

### Problem: "Failed to connect to cleanup service"
- Prüfe, ob `CLEANUP_SERVICE_URL` korrekt gesetzt ist
- Verifiziere, dass der Service-Name in der URL mit dem Railway-Service-Namen übereinstimmt
- Prüfe, ob beide Services im selben Railway-Projekt sind

### Problem: "Database connection error"
- Prüfe, ob `DATABASE_URL` im cleanup_service gesetzt ist
- Verifiziere, dass es derselbe `DATABASE_URL` wie in der Hauptapp ist

## Service ID

Deine Service ID: `841598ff-e5ee-48bd-82c1-43b1533d8cb5`

Falls der Service bereits existiert, kannst du ihn direkt verwenden:
```bash
railway service --id 841598ff-e5ee-48bd-82c1-43b1533d8cb5
railway up
```

