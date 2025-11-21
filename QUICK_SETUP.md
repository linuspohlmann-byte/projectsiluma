# 🚀 Quick Setup - Cleanup Service

## Automatisches Setup (Empfohlen)

```bash
./auto_setup_cleanup_service.sh
```

Das Script:
- ✅ Verlinkt automatisch das Railway-Projekt
- ✅ Findet den Hauptapp-Service
- ✅ Setzt `CLEANUP_SERVICE_URL` automatisch
- ✅ Verifiziert die Konfiguration

## Manuelles Setup (Falls automatisch nicht funktioniert)

### 1. Railway Dashboard öffnen
https://railway.app/dashboard

### 2. Hauptapp-Service → Variables
- Name: `CLEANUP_SERVICE_URL`
- Value: `http://cleanup_serivce.railway.internal`
- Add

### 3. cleanup_serivce → Variables → Add from Service
- PostgreSQL-Service auswählen
- `DATABASE_URL` auswählen
- Add

## Fertig! 🎉

Nach dem Setup:
1. Hauptapp wird automatisch neu deployed
2. Als Admin (User ID 2) einloggen
3. Settings → Admin Tools → "🔍 Dry Run" testen

