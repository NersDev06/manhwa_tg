from contextlib import nullcontext

import pytest
from manhwa.source import MangaShi, SourceError


def response(html):
    class R:
        text = html
    return nullcontext(R())


def test_paginated_chapters_sorted_without_rounding(monkeypatch):
    first = '<h1>Тест</h1><div id="chapters-list"><a href="/manga/test/tom-1/glava-2/"><span class="chapter-title">2</span></a></div><div id="chapters-load-more"><a hx-get="/manga/test/chapters/?page=2">Ещё</a></div>'
    second = '<a href="/manga/test/tom-1/glava-1,5/"><span class="chapter-title">1.5</span></a>'
    source = MangaShi(interval=0)
    monkeypatch.setattr(source, 'get', lambda url: response(second if 'page=2' in url else first))
    title, chapters = source.chapters('/manga/test/')
    assert title == 'Тест'
    assert [c.number for c in chapters] == ['1.5', '2']


def test_empty_source_is_error(monkeypatch):
    source = MangaShi()
    monkeypatch.setattr(source, 'get', lambda *a: response('<h1>Challenge</h1>'))
    with pytest.raises(SourceError):
        source.chapters('/manga/test/')
    with pytest.raises(SourceError):
        source.pages('https://manga-shi.org/manga/test/tom-1/glava-1/')


def test_chapters_without_volume_and_fractional_extras(monkeypatch):
    html = '<h1>Рыцарь</h1><div id="chapters-list"><a href="/manga/test/glava-112-3/"><span class="chapter-title">Глава 112.3: Экстра 3</span></a><a href="/manga/test/glava-112/"><span class="chapter-title">Глава 112</span></a></div>'
    source = MangaShi()
    monkeypatch.setattr(source, 'get', lambda url: response(html))
    _, chapters = source.chapters('/manga/test/')
    assert [c.number for c in chapters] == ['112', '112.3']
    assert chapters[0].volume == '0'
