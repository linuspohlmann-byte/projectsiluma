#!/usr/bin/env python3
import subprocess
import json
import sys

# Versuche, alle Services zu finden
try:
    # Railway CLI hat keine direkte "list services" Funktion
    # Aber wir können versuchen, die Variable im Default-Service zu setzen
    # (normalerweise der erste Service oder der, der nicht cleanup_serivce ist)
    
    # Prüfe aktuellen Service
    result = subprocess.run(['railway', 'status'], capture_output=True, text=True)
    current_service = None
    for line in result.stdout.split('\n'):
        if 'Service:' in line:
            current_service = line.split('Service:')[1].strip()
            break
    
    print(f"Aktueller Service: {current_service}")
    
    # Wenn wir im cleanup_serivce sind, müssen wir zum Hauptapp wechseln
    if current_service == 'cleanup_serivce':
        print("⚠️  Wir sind im cleanup_serivce Service")
        print("Die Variable muss im Hauptapp-Service gesetzt werden!")
        print("\nBitte führe manuell aus:")
        print("  1. railway service <hauptapp-service-name>")
        print("  2. railway variables --set 'CLEANUP_SERVICE_URL=http://cleanup_serivce.railway.internal'")
        sys.exit(1)
    
    # Versuche, die Variable zu setzen
    print(f"\n🔧 Setze CLEANUP_SERVICE_URL im Service: {current_service}")
    result = subprocess.run([
        'railway', 'variables', 
        '--set', 'CLEANUP_SERVICE_URL=http://cleanup_serivce.railway.internal'
    ], capture_output=True, text=True)
    
    if result.returncode == 0:
        print("✅ Variable erfolgreich gesetzt!")
        sys.exit(0)
    else:
        print(f"❌ Fehler: {result.stderr}")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Fehler: {e}")
    sys.exit(1)
