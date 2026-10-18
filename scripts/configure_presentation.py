"""Configure confirmed public channels; must run with the worker stopped."""
import json, os
from pathlib import Path
from dotenv import load_dotenv
from pymongo.errors import DuplicateKeyError
from manhwa.__main__ import database
from manhwa.source import MangaShi
from manhwa.telegram import Telegram
from manhwa.channel_setup import setup_channel
load_dotenv('.env')
s=database();m=MangaShi();t=Telegram(os.environ['TELEGRAM_BOT_TOKEN'])
for item in json.loads(Path('config/channels.json').read_text()):
    t.check_channel(item['channel'])
    chat=t.call('getChat',{'chat_id':item['channel']})
    if not chat.get('username'):
        raise RuntimeError('Public username is required')
    try:key=s.add(item['url'],item['channel'],item['mode'],item['start'])
    except DuplicateKeyError:key=s.subs.find_one({'url':item['url'],'channel':item['channel']})['_id']
    s.subs.update_one({'_id':key},{'$set':{'public_url':item['public_url'],'main_title_override':item['title']}})
    sub=s.subs.find_one({'_id':key})
    title,chapters=m.chapters(item['url']);s.sync(sub,title,chapters)
    me=t.call('getMe',{})
    rights=t.call('getChatMember',{'chat_id':item['channel'],'user_id':me['id']})
    if rights.get('can_change_info') and rights.get('can_edit_messages'):
        print(item['title'],len(chapters),'navigator',setup_channel(s,m,t,s.subs.find_one({'_id':key})),flush=True)
    else:
        meta=m.metadata(item['url']);meta['main_title_ru']=item['title']
        s.subs.update_one({'_id':key},{'$set':{'metadata':meta}})
        print(item['title'],len(chapters),'needs owner formatting permission',flush=True)
