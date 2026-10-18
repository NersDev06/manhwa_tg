"""A middle-page crop for review, using whitespace separators as panel hints."""
from pathlib import Path
import subprocess
import sys
from PIL import Image, ImageStat, ImageChops


def crop_preview(raw, target):
    # Keep the decoder in a subprocess in production, just like PDF conversion.
    with Image.open(raw) as source:
        if source.width * source.height > 16_000_000:
            raise ValueError('Image pixel limit exceeded')
        image = source.convert('RGB')
    small = image.copy()
    small.thumbnail((160, 4000))
    width, height = small.size
    rows = []
    for y in range(height):
        row = small.crop((0, y, width, y + 1))
        stat = ImageStat.Stat(row)
        rows.append((min(stat.mean) > 244 and max(stat.stddev) < 14) or
                    (max(stat.mean) < 18 and max(stat.stddev) < 10))
    spans, start = [], None
    for y, blank in enumerate(rows + [True]):
        if not blank and start is None:
            start = y
        if blank and start is not None:
            if y - start >= 35:
                spans.append((start, y))
            start = None
    # Prefer a substantial panel near the page centre; fallback is a central square.
    centre = height / 2
    spans = [span for span in spans if span[1] - span[0] >= max(35, width * 0.5)] or spans
    a, b = min(spans, key=lambda span: abs((span[0] + span[1]) / 2 - centre)) if spans else (0, height)
    scale = image.height / height
    top, bottom = int(a * scale), int(b * scale)
    # Keep the selected panel intact; crop margins, never zoom into a square.
    panel = image.crop((0, top, image.width, bottom))
    ink = ImageChops.difference(panel, Image.new('RGB', panel.size, 'white')).convert('L').point(lambda value: 255 if value > 20 else 0).getbbox()
    if ink:
        panel = panel.crop(ink)
    # Telegram photos accept at most 20:1; padding preserves unusually tall panels.
    if panel.height > panel.width * 20:
        canvas = Image.new('RGB', ((panel.height + 19) // 20, panel.height), 'white')
        canvas.paste(panel, ((canvas.width - panel.width) // 2, 0))
        panel = canvas
    panel.thumbnail((1000, 1800))
    panel.save(target, 'JPEG', quality=92)
    return Path(target)


def build_preview(source, chapter_url, folder):
    pages = source.pages(chapter_url)
    raw = Path(folder) / 'preview.raw'
    with source.get(pages[len(pages)//2], stream=True) as response, raw.open('wb') as out:
        size = 0
        for block in response.iter_content(65536):
            size += len(block)
            if size > 30_000_000:
                raise ValueError('Preview download too large')
            out.write(block)
    target = Path(folder) / 'preview.jpg'
    subprocess.run([sys.executable, '-m', 'manhwa.preview', str(raw), str(target)], check=True, timeout=120)
    raw.unlink()
    return target


if __name__ == '__main__':
    crop_preview(sys.argv[1], sys.argv[2])


def from_cached_pages(folder):
    """Reuse the PDF's downloaded pages; no second request to the source."""
    folder = Path(folder)
    pages = sorted(folder.glob('page-*-*.jpg'))
    if not pages:
        raise ValueError('No downloaded pages for chapter preview')
    target = folder / 'preview.jpg'
    subprocess.run([sys.executable, '-m', 'manhwa.preview', str(pages[len(pages)//2]), str(target)],
                   check=True, timeout=120, capture_output=True)
    return target
