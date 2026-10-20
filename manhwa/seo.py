"""Channel metadata and Telegram-safe presentation; no ranking guarantees."""
import re
from html import escape

_RU = dict(zip('абвгдеёжзийклмнопрстуфхцчшщъыьэюя',
    ['a','b','v','g','d','e','yo','zh','z','i','y','k','l','m','n','o','p','r','s','t','u','f','h','ts','ch','sh','sch','','y','','e','yu','ya']))


def slug(text):
    value = ''.join(_RU.get(c, c) for c in text.lower())
    value = re.sub('[^a-z0-9]+', '_', value).strip('_')
    return value if value and value[0].isalpha() else 'manhwa_' + value


def usernames(meta):
    ru, en = slug(meta['main_title_ru']), slug(meta.get('title_en') or meta['main_title_ru'])
    result = []
    for root, suffix in [(ru,'manhwa'), (en,'manhwa'), (ru,'read'), (ru,'chitat'), (en,'tg'), (ru,'glavy')]:
        candidate = root[:31-len(suffix)].rstrip('_') + '_' + suffix
        if candidate not in result:
            result.append(candidate)
    return result


def channel_title(meta):
    title = meta['main_title_ru']
    for tail in [' | Читать манхву', ' | Манхва', '']:
        if len(title + tail) <= 65:
            return title + tail
    return title[:128]


def bio(meta):
    # The Bot API currently permits longer descriptions, but keep the user's 250 cap.
    title = meta['main_title_ru']
    en = f" ({meta['title_en']})" if meta.get('title_en') else ''
    base = f'Читать манхву {title}{en} на русском. Главы в PDF, обновления автоматически.'
    if len(base) > 250:
        base = f'Читать манхву {title} на русском. Главы в PDF.'
    if len(base) > 250:
        base = ' '.join(base[:250].split(' ')[:-1])
    for alias in meta.get('alt_titles_ru', []):
        addition = (' Другие названия: ' if 'Другие названия:' not in base else ', ') + alias
        if len(base + addition) <= 250:
            base += addition
    return base


def chapter_caption(meta, number, part=''):
    title = meta['main_title_ru']
    tag = re.sub(r'[^\w]', '_', str(number))
    lead = f'📖 {title} — Глава {number}{part}\n#глава_{tag}'
    names = list(dict.fromkeys([title] + meta.get('alt_titles_ru', [])[:1] + [meta.get('title_en', '')]))
    search = f"Читать манхву {' / '.join(n for n in names if n)} — глава {number} на русском"
    if len(lead + search) < 950:
        return escape(lead) + '\n\n<tg-spoiler>' + escape(search) + '</tg-spoiler>'
    return escape(lead[:900])


def navigator(meta, first_url=None):
    names = list(dict.fromkeys(meta.get('alt_titles_ru', []) + meta.get('alt_titles_other', [])))
    title = escape(meta['main_title_ru'])
    en = '\n<i>' + escape(meta['title_en']) + '</i>' if meta.get('title_en') else ''
    aliases = '\n\nДругие названия: ' + escape(', '.join(names)) if names else ''
    state = escape(meta.get('status') or 'уточняется')
    start = f'<a href="{escape(first_url, quote=True)}">📖 Читать с первой главы</a>' if first_url else '📖 #глава_1'
    return f'<b>{title}</b>{en}{aliases}\n\nСтатус источника: {state}.\nПроверяем новые главы раз в час.\n\n{start}'
