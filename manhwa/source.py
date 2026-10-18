from dataclasses import dataclass
from decimal import Decimal
import re
import time
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = 'https://manga-shi.org'


class SourceError(RuntimeError):
    pass


@dataclass(frozen=True)
class Chapter:
    url: str
    name: str
    volume: str
    number: str

    @property
    def order(self):
        return Decimal(self.volume), Decimal(self.number)


class MangaShi:
    def __init__(self, interval=0.6):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0', 'Referer': BASE + '/'})
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.interval, self.last_request = interval, 0.0

    def get(self, url, **kwargs):
        time.sleep(max(0, self.interval - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        response = self.session.get(url, timeout=(15, 60), **kwargs)
        response.raise_for_status()
        return response

    @staticmethod
    def title_url(url):
        url = urljoin(BASE, url)
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.netloc != 'manga-shi.org':
            raise SourceError('Expected a MangaShi URL')
        match = re.fullmatch(r'/manga/([^/]+)/?', parsed.path)
        if not match:
            raise SourceError('Expected /manga/title/ URL')
        return BASE + '/manga/' + match[1] + '/'

    def search(self, query):
        with self.get(BASE + '/catalog/', params={'q': query}) as r:
            soup = BeautifulSoup(r.text, 'html.parser')
        grid = soup.select_one('#manga-grid')
        if grid is None:
            raise SourceError('Catalog markup missing')
        return [{'title': (a.select_one('h3, h4, .title') or a).get_text(' ', strip=True),
                 'url': urljoin(BASE, a['href'])}
                for a in grid.select(':scope > a[href*="/manga/"]')]

    def chapters(self, url):
        url = self.title_url(url)
        with self.get(url) as r:
            soup = BeautifulSoup(r.text, 'html.parser')
        h1 = soup.select_one('h1')
        listing = soup.select_one('#chapters-list')
        if h1 is None or listing is None:
            raise SourceError('Title or chapters markup missing')
        title = h1.get_text(' ', strip=True)
        chapters = {}
        seen = set()
        current = url
        fragment = soup
        while True:
            links = fragment.select('#chapters-list > a[href*="/glava"]') if not seen else fragment.select('a[href*="/glava"]')
            for a in links:
                name = a.select_one('span.chapter-title')
                href = urljoin(BASE, a.get('href', ''))
                match = re.search(r'/(?:tom[-_](\d+)/)?glava[-_](\d+(?:[-_,.]\d+)?)/?$', urlparse(href).path)
                if name is None or not match:
                    continue
                label = name.get_text(' ', strip=True)
                label_number = re.search(r'(?:Глава|Chapter)\s*(\d+(?:[.,]\d+)?)', label, re.I)
                number = (label_number[1] if label_number else match[2]).replace(',', '.').replace('-', '.').replace('_', '.')
                chapters[href] = Chapter(href, label, match[1] or '0', number)
            next_link = fragment.select_one('#chapters-load-more a[hx-get]') if not seen else None
            if next_link:
                next_url = next_link['hx-get']
            else:
                next_link = next((a for a in fragment.select('nav.flex a[href]')
                                  if 'Дальше' in a.get_text()), None)
                next_url = next_link['href'] if next_link else None
            if not next_url:
                break
            current = urljoin(current, next_url)
            if urlparse(current).netloc != 'manga-shi.org' or current in seen or len(seen) > 2000:
                raise SourceError('Invalid chapter pagination')
            seen.add(current)
            with self.get(current) as r:
                fragment = BeautifulSoup(r.text, 'html.parser')
            if not fragment.select('a[href*="/glava"]'):
                raise SourceError('Empty chapter pagination response')
        if not chapters:
            raise SourceError('No readable chapters found')
        return title, sorted(chapters.values(), key=lambda c: (c.order, c.url))

    def pages(self, url):
        if not url.startswith(BASE + '/manga/'):
            raise SourceError('Unexpected chapter URL')
        with self.get(url) as r:
            soup = BeautifulSoup(r.text, 'html.parser')
        pages = [urljoin(url, img.get('data-src') or img.get('src', ''))
                 for img in soup.select('img.reader-image')]
        if not pages or any(urlparse(p).scheme != 'https' for p in pages):
            raise SourceError('Missing reader images')
        return pages
