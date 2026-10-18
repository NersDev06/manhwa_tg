"""Retain prepared chapters across retries; receipts remain authoritative in MongoDB."""
import json
import os
from contextlib import contextmanager
from pathlib import Path
import shutil
from .pdf import build_chapter

@contextmanager
def prepared(source, job):
    root = Path(os.environ.get('MANHWA_SPOOL', 'tmp/spool'))
    folder = root / str(job['_id'])
    folder.mkdir(parents=True, exist_ok=True)
    manifest = folder / 'manifest.json'
    cached = None
    if manifest.exists():
        try:
            value = json.loads(manifest.read_text())
            paths = [folder / p for p in value['files']]
            if value['chapter_url'] == job['chapter_url'] and all(p.parent == folder and p.is_file() and p.stat().st_size for p in paths) and paths:
                cached = paths, value['stats']
        except (ValueError, KeyError, OSError):
            pass
    if cached is None:
        cached = build_chapter(source, job['chapter_url'], folder)
        paths, stats = cached
        temp = manifest.with_suffix('.tmp')
        temp.write_text(json.dumps({'chapter_url': job['chapter_url'], 'files': [p.name for p in paths], 'stats': stats}))
        temp.replace(manifest)
    yield folder, cached

def clean(job):
    shutil.rmtree(Path(os.environ.get('MANHWA_SPOOL', 'tmp/spool')) / str(job['_id']), ignore_errors=True)
