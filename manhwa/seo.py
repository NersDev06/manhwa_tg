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


def public_metadata(meta, subscription):
    import json
    from pathlib import Path
    result = dict(meta)
    rows = json.loads((Path(__file__).resolve().parents[1] / 'config/editorial.json').read_text())
    entry = next((row for row in rows if row['subscription'] == subscription), None)
    if entry:
        result.update(catalog_url='https://manhwa-frame.vercel.app/catalog/' + entry['slug'],
                      summary=entry['description'], genres=entry['genres'])
        if entry.get('english'):
            result['alt_titles_other'] = list(dict.fromkeys([meta.get('title_en', '')] + meta.get('alt_titles_other', [])))
            result['title_en'] = entry['english']
    return result


def channel_title(meta):
    title = meta['main_title_ru']
    suffix = ' | Манхва PDF'
    return title + suffix if len(title + suffix) <= 128 else title[:128]


def bio(meta):
    title = meta['main_title_ru']
    catalog = meta.get('catalog_url')
    footer = (' Оглавление: ' + catalog) if catalog else ''
    prefix = 'Манхва «' + title + '» на русском. Главы в PDF.'
    available = 250 - len(footer)
    if len(prefix) > available:
        prefix = title[:max(1, available - 22)].rstrip() + ' — манхва на русском.'
    english = meta.get('title_en', '')
    if english and len(prefix + ' ' + english + '.' + footer) <= 250:
        prefix += ' ' + english + '.'
    for alias in meta.get('alt_titles_ru', [])[:2]:
        addition = ' Также: ' + alias + '.'
        if len(prefix + addition + footer) <= 250:
            prefix += addition
    return (prefix + footer)[:250]


def chapter_caption(meta, number, part=''):
    title = meta['main_title_ru']
    chapter_tag = re.sub(r'[^\w]', '_', str(number))
    title_tag = re.sub(r'[\W_]+', '_', title.lower()).strip('_')[:60]
    lead = f'📖 {title} — Глава {number}{part}'
    english = meta.get('title_en', '')
    if english and len(lead + english) < 700:
        lead += '\n' + english
    return escape(lead[:800]) + f'\n\nPDF · на русском\n#манхва #{title_tag} #глава_{chapter_tag}'


def navigator(meta, first_url=None, chapters=None, channel_url=None):
    title = escape(meta['main_title_ru'])
    aliases = list(dict.fromkeys(meta.get('alt_titles_ru', [])[:2] + [meta.get('title_en', '')]))
    aliases = [n for n in aliases if n and n.casefold() != meta['main_title_ru'].casefold()]
    lines = ['<b>' + title + '</b>', 'Манхва на русском · PDF']
    if meta.get('summary'):
        lines += ['', escape(meta['summary'])]
    if aliases:
        lines += ['', 'Также: ' + escape(' · '.join(aliases))]
    if meta.get('genres'):
        lines += ['Жанры: ' + escape(', '.join(meta['genres']))]
    lines += ['', 'Новые главы проверяем раз в час.']
    if chapters:
        last = chapters[-1]
        last_url = channel_url.rstrip('/') + '/' + str(last['sent_parts'][0]['message_id'])
        lines += [f"В канале: {len(chapters)} глав.", '',
                  '<a href="' + escape(first_url, quote=True) + '">📖 Читать с начала</a>',
                  '<a href="' + escape(last_url, quote=True) + '">↗ Последняя: глава ' + escape(str(last['number'])) + '</a>',
                  '', '<b>Быстрые переходы</b>']
        links = []
        for offset in range(0, len(chapters), 50):
            group = chapters[offset:offset + 50]
            target = channel_url.rstrip('/') + '/' + str(group[0]['sent_parts'][0]['message_id'])
            label = str(group[0]['number']) + '–' + str(group[-1]['number'])
            links.append('<a href="' + escape(target, quote=True) + '">' + escape(label) + '</a>')
        lines += [' · '.join(links[i:i+3]) for i in range(0, len(links), 3)]
    elif first_url:
        lines += ['', '<a href="' + escape(first_url, quote=True) + '">📖 Читать с первой главы</a>']
    if meta.get('catalog_url'):
        lines += ['', '<a href="' + escape(meta['catalog_url'], quote=True) + '">📚 Все главы и подробное оглавление</a>']
    return '\n'.join(lines)
