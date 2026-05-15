# A0 Persistence Debugging Guide

## Problem

A0 wird im Onboarding gewählt, aber auf der Homepage wird A1 angezeigt.

## Debugging Steps

### 1. Nach Onboarding-Abschluss (VOR Reload)

In der Console sollte erscheinen:
```
🔧 Updating course configuration with onboarding data...
📊 Current onboarding data: {proficiency_level: "none", ...}
✅ localStorage updated: {cefr: "none", cefrKey: "siluma_cefr_ru", ...}
🔍 Verify localStorage values: {
    cefr_specific: "none",
    cefr_legacy: "none",
    ...
}
```

**Wenn diese Logs NICHT erscheinen:** Onboarding setzt localStorage nicht korrekt.

### 2. In Browser DevTools Console eingeben:

```javascript
// Prüfe localStorage direkt
localStorage.getItem('siluma_target')
localStorage.getItem('siluma_cefr')
localStorage.getItem('siluma_cefr_ru')  // oder welche Sprache gewählt wurde
```

**Expected:**
- `siluma_target`: "ru" (oder gewählte Sprache)
- `siluma_cefr`: "none"
- `siluma_cefr_ru`: "none"

**Wenn Werte fehlen:** localStorage wird nicht gesetzt.

### 3. Nach Reload/Homepage-Laden

In der Console sollte erscheinen:
```
🔍 restoreCefr called: {
    key: "siluma_cefr_ru",
    perValue: "none",
    legacyValue: "none",
    elementExists: true,
    currentValue: ""
}
✅ Restored CEFR from language-specific key: none
```

**Mögliche Szenarien:**

#### Scenario A: Element existiert nicht
```
🔍 restoreCefr called: {..., elementExists: false, ...}
⚠️ CEFR element not found, cannot set value: none
```
**Ursache:** CEFR-Dropdown existiert noch nicht im DOM
**Lösung:** restoreCefr() später aufrufen oder warten bis Element existiert

#### Scenario B: localStorage leer
```
🔍 restoreCefr called: {perValue: null, legacyValue: null, ...}
⚠️ No CEFR value in localStorage (neither specific nor legacy)
```
**Ursache:** Onboarding hat localStorage nicht gesetzt
**Lösung:** Onboarding-Code reparieren

#### Scenario C: Wert wird überschrieben
```
✅ Restored CEFR from language-specific key: none
[später...]
// Ein anderer Code setzt es zurück
```
**Ursache:** Irgendwo wird CEFR-Wert nach Restore überschrieben
**Lösung:** Finde welcher Code das überschreibt

### 4. Prüfe welcher Code CEFR setzt

In Console eingeben:
```javascript
// Überwache CEFR Änderungen
const cefrSelect = document.getElementById('cefr');
const originalSetter = Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype, 'value').set;
Object.defineProperty(cefrSelect, 'value', {
  set: function(val) {
    console.log('🔍 CEFR value being set to:', val, 'from:', new Error().stack);
    originalSetter.call(this, val);
  }
});
```

Das wird JEDE Änderung am CEFR-Dropdown loggen mit Stack Trace.

### 5. Vergleiche mit Topic (das funktioniert)

```javascript
localStorage.getItem('siluma_topic')
localStorage.getItem('siluma_topic_ru')
document.getElementById('topic').value
```

Wenn Topic korrekt ist, vergleiche die Werte und Timing.

## Wahrscheinliche Root Causes

### 1. Timing Issue
CEFR-Element existiert noch nicht wenn `restoreCefr()` aufgerufen wird.

**Fix:** Warte bis Element existiert oder rufe später auf.

### 2. localStorage nicht gesetzt
Onboarding setzt localStorage nicht korrekt (z.B. wegen Fehler).

**Fix:** Prüfe Onboarding-Logs und Error Handling.

### 3. Wert wird überschrieben
Irgendwo im Code wird CEFR nach Restore überschrieben.

**Fix:** Finde den Code der überschreibt (mit Stack Trace Monitoring).

### 4. Falscher Default
CEFR-Dropdown hat einen Default-Wert von "A1" der später gesetzt wird.

**Fix:** Entferne Default oder setze explizit nach Dropdown-Rebuild.

## Nächste Schritte

1. **Deploy** die neue Version mit Debugging
2. **Teste** Onboarding mit offener Console
3. **Kopiere** alle Logs die mit 🔍, ✅, ⚠️, ❌ beginnen
4. **Prüfe** localStorage-Werte direkt
5. **Teile** die Ergebnisse für weitere Diagnose

## Expected Full Log Sequence

```
// 1. Onboarding Completion
🔧 Updating course configuration with onboarding data...
📊 Current onboarding data: {proficiency_level: "none", ...}
✅ localStorage updated: {cefr: "none", cefrKey: "siluma_cefr_ru", ...}
🔍 Verify localStorage values: {cefr_specific: "none", cefr_legacy: "none", ...}

// 2. Page Reload
🔍 restoreCefr called: {key: "siluma_cefr_ru", perValue: "none", legacyValue: "none", elementExists: true}
✅ Restored CEFR from language-specific key: none

// 3. CEFR should be "none" (A0) on homepage
```

Falls etwas anders ist, zeigt das den Fehler!

