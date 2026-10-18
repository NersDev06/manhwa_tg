import re
from manhwa.seo import usernames, bio, channel_title, chapter_caption
from manhwa.source import MangaShi


def test_limits_and_safe_html():
    meta = {'main_title_ru': '123 Длинный <тайтл>' * 8, 'title_en': 'A long title', 'alt_titles_ru': ['синоним'] * 100}
    assert all(re.fullmatch('[a-z][a-z0-9_]{4,31}', s) for s in usernames(meta))
    assert len(bio(meta)) <= 250
    assert len(channel_title(meta)) <= 128
    assert '<тайтл>' not in chapter_caption(meta, '12.5')
    assert '#глава_12_5' in chapter_caption(meta, '12.5')


def test_metadata_from_actual_markup():
    meta = MangaShi.parse_metadata('<h1>Название / Title</h1><div><span>Другие названия:</span><span>Синоним, Other</span></div><meta property="og:image" content="/cover.jpg"><span>• Оригинал выходит</span>', 'https://manga-shi.org/manga/test/')
    assert meta['main_title_ru'] == 'Название'
    assert meta['alt_titles_ru'] == ['Синоним']
    assert meta['cover_url'] == 'https://manga-shi.org/cover.jpg'


def test_slash_separated_alternative_titles():
    meta = MangaShi.parse_metadata('<h1>Регрессор падшего дома</h1><div><span>Другие названия:</span><span>Regressor of the Fallen Family / Регрессор из Падшей Семьи / 멸망한 가문의 회귀자</span></div>', 'https://manga-shi.org/manga/test/')
    assert meta['title_en'] == 'Regressor of the Fallen Family'
    assert meta['alt_titles_ru'] == ['Регрессор из Падшей Семьи']
