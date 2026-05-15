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
JS_DIR = os.path.join(project_dir, 'static', 'js')

EXTRA_ENTRIES = {
    'alphabet.title': ('Alphabet', 'Alphabet'),
    'alphabet.back_button': ('Zurück', 'Back'),
    'alphabet.load_error': ('Alphabet konnte nicht geladen werden', 'Could not load alphabet'),
    'alphabet.audio_replay_button': ('Nochmal', 'Again'),
    'settings.title': ('Einstellungen', 'Settings'),
    'settings.subtitle': ('Verwalte deine App-Einstellungen und Präferenzen', 'Manage your app settings and preferences'),
    'settings.display': ('Anzeige', 'Display'),
    'settings.theme': ('Design', 'Theme'),
    'settings.language': ('Sprache', 'Language'),
    'settings.native_language': ('Muttersprache', 'Native language'),
    'settings.audio': ('Audio', 'Audio'),
    'settings.auto_play': ('Automatisches Abspielen', 'Auto-play'),
    'settings.sound_effects': ('Soundeffekte', 'Sound effects'),
    'settings.account': ('Konto', 'Account'),
    'settings.progress': ('Fortschritt', 'Progress'),
    'tabs.browse': ('Durchsuchen', 'Browse'),
    'buttons.practice': ('Üben', 'Practice'),
    'buttons.practice_difficult': ('Schwierig üben', 'Practice difficult'),
    'courses.title': ('🌍 Sprachen', '🌍 Languages'),
    'courses.subtitle': ('Wähle eine Sprache zum Lernen', 'Choose a language to start learning'),
    'onboarding.welcome.title': ('Willkommen bei Siluma!', 'Welcome to Siluma!'),
    'onboarding.welcome.subtitle': ('Lass uns dein Lernerlebnis in wenigen Schritten personalisieren.', "Let's personalize your learning experience in just a few steps."),
    'onboarding.native_language.title': ('Was ist deine Muttersprache?', "What's your native language?"),
    'onboarding.native_language.subtitle': ('Das hilft uns bei besseren Übersetzungen und Erklärungen.', 'This helps us provide better translations and explanations.'),
    'onboarding.target_language.title': ('Was möchtest du lernen?', 'What would you like to learn?'),
    'onboarding.target_language.subtitle': ('Wähle Zielsprache und aktuelles Sprachniveau.', 'Choose your target language and current proficiency level.'),
    'onboarding.learning_focus.title': ('Worauf liegt dein Lernfokus?', "What's your learning focus?"),
    'onboarding.learning_focus.subtitle': ('Wähle Themen, die dich am meisten interessieren.', 'Choose topics that interest you most.'),
    'onboarding.skip': ('Überspringen', 'Skip'),
    'onboarding.get_started': ('Los geht\'s', 'Get Started'),
    'onboarding.back': ('Zurück', 'Back'),
    'onboarding.next': ('Weiter', 'Next'),
    'onboarding.finish': ('Fertig', 'Finish'),
    'auth.login_title': ('Anmelden', 'Login'),
    'auth.register_title': ('Registrieren', 'Register'),
    'auth.username_or_email': ('Benutzername oder E-Mail', 'Username or Email'),
    'auth.username': ('Benutzername', 'Username'),
    'auth.email': ('E-Mail', 'Email'),
    'auth.password': ('Passwort', 'Password'),
    'auth.login_submit': ('Anmelden', 'Login'),
    'auth.register_submit': ('Registrieren', 'Register'),
    'settings.save': ('Einstellungen speichern', 'Save Settings'),
    'settings.reset_progress': ('Fortschritt zurücksetzen', 'Reset Progress'),
    'settings.theme_light': ('Hell', 'Light'),
    'settings.theme_dark': ('Dunkel', 'Dark'),
    'settings.theme_auto': ('Automatisch', 'Auto'),
    'settings.logout': ('Abmelden', 'Log out'),
    'settings.delete_account': ('Konto löschen', 'Delete account'),
    'settings.levels_completed': ('Abgeschlossene Level:', 'Total Levels Completed:'),
    'settings.words_learned': ('Gelernte Wörter:', 'Words Learned:'),
    'settings.current_streak': ('Aktuelle Serie:', 'Current Streak:'),
    'buttons.back_to_overview': ('Zurück zur Übersicht', 'Back to Overview'),
    'buttons.check_answer': ('Antwort prüfen', 'Check Answer'),
    'buttons.abort': ('Abbrechen', 'Cancel'),
    'status.level_completed': ('Level abgeschlossen!', 'Level completed!'),
}


def extract_pairs():
    html = open(HTML_PATH, encoding='utf-8').read()
    pairs = {}
    for m in re.finditer(r'data-i18n="([^"]+)"[^>]*>([^<]+)<', html):
        key, text = m.group(1).strip(), m.group(2).strip()
        if key and text and not text.startswith('['):
            pairs[key] = text
    # JS files are not scanned: regex false-positives on querySelector (e.g. `<=` in for-loops).
    pairs.update({k: v[0] for k, v in EXTRA_ENTRIES.items()})
    return pairs


def main():
    pairs = extract_pairs()
    init_db()
    for key, de_text in sorted(pairs.items()):
        en_text = EXTRA_ENTRIES.get(key, (de_text, de_text))[1]
        upsert_localization_entry({
            'reference_key': key,
            'description': f'UI: {key}',
            'german': de_text,
            'english': en_text,
        })
    print(f'Seeded {len(pairs)} UI localization keys from index.html')


if __name__ == '__main__':
    main()
