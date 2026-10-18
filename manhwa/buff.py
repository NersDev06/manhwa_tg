"""Verified public full-resolution reader for titles with unusable secondary strips."""
import re
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from .source import SourceError


def pages(source, url):
    match = re.fullmatch(r'https://mangabuff\.ru/manga/([^/]+)/(\d+)/(\d+(?:\.\d+)?)/?', url)
    if not match:
        raise SourceError('Unexpected full-resolution reader URL')
    with source.get(url) as r:
        soup = BeautifulSoup(r.content, 'html.parser')
    result = []
    for image in soup.select('.reader__item img'):
        label = image.get('alt', '')
        identity = re.search(r'том\s+(\d+)\s+глава\s+(\d+(?:\.\d+)?)\s+страница', label, re.I)
        if not identity or identity[1] != match[2] or identity[2] != match[3]:
            raise SourceError('Reader chapter identity does not match requested chapter')
        target = urljoin(url, image.get('data-src') or image.get('src', ''))
        if urlparse(target).scheme != 'https' or urlparse(target).netloc not in {'c2.mangabuff.ru','c3.mangabuff.ru','img.mangabuff.ru','custom.mangabuff.ru'}:
            raise SourceError('Unexpected full-resolution image host')
        result.append(target)
    if not result:
        raise SourceError('Full-resolution reader images missing')
    return result


def listed_chapters(source, title_url):
    """Supplement a full catalogue with public chapter links (including bonus releases)."""
    from .source import Chapter
    with source.get(title_url) as r:
        soup = BeautifulSoup(r.content, 'html.parser')
    result = []
    for a in soup.select('a.chapters__item[href]'):
        target = urljoin(title_url, a['href'])
        m = re.fullmatch(re.escape(title_url) + r'/(\d+)/(\d+(?:\.\d+)?)/?', target)
        if m:
            result.append(Chapter(target, 'Глава ' + m[2], m[1], m[2]))
    return result
