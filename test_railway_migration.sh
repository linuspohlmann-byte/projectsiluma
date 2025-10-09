#!/bin/bash

# Test-Skript für Railway Migration
# Führt die Migration auf Railway aus

echo "🚀 Testing Railway Migration for Custom Level Progress"
echo ""

# Railway URL (anpassen falls nötig)
RAILWAY_URL="${RAILWAY_URL:-https://projectsiluma-production.up.railway.app}"

echo "📡 Sending migration request to $RAILWAY_URL"
echo ""

# Führe Migration aus über den Debug-Endpoint
curl -X POST "$RAILWAY_URL/api/debug/migrate-progress-cache" \
  -H "Content-Type: application/json" \
  -w "\n\nHTTP Status: %{http_code}\n" \
  2>/dev/null

echo ""
echo "✅ Migration request sent!"
echo ""
echo "💡 Hinweis: Prüfe die Railway Logs für Details:"
echo "   railway logs"
echo ""
echo "📊 Oder teste die neuen Endpoints:"
echo "   GET  $RAILWAY_URL/api/custom-levels/{group_id}/{level_number}/progress"
echo "   POST $RAILWAY_URL/api/custom-levels/{group_id}/{level_number}/finish"

