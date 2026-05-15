# ⚡ Quick Start - Cleanup auslösen

## 🎯 Schnellste Methode (UI)

1. Als **Admin (User ID 2)** einloggen
2. **Settings** öffnen
3. Scroll nach unten → **Admin Tools**
4. **"🔍 Dry Run"** klicken (zeigt was passieren würde)
5. **"🧹 Run Cleanup"** klicken (führt aus)

## 💻 CLI-Methode

```bash
# Status prüfen
./monitor_cleanup.sh

# Dry Run
./trigger_cleanup.sh dry-run

# Echter Cleanup
./trigger_cleanup.sh run
```

## 📊 Monitoring

```bash
# Live-Logs
railway logs --service cleanup_serivce --follow

# Status-Check
./monitor_cleanup.sh
```

## ✅ Fertig!

Nach dem Cleanup:
- Duplikate sind entfernt
- Referenzen sind aktualisiert
- Statistiken werden angezeigt

**Weitere Details:** Siehe `README_CLEANUP.md`
