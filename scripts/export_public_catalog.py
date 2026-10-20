"""Export an allowlist-only resilience snapshot. No tokens, file IDs or private stats."""
from pathlib import Path
import json
from dotenv import load_dotenv
from manhwa.__main__ import database

ROOT=Path(__file__).resolve().parents[1]

def export(store):
    titles=json.loads((ROOT/'dashboard/data/titles.json').read_text())
    result=[]
    for title in titles:
        sub=store.subs.find_one({'_id':title['subscription']}) or {}
        chapters=[]
        for job in store.jobs.find({'subscription':title['subscription'],'status':'sent'},
                {'number':1,'volume':1,'sent_parts.message_id':1,'sent_at':1}).sort([('volume',1),('number',1)]):
            urls=[title['channel']+'/'+str(p['message_id']) for p in job.get('sent_parts',[]) if isinstance(p.get('message_id'),int) and p['message_id']>0]
            if urls: chapters.append({'number':str(job['number']),'volume':job['volume'],'urls':urls,'at':job['sent_at'].isoformat() if job.get('sent_at') else None})
        result.append({'slug':title['slug'],'chapters':chapters,'checkedAt':sub.get('checked').isoformat() if sub.get('checked') else None})
    return result

if __name__=='__main__':
    load_dotenv(ROOT/'.env')
    result=export(database())
    (ROOT/'dashboard/data/library-snapshot.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
    print('Public chapters exported:',sum(len(x['chapters']) for x in result))
