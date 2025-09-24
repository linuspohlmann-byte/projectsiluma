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
