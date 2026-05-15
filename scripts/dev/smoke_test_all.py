#!/usr/bin/env python3
"""Smoke-test critical ProjectSiluma API endpoints."""
import json
import sys
import urllib.error
import urllib.request

BASE = 'http://127.0.0.1:5001'


def req(method, path, token=None, body=None, headers=None):
    url = BASE + path
    h = {'Content-Type': 'application/json'}
    if token:
        h['Authorization'] = f'Bearer {token}'
    if headers:
        h.update(headers)
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, {'_raw': raw[:200]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
        except json.JSONDecodeError:
            return e.code, {'_raw': raw[:200]}
    except Exception as e:
        return 0, {'error': str(e)}


def main():
    fails = []
    ok = []

    def check(name, status, data, expect=(200,), success_key=None):
        good = status in expect
        if success_key and isinstance(data, dict):
            good = good and data.get(success_key) is not False
        if good:
            ok.append(name)
            print(f'OK  {name} ({status})')
        else:
            fails.append((name, status, data))
            err = data.get('error', data) if isinstance(data, dict) else data
            print(f'FAIL {name} ({status}) {str(err)[:120]}')

    st, _ = req('GET', '/')
    check('index', st, {})

    st, data = req('POST', '/api/auth/login', body={'username': 'testuser', 'password': 'password123'})
    check('login', st, data, success_key='success')
    token = data.get('session_token') if isinstance(data, dict) else None
    if not token:
        print('Cannot continue without token')
        return 1

    endpoints = [
        ('GET', '/api/localization/de', None, None, 'success'),
        ('GET', '/api/localization/en', None, None, 'success'),
        ('GET', '/api/available-languages', None, None, 'success'),
        ('GET', '/api/available-courses?native_lang=de', None, None, 'success'),
        ('GET', '/api/words?language=en', token, {'X-Native-Language': 'de'}, 'success'),
        ('GET', '/api/words/count_learned?language=en', token, None, None),
        ('GET', '/api/words/learning?language=en&min_familiarity=1&max_familiarity=4&limit=5', token, {'X-Native-Language': 'de'}, 'success'),
        ('GET', '/api/levels/summary', token, None, None),
        ('GET', '/api/levels/bulk?language=en&native_language=de', token, None, None),
        ('GET', '/api/custom-levels/groups/summary', token, None, 'success'),
        ('GET', '/api/custom-level-groups?language=en&native_language=de', token, None, 'success'),
        ('GET', '/api/notifications/unread-count', token, None, None),
        ('GET', '/api/user/settings', token, None, None),
        ('GET', '/api/localization/entries', token, None, None),
        ('GET', '/api/marketplace/groups?page=1&per_page=5', token, None, 'success'),
    ]

    for item in endpoints:
        method, path, tok, hdrs, sk = item
        st, data = req(method, path, token=tok or token, headers=hdrs)
        if sk:
            check(path, st, data, success_key=sk)
        else:
            check(path, st, data, expect=(200,))

    print(f'\n{len(ok)} passed, {len(fails)} failed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
