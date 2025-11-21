#!/bin/bash
# Script zum Auslösen des Cleanups
# Verwendung: ./trigger_cleanup.sh [dry-run|run]

set -e

DRY_RUN=${1:-dry-run}

if [ "$DRY_RUN" = "dry-run" ] || [ "$DRY_RUN" = "dry" ]; then
    DRY_RUN_VALUE=true
    echo "🔍 Starte Dry Run (keine Änderungen)..."
else
    DRY_RUN_VALUE=false
    echo "🧹 Starte Cleanup (echte Änderungen)..."
    read -p "⚠️  Bist du sicher? (yes/no): " confirm
    if [ "$confirm" != "yes" ]; then
        echo "❌ Abgebrochen"
        exit 1
    fi
fi

echo ""
echo "📡 Sende Request an Cleanup-Service..."
echo ""

# Versuche zuerst über Hauptapp (mit Auth)
if [ -n "$RAILWAY_SESSION_TOKEN" ]; then
    echo "Verwende Railway Session Token..."
    RESPONSE=$(curl -s -X POST https://polo-lingua.de/api/admin/cleanup-duplicates \
        -H "Authorization: Bearer $RAILWAY_SESSION_TOKEN" \
        -H "Content-Type: application/json" \
        -d "{\"dry_run\": $DRY_RUN_VALUE}" 2>&1)
else
    # Fallback: Direkt zum Cleanup-Service
    echo "Verwende direkte Cleanup-Service URL..."
    RESPONSE=$(curl -s -X POST http://cleanup_serivce.railway.internal/cleanup \
        -H "Content-Type: application/json" \
        -d "{\"dry_run\": $DRY_RUN_VALUE}" 2>&1)
fi

echo ""
echo "📊 Ergebnis:"
echo "------------"
echo "$RESPONSE" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE"
echo ""

if echo "$RESPONSE" | grep -q '"success":\s*true'; then
    echo "✅ Cleanup erfolgreich!"
    
    # Zeige Statistiken
    if echo "$RESPONSE" | grep -q "stats"; then
        echo ""
        echo "📈 Statistiken:"
        echo "$RESPONSE" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    stats = data.get('stats', {})
    print(f\"  Duplikate gefunden: {stats.get('duplicates_found', 0)}\")
    print(f\"  Aktualisierte Referenzen: {stats.get('updated_references', 0)}\")
    print(f\"  Gelöschte Einträge: {stats.get('deleted_entries', 0)}\")
    if stats.get('errors', 0) > 0:
        print(f\"  ⚠️  Fehler: {stats.get('errors', 0)}\")
except:
    pass
" 2>/dev/null || echo "  (Statistiken konnten nicht geparst werden)"
    fi
else
    echo "❌ Cleanup fehlgeschlagen!"
    exit 1
fi

