# Cleanup Service Setup für Railway

## Übersicht

Der Cleanup-Service ist ein separater Railway-Service, der Word-Duplikate in der PostgreSQL-Datenbank bereinigt.

## Railway Service Konfiguration

### 1. Service-Name
Der Service sollte als `cleanup_service` (oder `cleanup_serivce` wie aktuell) in Railway erstellt werden.

### 2. Procfile
Railway erkennt automatisch Flask-Apps. Falls nötig, kann ein `Procfile` mit folgendem Inhalt erstellt werden:
```
web: python cleanup_service.py
```

### 3. Environment Variables

Der Cleanup-Service benötigt:
- `DATABASE_URL` - PostgreSQL Connection String (wird automatisch von Railway gesetzt, wenn PostgreSQL als Service verbunden ist)
- `PORT` - Wird automatisch von Railway gesetzt
- `RAILWAY_PRIVATE_DOMAIN` - Wird automatisch von Railway gesetzt (z.B. `cleanup_serivce.railway.internal`)

### 4. Hauptapp Konfiguration

In der Hauptapp muss folgende Environment Variable gesetzt werden:

```
CLEANUP_SERVICE_URL=http://cleanup_serivce.railway.internal
```

**Wichtig:** Verwende die private Railway Domain (`.railway.internal`), nicht die öffentliche URL. Die private Domain funktioniert nur innerhalb des Railway-Netzwerks und ist kostenlos.

Falls `CLEANUP_SERVICE_URL` nicht gesetzt ist, versucht die App automatisch:
1. `RAILWAY_PRIVATE_DOMAIN` zu verwenden (falls gesetzt)
2. Fallback zu `http://localhost:5001` (für lokale Entwicklung)

## Verifizierung

### 1. Service Health Check
```bash
curl http://cleanup_serivce.railway.internal/health
```

Sollte zurückgeben:
```json
{"status": "ok", "service": "cleanup-service"}
```

### 2. Test von der Hauptapp
Als Admin (User ID 2) in der Settings-Seite:
- Klicke auf "🔍 Dry Run" um zu testen, ohne Änderungen zu machen
- Klicke auf "🧹 Run Cleanup" um die Bereinigung durchzuführen

## Troubleshooting

### Service nicht erreichbar
1. Prüfe Railway-Logs des Cleanup-Services
2. Verifiziere, dass `DATABASE_URL` gesetzt ist
3. Prüfe, ob der Service läuft (Railway Dashboard)

### Connection Error in Hauptapp
1. Prüfe, ob `CLEANUP_SERVICE_URL` korrekt gesetzt ist
2. Verwende die private Domain (`.railway.internal`), nicht die öffentliche URL
3. Prüfe Railway-Logs der Hauptapp für Fehlermeldungen

### Database Connection Error
1. Verifiziere, dass PostgreSQL-Service mit dem Cleanup-Service verbunden ist
2. Prüfe `DATABASE_URL` in den Environment Variables
3. Teste die Datenbankverbindung manuell

## Lokale Entwicklung

Für lokale Entwicklung:
```bash
# Terminal 1: Starte Cleanup-Service
python cleanup_service.py

# Terminal 2: Starte Hauptapp
python app.py
```

Die Hauptapp wird automatisch `http://localhost:5001` verwenden, wenn keine Environment Variables gesetzt sind.

