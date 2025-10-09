# Onboarding Auto-Import/Create Custom Level Group Feature

## Übersicht

Nach Abschluss des Onboardings wird **automatisch** eine passende Custom Level Group aus dem Marketplace importiert oder eine neue erstellt.

## Funktionsweise

### Ablauf

1. **User schließt Onboarding ab**
   - Wählt: Muttersprache, Zielsprache, CEFR-Level, Lernmotivation
   - Klickt "Finish"

2. **Automatische Marketplace-Suche**
   ```javascript
   // Sucht nach passenden Gruppen mit:
   - Target Language: z.B. 'ru' (Russisch)
   - Native Language: z.B. 'en' (Englisch)
   - CEFR Level: z.B. 'none' (A0)
   - Limit: 5 beste Matches
   ```

3. **Szenario A: Match gefunden**
   ```javascript
   ✅ Found matching marketplace group: "Russian for Beginners"
   📦 Importing group ID: 123
   ✅ Successfully imported marketplace group
   ```
   - Beste passende Gruppe wird automatisch importiert
   - User sieht Success-Message
   - Gruppe ist in der Bibliothek verfügbar

4. **Szenario B: Kein Match gefunden**
   ```javascript
   ⚠️ No matching marketplace groups found
   🎯 Will open create custom group modal after reload...
   ```
   - Flag wird in localStorage gesetzt: `siluma_onboarding_create_group = 'true'`
   - Nach Page Reload (2 Sekunden Verzögerung)
   - Modal "Neue Level-Gruppe erstellen" öffnet sich automatisch
   - User kann eigene Gruppe erstellen

## Implementierung

### 1. Onboarding.js - Auto-Import/Create Funktion

**Neue Methode: `importOrCreateLevelGroup()`**

```javascript
async importOrCreateLevelGroup() {
    // 1. Prüfe Authentication
    if (!window.authManager.isAuthenticated()) {
        console.log('⚠️ User not authenticated, skipping');
        return;
    }
    
    // 2. Suche Marketplace
    const params = new URLSearchParams({
        language: this.onboardingData.target_language,
        native_language: this.onboardingData.native_language,
        cefr_level: this.onboardingData.proficiency_level,
        limit: 5
    });
    
    const result = await fetch(`/api/marketplace/custom-level-groups?${params}`);
    
    // 3a. Match gefunden → Importieren
    if (result.groups.length > 0) {
        const bestMatch = result.groups[0];
        await fetch(`/api/marketplace/custom-level-groups/${bestMatch.id}/import`, {
            method: 'POST',
            headers: authHeaders
        });
        showSuccessMessage('Gruppe importiert: ' + bestMatch.group_name);
    }
    
    // 3b. Kein Match → Flag für Create Modal setzen
    else {
        localStorage.setItem('siluma_onboarding_create_group', 'true');
    }
}
```

**Aufruf in `finishOnboarding()`:**
```javascript
await this.importOrCreateLevelGroup();
```

### 2. main.js - Create Modal nach Reload öffnen

```javascript
setTimeout(() => {
    const shouldCreateGroup = localStorage.getItem('siluma_onboarding_create_group');
    if (shouldCreateGroup === 'true') {
        localStorage.removeItem('siluma_onboarding_create_group');
        window.showCreateCustomGroupModal();
    }
}, 2000);
```

### 3. app.py - Marketplace API mit CEFR-Filterung

**Vorher:**
```python
WHERE clg.status = 'published'
AND clg.language = ?
AND clg.native_language = ?
```

**Nachher:**
```python
WHERE clg.status = 'published'
AND clg.language = ?
AND clg.native_language = ?
AND clg.cefr_level = ?  # NEU!
```

## API-Endpunkte

### GET /api/marketplace/custom-level-groups

**Query Parameters:**
- `language` (required): Zielsprache (z.B. 'ru')
- `native_language` (required): Muttersprache (z.B. 'en')
- `cefr_level` (optional): CEFR-Level (z.B. 'none', 'A1', 'A2')
- `limit` (optional): Max Anzahl Ergebnisse (default: 20)
- `offset` (optional): Pagination offset (default: 0)

**Response:**
```json
{
    "success": true,
    "groups": [
        {
            "id": 123,
            "group_name": "Russian for Beginners",
            "context_description": "Daily conversations...",
            "language": "ru",
            "native_language": "en",
            "cefr_level": "none",
            "num_levels": 10,
            "rating_avg": 4.5,
            "rating_count": 23,
            "author_name": "John Doe"
        }
    ],
    "total": 1
}
```

### POST /api/marketplace/custom-level-groups/{groupId}/import

**Headers:**
- `Authorization`: Bearer token
- `Content-Type`: application/json

**Body (optional):**
```json
{
    "new_group_name": "Custom Name"  // Falls Gruppe bereits existiert
}
```

**Response:**
```json
{
    "success": true,
    "group_id": 456,  // ID der importierten Gruppe in User's Library
    "message": "Group imported successfully"
}
```

## Console-Logs

### Bei Match gefunden:
```
🎯 Auto-importing or creating custom level group...
📊 Settings: {target: "ru", native: "en", cefr: "none", focus: "daily life"}
🔍 Searching marketplace for matching groups... language=ru&native_language=en&cefr_level=none&limit=5
📋 Marketplace search result: {success: true, groups: [...], total: 3}
✅ Found matching marketplace group: Russian for Beginners
📦 Importing group ID: 123
✅ Successfully imported marketplace group: Russian for Beginners
```

### Bei kein Match:
```
🎯 Auto-importing or creating custom level group...
📊 Settings: {target: "ru", native: "en", cefr: "none", focus: "daily life"}
🔍 Searching marketplace for matching groups... language=ru&native_language=en&cefr_level=none&limit=5
📋 Marketplace search result: {success: true, groups: [], total: 0}
⚠️ No matching marketplace groups found
🎯 Will open create custom group modal after reload...
[Page Reload]
🎯 Onboarding requested custom group creation, opening modal...
✅ Create custom group modal opened after onboarding
```

## Fehlerbehandlung

**Fehler werden nicht dem User angezeigt**, weil:
- Dies ist ein "nice-to-have" Feature
- User kann manuell Gruppen erstellen/importieren
- Keine kritische Funktionalität

**Fehler werden nur in Console geloggt:**
```
❌ Error in importOrCreateLevelGroup: Error message
```

## Vorteile

1. **Sofortiger Start:** User kann direkt mit relevantem Content loslegen
2. **Kuratierter Content:** Marketplace-Gruppen sind von anderen Usern erstellt und bewertet
3. **Fallback:** Falls kein Match, kann User eigene Gruppe erstellen
4. **Nahtlose UX:** Alles automatisch, keine extra Schritte nötig

## Geänderte Dateien

1. **static/js/onboarding.js**
   - Neue Methode: `importOrCreateLevelGroup()`
   - Aufruf in `finishOnboarding()`

2. **static/js/main.js**
   - Check für `siluma_onboarding_create_group` Flag
   - Öffnet Create Modal nach Reload

3. **app.py**
   - CEFR-Level-Filterung in Marketplace API
   - Unterstützt jetzt `cefr_level` Query Parameter

## Deployment

```
✅ Git Commit: 3add9a7
✅ Git Push: origin/main
✅ Railway Deploy: In Progress
```

## Testing

1. **Erstelle Test-Marketplace-Gruppe:**
   - Language: ru
   - Native Language: en
   - CEFR Level: none (A0)
   - Publiziere die Gruppe

2. **Teste Onboarding:**
   - Wähle: EN → RU, A0
   - Schließe ab
   - → Sollte Gruppe automatisch importieren

3. **Teste ohne Match:**
   - Wähle: DE → JA, C2 (falls keine solche Gruppe existiert)
   - Schließe ab
   - → Create Modal sollte sich öffnen

## Zusammenfassung

Nach dem Onboarding wird **automatisch** der beste passende Content für den User bereitgestellt:
- ✅ Automatische Marketplace-Suche
- ✅ Automatischer Import bei Match
- ✅ Automatisches Create-Modal bei kein Match
- ✅ Basiert auf User's Einstellungen (Sprache, Niveau, Motivation)
- ✅ Nahtlose User Experience

Der User kann **sofort** mit lernen beginnen! 🚀

