# Lokaler Development-Server

## Schnellstart

```bash
# 1. Stelle sicher, dass alle Dependencies installiert sind
pip install -r requirements.txt

# 2. Erstelle einen Test-Benutzer (falls noch nicht vorhanden)
python3 scripts/dev/create_local_user.py

# 3. Starte den lokalen Server
python3 run_local.py
```

Die App läuft dann auf: **http://localhost:5001**

## Test-Benutzer

Standard-Test-Benutzer:
- **Username**: `testuser`
- **Password**: `password123`
- **Email**: `test@example.com`

### Eigene Test-Benutzer erstellen

```bash
# Mit Standard-Credentials
python3 scripts/dev/create_local_user.py

# Mit eigenen Credentials
python3 scripts/dev/create_local_user.py --username meinuser --email mein@email.com --password meinpasswort
```

## Alternative: Direkt mit app.py

```bash
python3 app.py
```

## Wichtige Hinweise

- **Port**: Der Server läuft standardmäßig auf Port 5001
- **Debug Mode**: Automatisch aktiviert (Code-Reload bei Änderungen)
- **Datenbank**: Verwendet lokale SQLite-Datenbank (falls keine PostgreSQL-Konfiguration vorhanden)
- **Environment Variables**: Stelle sicher, dass benötigte Variablen gesetzt sind (z.B. `OPENAI_API_KEY`)

## Troubleshooting

### Port bereits belegt
```bash
# Verwende einen anderen Port
PORT=5002 python3 run_local.py
```

### Dependencies fehlen
```bash
pip install -r requirements.txt
```

### Import-Fehler
Stelle sicher, dass du im Projektverzeichnis bist:
```bash
cd /Users/Air/Documents/ProjectSiluma
python3 run_local.py
```

