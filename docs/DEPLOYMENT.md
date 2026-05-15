# 🚀 Deployment-Anleitung für ProjectSiluma

## Option 1: Railway (Empfohlen)

### Schritt 1: GitHub Repository erstellen
1. Erstellen Sie ein GitHub Repository
2. Pushen Sie Ihren Code:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/ihr-username/projectsiluma.git
git push -u origin main
```

### Schritt 2: Railway Setup
1. Gehen Sie zu [railway.app](https://railway.app)
2. Melden Sie sich mit GitHub an
3. Klicken Sie auf "New Project"
4. Wählen Sie "Deploy from GitHub repo"
5. Wählen Sie Ihr Repository aus

### Schritt 3: Konfiguration
Railway erkennt automatisch:
- `Procfile` für den Start-Befehl
- `requirements_production.txt` für Dependencies

### Schritt 4: Umgebungsvariablen (falls nötig)
In Railway Dashboard:
- Settings → Variables
- Fügen Sie hinzu:
  - `FLASK_ENV=production`
  - `OPENAI_API_KEY=ihr_api_key` (falls verwendet)

## Option 2: Render

### Schritt 1: GitHub Repository (wie oben)

### Schritt 2: Render Setup
1. Gehen Sie zu [render.com](https://render.com)
2. Melden Sie sich mit GitHub an
3. Klicken Sie auf "New +" → "Web Service"
4. Verbinden Sie Ihr GitHub Repository

### Schritt 3: Konfiguration
- **Build Command**: `pip install -r requirements_production.txt`
- **Start Command**: `python wsgi.py`
- **Environment**: Python 3

## Option 3: PythonAnywhere

### Schritt 1: Account erstellen
1. Gehen Sie zu [pythonanywhere.com](https://pythonanywhere.com)
2. Erstellen Sie einen Account ($5/Monat)

### Schritt 2: Code hochladen
1. Gehen Sie zu "Files" Tab
2. Laden Sie Ihre Dateien hoch oder klonen Sie von GitHub

### Schritt 3: Web App konfigurieren
1. Gehen Sie zu "Web" Tab
2. Erstellen Sie eine neue Web App
3. Wählen Sie "Flask" und Python 3.10
4. Setzen Sie den Source Code Pfad
5. Konfigurieren Sie die WSGI-Datei

## Wichtige Hinweise

### Datenbank
- Ihre SQLite-Datenbank wird mit dem Code mitgeliefert
- Für bessere Performance: Migrieren Sie zu PostgreSQL (Railway/Render bieten kostenlose PostgreSQL)

### Statische Dateien
- Alle statischen Dateien in `/static` werden automatisch bereitgestellt
- Media-Dateien in `/media` werden ebenfalls mitgeliefert

### HTTPS
- Alle Plattformen bieten automatisch HTTPS
- Ihre App wird über eine sichere URL erreichbar sein

## Kostenvergleich

| Plattform | Kostenlos | Bezahlt | Besonderheiten |
|-----------|-----------|---------|----------------|
| Railway | 500h/Monat | $5/Monat | Sehr einfach |
| Render | 750h/Monat | $7/Monat | Sehr zuverlässig |
| PythonAnywhere | - | $5/Monat | Python-spezifisch |
| Heroku | - | $5/Monat | Etabliert |

## Empfehlung
**Railway** ist die beste Option für den Start:
- Einfachste Einrichtung
- Kostenloser Plan für Tests
- Automatische Deployments
- Gute Performance

---

## Cleanup Service (Kurzreferenz)

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
