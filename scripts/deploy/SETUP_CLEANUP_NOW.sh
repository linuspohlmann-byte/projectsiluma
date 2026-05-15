#!/bin/bash
# 🚀 Komplettes Setup für Railway Cleanup Service
# Führe dieses Script aus, um alles automatisch zu konfigurieren

set -e

echo "🚀 Railway Cleanup Service - Komplettes Setup"
echo "=============================================="
echo ""

# Farben
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

# Schritt 1: Railway CLI prüfen
echo -e "${BLUE}Schritt 1/4: Prüfe Railway CLI...${NC}"
if ! command -v railway &> /dev/null; then
    echo -e "${RED}❌ Railway CLI nicht gefunden${NC}"
    echo "Installiere mit: npm i -g @railway/cli"
    exit 1
fi
echo -e "${GREEN}✅ Railway CLI gefunden${NC}"
echo ""

# Schritt 2: Projekt verlinken
echo -e "${BLUE}Schritt 2/4: Verlinke Railway-Projekt...${NC}"
if ! railway status &> /dev/null; then
    echo -e "${YELLOW}⚠️  Projekt nicht verlinkt${NC}"
    echo ""
    echo "Bitte wähle dein Projekt aus der Liste:"
    echo ""
    railway link 2>&1 || {
        echo ""
        echo -e "${RED}❌ Automatisches Verlinken fehlgeschlagen${NC}"
        echo ""
        echo "Bitte führe manuell aus:"
        echo "  1. railway link"
        echo "  2. Wähle: projectsiluma"
        echo "  3. Führe dieses Script erneut aus"
        exit 1
    }
fi
echo -e "${GREEN}✅ Projekt verlinkt${NC}"
echo ""

# Schritt 3: Service finden und Variable setzen
echo -e "${BLUE}Schritt 3/4: Konfiguriere Cleanup Service URL...${NC}"
CLEANUP_URL="http://cleanup_serivce.railway.internal"

# Versuche, die Variable zu setzen
if railway variables set CLEANUP_SERVICE_URL="$CLEANUP_URL" 2>&1; then
    echo -e "${GREEN}✅ CLEANUP_SERVICE_URL gesetzt: ${CLEANUP_URL}${NC}"
else
    echo -e "${YELLOW}⚠️  Automatisches Setzen fehlgeschlagen${NC}"
    echo ""
    echo "Bitte setze manuell im Railway Dashboard:"
    echo "  1. Gehe zu deinem Hauptapp-Service (nicht cleanup_serivce!)"
    echo "  2. Variables → New Variable"
    echo "  3. Name: CLEANUP_SERVICE_URL"
    echo "  4. Value: ${CLEANUP_URL}"
    echo "  5. Add"
    echo ""
    read -p "Drücke Enter, wenn du die Variable gesetzt hast..."
fi
echo ""

# Schritt 4: PostgreSQL-Verbindung prüfen
echo -e "${BLUE}Schritt 4/4: Prüfe PostgreSQL-Verbindung...${NC}"
echo -e "${YELLOW}⚠️  Wichtig: PostgreSQL muss mit cleanup_serivce verbunden sein!${NC}"
echo ""
echo "Bitte prüfe im Railway Dashboard:"
echo "  1. Gehe zu cleanup_serivce Service"
echo "  2. Variables → Add Variable from Service"
echo "  3. Wähle deinen PostgreSQL-Service"
echo "  4. Wähle DATABASE_URL"
echo "  5. Add"
echo ""
read -p "Drücke Enter, wenn PostgreSQL verbunden ist..."

echo ""
echo -e "${GREEN}✅ Setup abgeschlossen!${NC}"
echo ""
echo "📝 Zusammenfassung:"
echo "  ✅ Railway CLI installiert"
echo "  ✅ Projekt verlinkt"
echo "  ✅ CLEANUP_SERVICE_URL konfiguriert"
echo "  ✅ PostgreSQL-Verbindung geprüft"
echo ""
echo "🎯 Nächste Schritte:"
echo "  1. Warte auf automatisches Deployment (Railway macht das automatisch)"
echo "  2. Prüfe Logs: railway logs --service cleanup_serivce"
echo "  3. Als Admin einloggen (User ID 2)"
echo "  4. Settings → Admin Tools → '🔍 Dry Run' testen"
echo ""
echo -e "${GREEN}🎉 Alles fertig!${NC}"

