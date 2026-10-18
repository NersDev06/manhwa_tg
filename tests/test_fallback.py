from unittest.mock import Mock
import mongomock
import pytest
from manhwa.source import Chapter, SourceError
from manhwa.fallback import ResilientSource
from manhwa.store import Store


def test_fallback_retains_existing_queue_identity(monkeypatch):
    source=ResilientSource(interval=0)
    store=Store(mongomock.MongoClient().db)
    url=next(iter(source.mapping))
    store.add(url,'channel','archive','1')
    sub=store.subs.find_one()
    store.sync(sub,'title',[Chapter(url+'glava-1/','Глава 1','1','1')])
    source.bind(store)
    monkeypatch.setattr(source,'_primary',Mock(side_effect=SourceError('unavailable')))
    monkeypatch.setattr(source,'_catalog',lambda u:('title',{'1':Chapter('https://wamanga.ru/manhwa/x/glava-1','Глава 1','0','1'),'2':Chapter('https://wamanga.ru/manhwa/x/glava-2','Глава 2','0','2')}))
    title,chapters=source.chapters(url)
    store.sync(sub,title,chapters)
    assert store.jobs.count_documents({})==2
    assert chapters[0].url==url+'glava-1/'
    assert chapters[1].volume=='1'


def test_fallback_refuses_missing_chapter(monkeypatch):
    source=ResilientSource(interval=0)
    url=next(iter(source.mapping))
    monkeypatch.setattr(source,'_primary',Mock(side_effect=SourceError('unavailable')))
    monkeypatch.setattr(source,'_catalog',lambda u:('title',{}))
    with pytest.raises(SourceError,match='missing or ambiguous'):
        source.pages(url+'glava-99/')


def test_primary_recovery_does_not_duplicate_secondary_jobs(monkeypatch):
    source=ResilientSource(interval=0)
    store=Store(mongomock.MongoClient().db)
    url=next(iter(source.mapping))
    store.add(url,'channel','archive','1');sub=store.subs.find_one()
    backup=Chapter('https://wamanga.ru/manhwa/x/glava-1','Глава 1','1','1')
    store.sync(sub,'title',[backup]);source.bind(store)
    monkeypatch.setattr(source,'_primary',lambda call,u:('title',[Chapter(url+'glava-1/','Глава 1','1','1')]))
    title,chapters=source.chapters(url);store.sync(sub,title,chapters)
    assert store.jobs.count_documents({})==1
    assert chapters[0].url==backup.url
