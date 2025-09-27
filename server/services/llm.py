import os, json, math, urllib.request
from typing import List, Dict
from .cache import cached_enrichment
OPENAI_KEY  = os.environ.get('OPENAI_API_KEY')
OPENAI_BASE = os.environ.get('OPENAI_BASE', 'https://api.openai.com/v1')

def _http_json(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception:
        return None

def _http_binary(url, payload, headers):
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except Exception:
        return None

def llm_generate_sentences(target_lang, native_lang, n=15, topic='daily life', cefr='A2-B1', level_title=''):
    """Generate exactly n sentences in the TARGET language.
    Enforces target language via prompt + post-check. One retry with stricter instruction if needed.
    Level title provides additional context for sentence generation.
    """
    if not OPENAI_KEY:
        return None

    # Normalize simple tags
    tl = (target_lang or 'en').split('-')[0].lower()
    nl = (native_lang or 'de').split('-')[0].lower()

    def _parse_array(text):
        import re, json as _json
        cleaned = re.sub(r"^```[a-zA-Z]*|```$", "", (text or '').strip())
        if '[' in cleaned and ']' in cleaned:
            cleaned = cleaned[cleaned.index('['): cleaned.rindex(']')+1]
        arr = _json.loads(cleaned)
        return [str(x).strip() for x in arr if str(x).strip()]

    def _looks_georgian(s):
        import re
        return bool(re.search('[\u10A0-\u10FF]', s or ''))

    # Minimal German stopword probe to detect leakage when nl == 'de'
    DE_SW = {"der","die","das","und","ist","ich","du","wir","ihr","sie","nicht","ein","eine","zu","mit","auf","von","für","dass","wie","im","in","den","dem"}

    def _fails_language_check(arr):
        if not arr:
            return True
        # Georgian: require Mkhedruli characters in most sentences
        if tl == 'ka':
            hits = sum(1 for s in arr if _looks_georgian(s))
            return hits < max(1, int(0.8 * len(arr)))
        # If native is German and target != German, flag if too many DE stopwords appear
        if nl == 'de' and tl != 'de':
            import re
            bad = 0
            for s in arr:
                toks = [t.lower() for t in re.findall(r"[A-Za-zÄÖÜäöüß]+", s)]
                if sum(1 for t in toks if t in DE_SW) >= 2:
                    bad += 1
            return bad >= max(1, int(0.5 * len(arr)))
        return False  # default: accept

    # First attempt
    sys_msg = {
        'role':'system',
        'content': (
            "You are a language learning assistant creating educational content. "
            "You MUST write ONLY in the target language '{tl}'. "
            "Do NOT use the native language '{nl}'. "
            "CEFR level: {cefr}. Return ONLY a JSON array of exactly {n} strings. No prose, no explanations, no code fences."
        ).format(tl=tl, nl=nl, cefr=cefr, n=n)
    }
    
    # Build user message with level title context
    level_context = f"Level: {level_title}. " if level_title.strip() else ""
    # Build CEFR-specific instructions
    cefr_instructions = ""
    if cefr.upper() == 'A0':
        cefr_instructions = " Use ONLY simple vocabulary and basic sentence structures. Avoid complex grammar, subclauses, or advanced vocabulary. Focus on essential words and phrases."
    elif cefr.upper() == 'A1':
        cefr_instructions = " Use simple vocabulary and basic sentence structures. Avoid complex grammar or advanced vocabulary."
    elif cefr.upper() in ['A2', 'B1', 'B2']:
        cefr_instructions = " Use appropriate vocabulary and sentence structures for intermediate learners."
    else:
        cefr_instructions = " Use vocabulary and sentence structures appropriate for the CEFR level."
    
    user_msg = {
        'role':'user',
        'content': (
            "Create exactly {n} short, natural sentences in the target language '{tl}' for language learning. "
            "{level_context}Topic: {topic}. "
            "These sentences should be educational and appropriate for language learners at CEFR level {cefr}. "
            "{cefr_instructions} "
            "Make each sentence different and varied - avoid repetition. "
            "Use diverse vocabulary and sentence structures. "
            "Do not include any words from '{nl}'. Output JSON array only."
        ).format(n=n, tl=tl, nl=nl, topic=topic, level_context=level_context, cefr=cefr, cefr_instructions=cefr_instructions)
    }
    payload = {'model': os.environ.get('OPENAI_CHAT_MODEL','gpt-4o-mini'), 'messages':[sys_msg,user_msg], 'temperature':0.7}
    headers = {'Content-Type':'application/json','Authorization': f'Bearer {OPENAI_KEY}'}
    data = _http_json(f'{OPENAI_BASE}/chat/completions', payload, headers)
    try:
        text = data['choices'][0]['message']['content']
    except Exception:
        return None

    arr = None
    try:
        arr = _parse_array(text)
    except Exception:
        arr = None

    # Retry once if language check fails
    if _fails_language_check(arr):
        sys_msg2 = {
            'role':'system',
            'content': (
                "Strict mode: You are a language learning assistant. Write ONLY in '{tl}'. Absolutely NO '{nl}'. "
                "If '{tl}' uses a non-Latin script, use that script. Return ONLY a JSON array with exactly {n} strings."
            ).format(tl=tl, nl=nl, n=n)
        }
        level_context_retry = f"Level: {level_title}. " if level_title.strip() else ""
        # Build CEFR-specific instructions for retry
        cefr_instructions_retry = ""
        if cefr.upper() == 'A0':
            cefr_instructions_retry = " Use ONLY simple vocabulary and basic sentence structures. Avoid complex grammar, subclauses, or advanced vocabulary. Focus on essential words and phrases."
        elif cefr.upper() == 'A1':
            cefr_instructions_retry = " Use simple vocabulary and basic sentence structures. Avoid complex grammar or advanced vocabulary."
        elif cefr.upper() in ['A2', 'B1', 'B2']:
            cefr_instructions_retry = " Use appropriate vocabulary and sentence structures for intermediate learners."
        else:
            cefr_instructions_retry = " Use vocabulary and sentence structures appropriate for the CEFR level."
        
        user_msg2 = {
            'role':'user',
            'content': (
                "Regenerate {n} educational sentences in '{tl}' for language learning. "
                "{level_context_retry}Topic: '{topic}'. CEFR level: {cefr}. "
                "{cefr_instructions_retry} "
                "Make each sentence different and varied - avoid repetition. "
                "Use diverse vocabulary and sentence structures. "
                "No other language words allowed. JSON array only."
            ).format(n=n, tl=tl, topic=topic, level_context_retry=level_context_retry, cefr=cefr, cefr_instructions_retry=cefr_instructions_retry)
        }
        payload2 = {'model': os.environ.get('OPENAI_CHAT_MODEL','gpt-4o-mini'), 'messages':[sys_msg2,user_msg2], 'temperature':0.6}
        data2 = _http_json(f'{OPENAI_BASE}/chat/completions', payload2, headers)
        try:
            text2 = data2['choices'][0]['message']['content']
            arr = _parse_array(text2)
        except Exception:
            pass

    # Final sanitation and length clamp
    if isinstance(arr, list) and arr:
        arr = [str(x).strip() for x in arr if str(x).strip()]
        if len(arr) > n:
            arr = arr[:n]
        return arr

    # Last-resort fallback: None (caller will fallback to hardcoded examples)
    return None

def llm_translate_batch(sentences, native_lang, source_lang=None):
    if not OPENAI_KEY or not sentences: return None
    
    # Detect source language if not provided
    if not source_lang:
        # Check if sentences contain Georgian script
        if any('\u10A0' <= char <= '\u10FF' for sentence in sentences for char in str(sentence)):
            source_lang = 'Georgian'
        else:
            source_lang = 'the source language'
    
    # Map language codes to proper names
    language_names = {
        'ka': 'Georgian',
        'de': 'German', 
        'en': 'English',
        'fr': 'French',
        'es': 'Spanish',
        'it': 'Italian',
        'pt': 'Portuguese',
        'ru': 'Russian',
        'tr': 'Turkish',
        'pl': 'Polish',
        'ar': 'Arabic',
        'hi': 'Hindi',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ko': 'Korean',
        'th': 'Thai',
        'vi': 'Vietnamese'
    }
    
    # Convert language codes to proper names
    if source_lang in language_names:
        source_lang = language_names[source_lang]
    if native_lang in language_names:
        native_lang = language_names[native_lang]
    
    sys_msg = {
        'role': 'system',
        'content': (
            "You are a professional translator. Translate the given sentences from {source_lang} to {native_lang}. "
            "Provide accurate, natural translations that preserve the meaning and context. "
            "Return ONLY a JSON array of translated strings in the same order as the input. "
            "Do not include any explanations or additional text."
        ).format(source_lang=source_lang, native_lang=native_lang)
    }
    
    user_msg = {
        'role': 'user',
        'content': f"Translate these {source_lang} sentences to {native_lang}: {json.dumps(sentences, ensure_ascii=False)}"
    }
    
    payload = {
        'model': os.environ.get('OPENAI_CHAT_MODEL','gpt-4o-mini'),
        'messages': [sys_msg, user_msg],
        'temperature': 0.1  # Lower temperature for more consistent translations
    }
    headers = {'Content-Type':'application/json','Authorization': f'Bearer {OPENAI_KEY}'}
    data = _http_json(f'{OPENAI_BASE}/chat/completions', payload, headers)
    try:
        text = data['choices'][0]['message']['content']
        import re
        cleaned = re.sub(r"^```[a-zA-Z]*|```$", "", text.strip())
        if '[' in cleaned and ']' in cleaned:
            cleaned = cleaned[cleaned.index('['): cleaned.rindex(']')+1]
        result = json.loads(cleaned)
        print(f"Translation result: {result}")
        return result
    except Exception as e:
        print(f"Translation error: {e}")
        return None

def llm_similarity(a, b):
    if not OPENAI_KEY: return -1.0
    model = os.environ.get('OPENAI_EMBED_MODEL','text-embedding-3-small')
    payload = {'model': model, 'input': [a or '', b or '']}
    headers = {'Content-Type':'application/json','Authorization': f'Bearer {OPENAI_KEY}'}
    data = _http_json(f'{OPENAI_BASE}/embeddings', payload, headers)
    try:
        v1 = data['data'][0]['embedding']; v2 = data['data'][1]['embedding']
        dot = sum(x*y for x,y in zip(v1,v2))
        n1 = sum(x*x for x in v1) ** 0.5
        n2 = sum(y*y for y in v2) ** 0.5
        return float(dot/(n1*n2)) if n1 and n2 else -1.0
    except Exception:
        return -1.0

# ---------------- Language + CEFR helpers ----------------

def cefr_norm(x: str) -> str:
    x = (x or '').upper().strip()
    if x in ('A0','A1','A2','B1','B2','C1','C2'):
        return x
    if x.startswith('A0'): return 'A0'
    if x.startswith('A1'): return 'A1'
    if x.startswith('A2'): return 'A2'
    if x.startswith('B1'): return 'B1'
    if x.startswith('B2'): return 'B2'
    if x.startswith('C1'): return 'C1'
    if x.startswith('C2'): return 'C2'
    return 'A1'

CEFR_PRESETS = {
    'A0': [
        'Hallo', 'Wie ist das Wetter?', 'Zahlen 1–10', 'Farben benennen', 'Ich heiße …', 'Woher kommst du?', 'Guten Morgen', 'Im Café: Wasser bestellen'
    ],
    'A1': [
        'Im Supermarkt einkaufen', 'Im Restaurant bestellen', 'Weg fragen', 'Tageszeiten und Uhrzeit', 'Familie vorstellen', 'Hobbys nennen', 'Ticket kaufen', 'Im Hotel einchecken'
    ],
    'A2': [
        'Stadtführung zu Fuß', 'Arzttermin vereinbaren', 'Wohnung beschreiben', 'In der Apotheke', 'Wochenende planen', 'Kleidung kaufen', 'Im Büro anrufen'
    ],
    'B1': [
        'Leben in der Stadt', 'Umzug organisieren', 'Jobinterview vorbereiten', 'Reklamation schreiben', 'Freizeit und Vereine', 'Nachhaltig einkaufen'
    ],
    'B2': [
        'Politik diskutieren', 'Klimawandel und Energie', 'Kulturvergleich', 'Wirtschaftsnachrichten', 'Technologie im Alltag'
    ],
    'C1': [
        'Gesundheitssysteme vergleichen', 'Urbanisierung bewerten', 'Arbeitsmarkttrends analysieren'
    ],
    'C2': [
        'Philosophische Debatte', 'Außenpolitik beurteilen', 'Literaturkritik'
    ]
}

def suggest_topic(target_lang: str, native_lang: str, cefr: str, base_topic: str = '', level: int = 1, previous_topics: list = None) -> str:
    cefr = cefr_norm(cefr or 'A1')
    allowed = CEFR_PRESETS.get(cefr, CEFR_PRESETS['A1'])
    
    # If base_topic is specific and not generic, use AI to generate topic variations
    if base_topic and base_topic.lower() not in ['level 1', 'level 2', 'level 3', 'level 4', 'level 5', 'daily life']:
        try:
            examples = ', '.join(allowed[:5])
            
            # Create CEFR-specific topic complexity guidance
            topic_cefr_guidance = {
                'A0': "Use extremely basic, single-concept topics. Examples: 'Hello', 'Yes', 'No', 'Me', 'You'",
                'A1': "Use very basic, concrete topics. Examples: 'Greetings', 'Numbers', 'Family', 'Food'",
                'A2': "Use simple, everyday topics. Examples: 'Shopping', 'Travel', 'Work', 'Hobbies'",
                'B1': "Use intermediate topics. Examples: 'Career planning', 'Cultural differences', 'Problem solving'",
                'B2': "Use more complex topics. Examples: 'Business negotiations', 'Social issues', 'Future planning'",
                'C1': "Use advanced topics. Examples: 'Philosophical discussions', 'Complex problem solving', 'Strategic thinking'",
                'C2': "Use sophisticated topics. Examples: 'Nuanced communication', 'Complex analysis', 'Abstract concepts'"
            }
            
            topic_complexity = topic_cefr_guidance.get(cefr, topic_cefr_guidance['A1'])
            
            # Build story progression context
            story_progression = ""
            if previous_topics and len(previous_topics) > 0:
                story_progression = f"STORY PROGRESSION: Previous chapters were: {', '.join(previous_topics[:level-1])}. "
                story_progression += f"This is chapter {level} of 10. Create a topic that naturally follows and builds upon the story so far. "
                story_progression += f"Think of this as a book where each chapter advances the plot chronologically. "
            else:
                story_progression = f"This is chapter {level} of 10. Create an opening topic that sets up the story. "
            
            sys_msg = {'role':'system','content': 'Return ONLY a short, specific topic title (max 5 words), no punctuation, no quotes. Create a coherent story progression topic that advances the narrative chronologically.'}
            user_msg = {'role':'user','content': (
                f"Suggest one concrete, specific topic for a language learning story chapter. "
                f"Target language: {target_lang}. Native language: {native_lang}. CEFR: {cefr}. Level: {level} of 10. "
                f"Main story context: {base_topic}. "
                f"{story_progression}"
                f"Create a specific chapter topic that fits into a coherent story progression. "
                f"This should feel like a natural next step in the narrative, building on previous levels. "
                f"Make it engaging and story-driven, not just a random topic. "
                f"IMPORTANT: Adjust topic complexity based on CEFR level {cefr}. {topic_complexity}. "
                f"Write the topic in the target language '{target_lang}' if possible, otherwise in English. "
                f"Keep comparable to: {examples}. Output only the title."
            )}
            payload_llm = {
                'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
                'messages': [sys_msg, user_msg],
                'temperature': 0.8  # Slightly lower for more coherent story progression
            }
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
            data = _http_json(f'{OPENAI_BASE}/chat/completions', payload_llm, headers)
            text = (data or {}).get('choices', [{}])[0].get('message', {}).get('content', '')
            topic = (text or '').strip().strip('"').strip("'").replace('\n',' ').strip()
            if topic and len(topic) > 48:
                topic = topic[:48].rsplit(' ',1)[0]
            return topic or f"{base_topic} - Level {level}"
        except Exception:
            return f"{base_topic} - Level {level}"
    
    # Level-specific topic mappings for the first 50 levels (only for generic courses)
    level_topic_mappings = {
        1: 'Stellen Sie sich vor',
        2: 'Begrüßungen', 
        3: 'Familie & Freunde',
        4: 'Zahlen & Zeit',
        5: 'Alltagswörter & Farben',
        6: 'Meine Arbeit',
        7: 'Meine Freunde',
        8: 'Meine Stadt',
        9: 'Meine Reisen',
        10: 'Meine Gesundheit',
        11: 'Meine Träume',
        12: 'Meine Zukunft',
        13: 'Meine Vergangenheit',
        14: 'Meine Lieblingsorte',
        15: 'Meine Lieblingsmusik',
        16: 'Meine Lieblingsfilme',
        17: 'Meine Lieblingsbücher',
        18: 'Meine Lieblingssportarten',
        19: 'Meine Lieblingsgerichte',
        20: 'Meine Lieblingsfarben',
        21: 'Meine Lieblingstiere',
        22: 'Meine Lieblingsjahreszeiten',
        23: 'Meine Lieblingsfeiertage',
        24: 'Meine Lieblingsaktivitäten',
        25: 'Meine Lieblingserinnerungen',
        26: 'Meine Lieblingsmomente',
        27: 'Meine Lieblingszitate',
        28: 'Meine Lieblingsweisheiten',
        29: 'Meine Lieblingsgeschichten',
        30: 'Meine Lieblingsabenteuer',
        31: 'Meine Lieblingserfahrungen',
        32: 'Meine Lieblingslernerfahrungen',
        33: 'Meine Lieblingssprachen',
        34: 'Meine Lieblingskulturen',
        35: 'Meine Lieblingsländer',
        36: 'Meine Lieblingsstädte',
        37: 'Meine Lieblingslandschaften',
        38: 'Meine Lieblingsnatur',
        39: 'Meine Lieblingswetter',
        40: 'Meine Lieblingszeiten',
        41: 'Meine Lieblingsgefühle',
        42: 'Meine Lieblingsgedanken',
        43: 'Meine Lieblingsideen',
        44: 'Meine Lieblingsprojekte',
        45: 'Meine Lieblingsziele',
        46: 'Meine Lieblingswünsche',
        47: 'Meine Lieblingshoffnungen',
        48: 'Meine Lieblingsträume',
        49: 'Meine Lieblingsvisionen',
        50: 'Meine Lieblingsperspektiven'
    }
    
    
    # If base_topic is generic like "Level X", use level-specific mapping
    if base_topic and base_topic.lower().startswith('level ') and base_topic.lower() not in ['daily life']:
        try:
            level_num = int(base_topic.split()[-1])
            if 1 <= level_num <= 50:
                mapped_topic = level_topic_mappings.get(level_num, base_topic)
                
                # For Level 1-5, use direct translations
                if mapped_topic in ['Stellen Sie sich vor', 'Begrüßungen', 'Familie & Freunde', 'Zahlen & Zeit', 'Alltagswörter & Farben']:
                    topic_translations = {
                        'Stellen Sie sich vor': {
                            'ka': 'თავისი წარდგენა',
                            'en': 'Introduce yourself',
                            'fr': 'Présentez-vous',
                            'es': 'Preséntate',
                            'it': 'Presentati'
                        },
                        'Begrüßungen': {
                            'ka': 'მოგესალმებით',
                            'en': 'Greetings',
                            'fr': 'Salutations',
                            'es': 'Saludos',
                            'it': 'Saluti'
                        },
                        'Familie & Freunde': {
                            'ka': 'ოჯახი და მეგობრები',
                            'en': 'Family & Friends',
                            'fr': 'Famille et amis',
                            'es': 'Familia y amigos',
                            'it': 'Famiglia e amici'
                        },
                        'Zahlen & Zeit': {
                            'ka': 'რიცხვები და დრო',
                            'en': 'Numbers & Time',
                            'fr': 'Nombres et temps',
                            'es': 'Números y tiempo',
                            'it': 'Numeri e tempo'
                        },
                        'Alltagswörter & Farben': {
                            'ka': 'ყოველდღიური სიტყვები და ფერები',
                            'en': 'Daily Words & Colors',
                            'fr': 'Mots quotidiens et couleurs',
                            'es': 'Palabras diarias y colores',
                            'it': 'Parole quotidiane e colori'
                        }
                    }
                    translated = topic_translations.get(mapped_topic, {}).get(target_lang, mapped_topic)
                    return translated
                
                # For Level 6-50, use AI translation
                elif target_lang != 'de' and OPENAI_KEY:
                    try:
                        sys_msg = {'role':'system','content': 'Return ONLY a short, specific topic title (max 5 words), no punctuation, no quotes. Make it concrete and engaging for language learners.'}
                        user_msg = {'role':'user','content': (
                            f"Translate this German topic to {target_lang}: '{mapped_topic}'. "
                            f"Make it appropriate for language learning. "
                            f"Output only the translated topic title."
                        )}
                        payload_llm = {
                            'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
                            'messages': [sys_msg, user_msg],
                            'temperature': 0.3
                        }
                        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
                        data = _http_json(f'{OPENAI_BASE}/chat/completions', payload_llm, headers)
                        text = (data or {}).get('choices', [{}])[0].get('message', {}).get('content', '')
                        translated = (text or '').strip().strip('"').strip("'").replace('\n',' ').strip()
                        if translated and len(translated) > 48:
                            translated = translated[:48].rsplit(' ',1)[0]
                        return translated or mapped_topic
                    except Exception:
                        return mapped_topic
                else:
                    return mapped_topic
            return base_topic
        except (ValueError, IndexError):
            return base_topic
    
    if not OPENAI_KEY:
        import random as _r
        return (_r.choice(allowed) if allowed else 'Alltag')
    
    try:
        examples = ', '.join(allowed[:5])
        sys_msg = {'role':'system','content': 'Return ONLY a short, specific topic title (max 5 words), no punctuation, no quotes. Make it concrete and engaging for language learners.'}
        user_msg = {'role':'user','content': (
            f"Suggest one concrete, specific topic for a language learning level. "
            f"Target language: {target_lang}. Native language: {native_lang}. CEFR: {cefr}. Level: {level}. "
            f"Base theme: {base_topic}. Make it different from generic 'Level X' topics. "
            f"Write the topic in the target language '{target_lang}' if possible, otherwise in English. "
            f"Keep comparable to: {examples}. Output only the title."
        )}
        payload_llm = {
            'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
            'messages': [sys_msg, user_msg],
            'temperature': 0.9
        }
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
        data = _http_json(f'{OPENAI_BASE}/chat/completions', payload_llm, headers)
        text = (data or {}).get('choices', [{}])[0].get('message', {}).get('content', '')
        topic = (text or '').strip().strip('"').strip("'").replace('\n',' ').strip()
        if topic and len(topic) > 48:
            topic = topic[:48].rsplit(' ',1)[0]
        return topic or (allowed[0] if allowed else 'Alltag')
    except Exception:
        return (allowed[0] if allowed else 'Alltag')

def suggest_level_title(target_lang: str, native_lang: str, topic: str, level: int, cefr: str = 'A1', context_description: str = '', all_topics: list = None, previous_titles: list = None) -> str:
    """Generate a coherent, story-based level title that fits into a narrative progression."""
    if not OPENAI_KEY:
        # Fallback: create title from topic
        return f"{topic}" if topic and topic.lower() not in ['level 1', 'level 2', 'level 3', 'level 4', 'level 5'] else f"Level {level}"
    
    try:
        # Create context about the story progression
        story_context = ""
        if all_topics and len(all_topics) > 1:
            story_context = f" This is part of a story progression. Previous topics: {', '.join(all_topics[:level-1])}. "
        
        # Add previous titles context for better uniqueness
        if previous_titles and len(previous_titles) > 0:
            story_context += f" Previous chapter titles were: {', '.join(previous_titles[:level-1])}. "
            story_context += f"CRITICAL: Create a UNIQUE title that is completely different from all previous titles. "
        
        # Create CEFR-specific complexity guidance
        cefr_guidance = {
            'A0': "Use extremely simple, single-word or two-word titles. Examples: 'Hallo', 'Ich bin', 'Du bist', 'Ja bitte', 'Nein danke', 'Mein Name', 'Dein Name', 'Guten Tag', 'Auf Wiedersehen', 'Danke schön'",
            'A1': "Use very simple, basic vocabulary. Examples: 'Der erste Tag', 'Mein Name', 'Hallo Freunde', 'Meine Familie', 'Das Haus', 'Die Schule'",
            'A2': "Use simple, everyday vocabulary. Examples: 'Ein neuer Freund', 'Das Restaurant', 'Die Reise', 'Der Einkauf', 'Das Wetter'",
            'B1': "Use intermediate vocabulary. Examples: 'Die große Entscheidung', 'Ein wichtiges Gespräch', 'Das Abenteuer', 'Die Herausforderung'",
            'B2': "Use more complex vocabulary. Examples: 'Die Verhandlung', 'Die Transformation', 'Die Komplexität', 'Die Strategie'",
            'C1': "Use advanced vocabulary. Examples: 'Die Komplexität der Situation', 'Die strategische Planung', 'Die philosophische Betrachtung'",
            'C2': "Use sophisticated, nuanced vocabulary. Examples: 'Die Nuancen der Kommunikation', 'Die subtilen Unterschiede', 'Die tiefgreifende Analyse'"
        }
        
        complexity_guidance = cefr_guidance.get(cefr, cefr_guidance['A1'])
        
        sys_msg = {'role':'system','content': 'Return ONLY a short, engaging level title (max 6 words), no punctuation, no quotes. Create a coherent story chapter title that fits into a narrative progression.'}
        user_msg = {'role':'user','content': (
            f"Create a coherent level title for a language learning story. "
            f"Target language: {target_lang}. Native language: {native_lang}. "
            f"Main story context: {context_description}. "
            f"Current chapter topic: {topic}. Level: {level} of 10. CEFR: {cefr}. "
            f"{story_context}"
            f"Create a title that sounds like a chapter in a book - engaging, specific, and part of a larger story. "
            f"Make it feel like a natural progression in the narrative. Think chronologically - what happens next in the story? "
            f"Write the title in the native language '{native_lang}' so the learner can understand it. "
            f"IMPORTANT: Adjust complexity based on CEFR level {cefr}. {complexity_guidance}. "
            f"CRITICAL: Each level must have a UNIQUE, DISTINCT title. Avoid repetition. Be creative and varied. "
            f"STORY FOCUS: This should feel like reading a book where each chapter advances the plot naturally. "
            f"Output only the title."
        )}
        # Adjust temperature based on CEFR level for more appropriate complexity
        temperature_map = {
            'A0': 0.7,  # Increased from 0.3 to 0.7 for more variety while keeping simplicity
            'A1': 0.7,  # Increased from 0.5 to 0.7 for better creativity
            'A2': 0.7,  # Increased from 0.6 to 0.7 for consistency
            'B1': 0.8,  # Balanced consistency and creativity
            'B2': 0.8,  # More creative, varied results
            'C1': 0.8,  # More creative, varied results
            'C2': 0.9   # Most creative, sophisticated results
        }
        
        temperature = temperature_map.get(cefr, 0.7)
        
        payload_llm = {
            'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
            'messages': [sys_msg, user_msg],
            'temperature': temperature
        }
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
        data = _http_json(f'{OPENAI_BASE}/chat/completions', payload_llm, headers)
        text = (data or {}).get('choices', [{}])[0].get('message', {}).get('content', '')
        title = (text or '').strip().strip('"').strip("'").replace('\n',' ').strip()
        if title and len(title) > 60:
            title = title[:60].rsplit(' ',1)[0]
        return title or f"{topic}" if topic and topic.lower() not in ['level 1', 'level 2', 'level 3', 'level 4', 'level 5'] else f"Level {level}"
    except Exception:
        return f"{topic}" if topic and topic.lower() not in ['level 1', 'level 2', 'level 3', 'level 4', 'level 5'] else f"Level {level}"

# ---------------- Tokenization ----------------

def tokenize_words(text: str):
    import re
    # Unicode-safe: match sequences of letters (excluding digits/underscore), allow apostrophe inside word
    # For Japanese, Chinese, Korean: match any non-whitespace, non-punctuation characters
    if re.search(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF\uAC00-\uD7AF]', text):
        # CJK languages: split on whitespace and punctuation, keep meaningful characters
        # For Japanese specifically, try to split on particles and common separators
        if re.search(r'[\u3040-\u309F\u30A0-\u30FF]', text):  # Japanese
            # Split on common Japanese particles and punctuation
            text = re.sub(r'([はがをにでとからまで])', r' \1 ', text)
            text = re.sub(r'([。、！？])', r' \1 ', text)
            tokens = [t.strip() for t in text.split() if t.strip() and not re.match(r'^[。、！？]+$', t)]
        else:
            # Chinese/Korean: split on whitespace and punctuation
            tokens = re.findall(r'[^\s\W\d_]+', text, flags=re.UNICODE)
    elif re.search(r'[\u0900-\u097F]', text):  # Hindi/Devanagari
        # Hindi: split on whitespace and punctuation, keep meaningful characters
        # Remove diacritics and split on spaces
        text = re.sub(r'[।॥]', ' ', text)  # Remove Hindi punctuation
        tokens = [t.strip() for t in text.split() if t.strip()]
    else:
        # Latin-based languages: use original regex
        tokens = re.findall(r"[^\W\d_]+(?:'[^\W\d_]+)?", text, flags=re.UNICODE)
    return tokens

# ---------------- Word enrichment ----------------

ALLOWED_POS = {"NOUN","VERB","ADJ","ADV","PRON","DET","PREP","CONJ","NUM","PART","INTJ"}
ALLOWED_GENDERS = {'masc','fem','neut','common','none'}

def _norm_gender(g: str, language: str = '') -> str:
    g = (g or '').strip().lower()
    if g in ALLOWED_GENDERS:
        return g
    m = {
        'm':'masc','masculine':'masc','male':'masc',
        'f':'fem','feminine':'fem','female':'fem',
        'n':'neut','neuter':'neut',
        'u':'common','utrum':'common','commune':'common',
        'none':'none','-':'none','na':'none','n/a':'none','null':'none'
    }
    return m.get(g, 'none')

def _force_pos_via_llm(word, target_lang, native_lang):
    if not OPENAI_KEY:
        return ''
    try:
        sys2 = {'role':'system','content': 'Return ONLY one token, no quotes, exactly one of: NOUN, VERB, ADJ, ADV, PRON, DET, PREP, CONJ, NUM, PART, INTJ.'}
        usr2 = {'role':'user','content': json.dumps({'task':'pos_classify','word':word,'target_lang':target_lang,'native_lang':native_lang}, ensure_ascii=False)}
        payload2 = {'model': os.environ.get('OPENAI_CHAT_MODEL','gpt-4o-mini'), 'messages':[sys2,usr2], 'temperature':0}
        headers = {'Content-Type':'application/json','Authorization': f'Bearer {OPENAI_KEY}'}
        data2 = _http_json(f'{OPENAI_BASE}/chat/completions', payload2, headers)
        out = ((data2 or {}).get('choices',[{}])[0].get('message',{}) or {}).get('content','').strip().upper()
        if out in ALLOWED_POS:
            return out
    except Exception:
        pass
    return ''

def _extract_word_translation_from_context(word: str, sentence_context: str, sentence_native: str, target_lang: str, native_lang: str) -> str:
    """Extract word translation from sentence context using AI."""
    if not sentence_context or not sentence_native or not OPENAI_KEY:
        return ''
    
    try:
        sys_msg = {
            'role': 'system',
            'content': (
                'You are a language learning assistant. Extract the translation of a specific word from a sentence pair. '
                'Return ONLY the translated word/phrase, nothing else. '
                'Be precise and match the exact meaning in context.'
            )
        }
        
        user_msg = {
            'role': 'user',
            'content': (
                f'Extract the translation of the word "{word}" from this sentence pair:\n'
                f'Target language ({target_lang}): {sentence_context}\n'
                f'Native language ({native_lang}): {sentence_native}\n\n'
                f'Return only the translated word/phrase for "{word}".'
            )
        }
        
        payload = {
            'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
            'messages': [sys_msg, user_msg],
            'temperature': 0.1
        }
        
        headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
        data = _http_json(f'{OPENAI_BASE}/chat/completions', payload, headers)
        
        if data and 'choices' in data:
            text = data['choices'][0]['message']['content']
            translation = (text or '').strip().strip('"').strip("'")
            return translation
            
    except Exception as e:
        print(f"Error extracting word translation from context: {e}")
    
    return ''

@cached_enrichment(ttl=3600)  # Cache for 1 hour
def llm_enrich_word(word: str, language: str, native_language: str, sentence_context: str = '', sentence_native: str = '') -> dict:
    """Return normalized enrichment dict 'upd' for a word.
    Does LLM call if available, enforces schema, normalizes fields.
    """
    llm_available = bool(OPENAI_KEY)
    schema_hint = {
        'lemma':'string','pos':'string','translation':['string'],'example':'string','example_native':'string','ipa':'string','gender':'string','plural':'string',
        'conj':{'pres_3sg':'string','past':'string','part2':'string'},
        'comp':{'pos':'string','comp':'string','sup':'string'},
        'synonyms':['string'],'collocations':['string'],'cefr':'string','freq_rank':'integer'
    }
    # Build system message with context awareness
    context_instructions = ""
    if sentence_context:
        context_instructions = (
            '\nIMPORTANT: If "sentence_context" is provided, use it as the "example" field. '
            'If "sentence_native" is also provided, use it as the "example_native" field. '
            'This ensures the word examples come from the actual learning context where the word appears.'
        )
    
    sys_msg = {
        'role': 'system',
        'content': (
            'Return ONLY a single JSON object for lexical data. '
            'You MUST respect the per-field language mapping provided under "field_language". '
            'For each field, output text strictly in the specified language. '
            'Fields with language "target" must be written in the target language (target_lang). '
            'Fields with language "native" must be written in the native language (native_lang). '
            'For "ipa": provide the International Phonetic Alphabet transcription for the TARGET language word, using standard IPA symbols (e.g., ɡ, ʃ, ɛː). No language words, only the phonetic transcription. '
            'Use empty strings or empty arrays for unknown values. No prose. No extra fields.'
            '\nFor "pos": you MUST choose exactly one tag from this closed set and return it verbatim: ["NOUN","VERB","ADJ","ADV","PRON","DET","PREP","CONJ","NUM","PART","INTJ"]. If uncertain, pick the most probable. Never invent other labels.'
            'For "gender": choose ONLY from {"masc","fem","neut","common","none"} for the TARGET language. Never infer from native language.'
            + context_instructions
        )
    }
    # Prepare context information
    context_info = {}
    if sentence_context and sentence_native:
        context_info = {
            'sentence_context': sentence_context,
            'sentence_native': sentence_native,
            'use_context_examples': True
        }
    elif sentence_context:
        context_info = {
            'sentence_context': sentence_context,
            'use_context_examples': True
        }
    
    user_msg = {
        'role': 'user',
        'content': json.dumps({
            'task': 'enrich_word',
            'word': word,
            'target_lang': language,
            'native_lang': native_language,
            'schema': schema_hint,
            'field_language': {
                'translation': 'native',
                'example': 'target',
                'example_native': 'native',
                'lemma': 'target',
                'pos': 'target',
                'ipa': 'target',
                'gender': 'target',
                'plural': 'target',
                'conj': 'target',
                'comp': 'target',
                'synonyms': 'target',
                'collocations': 'target',
                'cefr': 'target',
                'freq_rank': 'number'
            },
            'constraints': {
                'translation_lang': native_language,
                'example_lang': language,
                'example_native_lang': native_language
            },
            **context_info
        }, ensure_ascii=False)
    }
    obj = {}
    if llm_available:
        try:
            payload_llm = {
                'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
                'messages': [sys_msg, user_msg],
                'temperature': 0.2
            }
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
            data = _http_json(f'{OPENAI_BASE}/chat/completions', payload_llm, headers)
            text = (data or {}).get('choices', [{}])[0].get('message', {}).get('content', '')
            import re
            cleaned = re.sub(r"^```[a-zA-Z]*|```$", "", (text or '').strip())
            if '{' in cleaned and '}' in cleaned:
                start = cleaned.find('{')
                end = cleaned.rfind('}')
                obj = json.loads(cleaned[start:end+1])
        except Exception:
            obj = {}
    if not obj:
        # Extract translation from context if available
        context_translation = ''
        if sentence_context and sentence_native:
            context_translation = _extract_word_translation_from_context(word, sentence_context, sentence_native, language, native_language)
        
        obj = {
            'lemma': word,
            'pos': '',
            'translation': [context_translation] if context_translation else [],
            'example': sentence_context if sentence_context else '',
            'example_native': sentence_native if sentence_native else '',
            'ipa': word,
            'gender': '',
            'plural': '',
            'conj': {},
            'comp': {},
            'synonyms': [],
            'collocations': [],
            'cefr': '',
            'freq_rank': None
        }

    raw_pos = str(obj.get('pos') or '').strip().upper()
    if raw_pos not in ALLOWED_POS:
        raw_pos = _force_pos_via_llm(word, language, native_language)
    obj['pos'] = raw_pos or ''

    def norm_s(s):
        return (s or '').strip()
    def norm_arr(a):
        if isinstance(a, list):
            return [str(x).strip() for x in a if str(x).strip()][:3]
        return []
    conj = obj.get('conj') if isinstance(obj.get('conj'), dict) else {}
    comp = obj.get('comp') if isinstance(obj.get('comp'), dict) else {}

    # Use context examples if available, otherwise use AI-generated examples
    example = sentence_context if sentence_context else norm_s(obj.get('example'))
    example_native = sentence_native if sentence_native else norm_s(obj.get('example_native'))
    
    # Extract translation from context if available
    context_translation = ''
    if sentence_context and sentence_native:
        context_translation = _extract_word_translation_from_context(word, sentence_context, sentence_native, language, native_language)
    
    # Use context translation if available, otherwise use AI-generated translation
    translation = context_translation if context_translation else ', '.join(norm_arr(obj.get('translation'))[:2])
    
    upd = {
        'lemma': norm_s(obj.get('lemma')),
        'pos': norm_s(obj.get('pos')).upper(),
        'translation': translation,
        'example': example,
        'example_native': example_native,
        'ipa': norm_s(obj.get('ipa')),
        'gender': _norm_gender(obj.get('gender'), language),
        'plural': norm_s(obj.get('plural')),
        'conj': conj,
        'comp': comp,
        'synonyms': norm_arr(obj.get('synonyms')),
        'collocations': norm_arr(obj.get('collocations')),
        'cefr': norm_s(obj.get('cefr')).upper(),
        'freq_rank': int(obj.get('freq_rank')) if str(obj.get('freq_rank') or '').isdigit() else None
    }
    return upd
# ---------------- Similarity with fallback ----------------

def similarity_score(a: str, b: str) -> float:
    """LLM cosine similarity if available; fallback to difflib ratio.
    Returns 0.0..1.0 with improved scoring for better user experience.
    """
    sa = (a or '').strip(); sb = (b or '').strip()
    if not sa and not sb:
        return 1.0
    if not sa or not sb:
        return 0.0
    
    # First try LLM similarity
    llm_score = None
    try:
        s = llm_similarity(sa, sb)
        if isinstance(s, (int, float)) and s >= 0:
            llm_score = float(max(0.0, min(1.0, s)))
    except Exception:
        pass
    
    # Fallback to difflib
    difflib_score = 0.0
    try:
        from difflib import SequenceMatcher
        difflib_score = float(SequenceMatcher(None, sa.lower(), sb.lower()).ratio())
    except Exception:
        pass
    
    # Use the higher of the two scores, but apply a more generous scoring curve
    base_score = max(llm_score or 0.0, difflib_score)
    
    # Apply a more generous scoring curve for better user experience
    # This maps the raw similarity to a more forgiving scale
    if base_score >= 0.8:
        return 1.0  # Very similar = perfect score
    elif base_score >= 0.6:
        return 0.9  # Similar = excellent score
    elif base_score >= 0.4:
        return 0.8  # Somewhat similar = good score
    elif base_score >= 0.2:
        return 0.6  # Somewhat different = acceptable score
    else:
        return base_score  # Very different = raw score

def llm_enrich_words_batch(words: List[str], language: str, native_language: str, sentence_contexts: Dict[str, str] = None) -> Dict[str, dict]:
    """
    Batch enrich multiple words with translations, POS, IPA, and other metadata using concurrent processing.
    Returns a dictionary mapping word -> enrichment_data (or empty dict if failed).
    """
    if not OPENAI_KEY or not words:
        return {}
    
    # Filter out words that already have full enrichment
    words_to_enrich = []
    existing_words = {}
    
    for word in words:
        if not word or not word.strip():
            continue
            
        word = word.strip()
        
        # Check if word already exists in Multi-User-DB with full enrichment
        try:
            from server.multi_user_db import db_manager
            word_hash = db_manager.generate_word_hash(word, language, native_language)
            existing_data = db_manager.get_global_word_data(native_language, [word_hash])
            
            if existing_data and existing_data.get(word_hash, {}).get('translation') and existing_data.get(word_hash, {}).get('pos'):
                # Word already has full enrichment in Multi-User-DB, skip
                existing_word_data = existing_data[word_hash]
                existing_word_data['word_hash'] = word_hash
                existing_words[word] = existing_word_data
                continue
        except Exception:
            pass
        
        # Fallback: Check old database
        try:
            from server.db import get_word_row
            existing_word = get_word_row(word, language)
            if existing_word and existing_word.get('translation') and existing_word.get('pos'):
                # Word exists in old DB, but we should still migrate it to Multi-User-DB
                # We'll process it to ensure it's in both systems
                pass
        except Exception:
            pass
        
        words_to_enrich.append(word)
    
    if not words_to_enrich:
        print(f"⏭️ All {len(words)} words already enriched, skipping batch enrichment")
        return existing_words
    
    print(f"📚 Batch enriching {len(words_to_enrich)} words with metadata...")
    
    # Prepare batch request
    enriched_results = {}
    
    # Process words in smaller batches to avoid token limits
    batch_size = 10  # Adjust based on API limits
    for i in range(0, len(words_to_enrich), batch_size):
        batch_words = words_to_enrich[i:i + batch_size]
        
        try:
            # Create batch prompt for multiple words
            word_list = ', '.join([f'"{word}"' for word in batch_words])
            
            # Get sentence contexts for this batch
            batch_contexts = []
            for word in batch_words:
                context = sentence_contexts.get(word, '') if sentence_contexts else ''
                batch_contexts.append(context)
            
            context_list = ' | '.join([f'"{ctx}"' for ctx in batch_contexts if ctx])
            
            system_msg = {
                'role': 'system',
                'content': (
                    'Return ONLY a JSON object with lexical data for multiple words. '
                    'You MUST respect the per-field language mapping provided under "field_language". '
                    'For each field, output text strictly in the specified language. '
                    'Fields with language "target" must be written in the target language (target_lang). '
                    'Fields with language "native" must be written in the native language (native_lang). '
                    'For "ipa": provide the International Phonetic Alphabet transcription for the TARGET language word, using standard IPA symbols (e.g., ɡ, ʃ, ɛː). No language words, only the phonetic transcription. '
                    'Use empty strings or empty arrays for unknown values. No prose. No extra fields.'
                    '\nFor "pos": you MUST choose exactly one tag from this closed set and return it verbatim: ["NOUN","VERB","ADJ","ADV","PRON","DET","PREP","CONJ","NUM","PART","INTJ"]. If uncertain, pick the most probable. Never invent other labels.'
                    'For "gender": choose ONLY from {"masc","fem","neut","common","none"} for the TARGET language. Never infer from native language.'
                    '\nReturn a JSON object where each key is a word and the value is its enrichment data.'
                )
            }
            
            user_msg = {
                'role': 'user',
                'content': f'''Provide lexical data for these {len(batch_words)} words in {language} (target) and {native_language} (native):

Words: {word_list}
Contexts: {context_list if context_list else 'No specific contexts provided'}

Return JSON format:
{{
  "word1": {{
    "translation": "native translation",
    "pos": "POS_TAG",
    "ipa": "phonetic transcription",
    "example": "example sentence in target language",
    "example_native": "example sentence in native language",
    "synonyms": ["synonym1", "synonym2"],
    "collocations": ["collocation1", "collocation2"],
    "gender": "gender_tag"
  }},
  "word2": {{ ... }}
}}'''
            }
            
            payload = {
                'model': os.environ.get('OPENAI_CHAT_MODEL', 'gpt-4o-mini'),
                'messages': [system_msg, user_msg],
                'temperature': 0.1,
                'max_tokens': 4000
            }
            headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {OPENAI_KEY}'}
            data = _http_json(f'{OPENAI_BASE}/chat/completions', payload, headers)
            
            if data and 'choices' in data and data['choices'][0]['message']['content']:
                try:
                    batch_data = json.loads(data['choices'][0]['message']['content'])
                    
                    for word in batch_words:
                        if word in batch_data:
                            enriched_results[word] = batch_data[word]
                            print(f"✅ Batch enriched word: {word} -> {batch_data[word].get('translation', '')}")
                        else:
                            enriched_results[word] = {}
                            print(f"⚠️ No enrichment data for word: {word}")
                            
                except json.JSONDecodeError as e:
                    print(f"Error parsing batch enrichment JSON: {e}")
                    # Fallback to individual enrichment
                    for word in batch_words:
                        enriched_results[word] = {}
            else:
                print("No response from batch enrichment API")
                for word in batch_words:
                    enriched_results[word] = {}
                    
        except Exception as e:
            print(f"Error in batch enrichment for words {batch_words}: {e}")
            # Fallback to individual enrichment
            for word in batch_words:
                enriched_results[word] = {}
    
    # Store enriched words in both Multi-User-DB and old DB
    enriched_count = 0
    word_hashes = {}
    
    for word, enrichment_data in enriched_results.items():
        if enrichment_data:
            try:
                # Store in Multi-User-DB first (primary storage)
                from server.multi_user_db import db_manager
                word_hash = db_manager.add_word_to_global(word, language, native_language, enrichment_data)
                if word_hash:
                    word_hashes[word] = word_hash
                    print(f"✅ Stored enriched word '{word}' in Multi-User-DB")
                
                # Also store in old DB for backward compatibility
                from server.db import upsert_word_row
                upsert_word_row({
                    'word': word,
                    'language': language,
                    'native_language': native_language,
                    'translation': enrichment_data.get('translation', ''),
                    'pos': enrichment_data.get('pos', ''),
                    'ipa': enrichment_data.get('ipa', ''),
                    'example': enrichment_data.get('example', ''),
                    'example_native': enrichment_data.get('example_native', ''),
                    'synonyms': enrichment_data.get('synonyms', []),
                    'collocations': enrichment_data.get('collocations', []),
                    'gender': enrichment_data.get('gender', 'none'),
                    'familiarity': 0
                })
                enriched_count += 1
                
            except Exception as e:
                print(f"❌ Error storing enriched word '{word}': {e}")
    
    print(f"📚 Batch word enrichment complete: {enriched_count} words enriched and stored in both DB systems")
    
    # Combine with existing words and add word hashes
    all_results = {**existing_words, **enriched_results}
    
    # Add word hashes to results for Multi-User-DB compatibility
    for word in all_results.keys():
        if word not in word_hashes:
            # Generate hash for existing words
            word_hash = db_manager.generate_word_hash(word, language, native_language)
            word_hashes[word] = word_hash
    
    # Store word hashes in the results
    for word, data in all_results.items():
        if isinstance(data, dict):
            data['word_hash'] = word_hashes.get(word)
    
    return all_results