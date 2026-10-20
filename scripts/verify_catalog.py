"""Read-only HTTP verification of public SEO and private control boundaries."""
import argparse,json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]

def check(base):
    titles=json.loads((ROOT/'dashboard/data/titles.json').read_text())
    def page(path):
        r=requests.get(base+path,timeout=60)
        assert r.status_code==200,(path,r.status_code)
        return r,BeautifulSoup(r.text,'html.parser')
    r,home=page('/catalog')
    assert home.select_one('meta[name=robots]')['content']=='index, follow'
    assert len(home.select('h1'))==1
    assert len(home.select('.lib-book-card'))==8
    assert home.select_one('link[rel=canonical]')['href']=='https://manhwa-frame.vercel.app/catalog'
    for marker in ['MONGODB_URI','TELEGRAM_BOT_TOKEN','sent_parts','preview_receipt','file_id']:
        assert marker not in r.text,marker
    for book in titles:
        assert book['subscription'] not in r.text,'Private subscription ID in public payload'
    total=0;headings=set()
    def title_check(book):
        r,soup=page('/catalog/'+book['slug'])
        assert soup.select_one('meta[name=robots]')['content']=='index, follow'
        assert soup.select_one('h1').get_text()==book['title']
        assert soup.select_one('link[rel=canonical]')['href']=='https://manhwa-frame.vercel.app/catalog/'+book['slug']
        scripts=soup.select('script[type="application/ld+json"]')
        assert scripts
        for script in scripts:json.loads(script.string)
        links=soup.select('.lib-chapter>a')
        assert links
        assert all(a['href'].startswith(book['channel']+'/') for a in links)
        image=requests.get(base+book['cover'],timeout=30)
        assert image.status_code==200 and image.headers['Content-Type'].startswith('image/')
        return len(links),soup.title.get_text()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for count,title in pool.map(title_check,titles):total+=count;headings.add(title)
    assert len(headings)==8
    root=requests.get(base+'/',timeout=30)
    soup=BeautifulSoup(root.text,'html.parser')
    assert 'noindex' in soup.select_one('meta[name=robots]')['content']
    for path in ['/api/state','/api/jobs']:
        assert requests.get(base+path,timeout=30).status_code==401
    assert requests.post(base+'/api/control',json={'paused':True},timeout=30).status_code==401
    robots=requests.get(base+'/robots.txt',timeout=30)
    assert 'Disallow: /api/' in robots.text and 'Sitemap: https://manhwa-frame.vercel.app/sitemap.xml' in robots.text
    sitemap=requests.get(base+'/sitemap.xml',timeout=30)
    xml=BeautifulSoup(sitemap.text,'xml')
    assert len(xml.find_all('loc'))==10
    for path in ['/catalog/og/library','/catalog/og/ubiytsa-peter']:
        r=requests.get(base+path,timeout=60)
        assert r.status_code==200 and r.headers['Content-Type'].startswith('image/png')
    assert requests.get(base+'/catalog/nonexistent-book',timeout=30).status_code==404
    print('Verified: 8 titles,',total,'public chapter links, 10 sitemap URLs; private APIs remain protected')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--base',required=True);args=parser.parse_args();check(args.base.rstrip('/'))
