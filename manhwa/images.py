"""Convert one original image per process; preserve its full reading canvas."""
import sys
import warnings
from pathlib import Path
from PIL import Image

MAX_PIXELS = 16_000_000


def tile_image(raw, folder, prefix):
    # Keep the original long-strip aspect ratio; no speech balloons are cut.
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(raw) as image:
            if image.width * image.height > MAX_PIXELS:
                raise ValueError('Source image exceeds safe pixel limit')
            with image.convert('RGB') as rgb:
                rgb.save(Path(folder) / f'{prefix}-00000.jpg', 'JPEG', quality=90)
            image.close()
    return 1


if __name__ == '__main__':
    tile_image(*sys.argv[1:])
