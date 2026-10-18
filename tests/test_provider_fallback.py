from contextlib import nullcontext
from io import BytesIO
from types import SimpleNamespace
import requests
from PIL import Image
from manhwa.pdf import build_chapter


def image_bytes(color):
    out=BytesIO();Image.new('RGB',(600,1400),color).save(out,'PNG');return out.getvalue()


def test_half_download_failure_restarts_whole_chapter_without_mixing_sources(tmp_path):
    candidates=[SimpleNamespace(name='first',url='first'),SimpleNamespace(name='second',url='second')]
    rejected=[]
    def get(url,**kwargs):
        if url=='broken':raise requests.ConnectionError('source down')
        color='red' if url.startswith('red') else 'blue'
        response=SimpleNamespace(iter_content=lambda size:iter([image_bytes(color)]))
        return nullcontext(response)
    source=SimpleNamespace(candidates=lambda url:candidates,
        provider_pages=lambda c:['red','broken','red2'] if c.name=='first' else ['blue','blue2'],
        get=get,reject=lambda c,e:rejected.append(c.name))
    paths,stats=build_chapter(source,'chapter',tmp_path)
    assert rejected==['first']
    assert stats['source']=='second' and stats['pdf_pages']==2
    assert len(paths)==1 and paths[0].is_file()
    assert len(list(tmp_path.glob('page-*.jpg')))==2
    with Image.open(tmp_path/'page-00000-00000.jpg') as page:
        assert page.getpixel((10,10))[2]>240
    assert not list(tmp_path.glob('.candidate-*'))
