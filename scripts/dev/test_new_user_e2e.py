#!/usr/bin/env python3
"""End-to-end API flow as a freshly registered user."""
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


def req(method, path, token=None, body=None, native=NATIVE):
    url = BASE + path
    h = {'Content-Type': 'application/json', 'X-Native-Language': native}
    if token:
        h['Authorization'] = f'Bearer {token}'
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            return e.code, json.loads(raw)
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

    suffix = uuid4().hex[:8]
    username = f'qa_{suffix}'
    email = f'{username}@qa.test'
    password = 'QaTest123!'

    print(f'BASE={BASE} user={username}\n')

    st, data = req('GET', '/health')
    check('health', st == 200 and data.get('ok'), str(data))

    st, data = req('POST', '/api/auth/register', body={
        'username': username,
        'email': email,
        'password': password,
    })
    check('register', st in (200, 201) and data.get('success'), f'{st} {data}')

    st, data = req('POST', '/api/auth/login', body={'username': username, 'password': password})
    token = data.get('session_token')
    check('login', bool(token), f'{st} {data}')

    st, data = req('GET', '/api/auth/me', token=token)
    check('me', st == 200 and data.get('success') and data.get('user'), str(data)[:120])

    st, data = req('POST', '/api/user/settings', token=token, body={
        'native_language': NATIVE,
        'target_language': TARGET,
        'onboarding_completed': True,
        'theme': 'light',
        'auto_play_audio': False,
        'sound_enabled': True,
    })
    check('onboarding_settings', st == 200 and data.get('success'), f'{st} {data}')

    st, data = req('GET', '/api/user/settings', token=token)
    settings = data.get('settings') or {}
    check(
        'settings_persisted',
        settings.get('onboarding_completed') is True,
        str(settings)[:200],
    )

    group_id = None

    # Create group first (production has AI; local may skip)
    st, data = req('POST', '/api/custom-level-groups/create', token=token, body={
        'group_name': f'QA Story {suffix}',
        'context_description': 'A traveler learning phrases at a café in Paris.',
        'language': TARGET,
        'native_language': NATIVE,
        'cefr_level': 'A1',
        'num_levels': 3,
    })
    if data.get('success') and data.get('group_id'):
        check('create_group', True)
        group_id = data['group_id']
        for i in range(90):
            time.sleep(2)
            st, gs = req('GET', f'/api/custom-level-groups/{group_id}/generation-status', token=token)
            if gs.get('status') in ('completed', 'done'):
                check('generation_status', True, gs.get('message', ''))
                break
            if gs.get('status') == 'failed':
                check('generation_status', False, str(gs)[:200])
                break
        else:
            check('generation_status', st == 200, 'timeout waiting for generation')
    else:
        print(f'SKIP create_group ({st}): {str(data)[:200]}')

    st, data = req('GET', f'/api/custom-levels/groups/summary?language={TARGET}&native_language={NATIVE}', token=token)
    groups = data.get('groups') or []
    check('library_list', st == 200 and data.get('success'), f'groups={len(groups)}')

    if not group_id and groups:
        group_id = groups[0].get('id')

    st, data = req(
        'GET',
        f'/api/marketplace/custom-level-groups?language={TARGET}&native_language={NATIVE}&limit=5&offset=0',
        token=token,
    )
    mp = data.get('groups') or []
    check('marketplace_list', st == 200 and data.get('success'), f'count={len(mp)}')

    if mp and not group_id:
        gid = mp[0].get('id')
        st, data = req('POST', f'/api/marketplace/custom-level-groups/{gid}/import', token=token, body={})
        if data.get('success') and data.get('group_id'):
            group_id = data['group_id']
            check('marketplace_import', True)

    if group_id:
        st, data = req('PUT', f'/api/custom-level-groups/{group_id}', token=token, body={
            'group_name': f'QA Story {suffix} updated',
        })
        check('update_group', st == 200 and data.get('success'), str(data)[:120])

        st, data = req('GET', f'/api/custom-level-groups/{group_id}', token=token)
        check('group_detail', st == 200 and data.get('success'), str(data)[:120])

        st, data = req('GET', f'/api/custom-levels/{group_id}/bulk-stats', token=token)
        levels = data.get('levels') or {}
        check('bulk_stats', st == 200 and data.get('success'), f'levels={len(levels)}')

        level_num = 1
        if levels:
            level_num = min(int(k) for k in levels.keys() if str(k).isdigit()) or 1

        st, data = req('POST', f'/api/custom-levels/{group_id}/{level_num}/start', token=token, body={})
        items = data.get('items') or []
        if data.get('success') and not items:
            req('POST', f'/api/custom-levels/{group_id}/{level_num}/generate-content', token=token, body={})
            time.sleep(3)
            st, data = req('POST', f'/api/custom-levels/{group_id}/{level_num}/start', token=token, body={})
            items = data.get('items') or []
        run_id = data.get('run_id')
        check('lesson_start', st == 200 and data.get('success') and run_id and len(items) > 0, str(data)[:150])

        if items and run_id:
            word = None
            for it in items:
                tt = (it.get('text_target') or '').split()
                if tt:
                    word = tt[0].strip('.,!?;:')
                    break
            if word:
                st, wd = req(
                    'GET',
                    f'/api/word?word={urllib.parse.quote(word)}&language={TARGET}&native_language={NATIVE}',
                    token=token,
                )
                check('word_lookup', st == 200 and wd.get('word'), str(wd)[:100])

            st, data = req(
                'POST',
                f'/api/custom-levels/{group_id}/{level_num}/finish',
                token=token,
                body={'run_id': run_id, 'score': 0.5},
            )
            check('lesson_finish', st == 200 and data.get('success'), str(data)[:120])

        st, data = req('POST', f'/api/custom-level-groups/{group_id}/publish', token=token, body={})
        check('publish_group', st == 200 and data.get('success'), str(data)[:120])

        st, data = req('POST', f'/api/custom-level-groups/{group_id}/unpublish', token=token, body={})
        check('unpublish_group', st == 200 and data.get('success'), str(data)[:120])
    else:
        print('SKIP group flows (no group)')

    st, data = req('GET', f'/api/words/learning?language={TARGET}&min_familiarity=0&max_familiarity=4&limit=10', token=token)
    check('words_list', st == 200 and data.get('success'), str(data)[:80])

    st, data = req('GET', '/api/user/stats', token=token)
    check('user_stats', st == 200 and data.get('success'), str(data)[:80])

    st, data = req('GET', '/api/notifications/unread-count', token=token)
    check('notifications', st == 200 and data.get('success') is not False, str(data)[:80])

    st, data = req('GET', f'/api/available-courses?native_lang={NATIVE}', token=token)
    check('courses', st == 200 and data.get('success'), str(data)[:80])

    print(f'\n{len(ok)} passed, {len(fails)} failed')
    for name, detail in fails:
        print(f'  - {name}: {detail}')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
