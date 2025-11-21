#!/usr/bin/env python3
"""
Script to add localization entries for new topic options via API.
Can be run locally or on Railway.
"""

import requests
import json
import sys

# Base URL - change if running locally vs Railway
BASE_URL = os.environ.get('RAILWAY_PUBLIC_DOMAIN', 'http://localhost:5000')
if BASE_URL and not BASE_URL.startswith('http'):
    BASE_URL = f'https://{BASE_URL}'

# New topic entries with translations for all languages
NEW_TOPICS = {
    'topics.academic': {
        'description': 'Academic topic',
        'en': 'Academic', 'de': 'Studium', 'es': 'Académico', 'fr': 'Académique',
        'it': 'Accademico', 'pt': 'Acadêmico', 'ru': 'Академический', 'tr': 'Akademik',
        'ka': 'აკადემიური', 'nl': 'Academisch', 'sv': 'Akademisk', 'no': 'Akademisk',
        'da': 'Akademisk', 'fi': 'Akateeminen', 'pl': 'Akademicki', 'cs': 'Akademický',
        'sk': 'Akademický', 'hu': 'Akadémiai', 'ro': 'Academic', 'bg': 'Академичен',
        'el': 'Ακαδημαϊκό', 'uk': 'Академічний', 'zh': '学术', 'ja': '学術', 'ko': '학술',
        'hi': 'शैक्षणिक', 'ur': 'تعلیمی', 'id': 'Akademik', 'ms': 'Akademik', 'th': 'วิชาการ',
        'vi': 'Học thuật', 'fa': 'آکادمیک', 'ar': 'أكاديمي', 'sw': 'Kielimu',
    },
    'topics.family': {
        'description': 'Family topic',
        'en': 'Family', 'de': 'Familie', 'es': 'Familia', 'fr': 'Famille',
        'it': 'Famiglia', 'pt': 'Família', 'ru': 'Семья', 'tr': 'Aile', 'ka': 'ოჯახი',
        'nl': 'Familie', 'sv': 'Familj', 'no': 'Familie', 'da': 'Familie', 'fi': 'Perhe',
        'pl': 'Rodzina', 'cs': 'Rodina', 'sk': 'Rodina', 'hu': 'Család', 'ro': 'Familie',
        'bg': 'Семейство', 'el': 'Οικογένεια', 'uk': 'Сім\'я', 'zh': '家庭', 'ja': '家族',
        'ko': '가족', 'hi': 'परिवार', 'ur': 'خاندان', 'id': 'Keluarga', 'ms': 'Keluarga',
        'th': 'ครอบครัว', 'vi': 'Gia đình', 'fa': 'خانواده', 'ar': 'عائلة', 'sw': 'Familia',
    },
    'topics.immigration': {
        'description': 'Immigration topic',
        'en': 'Immigration', 'de': 'Einwanderung', 'es': 'Inmigración', 'fr': 'Immigration',
        'it': 'Immigrazione', 'pt': 'Imigração', 'ru': 'Иммиграция', 'tr': 'Göç',
        'ka': 'იმიგრაცია', 'nl': 'Immigratie', 'sv': 'Invandring', 'no': 'Innvandring',
        'da': 'Indvandring', 'fi': 'Maahanmuutto', 'pl': 'Imigracja', 'cs': 'Imigrace',
        'sk': 'Imigrácia', 'hu': 'Bevándorlás', 'ro': 'Imigrație', 'bg': 'Имиграция',
        'el': 'Μετανάστευση', 'uk': 'Імміграція', 'zh': '移民', 'ja': '移民', 'ko': '이민',
        'hi': 'आप्रवासन', 'ur': 'ہجرت', 'id': 'Imigrasi', 'ms': 'Imigresen', 'th': 'การเข้าเมือง',
        'vi': 'Nhập cư', 'fa': 'مهاجرت', 'ar': 'الهجرة', 'sw': 'Uhamiaji',
    },
    'topics.culture': {
        'description': 'Culture topic',
        'en': 'Culture', 'de': 'Kultur', 'es': 'Cultura', 'fr': 'Culture', 'it': 'Cultura',
        'pt': 'Cultura', 'ru': 'Культура', 'tr': 'Kültür', 'ka': 'კულტურა', 'nl': 'Cultuur',
        'sv': 'Kultur', 'no': 'Kultur', 'da': 'Kultur', 'fi': 'Kulttuuri', 'pl': 'Kultura',
        'cs': 'Kultura', 'sk': 'Kultúra', 'hu': 'Kultúra', 'ro': 'Cultură', 'bg': 'Култура',
        'el': 'Πολιτισμός', 'uk': 'Культура', 'zh': '文化', 'ja': '文化', 'ko': '문화',
        'hi': 'संस्कृति', 'ur': 'ثقافت', 'id': 'Budaya', 'ms': 'Budaya', 'th': 'วัฒนธรรม',
        'vi': 'Văn hóa', 'fa': 'فرهنگ', 'ar': 'ثقافة', 'sw': 'Utamaduni',
    },
    'topics.hobbies': {
        'description': 'Hobbies topic',
        'en': 'Hobbies', 'de': 'Hobbys', 'es': 'Pasatiempos', 'fr': 'Loisirs', 'it': 'Hobby',
        'pt': 'Passatempos', 'ru': 'Хобби', 'tr': 'Hobiler', 'ka': 'ჰობი', 'nl': 'Hobby\'s',
        'sv': 'Hobbys', 'no': 'Hobbyer', 'da': 'Hobbyer', 'fi': 'Harrastukset', 'pl': 'Hobby',
        'cs': 'Koníčky', 'sk': 'Koníčky', 'hu': 'Hobbik', 'ro': 'Hobby-uri', 'bg': 'Хобита',
        'el': 'Χόμπι', 'uk': 'Хобі', 'zh': '爱好', 'ja': '趣味', 'ko': '취미', 'hi': 'शौक',
        'ur': 'شوقیہ', 'id': 'Hobi', 'ms': 'Hobi', 'th': 'งานอดิเรก', 'vi': 'Sở thích',
        'fa': 'سرگرمی‌ها', 'ar': 'الهوايات', 'sw': 'Burudani',
    },
    'topics.healthcare': {
        'description': 'Healthcare topic',
        'en': 'Healthcare', 'de': 'Gesundheitswesen', 'es': 'Salud', 'fr': 'Santé',
        'it': 'Sanità', 'pt': 'Saúde', 'ru': 'Здравоохранение', 'tr': 'Sağlık',
        'ka': 'ჯანდაცვა', 'nl': 'Gezondheidszorg', 'sv': 'Hälsovård', 'no': 'Helsevesen',
        'da': 'Sundhedsvæsen', 'fi': 'Terveydenhuolto', 'pl': 'Opieka zdrowotna',
        'cs': 'Zdravotnictví', 'sk': 'Zdravotníctvo', 'hu': 'Egészségügy', 'ro': 'Sănătate',
        'bg': 'Здравеопазване', 'el': 'Υγεία', 'uk': 'Охорона здоров\'я', 'zh': '医疗保健',
        'ja': '医療', 'ko': '의료', 'hi': 'स्वास्थ्य सेवा', 'ur': 'صحت', 'id': 'Kesehatan',
        'ms': 'Penjagaan kesihatan', 'th': 'การดูแลสุขภาพ', 'vi': 'Chăm sóc sức khỏe',
        'fa': 'مراقبت‌های بهداشتی', 'ar': 'الرعاية الصحية', 'sw': 'Afya',
    },
    'topics.technology': {
        'description': 'Technology topic',
        'en': 'Technology', 'de': 'Technologie', 'es': 'Tecnología', 'fr': 'Technologie',
        'it': 'Tecnologia', 'pt': 'Tecnologia', 'ru': 'Технология', 'tr': 'Teknoloji',
        'ka': 'ტექნოლოგია', 'nl': 'Technologie', 'sv': 'Teknologi', 'no': 'Teknologi',
        'da': 'Teknologi', 'fi': 'Teknologia', 'pl': 'Technologia', 'cs': 'Technologie',
        'sk': 'Technológia', 'hu': 'Technológia', 'ro': 'Tehnologie', 'bg': 'Технология',
        'el': 'Τεχνολογία', 'uk': 'Технологія', 'zh': '技术', 'ja': '技術', 'ko': '기술',
        'hi': 'प्रौद्योगिकी', 'ur': 'ٹیکنالوجی', 'id': 'Teknologi', 'ms': 'Teknologi',
        'th': 'เทคโนโลยี', 'vi': 'Công nghệ', 'fa': 'فناوری', 'ar': 'التكنولوجيا',
        'sw': 'Teknolojia',
    },
    'topics.romance': {
        'description': 'Romance topic',
        'en': 'Romance', 'de': 'Romantik', 'es': 'Romance', 'fr': 'Romance',
        'it': 'Romanticismo', 'pt': 'Romance', 'ru': 'Романтика', 'tr': 'Romantizm',
        'ka': 'რომანტიკა', 'nl': 'Romantiek', 'sv': 'Romantik', 'no': 'Romantikk',
        'da': 'Romantik', 'fi': 'Romantiikka', 'pl': 'Romans', 'cs': 'Romantika',
        'sk': 'Romantika', 'hu': 'Romantika', 'ro': 'Romantism', 'bg': 'Романтика',
        'el': 'Ρομαντισμός', 'uk': 'Романтика', 'zh': '浪漫', 'ja': 'ロマンス', 'ko': '로맨스',
        'hi': 'रोमांस', 'ur': 'رومانوی', 'id': 'Romantis', 'ms': 'Romantik',
        'th': 'ความโรแมนติก', 'vi': 'Lãng mạn', 'fa': 'عاشقانه', 'ar': 'رومانسي',
        'sw': 'Mapenzi',
    },
    'topics.media': {
        'description': 'Media topic',
        'en': 'Media', 'de': 'Medien', 'es': 'Medios', 'fr': 'Médias', 'it': 'Media',
        'pt': 'Mídia', 'ru': 'СМИ', 'tr': 'Medya', 'ka': 'მედია', 'nl': 'Media',
        'sv': 'Media', 'no': 'Media', 'da': 'Medier', 'fi': 'Media', 'pl': 'Media',
        'cs': 'Média', 'sk': 'Médiá', 'hu': 'Média', 'ro': 'Media', 'bg': 'Медии',
        'el': 'Μέσα', 'uk': 'Медіа', 'zh': '媒体', 'ja': 'メディア', 'ko': '미디어',
        'hi': 'मीडिया', 'ur': 'میڈیا', 'id': 'Media', 'ms': 'Media', 'th': 'สื่อ',
        'vi': 'Truyền thông', 'fa': 'رسانه', 'ar': 'الإعلام', 'sw': 'Vyombo vya habari',
    },
}

ONBOARDING_DESCRIPTIONS = {
    'onboarding.topics.academic.desc': {
        'description': 'Onboarding description for academic topic',
        'en': 'Academic learning and education', 'de': 'Akademisches Lernen und Bildung',
        'es': 'Aprendizaje académico y educación', 'fr': 'Apprentissage académique et éducation',
        'it': 'Apprendimento accademico e istruzione', 'pt': 'Aprendizado acadêmico e educação',
        'ru': 'Академическое обучение и образование', 'tr': 'Akademik öğrenme ve eğitim',
        'ka': 'აკადემიური სწავლა და განათლება', 'nl': 'Academisch leren en onderwijs',
        'sv': 'Akademiskt lärande och utbildning', 'no': 'Akademisk læring og utdanning',
        'da': 'Akademisk læring og uddannelse', 'fi': 'Akateeminen oppiminen ja koulutus',
        'pl': 'Nauka akademicka i edukacja', 'cs': 'Akademické učení a vzdělávání',
        'sk': 'Akademické učenie a vzdelávanie', 'hu': 'Akadémiai tanulás és oktatás',
        'ro': 'Învățare academică și educație', 'bg': 'Академично обучение и образование',
        'el': 'Ακαδημαϊκή μάθηση και εκπαίδευση', 'uk': 'Академічне навчання та освіта',
        'zh': '学术学习和教育', 'ja': '学術的な学習と教育', 'ko': '학술 학습 및 교육',
        'hi': 'शैक्षणिक सीख और शिक्षा', 'ur': 'تعلیمی سیکھنا اور تعلیم',
        'id': 'Pembelajaran akademik dan pendidikan', 'ms': 'Pembelajaran akademik dan pendidikan',
        'th': 'การเรียนรู้ทางวิชาการและการศึกษา', 'vi': 'Học tập và giáo dục học thuật',
        'fa': 'یادگیری و آموزش آکادمیک', 'ar': 'التعلم الأكاديمي والتعليم',
        'sw': 'Kujifunza kitaaluma na elimu',
    },
    'onboarding.topics.family.desc': {
        'description': 'Onboarding description for family topic',
        'en': 'Family relationships and communication', 'de': 'Familienbeziehungen und Kommunikation',
        'es': 'Relaciones familiares y comunicación', 'fr': 'Relations familiales et communication',
        'it': 'Relazioni familiari e comunicazione', 'pt': 'Relações familiares e comunicação',
        'ru': 'Семейные отношения и общение', 'tr': 'Aile ilişkileri ve iletişim',
        'ka': 'ოჯახური ურთიერთობები და კომუნიკაცია', 'nl': 'Familierelaties en communicatie',
        'sv': 'Familjerelationer och kommunikation', 'no': 'Familierelasjoner og kommunikasjon',
        'da': 'Familierelationer og kommunikation', 'fi': 'Perhesuhteet ja viestintä',
        'pl': 'Relacje rodzinne i komunikacja', 'cs': 'Rodinné vztahy a komunikace',
        'sk': 'Rodinné vzťahy a komunikácia', 'hu': 'Családi kapcsolatok és kommunikáció',
        'ro': 'Relații de familie și comunicare', 'bg': 'Семейни отношения и комуникация',
        'el': 'Οικογενειακές σχέσεις και επικοινωνία', 'uk': 'Сімейні стосунки та спілкування',
        'zh': '家庭关系和沟通', 'ja': '家族関係とコミュニケーション', 'ko': '가족 관계 및 소통',
        'hi': 'पारिवारिक रिश्ते और संचार', 'ur': 'خاندانی تعلقات اور مواصلت',
        'id': 'Hubungan keluarga dan komunikasi', 'ms': 'Hubungan keluarga dan komunikasi',
        'th': 'ความสัมพันธ์ในครอบครัวและการสื่อสาร', 'vi': 'Mối quan hệ gia đình và giao tiếp',
        'fa': 'روابط خانوادگی و ارتباطات', 'ar': 'العلاقات الأسرية والتواصل',
        'sw': 'Uhusiano wa familia na mawasiliano',
    },
    'onboarding.topics.immigration.desc': {
        'description': 'Onboarding description for immigration topic',
        'en': 'Living in a new country', 'de': 'Leben in einem neuen Land',
        'es': 'Vivir en un nuevo país', 'fr': 'Vivre dans un nouveau pays',
        'it': 'Vivere in un nuovo paese', 'pt': 'Viver em um novo país', 'ru': 'Жизнь в новой стране',
        'tr': 'Yeni bir ülkede yaşamak', 'ka': 'ახალ ქვეყანაში ცხოვრება',
        'nl': 'Leven in een nieuw land', 'sv': 'Leva i ett nytt land', 'no': 'Bo i et nytt land',
        'da': 'At bo i et nyt land', 'fi': 'Eläminen uudessa maassa', 'pl': 'Życie w nowym kraju',
        'cs': 'Život v nové zemi', 'sk': 'Život v novej krajine', 'hu': 'Új országban élés',
        'ro': 'Trăirea într-o țară nouă', 'bg': 'Живот в нова страна', 'el': 'Ζώντας σε μια νέα χώρα',
        'uk': 'Життя в новій країні', 'zh': '在新国家生活', 'ja': '新しい国での生活',
        'ko': '새로운 국가에서 살기', 'hi': 'एक नए देश में रहना', 'ur': 'ایک نئے ملک میں رہنا',
        'id': 'Hidup di negara baru', 'ms': 'Hidup di negara baharu', 'th': 'การใช้ชีวิตในประเทศใหม่',
        'vi': 'Sống ở một đất nước mới', 'fa': 'زندگی در یک کشور جدید', 'ar': 'العيش في بلد جديد',
        'sw': 'Kuishi katika nchi mpya',
    },
    'onboarding.topics.culture.desc': {
        'description': 'Onboarding description for culture topic',
        'en': 'Cultural understanding and traditions', 'de': 'Kulturelles Verständnis und Traditionen',
        'es': 'Comprensión cultural y tradiciones', 'fr': 'Compréhension culturelle et traditions',
        'it': 'Comprensione culturale e tradizioni', 'pt': 'Compreensão cultural e tradições',
        'ru': 'Культурное понимание и традиции', 'tr': 'Kültürel anlayış ve gelenekler',
        'ka': 'კულტურული გაგება და ტრადიციები', 'nl': 'Cultureel begrip en tradities',
        'sv': 'Kulturell förståelse och traditioner', 'no': 'Kulturell forståelse og tradisjoner',
        'da': 'Kulturel forståelse og traditioner', 'fi': 'Kulttuurinen ymmärrys ja perinteet',
        'pl': 'Zrozumienie kulturowe i tradycje', 'cs': 'Kulturní porozumění a tradice',
        'sk': 'Kultúrne porozumenie a tradície', 'hu': 'Kulturális megértés és hagyományok',
        'ro': 'Înțelegere culturală și tradiții', 'bg': 'Културно разбиране и традиции',
        'el': 'Κατανόηση πολιτισμού και παραδόσεις', 'uk': 'Культурне розуміння та традиції',
        'zh': '文化理解和传统', 'ja': '文化的理解と伝統', 'ko': '문화적 이해와 전통',
        'hi': 'सांस्कृतिक समझ और परंपराएं', 'ur': 'ثقافتی سمجھ اور روایات',
        'id': 'Pemahaman budaya dan tradisi', 'ms': 'Pemahaman budaya dan tradisi',
        'th': 'ความเข้าใจทางวัฒนธรรมและประเพณี', 'vi': 'Hiểu biết văn hóa và truyền thống',
        'fa': 'درک فرهنگی و سنت‌ها', 'ar': 'الفهم الثقافي والتقاليد',
        'sw': 'Uelewa wa kitamaduni na mila',
    },
    'onboarding.topics.hobbies.desc': {
        'description': 'Onboarding description for hobbies topic',
        'en': 'Leisure activities and interests', 'de': 'Freizeitaktivitäten und Interessen',
        'es': 'Actividades de ocio e intereses', 'fr': 'Activités de loisirs et intérêts',
        'it': 'Attività ricreative e interessi', 'pt': 'Atividades de lazer e interesses',
        'ru': 'Досуг и интересы', 'tr': 'Boş zaman aktiviteleri ve ilgi alanları',
        'ka': 'დასვენების აქტივობები და ინტერესები', 'nl': 'Vrijetijdsactiviteiten en interesses',
        'sv': 'Fritidsaktiviteter och intressen', 'no': 'Fritidsaktiviteter og interesser',
        'da': 'Fritidsaktiviteter og interesser', 'fi': 'Vapaa-ajan aktiviteetit ja kiinnostuksen kohteet',
        'pl': 'Zajęcia rekreacyjne i zainteresowania', 'cs': 'Volnočasové aktivity a zájmy',
        'sk': 'Voľnočasové aktivity a záujmy', 'hu': 'Szabadidős tevékenységek és érdeklődési körök',
        'ro': 'Activități de agrement și interese', 'bg': 'Досугови дейности и интереси',
        'el': 'Δραστηριότητες αναψυχής και ενδιαφέροντα', 'uk': 'Дозвілля та інтереси',
        'zh': '休闲活动和兴趣', 'ja': 'レジャー活動と興味', 'ko': '여가 활동 및 관심사',
        'hi': 'अवकाश गतिविधियां और रुचियां', 'ur': 'تفریحی سرگرمیاں اور دلچسپیاں',
        'id': 'Aktivitas rekreasi dan minat', 'ms': 'Aktiviti rekreasi dan minat',
        'th': 'กิจกรรมยามว่างและความสนใจ', 'vi': 'Hoạt động giải trí và sở thích',
        'fa': 'فعالیت‌های تفریحی و علایق', 'ar': 'أنشطة الترفيه والاهتمامات',
        'sw': 'Shughuli za burudani na maslahi',
    },
    'onboarding.topics.healthcare.desc': {
        'description': 'Onboarding description for healthcare topic',
        'en': 'Medical communication', 'de': 'Medizinische Kommunikation',
        'es': 'Comunicación médica', 'fr': 'Communication médicale', 'it': 'Comunicazione medica',
        'pt': 'Comunicação médica', 'ru': 'Медицинское общение', 'tr': 'Tıbbi iletişim',
        'ka': 'სამედიცინო კომუნიკაცია', 'nl': 'Medische communicatie',
        'sv': 'Medicinsk kommunikation', 'no': 'Medisinsk kommunikasjon', 'da': 'Medicinsk kommunikation',
        'fi': 'Lääketieteellinen viestintä', 'pl': 'Komunikacja medyczna', 'cs': 'Lékařská komunikace',
        'sk': 'Lekárska komunikácia', 'hu': 'Orvosi kommunikáció', 'ro': 'Comunicare medicală',
        'bg': 'Медицинска комуникация', 'el': 'Ιατρική επικοινωνία', 'uk': 'Медична комунікація',
        'zh': '医疗沟通', 'ja': '医療コミュニケーション', 'ko': '의료 소통',
        'hi': 'चिकित्सा संचार', 'ur': 'طبی مواصلت', 'id': 'Komunikasi medis',
        'ms': 'Komunikasi perubatan', 'th': 'การสื่อสารทางการแพทย์', 'vi': 'Giao tiếp y tế',
        'fa': 'ارتباطات پزشکی', 'ar': 'التواصل الطبي', 'sw': 'Mawasiliano ya kimatibabu',
    },
    'onboarding.topics.technology.desc': {
        'description': 'Onboarding description for technology topic',
        'en': 'IT and digital communication', 'de': 'IT und digitale Kommunikation',
        'es': 'TI y comunicación digital', 'fr': 'Informatique et communication numérique',
        'it': 'IT e comunicazione digitale', 'pt': 'TI e comunicação digital',
        'ru': 'ИТ и цифровая коммуникация', 'tr': 'BT ve dijital iletişim',
        'ka': 'IT და ციფრული კომუნიკაცია', 'nl': 'IT en digitale communicatie',
        'sv': 'IT och digital kommunikation', 'no': 'IT og digital kommunikasjon',
        'da': 'IT og digital kommunikation', 'fi': 'IT ja digitaalinen viestintä',
        'pl': 'IT i komunikacja cyfrowa', 'cs': 'IT a digitální komunikace',
        'sk': 'IT a digitálna komunikácia', 'hu': 'IT és digitális kommunikáció',
        'ro': 'IT și comunicare digitală', 'bg': 'ИТ и цифрова комуникация',
        'el': 'Τεχνολογία πληροφοριών και ψηφιακή επικοινωνία', 'uk': 'IT та цифрова комунікація',
        'zh': 'IT和数字通信', 'ja': 'ITとデジタルコミュニケーション', 'ko': 'IT 및 디지털 커뮤니케이션',
        'hi': 'आईटी और डिजिटल संचार', 'ur': 'IT اور ڈیجیٹل مواصلت',
        'id': 'IT dan komunikasi digital', 'ms': 'IT dan komunikasi digital',
        'th': 'IT และการสื่อสารดิจิทัล', 'vi': 'CNTT và giao tiếp kỹ thuật số',
        'fa': 'فناوری اطلاعات و ارتباطات دیجیتال', 'ar': 'تقنية المعلومات والتواصل الرقمي',
        'sw': 'IT na mawasiliano ya kidijitali',
    },
    'onboarding.topics.romance.desc': {
        'description': 'Onboarding description for romance topic',
        'en': 'Dating and romantic relationships', 'de': 'Dating und romantische Beziehungen',
        'es': 'Citas y relaciones románticas', 'fr': 'Rencontres et relations romantiques',
        'it': 'Appuntamenti e relazioni romantiche', 'pt': 'Namoro e relacionamentos românticos',
        'ru': 'Знакомства и романтические отношения', 'tr': 'Flört ve romantik ilişkiler',
        'ka': 'შეხვედრები და რომანტიკული ურთიერთობები', 'nl': 'Daten en romantische relaties',
        'sv': 'Dejting och romantiska relationer', 'no': 'Dating og romantiske forhold',
        'da': 'Dating og romantiske forhold', 'fi': 'Seurustelu ja romanttiset suhteet',
        'pl': 'Randki i relacje romantyczne', 'cs': 'Rande a romantické vztahy',
        'sk': 'Rande a romantické vzťahy', 'hu': 'Randevúk és romantikus kapcsolatok',
        'ro': 'Întâlniri și relații romantice', 'bg': 'Срещи и романтични отношения',
        'el': 'Ραντεβού και ρομαντικές σχέσεις', 'uk': 'Побачення та романтичні стосунки',
        'zh': '约会和浪漫关系', 'ja': 'デートとロマンチックな関係', 'ko': '데이트와 로맨틱한 관계',
        'hi': 'डेटिंग और रोमांटिक रिश्ते', 'ur': 'ڈیٹنگ اور رومانوی تعلقات',
        'id': 'Kencan dan hubungan romantis', 'ms': 'Berkencan dan hubungan romantik',
        'th': 'การเดทและความสัมพันธ์โรแมนติก', 'vi': 'Hẹn hò và mối quan hệ lãng mạn',
        'fa': 'دوستیابی و روابط عاشقانه', 'ar': 'المواعدة والعلاقات الرومانسية',
        'sw': 'Kupatana na uhusiano wa kimapenzi',
    },
    'onboarding.topics.media.desc': {
        'description': 'Onboarding description for media topic',
        'en': 'Movies, music and entertainment', 'de': 'Filme, Musik und Unterhaltung',
        'es': 'Películas, música y entretenimiento', 'fr': 'Films, musique et divertissement',
        'it': 'Film, musica e intrattenimento', 'pt': 'Filmes, música e entretenimento',
        'ru': 'Фильмы, музыка и развлечения', 'tr': 'Filmler, müzik ve eğlence',
        'ka': 'ფილმები, მუსიკა და გასართობი', 'nl': 'Films, muziek en entertainment',
        'sv': 'Filmer, musik och underhållning', 'no': 'Filmer, musikk og underholdning',
        'da': 'Film, musik og underholdning', 'fi': 'Elokuvat, musiikki ja viihde',
        'pl': 'Filmy, muzyka i rozrywka', 'cs': 'Filmy, hudba a zábava',
        'sk': 'Filmy, hudba a zábava', 'hu': 'Filmek, zene és szórakoztatás',
        'ro': 'Filme, muzică și divertisment', 'bg': 'Филми, музика и развлечение',
        'el': 'Ταινίες, μουσική και ψυχαγωγία', 'uk': 'Фільми, музика та розваги',
        'zh': '电影、音乐和娱乐', 'ja': '映画、音楽、エンターテインメント', 'ko': '영화, 음악 및 엔터테인먼트',
        'hi': 'फिल्में, संगीत और मनोरंजन', 'ur': 'فلمیں، موسیقی اور تفریح',
        'id': 'Film, musik dan hiburan', 'ms': 'Filem, muzik dan hiburan',
        'th': 'ภาพยนตร์ ดนตรี และความบันเทิง', 'vi': 'Phim, âm nhạc và giải trí',
        'fa': 'فیلم، موسیقی و سرگرمی', 'ar': 'الأفلام والموسيقى والترفيه',
        'sw': 'Filamu, muziki na burudani',
    },
}

def add_via_api():
    """Add localizations via API endpoint"""
    print(f"🌐 Using API endpoint: {BASE_URL}/api/localization/entry")
    
    all_entries = {**NEW_TOPICS, **ONBOARDING_DESCRIPTIONS}
    
    success_count = 0
    error_count = 0
    
    for key, translations in all_entries.items():
        try:
            payload = {
                'reference_key': key,
                **translations
            }
            
            response = requests.post(
                f'{BASE_URL}/api/localization/entry',
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                print(f"  ✅ {key}")
                success_count += 1
            else:
                print(f"  ❌ {key}: {response.status_code} - {response.text}")
                error_count += 1
        except Exception as e:
            print(f"  ❌ {key}: {e}")
            error_count += 1
    
    print(f"\n📊 Results:")
    print(f"   ✅ Success: {success_count}")
    print(f"   ❌ Errors: {error_count}")
    print(f"   📝 Total: {len(all_entries)}")

if __name__ == '__main__':
    import os
    add_via_api()

