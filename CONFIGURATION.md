# Standard Level Groups Deaktivierung

## Übersicht

Die Standard-Level-Gruppen wurden erfolgreich deaktiviert, ohne sie zu löschen. Diese Konfiguration ermöglicht es, nur die Custom-Level-Gruppen in der Bibliothek anzuzeigen.

## Implementierung

Die Deaktivierung wurde durch eine einfache Konfigurationsvariable in `static/js/ui/levels.js` implementiert:

```javascript
// Configuration: Disable standard level groups (they won't be loaded in library)
const DISABLE_STANDARD_LEVEL_GROUPS = true; // Set to false to re-enable standard groups
```

## Funktionsweise

1. **Standard-Gruppen werden nicht geladen**: Die `ensureLevelGroups()` Funktion gibt ein leeres Array zurück, wenn `DISABLE_STANDARD_LEVEL_GROUPS` auf `true` gesetzt ist.

2. **Custom-Gruppen funktionieren weiterhin**: Alle Custom-Level-Gruppen werden normal über `showCustomLevelGroupsInLibrary()` geladen und angezeigt.

3. **Bibliothek bleibt funktional**: Die Bibliothek zeigt nur die Custom-Gruppen an, falls vorhanden.

## Wiedereinschaltung

Um die Standard-Level-Gruppen wieder zu aktivieren, ändern Sie einfach:

```javascript
const DISABLE_STANDARD_LEVEL_GROUPS = false; // Re-enable standard groups
```

## Vorteile dieser Lösung

- ✅ Standard-Gruppen werden nicht gelöscht (können jederzeit wieder aktiviert werden)
- ✅ Custom-Gruppen funktionieren weiterhin vollständig
- ✅ Einfache Konfiguration mit einer einzigen Variable
- ✅ Keine Datenbank-Änderungen erforderlich
- ✅ Saubere Trennung zwischen Standard- und Custom-Gruppen
