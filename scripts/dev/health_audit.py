#!/usr/bin/env python3
"""ShipLoop health audit: API smoke + localization sanity → health.json score."""
import json
import os
import re
import sys
import urllib.request

project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_dir)
os.environ.setdefault('FORCE_SQLITE', '1')
os.environ.setdefault('DATABASE_URL', '')

BASE = os.environ.get('SILUMA_BASE_URL', 'http://127.0.0.1:5001')
HEALTH_PATH = os.path.join(project_dir, '.shiploop', 'health.json')

CHECKS = []


def check(name, ok, severity='high', note=''):
    CHECKS.append({'name': name, 'ok': ok, 'severity': severity, 'note': note})


def fetch(path):
    req = urllib.request.Request(f'{BASE}{path}')
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, r.read()


def main():
    # API endpoints (critical)
    endpoints = [
        '/',
        '/api/localization/de',
        '/api/available-courses?native_lang=de',
        '/api/levels/summary',
        '/api/custom-levels/groups/summary',
        '/api/marketplace/groups?page=1&per_page=5',
    ]
    for ep in endpoints:
        try:
            status, _ = fetch(ep)
            check(f'API {ep}', status == 200, 'critical' if status != 200 else 'high')
        except Exception as e:
            check(f'API {ep}', False, 'critical', str(e))

    # Localization DB sanity
    import sqlite3
    db = os.path.join(project_dir, 'polo.db')
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute(
        "SELECT reference_key, german FROM localization WHERE german LIKE '%for(let%' OR german LIKE '%querySelector%'"
    )
    bad = cur.fetchall()
    check('No corrupted localization rows', len(bad) == 0, 'critical', str(bad[:3]))
    cur.execute("SELECT COUNT(*) FROM localization WHERE german IS NOT NULL AND german != ''")
    count = cur.fetchone()[0]
    check('Localization entries present', count >= 100, 'high', f'count={count}')
    conn.close()

    # HTML fallbacks (medium): no obvious EN defaults for DE-first keys
    html = open(os.path.join(project_dir, 'index.html'), encoding='utf-8').read()
    en_patterns = [
        (r'data-i18n="courses\.title"[^>]*>🌍 Languages', 'courses.title EN fallback'),
        (r'data-i18n="auth\.login_title"[^>]*>Login<', 'auth.login EN fallback'),
    ]
    for pat, label in en_patterns:
        check(label, not re.search(pat, html), 'medium')

    total = len(CHECKS)
    critical = sum(1 for c in CHECKS if not c['ok'] and c['severity'] == 'critical')
    high = sum(1 for c in CHECKS if not c['ok'] and c['severity'] == 'high')
    medium = sum(1 for c in CHECKS if not c['ok'] and c['severity'] == 'medium')
    low = sum(1 for c in CHECKS if not c['ok'] and c['severity'] == 'low')
    penalty = critical * 4 + high * 2 + medium * 1 + low * 0.5
    score = max(0, min(100, int(((total - penalty) / total) * 100))) if total else 0

    prev = {}
    if os.path.isfile(HEALTH_PATH):
        prev = json.load(open(HEALTH_PATH))
    history = prev.get('history', [])
    cycle = len(history)
    history.append({'cycle': cycle, 'score': score, 'note': 'health_audit.py'})

    out = {
        'current_score': score,
        'history': history,
        'total_checks': total,
        'critical': critical,
        'high': high,
        'medium': medium,
        'low': low,
        'cycle': cycle,
        'start_score': prev.get('start_score', 35),
        'failed_checks': [c for c in CHECKS if not c['ok']],
    }
    os.makedirs(os.path.dirname(HEALTH_PATH), exist_ok=True)
    json.dump(out, open(HEALTH_PATH, 'w'), indent=2)
    print(f'Health score: {score} ({total} checks, penalty={penalty})')
    for c in CHECKS:
        if not c['ok']:
            print(f"  FAIL [{c['severity']}] {c['name']}: {c.get('note', '')}")
    return 0 if score >= 95 else 1


if __name__ == '__main__':
    sys.exit(main())
