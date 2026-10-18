from contextlib import nullcontext
from io import BytesIO
from types import SimpleNamespace
import pytest
from PIL import Image
from manhwa.pdf import build_chapter
from manhwa.buff import pages
from manhwa.source import SourceError


def test_unreadable_long_strip_rejected_before_publication(tmp_path):
    buffer=BytesIO();Image.new('RGB',(103,2560),'white').save(buffer,'PNG')
    response=SimpleNamespace(iter_content=lambda size:iter([buffer.getvalue()]))
    source=SimpleNamespace(pages=lambda url:['image'],get=lambda *a,**k:nullcontext(response))
    with pytest.raises(ValueError,match='low-resolution'):
        build_chapter(source,'chapter',tmp_path)
    assert not list(tmp_path.glob('*.pdf'))


def test_full_resolution_reader_rejects_wrong_chapter():
    html='<div class="reader__item"><img alt="Убийца Педро том 1 глава 3 страница 1" src="https://c3.mangabuff.ru/page.jpg"></div>'
    source=SimpleNamespace(get=lambda *a:nullcontext(SimpleNamespace(content=html.encode())))
    with pytest.raises(SourceError,match='identity'):
        pages(source,'https://mangabuff.ru/manga/killer-pedro/1/2')
