"""Re-export the approved 84 tiles without changing their order or framing.

Requires Pillow. The source is pinned to the last approved asset in Git;
repeated exports never sharpen an already processed image.
This is conservative resampling, not recovery of missing source detail.
"""
import io
import subprocess
from pathlib import Path
from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
ASSET = 'frontend/public/images/reference/exercise-premium-sprite.webp'
SOURCE = 'a8f888522dc0ba836ecfe2f18843087b8faf0f74'
TILE = 192  # 84 * 192 = 16128, within WebP's dimension limit.


def export():
    data = subprocess.check_output(['git', 'show', f'{SOURCE}:{ASSET}'], cwd=ROOT)
    source = Image.open(io.BytesIO(data)).convert('RGB')
    assert source.size == (48, 48 * 84)
    atlas = Image.new('RGB', (TILE, TILE * 84))
    for slot in range(84):
        tile = source.crop((0, slot * 48, 48, (slot + 1) * 48))
        tile = tile.resize((TILE, TILE), Image.Resampling.LANCZOS)
        tile = tile.filter(ImageFilter.UnsharpMask(radius=2, percent=65, threshold=3))
        atlas.paste(tile, (0, slot * TILE))
    destination = ROOT / ASSET
    atlas.save(destination, 'WEBP', quality=95, method=6)
    decoded = Image.open(destination)
    decoded.load()  # Validate the entire bitstream, not just its header.
    assert decoded.size == (TILE, TILE * 84)
    assert destination.stat().st_size < 512_000
    print(f'Validated 84 tiles: {decoded.size}, {destination.stat().st_size} bytes')


if __name__ == '__main__':
    export()
