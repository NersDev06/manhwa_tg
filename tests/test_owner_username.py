import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
import mongomock
from telethon import errors
from manhwa.store import Store
from manhwa.owner_username import assign_username


def setup():
    s=Store(mongomock.MongoClient().db)
    sub={'_id':'a','channel':'-1001234567890','metadata':{'main_title_ru':'Название','title_en':'Title'}}
    s.subs.insert_one(sub)
    c=AsyncMock(); c.get_me.return_value=SimpleNamespace(bot=False)
    c.get_entity.return_value=SimpleNamespace(username=None)
    return s, sub, c


def test_occupied_candidate_uses_next():
    s, sub, c=setup();c.side_effect=[False,True,True]
    result=asyncio.run(assign_username(c,s,sub))
    assert result == 'title_manhwa'
    assert s.db.owner_tasks.find_one()['status']=='done'


def test_floodwait_saved_without_skipping_candidate():
    s, sub, c=setup();c.side_effect=errors.FloodWaitError(request=None,capture=120)
    assert asyncio.run(assign_username(c,s,sub)) is None
    task=s.db.owner_tasks.find_one()
    assert task['status']=='pending' and task['candidate_index']==0
    assert task['retry_at'] is not None
