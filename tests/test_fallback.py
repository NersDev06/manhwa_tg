from decimal import Decimal
from unittest.mock import Mock
import mongomock
import pytest
from manhwa.source import Chapter, SourceError
from manhwa.fallback import ResilientSource
from manhwa.store import Store

URL='https://manga-shi.org/manga/test/'
CONFIG=[{'url':URL,'canonical_volume':1,'sources':[
    {'kind':'mangashi','url':URL},
    {'kind':'wamanga','url':'https://wamanga.ru/manhwa/test'},
    {'kind':'mangabuff','url':'https://mangabuff.ru/manga/test'}]}]


def prepared(monkeypatch):
    source=ResilientSource(interval=0,config=CONFIG)
    store=Store(mongomock.MongoClient().db)
    store.add(URL,'channel','archive','1');sub=store.subs.find_one()
    store.sync(sub,'title',[Chapter(URL+'glava-1/','Глава 1','1','1')]);source.bind(store)
    return source,store,sub


def test_fallback_retains_existing_queue_identity(monkeypatch):
    source,store,sub=prepared(monkeypatch)
    backup={Decimal(n):Chapter(f'https://wamanga.ru/manhwa/test/glava-{n}','Глава '+n,'0',n) for n in ['1','2']}
    monkeypatch.setattr(source,'_catalogues',lambda u:[(CONFIG[0]['sources'][1],'title',backup)])
    title,chapters=source.chapters(URL);store.sync(sub,title,chapters)
    assert store.jobs.count_documents({})==2
    assert chapters[0].url==URL+'glava-1/'
    assert chapters[1].volume=='1'


def test_fallback_refuses_missing_chapter(monkeypatch):
    source=ResilientSource(interval=0,config=CONFIG)
    monkeypatch.setattr(source,'_catalogues',lambda u:[(CONFIG[0]['sources'][1],'title',{})])
    with pytest.raises(SourceError,match='missing from all'):
        source.pages(URL+'glava-99/')


def test_primary_recovery_preserves_published_receipts(monkeypatch):
    source,store,sub=prepared(monkeypatch)
    original=store.jobs.find_one();store.jobs.update_one({'_id':original['_id']},{'$set':{
        'status':'sent','sent_parts':[{'message_id':71,'file_id':'receipt'}], 'preview_receipt':{'message_id':70}}})
    for kind,reader in [('wamanga','https://wamanga.ru/manhwa/test/glava-1'),('mangabuff','https://mangabuff.ru/manga/test/1/1'),('mangashi',URL+'tom-1/glava-1/')]:
        cfg=next(c for c in CONFIG[0]['sources'] if c['kind']==kind)
        monkeypatch.setattr(source,'_catalogues',lambda u,cfg=cfg,reader=reader:[(cfg,'title',{Decimal(1):Chapter(reader,'Глава 1','0','1')})])
        title,chapters=source.chapters(URL);store.sync(sub,title,chapters)
    assert store.jobs.count_documents({})==1
    job=store.jobs.find_one();assert job['_id']==original['_id']
    assert job['status']=='sent' and job['sent_parts'][0]['message_id']==71
    assert job['preview_receipt']['message_id']==70


def test_failed_catalogue_does_not_hide_other_sources(monkeypatch):
    source=ResilientSource(interval=0,config=CONFIG)
    def catalogue(canonical,config):
        if config['kind']!='mangabuff':raise SourceError('offline')
        return 'title',{Decimal(1):Chapter('https://mangabuff.ru/manga/test/1/1','Глава 1','1','1')}
    monkeypatch.setattr(source,'_catalogue',catalogue)
    assert source.candidates(URL+'glava-1/')[0].kind=='mangabuff'


def test_provider_schema_change_does_not_break_backup_chain(monkeypatch):
    source=ResilientSource(interval=0, config=CONFIG)
    monkeypatch.setattr('manhwa.fallback.buff.catalogue', lambda *a: (_ for _ in ()).throw(KeyError('schema changed')))
    with pytest.raises(SourceError, match='Malformed provider'):
        source._catalogue(URL, CONFIG[0]['sources'][2])
    assert source.cooldowns
