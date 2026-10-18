from PIL import Image, ImageDraw
import pytest
from manhwa.images import tile_image


def test_original_long_canvas_preserved(tmp_path):
    original = tmp_path / 'input.png'
    with Image.new('RGB', (200, 1700), 'white') as image:
        ImageDraw.Draw(image).rectangle((0, 0, 199, 500), fill='red')
        image.save(original)
    assert tile_image(original, tmp_path, 'page') == 1
    with Image.open(tmp_path / 'page-00000.jpg') as image:
        assert image.size == (200, 1700)
        assert image.getpixel((100, 100))[0] > 240
        assert min(image.getpixel((100, 1600))) > 240


def test_oversized_image_fails_before_conversion(monkeypatch, tmp_path):
    original = tmp_path / 'input.png'
    with Image.new('RGB', (20, 20)) as image:
        image.save(original)
    monkeypatch.setattr('manhwa.images.MAX_PIXELS', 100)
    with pytest.raises(ValueError):
        tile_image(original, tmp_path, 'page')
    assert not list(tmp_path.glob('page-*.jpg'))


def test_jpeg_preserves_original_compressed_image_without_reencoding(tmp_path):
    raw=tmp_path/'original.jpg'
    with Image.new('RGB',(600,1800),(100,150,180)) as image:
        image.save(raw,'JPEG',quality=83)
    tile_image(raw,tmp_path,'page')
    assert (tmp_path/'page-00000.jpg').read_bytes()==raw.read_bytes()
