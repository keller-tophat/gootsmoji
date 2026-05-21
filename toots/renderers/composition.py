"""Compositional renderers that arrange other renderers' output."""

import contextlib
import io
import random
import sys

from PIL import Image

from .. import primitives, registry


def capture(fetch, style_name, name, size):
    """Run a tileable renderer with stdout captured; return the lines."""
    if style_name not in registry.TILE:
        raise ValueError(f"{style_name} is not tileable")

    buf = io.StringIO()
    sys.stdout.flush()
    with contextlib.redirect_stdout(buf):
        registry.STYLES[style_name](fetch, name, size)

    return buf.getvalue().rstrip("\n").splitlines()


@registry.style(tile=False)
def render_mosaic(fetch, name, size):
    half = max(8, size // 2)
    s = random.sample(sorted(registry.TILE), 4)
    a, b, c, d = (capture(fetch, x, name, half) for x in s)
    for x, y in zip(a, b):
        print(x + y)
    for x, y in zip(c, d):
        print(x + y)


def _tile_grid(fetch, name, size, n):
    """Tile `name` n*n times, then resize so halfblock hits 2*size cells wide."""
    tile_px = max(8, 2 * size // n)
    tile = fetch(name, tile_px, tile_px, "RGB")
    canvas = Image.new("RGB", (n * tile_px, n * tile_px))
    for j in range(n):
        for i in range(n):
            canvas.paste(tile, (i * tile_px, j * tile_px))

    sys.stdout.write(
        primitives.halfblock_text(canvas.resize((2 * size, 2 * size)))
    )


@registry.style(tile=False, colored=True)
def render_stamp(fetch, name, size):
    _tile_grid(fetch, name, size, 3)


@registry.style(tile=False, colored=True)
def render_filmstrip(fetch, name, size):
    for s in (size, max(4, size // 2), max(4, size // 4)):
        sys.stdout.write(
            primitives.halfblock_text(fetch(name, 2 * s, 2 * s, "RGB"))
        )


@registry.style(tile=False)
def render_flipbook(fetch, name, size):
    small = max(8, size // 3)
    styles = random.sample(sorted(registry.TILE), 9)
    tiles = [capture(fetch, st, name, small) for st in styles]
    rows = min(len(t) for t in tiles)
    for row in range(3):
        for ln in range(rows):
            print("".join(tiles[row * 3 + col][ln] for col in range(3)))


@registry.style(tile=False, colored=True)
def render_recurse(fetch, name, size):
    _tile_grid(fetch, name, size, 9)
