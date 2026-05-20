#!/usr/bin/env python3
"""Poll production until deploy markers match GitHub main (logout fix)."""
import json
import sys
import time
import urllib.error
import urllib.request

BASE = 'https://projectsiluma-production.up.railway.app'
EXPECTED_HEAD = '05a6f7b'  # bulk-stats graceful + word conflicts
INTERVAL = 45
MAX_WAIT = 900  # 15 min


def post(path, body=None, token=None):
    data = json.dumps(body or {}).encode()
    req = urllib.request.Request(
        f'{BASE}{path}',
        data=data,
        method='POST',
        headers={'Content-Type': 'application/json'},
    )
    if token:
        req.add_header('Authorization', f'Bearer {token}')
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {'raw': raw[:200]}
        return e.code, payload


def prod_git_sha():
    try:
        req = urllib.request.Request(f'{BASE}/health')
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read().decode())
        return data.get('git_sha')
    except Exception:
        return None


def logout_deployed():
    user = f'deploy_watch_{int(time.time())}'
    st, reg = post('/api/auth/register', {'username': user, 'password': 'DeployWatch1!', 'email': f'{user}@example.com'})
    if st not in (200, 201) and not reg.get('session_token'):
        st, reg = post('/api/auth/login', {'username': user, 'password': 'DeployWatch1!'})
    token = reg.get('session_token')
    if not token:
        return False, f'no token (register {st})'
    st, out = post('/api/auth/logout', {}, token=token)
    ok = st == 200 and out.get('success') is True
    return ok, f'logout HTTP {st} {str(out)[:80]}'


def main():
    start = time.time()
    attempt = 0
    print(f'Monitoring {BASE} (expect commit ~{EXPECTED_HEAD} markers)')
    while time.time() - start < MAX_WAIT:
        attempt += 1
        elapsed = int(time.time() - start)
        sha = prod_git_sha()
        try:
            deployed, detail = logout_deployed()
        except Exception as e:
            deployed, detail = False, str(e)
        ts = time.strftime('%H:%M:%S')
        sha_note = f' prod_sha={sha or "?"}'
        if deployed:
            print(f'[{ts}] attempt {attempt} (+{elapsed}s): DEPLOYED — {detail}{sha_note}')
            return 0
        print(f'[{ts}] attempt {attempt} (+{elapsed}s): waiting — {detail}{sha_note}')
        time.sleep(INTERVAL)
    print(f'Timeout after {MAX_WAIT}s')
    return 1


if __name__ == '__main__':
    sys.exit(main())
