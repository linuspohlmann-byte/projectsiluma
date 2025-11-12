"""TTS helpers.
Environment overrides for language-accurate voices:
  OPENAI_TTS_MODEL_<LANG>  e.g. OPENAI_TTS_MODEL_DE
  OPENAI_TTS_VOICE_<LANG>  e.g. OPENAI_TTS_VOICE_DE
Fallbacks: OPENAI_TTS_MODEL, OPENAI_TTS_VOICE.
OpenAI-only mode. You can override defaults via OPENAI_TTS_MODEL[_<LANG>] and OPENAI_TTS_VOICE[_<LANG>].
"""
import os, json
from datetime import datetime, UTC
from typing import List, Dict
from .llm import _http_binary, OPENAI_KEY, OPENAI_BASE
from server.db_config import get_db_connection, execute_query
from .cache import cached_tts
from .s3_storage import upload_tts_audio, upload_tts_audio_bytes, get_tts_audio_url, tts_audio_exists
import concurrent.futures
import threading

# S3 is required - no local disk storage
# All audio files must be stored in S3

# Per-language TTS configuration via environment overrides
# Prefer OPENAI_TTS_MODEL_<LANG> and OPENAI_TTS_VOICE_<LANG> if set, else fall back to global defaults
# Example: OPENAI_TTS_MODEL_DE=gpt-4o-mini-tts  OPENAI_TTS_VOICE_DE=gerhard

def _pick_tts_config(lang_code: str):
    lc = (lang_code or 'en').strip().lower()
    base = lc.split('-')[0]
    keys = [lc.replace('-', '_').upper(), base.upper()]
    global_model = os.environ.get('OPENAI_TTS_MODEL') or 'gpt-4o-mini-tts'
    global_voice = os.environ.get('OPENAI_TTS_VOICE') or 'alloy'
    model = global_model
    voice = global_voice
    used_override = False
    for k in keys:
        m = os.environ.get(f'OPENAI_TTS_MODEL_{k}')
        v = os.environ.get(f'OPENAI_TTS_VOICE_{k}')
        if m:
            model = m; used_override = True
        if v:
            voice = v; used_override = True
    if not used_override:
        # OpenAI TTS voices are multilingual but not accent-specific.
        # Assign stable defaults per language for consistency and treat as per-language override.
        openai_voice_defaults = {
            'en': 'alloy',
            'de': 'onyx',
            'fr': 'nova',  # Better French pronunciation
            'es': 'coral',
            'it': 'nova',
            'pt': 'verse',
            'nl': 'alloy',
            'sv': 'verse',
            'ru': 'onyx',
            'tr': 'coral',
            'pl': 'onyx',
            'ka': 'alloy',
            'ar': 'onyx',  # Arabic
            'hi': 'onyx',  # Hindi
            'zh': 'coral', # Chinese
            'ja': 'nova',  # Japanese
            'ko': 'coral', # Korean
            'th': 'nova',  # Thai
            'vi': 'coral', # Vietnamese
            'id': 'alloy', # Indonesian
            'bn': 'onyx',  # Bengali
            'ur': 'onyx',  # Urdu
            'fa': 'onyx',  # Persian
            'he': 'onyx',  # Hebrew
            'uk': 'onyx',  # Ukrainian
            'cs': 'onyx',  # Czech
            'sk': 'onyx',  # Slovak
            'hu': 'onyx',  # Hungarian
            'ro': 'nova',  # Romanian
            'bg': 'onyx',  # Bulgarian
            'hr': 'onyx',  # Croatian
            'sr': 'onyx',  # Serbian
            'sl': 'onyx',  # Slovenian
            'et': 'onyx',  # Estonian
            'lv': 'onyx',  # Latvian
            'lt': 'onyx',  # Lithuanian
            'fi': 'onyx',  # Finnish
            'no': 'verse', # Norwegian
            'da': 'verse', # Danish
            'is': 'verse', # Icelandic
            'sw': 'alloy', # Swahili
            'am': 'onyx',  # Amharic
            'yo': 'alloy', # Yoruba
            'zu': 'alloy', # Zulu
            'af': 'alloy', # Afrikaans
        }
        dv = openai_voice_defaults.get(base)
        if dv:
            voice = dv
            used_override = True
    return model, voice, used_override


# Helper: Does this TTS model support instructions?
def _supports_instructions(model: str) -> bool:
    """
    Returns True if the TTS model supports the 'instructions' parameter.
    Currently, 'tts-1' and 'tts-1-hd' do NOT support instructions.
    """
    return model not in ("tts-1", "tts-1-hd")



# Helper: Language display name for TTS instructions.
def _lang_display_name(lang_code: str) -> str:
    """
    Returns a human-readable name for a language code.
    Precedence:
      1. Env override: OPENAI_LANG_NAME_<KEY> (LC_UPPER, BASE_UPPER)
      2. Built-in map for common codes
      3. Fallback: uppercased base code
    Example: for 'de-DE', checks OPENAI_LANG_NAME_DE_DE, then OPENAI_LANG_NAME_DE, then built-in, then 'DE'.
    Customize via env: OPENAI_LANG_NAME_DE="German"
    """
    lc = (lang_code or 'en').strip().lower()
    base = lc.split('-')[0]
    keys = [lc.replace('-', '_').upper(), base.upper()]
    for k in keys:
        v = os.environ.get(f'OPENAI_LANG_NAME_{k}')
        if v is not None and str(v).strip():
            return str(v).strip()
    _builtins = {
        'de': 'German', 'en': 'English', 'fr': 'French', 'es': 'Spanish', 'it': 'Italian',
        'pt': 'Portuguese', 'nl': 'Dutch', 'sv': 'Swedish', 'ru': 'Russian', 'tr': 'Turkish',
        'pl': 'Polish', 'ka': 'Georgian', 'ar': 'Arabic', 'hi': 'Hindi', 'zh': 'Chinese',
        'ja': 'Japanese', 'ko': 'Korean', 'th': 'Thai', 'vi': 'Vietnamese', 'id': 'Indonesian',
        'bn': 'Bengali', 'ur': 'Urdu', 'fa': 'Persian', 'he': 'Hebrew', 'uk': 'Ukrainian',
        'cs': 'Czech', 'sk': 'Slovak', 'hu': 'Hungarian', 'ro': 'Romanian', 'bg': 'Bulgarian',
        'hr': 'Croatian', 'sr': 'Serbian', 'sl': 'Slovenian', 'et': 'Estonian', 'lv': 'Latvian',
        'lt': 'Lithuanian', 'fi': 'Finnish', 'no': 'Norwegian', 'da': 'Danish', 'is': 'Icelandic',
        'sw': 'Swahili', 'am': 'Amharic', 'yo': 'Yoruba', 'zu': 'Zulu', 'af': 'Afrikaans'
    }
    return _builtins.get(base, base.upper())

def _generate_alphabet_instruction(lang_name: str, lang_code: str) -> str:
    """
    Generate dynamic alphabet instructions for any language.
    This creates language-specific instructions without hardcoding.
    """
    # Common instruction patterns that work across languages
    instruction_templates = {
        'en': "CRITICAL: You are speaking in {LANG_NAME}. Pronounce each letter as its {LANG_NAME} phonetic sound, NOT as its name. Examples: F should sound like 'ffff', not 'eff'. B should sound like 'buh', not 'bee'. Use ONLY {LANG_NAME} pronunciation. NEVER use English pronunciation.",
        'de': "KRITISCH: Sie sprechen {LANG_NAME}. Sprechen Sie jeden Buchstaben als seinen {LANG_NAME} Laut aus, NICHT als Buchstabennamen. Beispiele: F soll wie 'ffff' klingen, nicht wie 'eff'. B soll wie 'buh' klingen, nicht wie 'bee'. Verwenden Sie NUR {LANG_NAME} Aussprache. NIEMALS englische Aussprache.",
        'fr': "CRITIQUE: Vous parlez {LANG_NAME}. Prononcez chaque lettre comme son son phonétique {LANG_NAME}, PAS comme son nom. Exemples: F doit sonner comme 'ffff', pas comme 'eff'. B doit sonner comme 'buh', pas comme 'bee'. Utilisez UNIQUEMENT la prononciation {LANG_NAME}. JAMAIS la prononciation anglaise.",
        'es': "CRÍTICO: Estás hablando {LANG_NAME}. Pronuncie cada letra como su sonido fonético {LANG_NAME}, NO como su nombre. Ejemplos: F debe sonar como 'ffff', no como 'efe'. B debe sonar como 'buh', no como 'be'. Use SOLO pronunciación {LANG_NAME}. NUNCA pronunciación inglesa.",
        'it': "CRITICO: Stai parlando {LANG_NAME}. Pronunciate ogni lettera come il suo suono fonetico {LANG_NAME}, NON come il suo nome. Esempi: F dovrebbe suonare come 'ffff', non come 'effe'. B dovrebbe suonare come 'buh', non come 'bi'. Usate SOLO pronuncia {LANG_NAME}. MAI pronuncia inglese.",
        'pt': "CRÍTICO: Você está falando {LANG_NAME}. Pronuncie cada letra como seu som fonético {LANG_NAME}, NÃO como seu nome. Exemplos: F deve soar como 'ffff', não como 'efe'. B deve soar como 'buh', não como 'bê'. Use APENAS pronúncia {LANG_NAME}. NUNCA pronúncia inglesa.",
        'ru': "КРИТИЧНО: Вы говорите на {LANG_NAME}. Произносите каждую букву как её {LANG_NAME} звук, НЕ как название буквы. Примеры: Ф должно звучать как 'фффф', а не как 'эф'. Б должно звучать как 'б', а не как 'бэ'. Используйте ТОЛЬКО {LANG_NAME} произношение. НИКОГДА английское произношение.",
        'tr': "KRİTİK: {LANG_NAME} konuşuyorsunuz. Her harfi {LANG_NAME} sesi olarak telaffuz edin, harf adı olarak değil. Örnekler: F 'ffff' gibi ses çıkarmalı, 'ef' değil. B 'buh' gibi ses çıkarmalı, 'be' değil. Sadece {LANG_NAME} telaffuz kullanın. Asla İngilizce telaffuz kullanmayın.",
        'ka': "კრიტიკული: თქვენ ლაპარაკობთ {LANG_NAME}. ყოველი ასო იწყება მისი {LANG_NAME} ფონეტიკური ხმით, არა ასოს სახელით. მაგალითები: ფ უნდა ჟღერდეს 'ფფფფ', არა 'ეფ'. ბ უნდა ჟღერდეს 'ბ', არა 'ბე'. გამოიყენეთ მხოლოდ {LANG_NAME} გამოთქმა. არასდროს ინგლისური გამოთქმა."
    }
    
    # Try to use the instruction in the target language, fallback to English
    instruction_template = instruction_templates.get(lang_code, instruction_templates['en'])
    
    # Replace placeholders
    instruction = instruction_template.replace('{LANG_NAME}', lang_name.upper())
    
    return instruction

def _generate_word_context_instruction(lang_code: str, word: str, sentence: str) -> str:
    """
    Generate context-aware instructions for word pronunciation.
    Provides the sentence context to help with proper pronunciation.
    """
    lang_name = _lang_display_name(lang_code)
    
    # Context instruction templates for different languages
    context_templates = {
        'en': "CONTEXT: The word '{WORD}' appears in this {LANG_NAME} sentence: '{SENTENCE}'. Pronounce '{WORD}' with proper {LANG_NAME} pronunciation as it would sound in this sentence context. Use {LANG_NAME} phonetics and accent.",
        'de': "KONTEXT: Das Wort '{WORD}' erscheint in diesem {LANG_NAME} Satz: '{SENTENCE}'. Sprechen Sie '{WORD}' mit korrekter {LANG_NAME} Aussprache aus, wie es in diesem Satzkontext klingen würde. Verwenden Sie {LANG_NAME} Phonetik und Akzent.",
        'fr': "CONTEXTE: Le mot '{WORD}' apparaît dans cette phrase {LANG_NAME}: '{SENTENCE}'. Prononcez '{WORD}' avec la prononciation {LANG_NAME} correcte comme il sonnerait dans ce contexte de phrase. Utilisez la phonétique et l'accent {LANG_NAME}.",
        'es': "CONTEXTO: La palabra '{WORD}' aparece en esta oración {LANG_NAME}: '{SENTENCE}'. Pronuncie '{WORD}' con la pronunciación {LANG_NAME} correcta como sonaría en este contexto de oración. Use fonética y acento {LANG_NAME}.",
        'it': "CONTESTO: La parola '{WORD}' appare in questa frase {LANG_NAME}: '{SENTENCE}'. Pronunciate '{WORD}' con la pronuncia {LANG_NAME} corretta come suonerebbe in questo contesto di frase. Usate fonetica e accento {LANG_NAME}.",
        'pt': "CONTEXTO: A palavra '{WORD}' aparece nesta frase {LANG_NAME}: '{SENTENCE}'. Pronuncie '{WORD}' com a pronúncia {LANG_NAME} correta como soaria neste contexto de frase. Use fonética e sotaque {LANG_NAME}.",
        'ru': "КОНТЕКСТ: Слово '{WORD}' появляется в этом {LANG_NAME} предложении: '{SENTENCE}'. Произносите '{WORD}' с правильным {LANG_NAME} произношением, как оно звучало бы в этом контексте предложения. Используйте {LANG_NAME} фонетику и акцент.",
        'tr': "BAĞLAM: '{WORD}' kelimesi bu {LANG_NAME} cümlede geçiyor: '{SENTENCE}'. '{WORD}' kelimesini bu cümle bağlamında nasıl ses çıkaracağı gibi doğru {LANG_NAME} telaffuzuyla söyleyin. {LANG_NAME} fonetik ve aksan kullanın.",
        'ka': "კონტექსტი: სიტყვა '{WORD}' ჩნდება ამ {LANG_NAME} წინადადებაში: '{SENTENCE}'. გამოითქვით '{WORD}' სწორი {LANG_NAME} გამოთქმით, როგორც ამ წინადადების კონტექსტში ჟღერდა. გამოიყენეთ {LANG_NAME} ფონეტიკა და აქცენტი."
    }
    
    # Get template for the language, fallback to English
    template = context_templates.get(lang_code, context_templates['en'])
    
    # Replace placeholders
    instruction = template.replace('{WORD}', word).replace('{LANG_NAME}', lang_name.upper()).replace('{SENTENCE}', sentence)
    
    return instruction

# Helper: Render language reference instructions for TTS.
def _render_langref_instructions(lang_code: str, context: str = 'word') -> str:
    """
    Returns a language reference TTS instruction for the given code.
    Precedence:
      1. Env template: OPENAI_TTS_INSTRUCTIONS_TEMPLATE or OPENAI_TTS_INSTRUCTIONS_TPL
      2. Fallback: "Speak strictly in {LANG_NAME} ({LANG_CODE}). Use native pronunciation and prosody. Do not switch languages."
    Customize via env: OPENAI_TTS_INSTRUCTIONS_TEMPLATE
    """
    tpl = (
        os.environ.get('OPENAI_TTS_INSTRUCTIONS_TEMPLATE')
        or os.environ.get('OPENAI_TTS_INSTRUCTIONS_TPL')
        or "Speak strictly in {LANG_NAME} ({LANG_CODE}). Use native pronunciation and prosody. Do not switch languages."
    )
    lc = (lang_code or 'en').strip().lower()
    base = lc.split('-')[0]
    lang_name = _lang_display_name(lang_code)
    
    # Add context-specific instructions for alphabet letters
    if context == 'alphabet':
        # Dynamic alphabet instructions that work for any language
        # Use environment variable for custom instructions, or generate dynamic ones
        custom_alphabet_instruction = os.environ.get(f'OPENAI_TTS_ALPHABET_INSTRUCTIONS_{base.upper()}')
        if custom_alphabet_instruction:
            context_instruction = custom_alphabet_instruction
        else:
            # Generate dynamic instruction based on language
            context_instruction = _generate_alphabet_instruction(lang_name, base)
        return f"{tpl.replace('{LANG_NAME}', lang_name).replace('{LANG_CODE}', base)} {context_instruction}"
    
    return tpl.replace("{LANG_NAME}", lang_name).replace("{LANG_CODE}", base)

# Helper: Pick per-language TTS instructions from environment.
# Precedence:
#   1. Per-language env: OPENAI_TTS_INSTRUCTIONS_<LANG>
#   2. Global env: OPENAI_TTS_INSTRUCTIONS
#   3. Language-reference template (see _render_langref_instructions)
def _pick_tts_instructions(lang_code: str, context: str = 'word') -> str:
    """
    Returns TTS instructions string for the given language code, using environment overrides.
    Precedence:
      1. Per-language env: OPENAI_TTS_INSTRUCTIONS_<LANG>
      2. Global env: OPENAI_TTS_INSTRUCTIONS
      3. Language-ref template (see _render_langref_instructions)
    Only applies to models that support 'instructions' (e.g., gpt-4o-mini-tts).
    """
    lc = (lang_code or 'en').strip().lower()
    base = lc.split('-')[0]
    keys = [lc.replace('-', '_').upper(), base.upper()]
    instr = os.environ.get('OPENAI_TTS_INSTRUCTIONS', '') or ''
    for k in keys:
        v = os.environ.get(f'OPENAI_TTS_INSTRUCTIONS_{k}')
        if v is not None:
            instr = v
            break
    if not instr:
        # Fallback to language-reference template with context
        instr = _render_langref_instructions(lang_code, context)
    return instr or ''

# Provider readiness: OpenAI only
def _openai_ready() -> bool:
    return bool(OPENAI_KEY)

# S3 readiness check
def _s3_ready() -> bool:
    """Check if S3 is configured and ready"""
    try:
        from .s3_storage import s3_storage
        return s3_storage.s3_client is not None
    except Exception as e:
        print(f"⚠️ S3 readiness check failed: {e}")
        return False

def _slug(s: str) -> str:
    return ''.join(c.lower() if c.isalnum() else '-' for c in s).strip('-') or 'word'

# Removed _audio_url_to_path - no local disk storage

@cached_tts(ttl=86400)  # Cache for 24 hours (audio files don't change)
def ensure_tts_for_word(word: str, language: str, instructions: str | None = None, context: str = 'word', sentence_context: str | None = None) -> str | None:
    """
    Generate TTS for a word, saving to disk and returning URL.
    Instructions precedence:
      1. Request override
      2. Per-language env: OPENAI_TTS_INSTRUCTIONS_<LANG>
      3. Global env: OPENAI_TTS_INSTRUCTIONS
      4. Language-ref template (see _render_langref_instructions)
    Always prefixes the language-ref instruction if not already present.
    
    Args:
        word: The word to generate audio for
        language: Target language code
        instructions: Custom TTS instructions
        context: Context type ('word', 'alphabet', 'sentence')
        sentence_context: Optional sentence containing the word for pronunciation context
    """
    if not _openai_ready():
        print(f"⚠️ OpenAI not ready - TTS unavailable for '{word}'")
        return None
    
    # S3 is REQUIRED - fail if not available
    if not _s3_ready():
        print(f"❌ S3 is not configured - TTS requires S3 storage. Cannot generate audio for '{word}'")
        return None
    
    lang = (language or 'en').lower()
    model, voice, has_lang_voice = _pick_tts_config(lang)
    import hashlib
    sig = hashlib.sha1(f"openai:{model}:{voice}".encode('utf-8')).hexdigest()[:6]
    fname = f"{_slug(word)}__{sig}.mp3"
    url_path = f'/media/tts/{lang}/{fname}'
    
    # First, check if audio_url already exists in database for this word
    try:
        conn = get_db_connection()
        result = execute_query(conn, 'SELECT audio_url FROM words WHERE word=? AND language=?', (word, lang))
        row = result.fetchone()
        if row:
            if isinstance(row, dict):
                existing_url = row.get('audio_url')
            elif isinstance(row, (list, tuple)) and len(row) > 0:
                existing_url = row[0]
            else:
                existing_url = None
            
            if existing_url and existing_url.strip():
                existing_url = existing_url.strip()
                conn.close()
                # If URL is already an S3 URL, return it directly
                if existing_url.startswith('https://') and 's3' in existing_url:
                    print(f"✅ Found existing S3 audio_url in DB for '{word}' ({lang}): {existing_url}")
                    return existing_url
                # If S3 is enabled and URL is local path, try to convert to S3 URL
                if _s3_ready() and existing_url.startswith('/media/tts/'):
                    parts = existing_url.strip('/').split('/')
                    if len(parts) == 4:
                        lang_part, fname = parts[2], parts[3]
                        # Check if file exists in S3
                        if tts_audio_exists(lang_part, fname, 'tts'):
                            s3_url = get_tts_audio_url(lang_part, fname, 'tts')
                            print(f"✅ Found existing audio_url in DB for '{word}' ({lang}), converted to S3 URL: {s3_url}")
                            # Update DB with S3 URL for future use
                            try:
                                conn = get_db_connection()
                                now = datetime.now(UTC).isoformat()
                                execute_query(conn, 'UPDATE words SET audio_url=?, updated_at=? WHERE word=? AND language=?',
                                             (s3_url, now, word, lang))
                                conn.commit()
                                conn.close()
                            except Exception as e:
                                print(f"⚠️ Warning: Could not update DB with S3 URL: {e}")
                                try:
                                    conn.close()
                                except:
                                    pass
                            return s3_url
                        else:
                            # File with exact name doesn't exist - try to find any file for this word
                            # The filename format is: {slug(word)}__{hash}.mp3
                            # Try to find files matching the word slug (hash might be different)
                            word_slug = _slug(word)
                            try:
                                from .s3_storage import s3_storage
                                s3_prefix = f"media/tts/{lang_part}/"
                                # List objects with this prefix
                                response = s3_storage.s3_client.list_objects_v2(
                                    Bucket=s3_storage.bucket_name,
                                    Prefix=s3_prefix
                                )
                                if 'Contents' in response:
                                    for obj in response['Contents']:
                                        obj_key = obj['Key']
                                        obj_fname = obj_key.split('/')[-1]
                                        # Check if filename starts with word slug
                                        if obj_fname.startswith(f"{word_slug}__") and obj_fname.endswith('.mp3'):
                                            # Found a matching file - use it
                                            s3_url = s3_storage.get_public_url(obj_key)
                                            print(f"✅ Found audio file in S3 for '{word}' ({lang}) with different hash: {obj_fname} -> {s3_url}")
                                            # Update DB with correct S3 URL
                                            try:
                                                conn = get_db_connection()
                                                now = datetime.now(UTC).isoformat()
                                                execute_query(conn, 'UPDATE words SET audio_url=?, updated_at=? WHERE word=? AND language=?',
                                                             (s3_url, now, word, lang))
                                                conn.commit()
                                                conn.close()
                                            except Exception as e:
                                                print(f"⚠️ Warning: Could not update DB with S3 URL: {e}")
                                                try:
                                                    conn.close()
                                                except:
                                                    pass
                                            return s3_url
                            except Exception as e:
                                print(f"⚠️ Warning: Could not search S3 for audio file: {e}")
                            
                            print(f"⚠️ Audio file '{fname}' not found in S3 for '{word}' ({lang}), will regenerate")
                            # File doesn't exist in S3, fall through to regenerate
                else:
                    # Not an S3 URL and not a local path - return as-is (might be external URL)
                print(f"✅ Found existing audio_url in DB for '{word}' ({lang}): {existing_url}")
                return existing_url
        conn.close()
    except Exception as e:
        print(f"⚠️ Warning: Could not check DB for existing audio_url: {e}")
        try:
            conn.close()
        except:
            pass
    
    # Check if file exists in S3
        if tts_audio_exists(lang, fname, 'tts'):
        # Return direct S3 URL for faster access (CDN)
        s3_url = get_tts_audio_url(lang, fname, 'tts')
        # Update DB with local URL path for compatibility (but return S3 URL)
            try:
                conn = get_db_connection()
                now = datetime.now(UTC).isoformat()
                execute_query(conn, 'UPDATE words SET audio_url=?, updated_at=? WHERE word=? AND language=?',
                             (url_path, now, word, lang))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ Warning: Could not update DB with URL: {e}")
                try:
                    conn.close()
                except:
                    pass
        print(f"✅ Found audio in S3 for '{word}' ({lang}), returning direct S3 URL")
        return s3_url

    # Determine instruction with correct precedence and always prefix with language reference.
    instr = _pick_tts_instructions(lang, context)
    if isinstance(instructions, str) and instructions.strip():
        instr = instructions.strip()
    # Always prefix with language reference
    langref = _render_langref_instructions(lang, context)
    if not instr:
        instr = langref
    else:
        instr = f"{langref} {instr}"
    
    # Add sentence context for better pronunciation if available
    if sentence_context and context == 'word':
        context_instruction = _generate_word_context_instruction(lang, word, sentence_context)
        instr = f"{instr} {context_instruction}"

    headers = {'Content-Type':'application/json','Authorization': f'Bearer {OPENAI_KEY}'}
    # OpenAI TTS API may not support all language codes
    # For unsupported languages like Georgian (ka), omit the language parameter
    # and rely on instructions to guide pronunciation
    supported_languages = {'en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'sv', 'ru', 'tr', 'pl', 'ar', 'hi', 'zh', 'ja', 'ko', 'th', 'vi', 'id', 'bn', 'ur', 'fa', 'he', 'uk', 'cs', 'sk', 'hu', 'ro', 'bg', 'hr', 'sr', 'sl', 'et', 'lv', 'lt', 'fi', 'no', 'da', 'is', 'sw', 'am', 'yo', 'zu', 'af'}
    payload = {'model': model, 'voice': voice, 'input': word, 'format': 'mp3'}
    if lang in supported_languages:
        payload['language'] = lang
    # Always include instructions for better pronunciation, especially for unsupported languages
    if _supports_instructions(model) and instr:
        payload['instructions'] = instr
        # For alphabet context, make instructions even more explicit
        if context == 'alphabet':
            payload['instructions'] = f"CRITICAL: You MUST speak in {lang.upper()} language only. {instr}"
            print(f"[TTS DEBUG] Alphabet audio for '{word}' in {lang}: {payload['instructions'][:200]}...")
    if lang not in supported_languages:
        print(f"[TTS] Language '{lang}' not in OpenAI's supported list - using instructions only for pronunciation guidance")
    if lang != 'en' and not has_lang_voice:
        try:
            print(f"[TTS] No per-language OpenAI voice for '{lang}'. Using OpenAI default '{voice}'. Accent may be wrong.")
        except Exception:
            pass
    try:
        audio = _http_binary(f'{OPENAI_BASE}/audio/speech', payload, headers)
        if not audio: 
            print(f"❌ OpenAI TTS API returned no audio for '{word}'")
            return None
        
        # Validate that we received valid MP3 data
        # MP3 files start with either ID3 tag (0x49 0x44 0x33) or MPEG frame sync (0xFF 0xFB or 0xFF 0xF3)
        if len(audio) < 3:
            print(f"❌ Audio data too short for '{word}' ({len(audio)} bytes)")
            return None
        
        # Check for MP3 header signatures
        is_id3 = audio[0:3] == b'ID3'
        is_mpeg = audio[0:2] == b'\xFF\xFB' or audio[0:2] == b'\xFF\xF3' or audio[0:2] == b'\xFF\xF2'
        
        if not (is_id3 or is_mpeg):
            print(f"⚠️ Warning: Audio data for '{word}' doesn't appear to be valid MP3 (first bytes: {audio[0:10].hex()})")
            # Still try to upload - might be valid but with different header
        else:
            print(f"✅ Validated MP3 data for '{word}' ({len(audio)} bytes)")
    except Exception as e:
        print(f"❌ OpenAI TTS API error for '{word}': {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None
    
    # Upload directly to S3 (S3 is required - no local disk)
    print(f"🔵 Uploading TTS audio for '{word}' directly to S3 (from memory)...")
    s3_url = upload_tts_audio_bytes(audio, lang, fname, 'tts')
        if s3_url:
            print(f"✅ S3 upload successful for '{word}': {s3_url}")
        # Update DB with local URL path for compatibility (but return S3 URL for faster access)
            url_path = f'/media/tts/{lang}/{fname}'
            try:
                conn = get_db_connection()
                now = datetime.now(UTC).isoformat()
                execute_query(conn, 'UPDATE words SET audio_url=?, updated_at=? WHERE word=? AND language=?',
                             (url_path, now, word, lang))
                conn.commit()
                conn.close()
            except Exception as e:
                print(f"⚠️ Warning: Could not update DB with URL: {e}")
                try:
                    conn.close()
                except:
                    pass
        return s3_url  # Return direct S3 URL for faster CDN access
        else:
        print(f"❌ S3 upload failed for '{word}' - S3 is required but upload failed.")
            return None

def ensure_tts_for_words_batch(words: List[str], language: str, max_workers: int = 3, sentence_contexts: Dict[str, str] = None) -> Dict[str, str]:
    """
    Generate TTS for multiple words in parallel for better performance.
    Returns a dictionary mapping words to their audio URLs.
    
    Args:
        words: List of words to generate audio for
        language: Target language code
        max_workers: Maximum number of parallel workers
        sentence_contexts: Optional dictionary mapping words to their sentence contexts for better pronunciation
    """
    if not _openai_ready():
        print(f"⚠️ OpenAI not ready - batch TTS unavailable")
        return {}
    
    results = {}
    
    def process_word(word: str) -> tuple[str, str | None]:
        """Process a single word and return (word, audio_url)"""
        try:
            # Check if we have a sentence context for this word
            sentence_context = None
            if sentence_contexts and word in sentence_contexts:
                sentence_context = sentence_contexts[word]
            
            # Use context-aware TTS if available
            if sentence_context:
                audio_url = ensure_tts_for_word(word, language, context='word', sentence_context=sentence_context)
            else:
                audio_url = ensure_tts_for_word(word, language)
            return word, audio_url
        except Exception as e:
            print(f"❌ Error processing word '{word}': {e}")
            return word, None
    
    # Use ThreadPoolExecutor for parallel processing
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all words for processing
        future_to_word = {executor.submit(process_word, word): word for word in words}
        
        # Collect results as they complete
        for future in concurrent.futures.as_completed(future_to_word):
            word, audio_url = future.result()
            if audio_url:
                results[word] = audio_url
    
    return results

from hashlib import sha1 as _sha1

@cached_tts(ttl=86400)  # Cache for 24 hours (audio files don't change)
def ensure_tts_for_sentence(text: str, language: str, instructions: str | None = None, context: str = 'sentence') -> str | None:
    """
    Create MP3 for a full sentence if missing. Return URL path or None.
    Instructions precedence:
      1. Request override
      2. Per-language env: OPENAI_TTS_INSTRUCTIONS_<LANG>
      3. Global env: OPENAI_TTS_INSTRUCTIONS
      4. Language-ref template (see _render_langref_instructions)
    Always prefixes the language-ref instruction if not already present.
    Files: media/tts_sentences/<lang>/<sha1>.mp3
    """
    if not _openai_ready():
        print(f"⚠️ OpenAI not ready - TTS unavailable for sentence")
        return None
    
    # S3 is REQUIRED - fail if not available
    if not _s3_ready():
        print(f"❌ S3 is not configured - TTS requires S3 storage. Cannot generate audio for sentence")
        return None
    
    lang = (language or 'en').lower()
    h = _sha1(f"{lang}:{text}".encode('utf-8')).hexdigest()
    fname = f"{h}.mp3"
    
    # Check if file exists in S3
        if tts_audio_exists(lang, fname, 'tts_sentences'):
            s3_url = get_tts_audio_url(lang, fname, 'tts_sentences')
        print(f"✅ Found sentence audio in S3, returning direct S3 URL")
            return s3_url
    model, voice, has_lang_voice = _pick_tts_config(lang)
    instr = _pick_tts_instructions(lang, context)
    if isinstance(instructions, str) and instructions.strip():
        instr = instructions.strip()
    # Always prefix with language reference
    langref = _render_langref_instructions(lang, context)
    if not instr:
        instr = langref
    else:
        instr = f"{langref} {instr}"
    headers = {'Content-Type':'application/json','Authorization': f'Bearer {OPENAI_KEY}'}
    # OpenAI TTS API may not support all language codes
    # For unsupported languages like Georgian (ka), omit the language parameter
    # and rely on instructions to guide pronunciation
    supported_languages = {'en', 'de', 'fr', 'es', 'it', 'pt', 'nl', 'sv', 'ru', 'tr', 'pl', 'ar', 'hi', 'zh', 'ja', 'ko', 'th', 'vi', 'id', 'bn', 'ur', 'fa', 'he', 'uk', 'cs', 'sk', 'hu', 'ro', 'bg', 'hr', 'sr', 'sl', 'et', 'lv', 'lt', 'fi', 'no', 'da', 'is', 'sw', 'am', 'yo', 'zu', 'af'}
    payload = {'model': model, 'voice': voice, 'input': text, 'format': 'mp3'}
    if lang in supported_languages:
        payload['language'] = lang
    # Always include instructions for better pronunciation, especially for unsupported languages
    if _supports_instructions(model) and instr:
        payload['instructions'] = instr
    if lang not in supported_languages:
        print(f"[TTS] Language '{lang}' not in OpenAI's supported list - using instructions only for pronunciation guidance")
    if lang != 'en' and not has_lang_voice:
        try:
            print(f"[TTS] No per-language OpenAI voice for '{lang}'. Using OpenAI default '{voice}'. Accent may be wrong.")
        except Exception:
            pass
    try:
        audio = _http_binary(f'{OPENAI_BASE}/audio/speech', payload, headers)
        if not audio:
            print(f"❌ OpenAI TTS API returned no audio for sentence")
            return None
        
        # Validate that we received valid MP3 data
        if len(audio) < 3:
            print(f"❌ Audio data too short for sentence ({len(audio)} bytes)")
            return None
        
        # Check for MP3 header signatures
        is_id3 = audio[0:3] == b'ID3'
        is_mpeg = audio[0:2] == b'\xFF\xFB' or audio[0:2] == b'\xFF\xF3' or audio[0:2] == b'\xFF\xF2'
        
        if not (is_id3 or is_mpeg):
            print(f"⚠️ Warning: Audio data for sentence doesn't appear to be valid MP3 (first bytes: {audio[0:10].hex()})")
        else:
            print(f"✅ Validated MP3 data for sentence ({len(audio)} bytes)")
    except Exception as e:
        print(f"❌ OpenAI TTS API error for sentence: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return None
    
    # Upload directly to S3 (S3 is required - no local disk)
    print(f"🔵 Uploading sentence TTS audio directly to S3 (from memory)...")
    s3_url = upload_tts_audio_bytes(audio, lang, fname, 'tts_sentences')
        if s3_url:
        print(f"✅ Sentence audio uploaded to S3, returning direct S3 URL")
        return s3_url
        else:
        print(f"❌ S3 upload failed for sentence - S3 is required but upload failed")
            return None

def ensure_tts_for_alphabet_letter(letter: str, language: str, instructions: str | None = None) -> str | None:
    """
    Generate TTS for an alphabet letter with phonetic pronunciation.
    This is a specialized version of ensure_tts_for_word that uses 'alphabet' context
    to ensure letters are pronounced as sounds, not letter names.
    """
    return ensure_tts_for_word(letter, language, instructions, context='alphabet')

def ensure_tts_for_word_with_context(word: str, language: str, sentence: str, instructions: str | None = None) -> str | None:
    """
    Generate TTS for a word with sentence context for better pronunciation.
    This provides the sentence context to help the AI understand how to pronounce the word.
    """
    return ensure_tts_for_word(word, language, instructions, context='word', sentence_context=sentence)

def batch_ensure_tts_for_sentences(sentences: List[str], language: str, instructions: str | None = None) -> Dict[str, str | None]:
    """
    Batch generate TTS for multiple sentences with async processing.
    Returns a dictionary mapping sentence -> audio_url (or None if failed).
    """
    if not _openai_ready() or not sentences:
        return {}
    
    results = {}
    lang = (language or 'en').lower()
    
    # S3 is REQUIRED - fail if not available
    if not _s3_ready():
        print(f"❌ S3 is not configured - batch TTS requires S3 storage")
        return {}
    
    # Check which sentences already have audio in S3
    existing_audio = {}
    for sentence in sentences:
        if sentence and sentence.strip():
            h = _sha1(f"{lang}:{sentence}".encode('utf-8')).hexdigest()
            fname = f"{h}.mp3"
            
            if tts_audio_exists(lang, fname, 'tts_sentences'):
                existing_audio[sentence] = get_tts_audio_url(lang, fname, 'tts_sentences')
            else:
                existing_audio[sentence] = None
    
    # Generate audio for sentences that don't have it
    sentences_to_generate = [s for s, url in existing_audio.items() if url is None and s and s.strip()]
    
    if sentences_to_generate:
        print(f"🎵 Batch generating audio for {len(sentences_to_generate)} sentences...")
        
        # Use concurrent processing for better performance
        import concurrent.futures
        import threading
        
        def generate_single_sentence(sentence):
            try:
                audio_url = ensure_tts_for_sentence(sentence, language, instructions)
                if audio_url:
                    print(f"✅ Generated sentence audio: {sentence[:50]}...")
                return sentence, audio_url
            except Exception as e:
                print(f"⚠️ Failed to generate sentence audio for '{sentence[:50]}...': {e}")
                return sentence, None
        
        # Use ThreadPoolExecutor for concurrent TTS generation
        max_workers = min(5, len(sentences_to_generate))  # Limit concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_sentence = {executor.submit(generate_single_sentence, sentence): sentence 
                                for sentence in sentences_to_generate}
            
            for future in concurrent.futures.as_completed(future_to_sentence):
                sentence, audio_url = future.result()
                existing_audio[sentence] = audio_url
    
    return existing_audio

def batch_ensure_tts_for_words(words: List[str], language: str, sentence_contexts: Dict[str, str] = None, instructions: str | None = None) -> Dict[str, str | None]:
    """
    Batch generate TTS for multiple words with concurrent processing.
    Returns a dictionary mapping word -> audio_url (or None if failed).
    """
    if not _openai_ready() or not words:
        return {}
    
    # S3 is REQUIRED - fail if not available
    if not _s3_ready():
        print(f"❌ S3 is not configured - batch TTS requires S3 storage")
        return {}
    
    results = {}
    lang = (language or 'en').lower()
    
    import hashlib
    model, voice, has_lang_voice = _pick_tts_config(lang)
    sig = hashlib.sha1(f"openai:{model}:{voice}".encode('utf-8')).hexdigest()[:6]
    
    # Check which words already have audio in S3
    existing_audio = {}
    for word in words:
        if word and word.strip():
            word = word.strip()
            fname = f"{_slug(word)}__{sig}.mp3"
            url_path = f'/media/tts/{lang}/{fname}'
            
            if tts_audio_exists(lang, fname, 'tts'):
                existing_audio[word] = get_tts_audio_url(lang, fname, 'tts')
            else:
                existing_audio[word] = None
    
    # Generate audio for words that don't have it
    words_to_generate = [w for w, url in existing_audio.items() if url is None and w and w.strip()]
    
    if words_to_generate:
        print(f"🎵 Batch generating audio for {len(words_to_generate)} words...")
        
        # Use concurrent processing for better performance
        import concurrent.futures
        
        def generate_single_word(word):
            try:
                # Find sentence context for this word
                sentence_context = None
                if sentence_contexts and word in sentence_contexts:
                    sentence_context = sentence_contexts[word]
                
                print(f"🎵 Generating audio for word: '{word}' (lang: {language})")
                audio_url = ensure_tts_for_word(
                    word, 
                    language, 
                    instructions,
                    context='word',
                    sentence_context=sentence_context
                )
                if audio_url:
                    print(f"✅ Generated word audio: '{word}' -> {audio_url}")
                else:
                    print(f"❌ Failed to generate audio for '{word}' - ensure_tts_for_word returned None")
                return word, audio_url
            except Exception as e:
                print(f"❌ Exception generating word audio for '{word}': {type(e).__name__}: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
                return word, None
        
        # Use ThreadPoolExecutor for concurrent TTS generation
        max_workers = min(5, len(words_to_generate))  # Limit concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_word = {executor.submit(generate_single_word, word): word 
                            for word in words_to_generate}
            
            for future in concurrent.futures.as_completed(future_to_word):
                word, audio_url = future.result()
                existing_audio[word] = audio_url
    
    return existing_audio