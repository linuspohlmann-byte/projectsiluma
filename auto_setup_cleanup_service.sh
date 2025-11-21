#!/bin/bash
# Automatisches Setup für Railway Cleanup Service
# Dieses Script konfiguriert alles automatisch

set -e

echo "🚀 Automatisches Railway Cleanup Service Setup"
echo "=============================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Prüfe Railway CLI
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI nicht gefunden${NC}"
    echo "Installiere mit: npm i -g @railway/cli"
    exit 1
fi

echo -e "${GREEN}✅ Railway CLI gefunden${NC}"
echo ""

# Projekt verlinken (falls nicht verlinkt)
if ! railway status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Projekt nicht verlinkt${NC}"
    echo "Bitte wähle dein Projekt aus:"
    echo ""
    railway link --project projectsiluma 2>&1 || {
        echo ""
        echo -e "${YELLOW}⚠️  Automatisches Verlinken fehlgeschlagen${NC}"
        echo "Bitte führe manuell aus: railway link"
        echo "Dann wähle: projectsiluma"
        exit 1
    }
fi

echo -e "${GREEN}✅ Projekt verlinkt${NC}"
echo ""

# Zeige aktuellen Status
echo -e "${BLUE}📋 Aktueller Railway Status:${NC}"
railway status
echo ""

# Service auswählen
echo -e "${BLUE}🔍 Suche nach Services...${NC}"
SERVICES=$(railway service 2>&1 || echo "")

if [ -z "$SERVICES" ]; then
    echo -e "${YELLOW}⚠️  Keine Services gefunden${NC}"
    echo "Bitte stelle sicher, dass du im richtigen Projekt bist"
    exit 1
fi

echo "$SERVICES"
echo ""

# Hauptapp Service finden (normalerweise der erste Service oder der mit 'web' im Namen)
MAIN_SERVICE=$(railway service list 2>&1 | grep -i "web\|main\|app" | head -1 | awk '{print $1}' || railway service list 2>&1 | head -2 | tail -1 | awk '{print $1}')

if [ -z "$MAIN_SERVICE" ]; then
    echo -e "${YELLOW}⚠️  Konnte Hauptapp-Service nicht automatisch finden${NC}"
    echo "Bitte wähle manuell:"
    railway service
    read -p "Service Name: " MAIN_SERVICE
fi

echo -e "${GREEN}✅ Verwende Service: ${MAIN_SERVICE}${NC}"
echo ""

# Zum Hauptapp Service wechseln
railway service "$MAIN_SERVICE" 2>&1 || {
    echo -e "${YELLOW}⚠️  Service-Wechsel fehlgeschlagen${NC}"
    echo "Bitte wähle manuell: railway service"
    exit 1
}

# Cleanup Service URL setzen
CLEANUP_URL="http://cleanup_serivce.railway.internal"
echo -e "${BLUE}🔧 Setze CLEANUP_SERVICE_URL=${CLEANUP_URL}${NC}"

railway variables set CLEANUP_SERVICE_URL="$CLEANUP_URL" 2>&1 || {
    echo -e "${RED}❌ Fehler beim Setzen der Variable${NC}"
    echo "Bitte setze manuell im Railway Dashboard:"
    echo "  Name: CLEANUP_SERVICE_URL"
    echo "  Value: $CLEANUP_URL"
    exit 1
}

echo -e "${GREEN}✅ Environment Variable gesetzt!${NC}"
echo ""

# Verifiziere
echo -e "${BLUE}🔍 Verifiziere Konfiguration...${NC}"
CURRENT_VALUE=$(railway variables 2>&1 | grep CLEANUP_SERVICE_URL || echo "")

if echo "$CURRENT_VALUE" | grep -q "$CLEANUP_URL"; then
    echo -e "${GREEN}✅ Verifiziert: CLEANUP_SERVICE_URL ist gesetzt${NC}"
else
    echo -e "${YELLOW}⚠️  Variable nicht gefunden in der Ausgabe${NC}"
    echo "Bitte prüfe manuell: railway variables"
fi

echo ""
echo -e "${GREEN}✅ Setup abgeschlossen!${NC}"
echo ""
echo "📝 Nächste Schritte:"
echo "  1. Stelle sicher, dass PostgreSQL mit cleanup_serivce verbunden ist"
echo "  2. Prüfe Railway Logs: railway logs --service cleanup_serivce"
echo "  3. Teste von der UI: Als Admin (User ID 2) → Settings → Admin Tools"
echo ""

