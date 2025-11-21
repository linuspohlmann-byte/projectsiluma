#!/bin/bash
# Monitoring-Script für Cleanup Service
# Zeigt Status, Logs und Statistiken

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "📊 Cleanup Service Monitoring"
echo "=============================="
echo ""

# 1. Health Check
echo -e "${BLUE}1. Health Check${NC}"
echo "-------------------"
HEALTH=$(curl -s http://cleanup_serivce.railway.internal/health 2>&1 || echo "ERROR")
if echo "$HEALTH" | grep -q "ok"; then
    echo -e "${GREEN}✅ Cleanup Service ist erreichbar${NC}"
    echo "$HEALTH" | python3 -m json.tool 2>/dev/null || echo "$HEALTH"
else
    echo -e "${RED}❌ Cleanup Service nicht erreichbar${NC}"
    echo "$HEALTH"
fi
echo ""

# 2. Service Status
echo -e "${BLUE}2. Service Status${NC}"
echo "-------------------"
railway status 2>&1 | grep -E "Service|Project|Environment" || echo "⚠️  Konnte Status nicht abrufen"
echo ""

# 3. Environment Variables
echo -e "${BLUE}3. Konfiguration${NC}"
echo "-------------------"
echo "Hauptapp-Service (projectsiluma):"
railway variables --service projectsiluma 2>&1 | grep CLEANUP_SERVICE_URL || echo "⚠️  CLEANUP_SERVICE_URL nicht gefunden"
echo ""
echo "Cleanup-Service (cleanup_serivce):"
railway variables --service cleanup_serivce 2>&1 | grep DATABASE_URL | head -1 || echo "⚠️  DATABASE_URL nicht gefunden"
echo ""

# 4. Letzte Logs
echo -e "${BLUE}4. Letzte Logs (Cleanup-Service)${NC}"
echo "-------------------"
railway logs --service cleanup_serivce --tail 20 2>&1 | tail -20 || echo "⚠️  Konnte Logs nicht abrufen"
echo ""

# 5. Optionen
echo -e "${BLUE}5. Nützliche Befehle${NC}"
echo "-------------------"
echo "Live-Logs anzeigen:"
echo "  railway logs --service cleanup_serivce --follow"
echo ""
echo "Cleanup auslösen (Dry Run):"
echo "  curl -X POST http://cleanup_serivce.railway.internal/cleanup -H 'Content-Type: application/json' -d '{\"dry_run\": true}'"
echo ""
echo "Cleanup auslösen (Echt):"
echo "  curl -X POST http://cleanup_serivce.railway.internal/cleanup -H 'Content-Type: application/json' -d '{\"dry_run\": false}'"
echo ""

