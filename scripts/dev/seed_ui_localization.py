#!/usr/bin/env python3
"""Seed UI strings from index.html data-i18n attributes into SQLite localization."""
import os
import re
import sys

project_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_dir)
os.environ.setdefault('FORCE_SQLITE', '1')
os.environ.setdefault('DATABASE_URL', '')

from server.db import init_db, upsert_localization_entry

HTML_PATH = os.path.join(project_dir, 'index.html')


def extract_pairs():
    html = open(HTML_PATH, encoding='utf-8').read()
    pairs = {}
    for m in re.finditer(r'data-i18n="([^"]+)"[^>]*>([^<]+)<', html):
        key, text = m.group(1).strip(), m.group(2).strip()
        if key and text and not text.startswith('['):
            pairs[key] = text
    return pairs


def main():
    pairs = extract_pairs()
    init_db()
    for key, de_text in sorted(pairs.items()):
        upsert_localization_entry({
            'reference_key': key,
            'description': f'UI: {key}',
            'german': de_text,
            'english': de_text,
        })
    print(f'Seeded {len(pairs)} UI localization keys from index.html')


if __name__ == '__main__':
    main()
