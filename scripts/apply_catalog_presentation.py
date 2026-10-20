"""Update project channel presentation in place. No chapters or navigators are reposted."""
import argparse,json,os,time
from pathlib import Path
from dotenv import load_dotenv
from manhwa.__main__ import database
from manhwa.telegram import Telegram
from manhwa.seo import public_metadata,channel_title,bio,chapter_caption
from manhwa.channel_setup import refresh_navigation

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    load_dotenv(ROOT/'.env');store=database();tg=Telegram(os.environ['TELEGRAM_BOT_TOKEN'])
    backup=[]
    for sub in store.subs.find():
        old=tg.call('getChat',{'chat_id':sub['channel']})
        meta=public_metadata(sub['metadata'],sub['_id'])
        backup.append({'subscription':sub['_id'],'metadata':sub['metadata'],'title':old.get('title'),'description':old.get('description')})
        print(sub['_id'],channel_title(meta), 'bio:',len(bio(meta)),flush=True)
        if not args.apply:continue
        (ROOT/'tmp/presentation-backup.json').write_text(json.dumps(backup,ensure_ascii=False,indent=2))
        store.subs.update_one({'_id':sub['_id']},{'$set':{'metadata':meta}})
        for method,key,value in [('setChatTitle','title',channel_title(meta)),('setChatDescription','description',bio(meta))]:
            if old.get(key)!=value:tg.call(method,{'chat_id':sub['channel'],key:value});time.sleep(.4)
        # Refresh visible entry and latest examples; historical chapter IDs remain authoritative.
        first=store.jobs.find_one({'subscription':sub['_id'],'status':'sent','sent_parts.0':{'$exists':True}},sort=[('volume',1),('number',1)])
        last=store.jobs.find_one({'subscription':sub['_id'],'status':'sent','sent_parts.0':{'$exists':True}},sort=[('volume',-1),('number',-1)])
        unique={j['_id']:j for j in (first,last) if j}
        for job in unique.values():
            parts=job['sent_parts']
            for i,part in enumerate(parts):
                label=f' · Часть {i+1}/{len(parts)}' if len(parts)>1 else ''
                tg.call('editMessageCaption',{'chat_id':sub['channel'],'message_id':part['message_id'],
                    'caption':chapter_caption(meta,str(job['number']),label),'parse_mode':'HTML'})
                time.sleep(.5)
    if args.apply:
        refresh_navigation(store,tg,force=True)
        print('All 8 channel navigators refreshed in place',flush=True)

if __name__=='__main__':main()
