from contextlib import nullcontext
from types import SimpleNamespace
import pytest
from manhwa import remanga
from manhwa.source import SourceError

CONFIG={'directory':'verified-title','title_id':100,'branch_id':200}
URL=remanga.API+'/api/titles/chapters/77/'

def reader(data):
    return SimpleNamespace(get=lambda *a,**k:nullcontext(SimpleNamespace(json=lambda:{'content':data})))

def chapter(**fields):
    return {'title_id':100,'branch_id':200,'chapter':'2','is_paid':False,'is_published':True,
            'pages':[[{'link':'https://img3.reimg2.org/first.jpeg'}],[{'link':'https://img3.reimg2.org/second.jpeg'}]],**fields}


def test_public_reader_preserves_fragment_order():
    assert remanga.pages(reader(chapter()),URL,CONFIG,'2')==[
        'https://img3.reimg2.org/first.jpeg','https://img3.reimg2.org/second.jpeg']


@pytest.mark.parametrize('fields',[{'is_paid':True},{'is_published':False},{'title_id':101},{'branch_id':201},{'chapter':'3'}])
def test_paid_or_different_chapter_cannot_be_used_as_fallback(fields):
    with pytest.raises(SourceError):remanga.pages(reader(chapter(**fields)),URL,CONFIG,'2')


def test_catalogue_paginates_and_excludes_paid_releases():
    seen=[]
    def get(url,params=None):
        if '/api/v2/titles/' in url:
            data={'id':100,'main_name':'Title','branches':[{'id':200}]}
        else:
            seen.append(params['page'])
            data={'content':[{'id':77,'chapter':'1','tome':1,'is_paid':False},
                             {'id':78,'chapter':'2','tome':1,'is_paid':True}] if params['page']==1 else []}
        return nullcontext(SimpleNamespace(json=lambda:data))
    _,chapters=remanga.catalogue(SimpleNamespace(get=get),CONFIG)
    assert seen==[1,2] and [c.number for c in chapters]==['1']
