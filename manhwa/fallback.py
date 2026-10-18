"""Public secondary reader, with explicit title mapping and stable queue identities."""
import json
import re
import time
from pathlib import Path
from decimal import Decimal
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import requests
from .source import MangaShi, Chapter, SourceError, BASE

class ResilientSource(MangaShi):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = json.loads((Path(__file__).resolve().parent.parent / 'config/channels.json').read_text())
        self.readers = {r['url']: (r['reader_url'], str(r.get('reader_volume', '1'))) for r in config if r.get('reader_url')}
        self.store = None
        self.blocked_until = 0
        self.cache = {}
        self.mapping = {row['url']: row['fallback_url'] for row in json.loads(
            (Path(__file__).resolve().parent.parent / 'config/channels.json').read_text()) if row.get('fallback_url')}

    def get(self, url, **kwargs):
        host = urlparse(url).netloc
        if host == 'mangabuff.ru' or host.endswith('.mangabuff.ru'):
            kwargs['headers'] = {**kwargs.get('headers', {}), 'Referer': 'https://mangabuff.ru/'}
        return super().get(url, **kwargs)

    def bind(self, store):
        self.store = store

    def _fallback(self, url):
        title = next((u for u in self.mapping if url.startswith(u)), None)
        if title is None:
            raise SourceError('No verified secondary title mapping')
        return title, self.mapping[title]

    def _catalog(self, title):
        cached = self.cache.get(title)
        if cached and time.monotonic() - cached[0] < 1800:
            return cached[1:]
        _, backup = self._fallback(title)
        with self.get(backup) as r:
            soup = BeautifulSoup(r.content, 'html.parser')
        heading = soup.select_one('h1')
        if heading is None:
            raise SourceError('Secondary title heading missing')
        chapters = {}
        for a in soup.select('a[href*="/glava-"]'):
            target = urljoin('https://wamanga.ru/', a['href'])
            match = re.fullmatch(re.escape(urlparse(backup).path) + r'/glava-(\d+(?:[.,_-]\d+)?)/?', urlparse(target).path)
            if match and urlparse(target).netloc == 'wamanga.ru':
                number = re.sub('[,_-]', '.', match[1])
                if number in chapters and chapters[number].url != target:
                    raise SourceError('Ambiguous secondary chapter number')
                chapters[number] = Chapter(target, 'Глава ' + number, '0', number)
        if not chapters:
            raise SourceError('Secondary chapter listing empty')
        if title in self.readers:
            from .buff import listed_chapters
            try:
                for chapter in listed_chapters(self, self.readers[title][0]):
                    chapters.setdefault(chapter.number, chapter)
            except (requests.RequestException, SourceError):
                pass  # A supplemental source must not discard the complete secondary catalogue.
        self.cache[title] = (time.monotonic(), heading.get_text(' ', strip=True), chapters)
        return self.cache[title][1:]

    def _primary(self, call, url):
        if time.monotonic() < self.blocked_until:
            raise SourceError('Primary source temporarily unavailable')
        try:
            return call(url)
        except (requests.Timeout, requests.ConnectionError):
            self.blocked_until = time.monotonic() + 1800
            raise
        except requests.HTTPError as exc:
            if exc.response is not None and exc.response.status_code in (403, 429, 500, 502, 503, 504):
                self.blocked_until = time.monotonic() + 1800
            raise

    def chapters(self, url):
        try:
            result = self._primary(super().chapters, url)
            if self.store:
                sub = self.store.subs.find_one({'url': url})
                existing = {}
                if sub:
                    for job in self.store.jobs.find({'subscription': sub['_id']}):
                        key = job['number'].to_decimal()
                        if key in existing:
                            raise SourceError('Ambiguous queue chapter number')
                        existing[key] = job
                title, chapters = result
                result = title, [Chapter(existing[Decimal(c.number)]['chapter_url'], existing[Decimal(c.number)]['name'], str(existing[Decimal(c.number)]['volume']), c.number) if Decimal(c.number) in existing else c for c in chapters]
                self.store.subs.update_one({'url': url}, {'$set': {'active_source': 'MangaShi', 'fallback_missing': [], 'source_note': None}})
            return result
        except (requests.RequestException, SourceError):
            title, chapters = self._catalog(url)
            existing = {}
            if self.store:
                sub = self.store.subs.find_one({'url': url})
                if sub:
                    for job in self.store.jobs.find({'subscription': sub['_id']}):
                        key = str(job['number'].to_decimal().normalize())
                        if key in existing:
                            raise SourceError('Ambiguous queue chapter number; manual mapping required')
                        existing[key] = job
            volume = str(next(iter(existing.values()))['volume']) if existing else '0'
            result = []
            for c in chapters.values():
                prior = existing.get(str(Decimal(c.number).normalize()))
                result.append(Chapter(prior['chapter_url'] if prior else c.url,
                    prior['name'] if prior else c.name, str(prior['volume']) if prior else volume, c.number))
            if self.store and sub:
                available = {Decimal(c.number) for c in chapters.values()}
                missing = [str(j['number']) for j in existing.values() if j['number'].to_decimal() not in available]
                self.store.subs.update_one({'_id': sub['_id']}, {'$set': {'active_source': 'MangaBuff' if url in self.readers else 'WaManga', 'fallback_url': self.mapping[url], 'fallback_missing': missing, 'source_note': 'Primary source unavailable; public secondary reader active'}})
            return title, sorted(result, key=lambda c: c.order)

    def pages(self, url):
        from . import buff
        if urlparse(url).netloc == 'mangabuff.ru':
            return buff.pages(self, url)
        for canonical, (reader, volume) in self.readers.items():
            if url.startswith(canonical) or url.startswith(self.mapping.get(canonical, 'INVALID')):
                match = re.search(r'/glava[-_](\d+(?:[.,_-]\d+)?)/?$', urlparse(url).path)
                if not match:
                    raise SourceError('Chapter identity missing')
                number = re.sub('[,_-]', '.', match[1])
                try:
                    return buff.pages(self, reader + '/' + volume + '/' + number)
                except (requests.RequestException, SourceError):
                    if url.startswith(canonical):
                        return self._primary(super().pages, url)
                    _, primary = self._primary(super().chapters, canonical)
                    matches = [c for c in primary if Decimal(c.number) == Decimal(number)]
                    if len(matches) != 1:
                        raise SourceError('Full-resolution chapter unavailable')
                    return self._primary(super().pages, matches[0].url)
        if urlparse(url).netloc != 'wamanga.ru':
            try:
                return self._primary(super().pages, url)
            except (requests.RequestException, SourceError):
                title, _ = self._fallback(url)
                match = re.search(r'/glava[-_](\d+(?:[.,_-]\d+)?)/?$', urlparse(url).path)
                if not match:
                    raise SourceError('Chapter identity missing')
                number = re.sub('[,_-]', '.', match[1])
                _, chapters = self._catalog(title)
                candidates = [c for c in chapters.values() if Decimal(c.number) == Decimal(number)]
                if len(candidates) != 1:
                    raise SourceError('Secondary chapter missing or ambiguous')
                url = candidates[0].url
        if not re.fullmatch(r'https://wamanga\.ru/manhwa/[^/]+/glava-[\d.,_-]+/?', url):
            raise SourceError('Unexpected secondary chapter URL')
        with self.get(url) as r:
            soup = BeautifulSoup(r.content, 'html.parser')
        pages = [urljoin(url, i.get('data-src') or i.get('src', '')) for i in soup.select('img.reader-page')]
        if not pages or any(urlparse(p).scheme != 'https' or urlparse(p).netloc != 'wamanga.ru' for p in pages):
            raise SourceError('Secondary reader images missing or unexpected host')
        return pages

    def metadata(self, url):
        try:
            return self._primary(super().metadata, url)
        except (requests.RequestException, SourceError):
            if self.store:
                sub = self.store.subs.find_one({'url': url}) or {}
                if sub.get('metadata'):
                    return sub['metadata']
            raise SourceError('Original metadata unavailable')
