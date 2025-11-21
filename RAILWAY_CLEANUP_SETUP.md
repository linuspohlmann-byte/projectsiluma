# Railway Cleanup Service - Komplette Setup-Anleitung

## Übersicht

Dieses Dokument führt dich durch die komplette Einrichtung des Cleanup-Services auf Railway.

## Schritt 1: Cleanup-Service verifizieren

### 1.1 Service-Status prüfen
Im Railway Dashboard:
- Gehe zum Service `cleanup_serivce`
- Prüfe, ob der Service läuft (Status: "Running")
- Prüfe die Logs - sollte zeigen:
  ```
  🧹 Word Duplicate Cleanup Service
  📋 Service: cleanup_serivce
  🌐 Private Domain: cleanup_serivce.railway.internal
  🔗 Database: PostgreSQL
  🚀 Starting cleanup service on 0.0.0.0:XXXX
  ```

### 1.2 PostgreSQL verbinden
Im Railway Dashboard:
1. Gehe zum `cleanup_serivce` Service
2. Klicke auf "Variables" Tab
3. Klicke auf "Add Variable from Service"
4. Wähle deinen PostgreSQL-Service aus
5. Wähle `DATABASE_URL` aus
6. Klicke "Add"

**Wichtig:** Der Cleanup-Service muss Zugriff auf dieselbe Datenbank haben wie die Hauptapp!

## Schritt 2: Hauptapp konfigurieren

### Option A: Mit Railway CLI (Empfohlen)

```bash
# 1. Railway CLI installieren (falls nicht vorhanden)
npm i -g @railway/cli

# 2. Zum Projekt navigieren
cd /path/to/your/project

# 3. Mit Railway verbinden
railway link

# 4. Zum Hauptapp-Service wechseln
railway service

# 5. Environment Variable setzen
railway variables set CLEANUP_SERVICE_URL=http://cleanup_serivce.railway.internal
```

### Option B: Manuell im Railway Dashboard

1. Gehe zum **Hauptapp-Service** (nicht cleanup_serivce!)
2. Klicke auf "Variables" Tab
3. Klicke auf "New Variable"
4. Name: `CLEANUP_SERVICE_URL`
5. Value: `http://cleanup_serivce.railway.internal`
6. Klicke "Add"

**Hinweis:** 
- Verwende die **private Domain** (`.railway.internal`), nicht die öffentliche URL
- Der Service-Name ist `cleanup_serivce` (mit Tippfehler, wie in Railway erstellt)

### Option C: Mit Setup-Script

```bash
# Script ausführbar machen
chmod +x setup_cleanup_service_railway.sh

# Script ausführen
./setup_cleanup_service_railway.sh
```

## Schritt 3: Verifizierung

### 3.1 Service Health Check

Im Railway Dashboard → cleanup_serivce → Logs:
- Suche nach: `🚀 Starting cleanup service`
- Sollte keine Fehler zeigen

### 3.2 Von der Hauptapp testen

1. **Als Admin einloggen:**
   - User ID muss `2` sein
   - Falls nicht vorhanden, erstelle einen Admin-User mit ID 2

2. **Settings öffnen:**
   - Klicke auf Settings-Button
   - Scroll nach unten
   - Admin-Bereich sollte sichtbar sein (nur für User ID 2)

3. **Dry Run testen:**
   - Klicke auf "🔍 Dry Run"
   - Sollte eine Zusammenfassung zeigen (ohne Änderungen)

4. **Cleanup ausführen:**
   - Klicke auf "🧹 Run Cleanup"
   - Sollte Erfolgsmeldung mit Statistiken zeigen

## Schritt 4: Troubleshooting

### Problem: "Failed to connect to cleanup service"

**Lösung:**
1. Prüfe, ob `CLEANUP_SERVICE_URL` korrekt gesetzt ist:
   ```bash
   railway variables
   ```
2. Verifiziere die private Domain:
   - Im cleanup_serivce Service → Variables
   - Prüfe `RAILWAY_PRIVATE_DOMAIN`
   - Sollte `cleanup_serivce.railway.internal` sein
3. Prüfe, ob beide Services im selben Railway-Projekt sind

### Problem: "Database connection error" im Cleanup-Service

**Lösung:**
1. Prüfe, ob PostgreSQL mit cleanup_serivce verbunden ist
2. Prüfe `DATABASE_URL` in cleanup_serivce Variables
3. Teste die Datenbankverbindung:
   ```bash
   railway run --service cleanup_serivce python -c "from server.db_config import get_db_connection; conn = get_db_connection(); print('✅ Connected')"
   ```

### Problem: Admin-Bereich nicht sichtbar

**Lösung:**
1. Verifiziere, dass du als User ID 2 eingeloggt bist
2. Prüfe Browser-Konsole für Fehler
3. Prüfe, ob `window.authManager.currentUser.id === 2`

### Problem: Cleanup-Service startet nicht

**Lösung:**
1. Prüfe Railway Logs für Fehlermeldungen
2. Verifiziere, dass `requirements.txt` alle Dependencies enthält
3. Prüfe, ob `cleanup_service.py` im Root-Verzeichnis ist
4. Prüfe Procfile (falls vorhanden)

## Schritt 5: Monitoring

### Logs überwachen

**Cleanup-Service Logs:**
```bash
railway logs --service cleanup_serivce
```

**Hauptapp Logs:**
```bash
railway logs
```

### Erfolgreiche Cleanup-Operation

Die Logs sollten zeigen:
```
🔄 Cleanup requested (dry_run=False)
🔍 Scanning for duplicate words...
📊 Found X total words in database
🔍 Found Y duplicate groups
🔄 Updating user_word_familiarity references...
✅ Updated Z references, merged W duplicate entries
🗑️  Removing duplicate word entries...
✅ Deleted V duplicate word entries
✅ Cleanup completed successfully!
```

## Wichtige Hinweise

1. **Private Domain:** Verwende immer `.railway.internal`, nie die öffentliche URL
2. **Service-Name:** Der Service heißt `cleanup_serivce` (mit Tippfehler)
3. **Database:** Beide Services müssen auf dieselbe PostgreSQL-Datenbank zugreifen
4. **Admin-Zugriff:** Nur User ID 2 kann den Cleanup triggern
5. **Dry Run:** Immer zuerst Dry Run testen!

## Nächste Schritte

Nach erfolgreichem Setup:
- ✅ Cleanup-Service läuft kontinuierlich
- ✅ Hauptapp kann Cleanup triggern
- ✅ Admin kann Cleanup von UI aus starten
- ✅ Duplikate werden automatisch verhindert (durch Normalisierung)
- ✅ Bestehende Duplikate können bereinigt werden

## Support

Bei Problemen:
1. Prüfe Railway Logs beider Services
2. Verifiziere Environment Variables
3. Teste Health-Check Endpoint
4. Prüfe Database-Verbindung

