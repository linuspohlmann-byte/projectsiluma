#!/usr/bin/env python3
"""Verify SPA routes return index.html and legacy/API paths work."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get('SPA_BASE', 'http://127.0.0.1:5173').rstrip('/')
API = os.environ.get('API_BASE', 'http://127.0.0.1:5001').rstrip('/')


def get(url):
    r = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, resp.read().decode(errors='replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode(errors='replace')


def post_json(url, body):
    data = json.dumps(body).encode()
    r = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')
    with urllib.request.urlopen(r, timeout=15) as resp:
        return json.loads(resp.read().decode())


def main():
    fails = []
    routes = ['/login', '/library', '/browse', '/courses', '/words', '/practice', '/settings', '/legacy']
    for path in routes:
        st, body = get(f'{BASE}{path}' if path != '/legacy' else f'{API}{path}')
        if path == '/legacy':
            ok = st == 200 and 'Sprachlern' in body
        else:
            ok = st == 200 and ('id="root"' in body or 'Polo' in body)
        print(f'{"OK" if ok else "FAIL"} {path} ({st})')
        if not ok:
            fails.append(path)

    token = post_json(f'{API}/api/auth/login', {'username': 'testuser', 'password': 'password123'}).get('session_token')
    if token:
        mp = f'{API}/api/marketplace/custom-level-groups?language=en&native_language=de&limit=5&offset=0'
        r = urllib.request.Request(mp, headers={'Authorization': f'Bearer {token}'})
        with urllib.request.urlopen(r, timeout=15) as resp:
            d = json.loads(resp.read().decode())
        ok = d.get('success') and 'groups' in d
        print(f'{"OK" if ok else "FAIL"} marketplace API')
        if not ok:
            fails.append('marketplace')
    else:
        print('SKIP marketplace (no token)')

    print(f'\n{len(fails)} failures')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
