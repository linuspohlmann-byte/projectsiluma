#!/usr/bin/env python3
"""
Automatische Railway-Konfiguration für Cleanup Service
Versucht, die Environment Variable über Railway API zu setzen
"""
import os
import subprocess
import sys

def run_command(cmd, check=True):
    """Führe Railway CLI Befehl aus"""
    try:
        result = subprocess.run(
            cmd, 
            shell=True, 
            capture_output=True, 
            text=True,
            check=check
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.CalledProcessError as e:
        return e.stdout, e.stderr, e.returncode

def main():
    print("🚀 Automatische Railway-Konfiguration")
    print("=" * 50)
    print()
    
    # Prüfe Railway CLI
    stdout, stderr, code = run_command("railway --version", check=False)
    if code != 0:
        print("❌ Railway CLI nicht gefunden")
        print("Installiere mit: npm i -g @railway/cli")
        return 1
    
    print(f"✅ Railway CLI: {stdout}")
    print()
    
    # Prüfe Projekt-Link
    stdout, stderr, code = run_command("railway status", check=False)
    if code != 0:
        print("⚠️  Projekt nicht verlinkt")
        print("Bitte führe aus: railway link")
        print("Dann wähle: projectsiluma")
        return 1
    
    print("✅ Projekt verlinkt")
    print()
    
    # Setze Environment Variable
    cleanup_url = "http://cleanup_serivce.railway.internal"
    print(f"🔧 Setze CLEANUP_SERVICE_URL={cleanup_url}")
    
    stdout, stderr, code = run_command(
        f'railway variables set CLEANUP_SERVICE_URL="{cleanup_url}"',
        check=False
    )
    
    if code == 0:
        print("✅ Environment Variable gesetzt!")
        print()
        print("📝 Nächste Schritte:")
        print("  1. PostgreSQL mit cleanup_serivce verbinden")
        print("  2. Railway Logs prüfen")
        print("  3. Als Admin testen (User ID 2)")
        return 0
    else:
        print("❌ Fehler beim Setzen der Variable")
        print(f"Error: {stderr}")
        print()
        print("Bitte setze manuell im Railway Dashboard:")
        print(f"  CLEANUP_SERVICE_URL={cleanup_url}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
