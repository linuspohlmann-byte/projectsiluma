#!/usr/bin/env python3
"""Smoke-test SPA routes and APIs on production or local."""
import json
import os
import sys
import urllib.error
import urllib.request

BASE = os.environ.get('SPA_BASE', 'https://projectsiluma-production.up.railway.app')


def req(method, path, token=None, body=None):
    url = BASE.rstrip('/') + path
    h = {'Content-Type': 'application/json'}
    if token:
        h['Authorization'] = f'Bearer {token}'
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {'_raw': raw[:300]}
    except Exception as e:
        return 0, {'error': str(e)}


def main():
    fails = []
    ok = []

    def check(name, cond, detail=''):
        if cond:
            ok.append(name)
            print(f'OK  {name}')
        else:
            fails.append((name, detail))
            print(f'FAIL {name} {detail}')

    st, html = req('GET', '/')
    if isinstance(html, dict):
        html = html.get('_raw', '')
    check('spa_index', 'id="root"' in str(html) or st == 200 and isinstance(html, str), f'status={st}')

    st, legacy = req('GET', '/legacy')
    if isinstance(legacy, dict):
        legacy = legacy.get('_raw', '')
    check('legacy_route', 'Sprachlern' in str(legacy) or st == 200, f'status={st}')

    st, data = req('GET', '/health')
    check('health', st == 200 and data.get('ok'), str(data))

    # Try login — optional (may fail if no test user on prod)
    st, data = req('POST', '/api/auth/login', body={'username': 'testuser', 'password': 'password123'})
    token = data.get('session_token') if isinstance(data, dict) else None
    if token:
        check('login', True)
        for name, path, key in [
            ('localization', '/api/localization/de', 'success'),
            ('courses', '/api/available-courses?native_lang=de', 'success'),
            ('groups_summary', '/api/custom-levels/groups/summary?language=en&native_language=de', 'success'),
            ('words_learning', '/api/words/learning?language=en&native_language=de&limit=5', 'success'),
            ('marketplace', '/api/marketplace/custom-level-groups?language=en&native_language=de&limit=5&offset=0', 'success'),
            ('auth_me', '/api/auth/me', 'success'),
        ]:
            st, d = req('GET', path, token=token)
            check(name, st == 200 and (key is None or d.get(key) is not False), f'{st} {str(d)[:80]}')
    else:
        print(f'SKIP auth APIs (login {st}: {data.get("error", data) if isinstance(data, dict) else data})')

    print(f'\n{len(ok)} passed, {len(fails)} failed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
