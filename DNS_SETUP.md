# DNS Configuration für polo-lingua.de

## Railway DNS-Einstellungen

Um deine Custom Domain `polo-lingua.de` mit Railway zu verbinden, musst du die folgenden DNS-Records bei deinem Domain-Provider konfigurieren:

### DNS-Record

| Type | Name | Value | TTL |
|------|------|-------|-----|
| CNAME | @ | m66fvx81.up.railway.app | 3600 (oder Standard) |

## Anleitung für verschiedene DNS-Provider

### 1. Allgemeine Schritte

1. Logge dich bei deinem Domain-Provider ein (wo du `polo-lingua.de` registriert hast)
2. Navigiere zu den DNS-Einstellungen / DNS-Verwaltung
3. Suche nach dem Bereich für DNS-Records oder Zone Records
4. Füge einen neuen CNAME-Record hinzu:
   - **Name/Host:** `@` oder leer lassen (für Root-Domain)
   - **Type:** `CNAME`
   - **Value/Target:** `m66fvx81.up.railway.app`
   - **TTL:** 3600 Sekunden (1 Stunde) oder Standard

### 2. Wichtige Hinweise

- **@ Symbol:** Das `@` Symbol steht für die Root-Domain (polo-lingua.de ohne www)
- **CNAME vs A Record:** Verwende einen CNAME-Record, NICHT einen A-Record
- **Propagation:** DNS-Änderungen können bis zu 72 Stunden dauern, normalerweise aber nur wenige Minuten bis Stunden
- **Bestehende Records:** Wenn bereits ein A-Record für `@` existiert, entferne ihn zuerst, bevor du den CNAME-Record hinzufügst

### 3. Provider-spezifische Anleitungen

#### Strato (falls Strato dein Provider ist)
1. Logge dich in das Strato-Kundencenter ein
2. Gehe zu "Domains" → "DNS-Verwaltung"
3. Wähle `polo-lingua.de`
4. Klicke auf "DNS-Einträge verwalten"
5. Entferne ggf. bestehende A-Records für `@`
6. Füge neuen CNAME-Record hinzu:
   - Name: `@`
   - Typ: `CNAME`
   - Ziel: `m66fvx81.up.railway.app`
7. Speichere die Änderungen

#### Andere Provider
Die Schritte sind ähnlich, nur die Benutzeroberfläche variiert:
- **Namecheap:** Advanced DNS → Add New Record → CNAME Record
- **GoDaddy:** DNS Management → Add → CNAME
- **Cloudflare:** DNS → Add Record → CNAME
- **IONOS:** Domain & SSL → DNS → Neue Einstellung hinzufügen

### 4. Verifikation

Nach dem Hinzufügen des DNS-Records kannst du die Konfiguration überprüfen:

```bash
# Prüfe den CNAME-Record
dig polo-lingua.de CNAME

# Oder mit nslookup
nslookup -type=CNAME polo-lingua.de
```

Die Ausgabe sollte `m66fvx81.up.railway.app` zeigen.

### 5. Railway Dashboard

1. Gehe zu deinem Railway Dashboard
2. Wähle deinen Service aus
3. Gehe zu "Settings" → "Domains"
4. Füge `polo-lingua.de` als Custom Domain hinzu
5. Railway wird automatisch ein SSL-Zertifikat bereitstellen (Let's Encrypt)

### 6. Wartezeit

- **DNS Propagation:** 5 Minuten bis 72 Stunden (meist 15-60 Minuten)
- **SSL-Zertifikat:** Wird automatisch von Railway bereitgestellt, kann 5-10 Minuten dauern

### 7. Troubleshooting

**Problem:** Domain wird nicht erkannt
- **Lösung:** Warte auf DNS-Propagation (kann bis zu 72 Stunden dauern)
- Prüfe mit `dig` oder `nslookup`, ob der CNAME-Record korrekt ist

**Problem:** "Record not yet detected" in Railway
- **Lösung:** Das ist normal, Railway prüft periodisch. Warte 5-15 Minuten und aktualisiere die Seite

**Problem:** SSL-Zertifikat wird nicht erstellt
- **Lösung:** Stelle sicher, dass der DNS-Record korrekt propagiert ist, dann wird das Zertifikat automatisch erstellt

## Status

- [ ] DNS-Record bei Domain-Provider hinzugefügt
- [ ] Railway Dashboard: Domain hinzugefügt
- [ ] DNS-Propagation abgewartet (prüfen mit `dig polo-lingua.de CNAME`)
- [ ] SSL-Zertifikat aktiv (automatisch von Railway)
- [ ] Domain funktioniert: https://polo-lingua.de

