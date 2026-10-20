from unittest.mock import Mock
from datetime import timedelta
import mongomock
from manhwa.store import Store, now
from manhwa.channel_setup import navigation_content, refresh_navigation
from manhwa.seo import public_metadata, bio, chapter_caption


def setup():
    s=Store(mongomock.MongoClient().db)
    key='1483b9d7af5bc27142f1'
    meta={'main_title_ru':'Убийца Петер','title_en':'Killer Pedro','alt_titles_ru':['Киллер Педро'],'alt_titles_other':[]}
    s.subs.insert_one({'_id':key,'enabled':True,'public_url':'https://t.me/ubiytsa_peter_manhwa','channel':'@test','metadata':meta})
    s.db.outbox.insert_one({'_id':'navigator:'+key,'status':'sent','pinned':True,'message_id':5})
    s.jobs.insert_many([{'subscription':key,'status':'sent','volume':0,'number':n,'sent_parts':[{'message_id':100+n}]} for n in range(1,104)])
    s.jobs.insert_one({'subscription':key,'status':'pending','volume':0,'number':104,'sent_parts':[]})
    return s,key


def test_rich_navigation_links_confirmed_first_last_and_ranges():
    s,key=setup();text,first=navigation_content(s,s.subs.find_one())
    assert first.endswith('/101')
    assert '103 глав' in text and 'глава 103' in text
    assert '1–50' in text and '51–100' in text and '101–103' in text
    assert 'https://manhwa-frame.vercel.app/catalog/ubiytsa-peter' in text
    assert 'глава 104' not in text
    assert len(text)<4096


def test_navigation_updates_same_message_only_when_content_changes():
    s,key=setup();tg=Mock()
    refresh_navigation(s,tg);refresh_navigation(s,tg,force=True)
    assert tg.call.call_count==1
    assert tg.call.call_args.args[0]=='editMessageText'
    assert tg.call.call_args.args[1]['message_id']==5
    s.jobs.update_one({'number':104},{'$set':{'status':'sent','sent_parts':[{'message_id':204}]}})
    s.db.outbox.update_one({'_id':'navigator:'+key},{'$set':{'navigation_checked':now()-timedelta(minutes=6)}})
    refresh_navigation(s,tg)
    assert tg.call.call_count==2
    assert 'глава 104' in tg.call.call_args.args[1]['text']


def test_caption_clear_metadata_preserves_alternative_name_and_catalog():
    s,key=setup();meta=public_metadata(s.subs.find_one()['metadata'],key)
    assert meta['title_en']=='Killer Peter'
    assert meta['catalog_url'] in bio(meta)
    text=chapter_caption(meta,'104.1')
    assert '#убийца_петер' in text and '#глава_104_1' in text
    assert 'tg-spoiler' not in text
    assert len(text)<1024
