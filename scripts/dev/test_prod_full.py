#!/usr/bin/env python3
"""Full production smoke + journey test for ProjectSiluma SPA."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from uuid import uuid4

BASE = os.environ.get('SPA_BASE', 'https://projectsiluma-production.up.railway.app').rstrip('/')
NATIVE = 'de'
TARGET = 'en'
TIMEOUT = 120


def req(method, path, token=None, body=None, native=NATIVE, expect_json=True):
    url = BASE + path
    h = {'Content-Type': 'application/json', 'X-Native-Language': native}
    if token:
        h['Authorization'] = f'Bearer {token}'
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=TIMEOUT) as resp:
            raw = resp.read().decode()
            if not expect_json:
                return resp.status, raw
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, {'_raw': raw[:500]}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return e.code, {'_raw': raw[:500]}
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

    print(f'=== Production full test @ {BASE} ===\n')

    # --- Static / SPA shell ---
    st, html = req('GET', '/', expect_json=False)
    check('spa_index', st == 200 and 'id="root"' in str(html), f'st={st}')
    st, legacy = req('GET', '/legacy', expect_json=False)
    check('legacy_route', st == 200, f'st={st}')
    for route in ['/library', '/browse', '/settings', '/login', '/onboarding', '/practice', '/alphabet', '/words', '/courses']:
        st, html = req('GET', route, expect_json=False)
        check(f'spa_route_{route.strip("/") or "home"}', st == 200 and 'id="root"' in str(html), f'st={st}')

    st, data = req('GET', '/health')
    check('health', st == 200 and data.get('ok'), str(data))

    # --- Auth ---
    suffix = uuid4().hex[:8]
    user = f'prod_{suffix}'
    pwd = 'ProdTest123!'

    st, data = req('POST', '/api/auth/register', body={
        'username': user, 'email': f'{user}@qa.test', 'password': pwd,
    })
    check('register', st in (200, 201) and data.get('success'), str(data)[:120])

    st, data = req('POST', '/api/auth/login', body={'username': user, 'password': pwd})
    token = data.get('session_token')
    check('login', bool(token), str(data)[:120])

    st, data = req('GET', '/api/auth/me', token=token)
    check('auth_me', st == 200 and data.get('user'), str(data)[:80])

    # --- i18n / courses ---
    for lang in ('de', 'en'):
        st, data = req('GET', f'/api/localization/{lang}')
        check(f'localization_{lang}', st == 200 and data.get('success'), str(data)[:60])

    st, data = req('GET', f'/api/available-courses?native_lang={NATIVE}', token=token)
    check('courses', st == 200 and data.get('success'), str(data)[:60])

    st, data = req('GET', '/api/available-languages')
    check('languages', st == 200, str(data)[:60])

    # --- Settings ---
    st, data = req('POST', '/api/user/settings', token=token, body={
        'native_language': NATIVE, 'target_language': TARGET,
        'onboarding_completed': True, 'theme': 'dark',
    })
    check('settings_save', st == 200 and data.get('success'), str(data)[:80])

    st, data = req('GET', '/api/user/settings', token=token)
    check('settings_get', data.get('settings', {}).get('onboarding_completed') is True, str(data)[:80])

    st, data = req('GET', '/api/user/stats', token=token)
    check('user_stats', st == 200 and data.get('success'), str(data)[:80])

    # --- Notifications ---
    st, data = req('GET', '/api/notifications?limit=10', token=token)
    check('notifications_list', st == 200 and data.get('success') is not False, str(data)[:80])
    st, data = req('GET', '/api/notifications/unread-count', token=token)
    check('notifications_count', st == 200, str(data)[:80])

    # --- Words ---
    st, data = req('GET', f'/api/words/learning?language={TARGET}&min_familiarity=0&max_familiarity=4&limit=10', token=token)
    check('words_learning', st == 200 and data.get('success'), str(data)[:80])

    # --- Alphabet ---
    st, data = req('GET', f'/api/alphabet?language={TARGET}')
    letters = data if isinstance(data, list) else data.get('letters', [])
    check('alphabet_get', st == 200 and (isinstance(data, list) or data.get('success') is not False), f'len={len(letters) if isinstance(letters, list) else "?"}')

    st, data = req('POST', '/api/alphabet/ensure', token=token, body={'language': TARGET})
    check('alphabet_ensure', st == 200 and (data.get('success') or data.get('letters')), str(data)[:80])

    st, data = req('POST', '/api/alphabet/tts', token=token, body={'letter': 'a', 'language': TARGET})
    if st == 200 and data.get('success'):
        check('alphabet_tts', True)
    else:
        print(f'WARN alphabet_tts (optional): {str(data)[:80]}')

    # --- Practice ---
    st, data = req('POST', '/api/practice/start', token=token, body={
        'language': TARGET, 'custom_words': ['hello', 'world'], 'exclude_max': True,
    })
    check('practice_start', st == 200 and data.get('success'), str(data)[:80])
    if data.get('word'):
        st, data = req('POST', '/api/practice/grade', token=token, body={
            'word': data['word'], 'mark': 'good', 'language': TARGET,
        })
        check('practice_grade', st == 200 and data.get('success'), str(data)[:80])

    # --- Marketplace ---
    st, data = req('GET', f'/api/marketplace/custom-level-groups?language={TARGET}&native_language={NATIVE}&limit=5&offset=0', token=token)
    check('marketplace', st == 200 and data.get('success'), f'groups={len(data.get("groups") or [])}')

    # --- Create group + full lesson flow ---
    group_id = None
    st, data = req('POST', '/api/custom-level-groups/create', token=token, body={
        'group_name': f'Prod QA {suffix}',
        'context_description': 'Traveler orders coffee and asks directions in the city.',
        'language': TARGET,
        'native_language': NATIVE,
        'cefr_level': 'A1',
        'num_levels': 3,
    })
    if data.get('success') and data.get('group_id'):
        check('create_group', True)
        group_id = data['group_id']
        for _ in range(90):
            time.sleep(2)
            st, gs = req('GET', f'/api/custom-level-groups/{group_id}/generation-status', token=token)
            if gs.get('status') in ('completed', 'done'):
                check('generation_done', True)
                break
            if gs.get('status') == 'failed':
                check('generation_done', False, str(gs)[:120])
                break
    else:
        print(f'SKIP create_group: {str(data)[:150]}')

    st, data = req('GET', f'/api/custom-levels/groups/summary?language={TARGET}&native_language={NATIVE}', token=token)
    check('library_summary', st == 200 and data.get('success'), f'n={len(data.get("groups") or [])}')

    if group_id:
        st, data = req('GET', f'/api/custom-level-groups/{group_id}', token=token)
        check('group_detail', st == 200 and data.get('success'), str(data)[:80])

        st, data = req('GET', f'/api/custom-levels/{group_id}/bulk-stats', token=token)
        check('bulk_stats', st == 200 and data.get('success'), str(data)[:80])

        st, data = req('GET', f'/api/custom-level-groups/{group_id}/levels/1', token=token)
        lvl = data.get('level') or {}
        has_level = st == 200 and data.get('success') and bool(lvl)
        check('level_content_endpoint', has_level, str(data)[:80])

        st, data = req('POST', f'/api/custom-levels/{group_id}/1/start', token=token, body={})
        items = data.get('items') or []
        if data.get('success') and not items:
            req('POST', f'/api/custom-levels/{group_id}/1/generate-content', token=token, body={})
            time.sleep(4)
            st, data = req('POST', f'/api/custom-levels/{group_id}/1/start', token=token, body={})
            items = data.get('items') or []
        run_id = data.get('run_id')
        check('lesson_start', data.get('success') and run_id and len(items) > 0, f'items={len(items)}')

        if items and run_id:
            st, data = req('POST', f'/api/custom-levels/{group_id}/1/finish', token=token, body={'run_id': run_id, 'score': 0.6})
            check('lesson_finish', st == 200 and data.get('success'), str(data)[:80])

        st, data = req('POST', f'/api/custom-level-groups/{group_id}/publish', token=token, body={})
        check('publish', st == 200 and data.get('success'), str(data)[:80])

        st, data = req('POST', f'/api/custom-level-groups/{group_id}/unpublish', token=token, body={})
        check('unpublish', st == 200 and data.get('success'), str(data)[:80])

    st, data = req('POST', '/api/auth/logout', token=token, body={})
    check('logout', st == 200, str(data)[:60])

    print(f'\n=== {len(ok)} passed, {len(fails)} failed ===')
    for name, detail in fails:
        print(f'  - {name}: {detail}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
