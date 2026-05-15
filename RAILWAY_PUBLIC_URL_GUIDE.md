# 🔌 Railway PostgreSQL - Öffentliche URL für DBeaver

## Problem
Die interne URL (`postgres.railway.internal`) funktioniert nur innerhalb des Railway-Netzwerks und nicht von deinem lokalen Computer aus.

## Lösung: Öffentliche URL aktivieren

### Schritt 1: Railway Dashboard öffnen
1. Gehe zu: https://railway.app/dashboard
2. Wähle dein Projekt
3. Klicke auf den **PostgreSQL Service**

### Schritt 2: Public Network aktivieren
1. Im PostgreSQL Service, gehe zum Tab **"Connect"** oder **"Networking"**
2. Suche nach **"Public Network"** oder **"Publicly Accessible"**
3. **Aktiviere** das Public Network (falls noch nicht aktiviert)
4. Warte ein paar Sekunden, bis Railway die öffentliche URL generiert

### Schritt 3: Öffentliche URL kopieren
1. Im **"Connect"** Tab findest du jetzt zwei URLs:
   - **Private Network**: `postgres.railway.internal:5432` ❌ (funktioniert nicht lokal)
   - **Public Network**: `monorail.proxy.rlwy.net:5432` ✅ (funktioniert lokal)

2. Kopiere die **Public Network URL** - sie sieht so aus:
   ```
   postgresql://postgres:XRMeJyDbesakYJLwdCfigXhOeYTjOjTL@monorail.proxy.rlwy.net:5432/railway
   ```

### Schritt 4: In DBeaver verwenden
Die öffentliche URL hat:
- **Gleicher Username**: `postgres`
- **Gleiches Passwort**: `XRMeJyDbesakYJLwdCfigXhOeYTjOjTL`
- **Gleiche Database**: `railway`
- **Neuer Host**: `monorail.proxy.rlwy.net` (statt `postgres.railway.internal`)
- **Gleicher Port**: `5432`

## Alternative: Railway CLI
Falls du die Railway CLI verwendest:
```bash
railway connect postgres
```
Dies zeigt dir die Verbindungsinformationen.

## DBeaver Einstellungen (mit öffentlicher URL)
- **Host**: `monorail.proxy.rlwy.net` (aus der öffentlichen URL)
- **Port**: `5432`
- **Database**: `railway`
- **Username**: `postgres`
- **Password**: `XRMeJyDbesakYJLwdCfigXhOeYTjOjTL`
- **SSL**: Aktivieren, Mode: `require`


