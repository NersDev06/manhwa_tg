from unittest.mock import Mock
import pytest
from manhwa import buff
from manhwa.source import SourceError


def response(html=None, data=None):
    r = Mock(); r.content = (html or '').encode(); r.json.return_value = data
    r.__enter__ = Mock(return_value=r); r.__exit__ = Mock(return_value=False)
    return r


def test_public_continuation_includes_older_chapters():
    source = Mock()
    source.get.return_value = response('''<h1>Title</h1><meta name="csrf-token" content="public-csrf">
    <div class="manga" data-id="42"></div><div class="load-chapters-trigger"></div>
    <a class="chapters__item" href="/manga/test/1/101">101</a>''')
    source.session.post.return_value = response(data={'content': '<a class="chapters__item" href="/manga/test/1/1">1</a>'})
    title, chapters = buff.catalogue(source, 'https://mangabuff.ru/manga/test')
    assert {c.number for c in chapters} == {'1', '101'}
    assert source.session.post.call_args.kwargs['data'] == {'manga_id': '42'}
    assert source.session.post.call_args.kwargs['headers']['X-CSRF-TOKEN'] == 'public-csrf'


@pytest.mark.parametrize('numbers', [[1, 3], [1, 1], [2]])
def test_missing_or_duplicate_reader_pages_are_rejected(numbers):
    source = Mock()
    source.get.return_value = response('<div class="reader__item">' + ''.join(
        f'<img alt="Title том 1 глава 2 страница {n}" src="https://c2.mangabuff.ru/{n}.jpg">' for n in numbers) + '</div>')
    with pytest.raises(SourceError, match='sequence'):
        buff.pages(source, 'https://mangabuff.ru/manga/test/1/2')
