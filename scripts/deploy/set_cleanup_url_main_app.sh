#!/bin/bash
# Setze CLEANUP_SERVICE_URL im Hauptapp-Service
# Der Hauptapp-Service ist normalerweise der Service, der nicht cleanup_serivce heißt

echo "🔍 Suche nach Hauptapp-Service..."

# Versuche verschiedene Service-Namen
SERVICES=("projectsiluma" "polo" "siluma" "web" "app" "main")

for service in "${SERVICES[@]}"; do
    echo "Versuche Service: $service"
    if railway variables --service "$service" --set "CLEANUP_SERVICE_URL=http://cleanup_serivce.railway.internal" 2>&1 | grep -q "error\|not found"; then
        continue
    else
        echo "✅ Variable gesetzt im Service: $service"
        railway variables --service "$service" 2>&1 | grep CLEANUP_SERVICE_URL
        exit 0
    fi
done

echo "❌ Konnte Hauptapp-Service nicht finden"
echo "Bitte setze manuell im Railway Dashboard"
