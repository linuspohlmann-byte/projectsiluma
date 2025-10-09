# A0 CEFR Persistence - Final Solution

## Problem-Analyse

**Symptom:** A0 wird im Onboarding gewählt, aber Homepage zeigt A1

**Root Cause:** TIMING + ASYNC OPERATIONS + DEFAULT VALUES

## Warum funktioniert Topic, aber NICHT CEFR?

### Topic hatte 3 Vorteile:

1. **Fallback in loadTopicForLang()** ✅
2. **Fallback in restoreTopic()** ✅  
3. **KEIN Default-Wert von 'A1'** ✅

### CEFR hatte Probleme:

1. **Kein Fallback in loadCefrForLang()** ❌ → FIXED ✅
2. **Kein restoreCefr()** ❌ → FIXED ✅
3. **Default-Werte überall 'A1'** ❌ → NOCH NICHT GEFIXT

## Gefundene Default 'A1' Werte

### levels.js (3 Stellen):
```javascript
Line 1980: const cefr = document.getElementById('cefr')?.value || 'A1';
Line 2314: const cef = document.getElementById('cefr')?.value || 'A1';
Line 2465: const cef = document.getElementById('cefr')?.value || 'A1';
```

### custom-level-groups.js:
```javascript
Line 570: cefr_level: localStorage.getItem('siluma_cefr_' + currentLanguage) || 'A1'
```

**Diese Defaults werden verwendet wenn:**
- CEFR-Element leer ist
- localStorage leer ist
- Element noch nicht existiert

## Implementierte Lösungen

### 1. ✅ Fallback in loadCefrForLang() (wie Topic)
```javascript
let val = localStorage.getItem(key);
if(!val){
  const legacy = localStorage.getItem('siluma_cefr');
  if(legacy) val = legacy;
}
```

### 2. ✅ restoreCefr() Funktion erstellt
```javascript
function restoreCefr(){
  // Same logic as restoreTopic()
  const per = localStorage.getItem( cefrKey() );
  if(per && $('#cefr')){ $('#cefr').value = per; return; }
  const legacy = localStorage.getItem('siluma_cefr');
  if(legacy){
    localStorage.setItem( cefrKey(), legacy );
    if($('#cefr')) $('#cefr').value = legacy;
  }
}
```

### 3. ✅ Reihenfolge in initTopbar()
```javascript
restoreSettings();
restoreCefr();      // Früh aufgerufen
restoreTopic();
```

### 4. ✅ Delayed Re-Restore (NEU!)
```javascript
setTimeout(() => {
  console.log('🔄 Re-restoring CEFR after async operations...');
  restoreCefr();
  restoreTopic();
}, 1000);
```

**Warum?** Falls `ensureTargetLangOptions()` oder andere async operations CEFR überschreiben, wird es nach 1 Sekunde erneut gesetzt.

### 5. ✅ Umfangreiches Logging
```javascript
console.log('🎬 initTopbar() started');
console.log('🧹 Cleared dropdown values');
console.log('📥 Restoring settings from localStorage...');
console.log('🔍 restoreCefr called:', {...});
console.log('✅ Restored CEFR from language-specific key:', per);
console.log('🔄 Migrated CEFR from legacy key:', legacy);
console.log('🔄 Re-restoring CEFR after async operations...');
```

## Was jetzt in den Logs erscheinen sollte

### Beim Page-Load:
```
🎬 initTopbar() started
🧹 Cleared dropdown values
📥 Restoring settings from localStorage...
🔍 restoreCefr called: {
    key: "siluma_cefr_ru",
    perValue: "none",
    legacyValue: "none",
    elementExists: true,
    currentValue: ""
}
✅ Restored CEFR from language-specific key: none
✅ Settings restored
[... async operations ...]
🔄 Re-restoring CEFR after async operations...
🔍 restoreCefr called: {key: "siluma_cefr_ru", perValue: "none", ...}
✅ Restored CEFR from language-specific key: none
```

## Weitere mögliche Probleme

### Wenn es IMMER NOCH nicht funktioniert:

#### Problem A: Default 'A1' Werte überschreiben
**Wenn:** Code verwendet `$('#cefr')?.value || 'A1'` und setzt dann das Element
**Lösung:** Defaults von 'A1' auf 'none' ändern ODER sicherstellen dass localStorage immer gesetzt ist

#### Problem B: Element wird dynamisch neu erstellt
**Wenn:** CEFR-Dropdown wird komplett neu erstellt nach restoreCefr()
**Lösung:** Event Listener für DOM-Änderungen oder MutationObserver

#### Problem C: saveSessionPrefs() überschreibt mit leerem Wert
**Wenn:** `$('#cefr')?.value` ist leer zu diesem Zeitpunkt
**Lösung:** Verschiebe saveSessionPrefs() nach delayed restore

## Deployment

```
✅ Git Commit: a6e721d
✅ Git Push: origin/main
✅ Railway Deploy: In Progress
```

## Testing

Nach dem Deployment bitte testen mit **offener Console** und schauen ob die neuen Logs erscheinen:

1. ✅ "🔍 restoreCefr called: {...}"
2. ✅ "✅ Restored CEFR from language-specific key: none"
3. ✅ "🔄 Re-restoring CEFR after async operations..."

Falls diese Logs NICHT erscheinen, bedeutet das:
- restoreCefr() wird nicht aufgerufen
- JavaScript-Fehler verhindert Ausführung
- Changes sind noch nicht deployed

Falls Logs erscheinen ABER CEFR ist trotzdem A1:
- Etwas überschreibt es NACH dem delayed restore
- Wir brauchen Stack Trace Monitoring (siehe DEBUGGING_A0_PERSISTENCE.md)

