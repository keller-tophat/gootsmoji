"""Glyph-ramp renderers: ASCII / blocks / dithering / braille / half-block / etc."""

import random
import sys

from PIL import ImageFilter, ImageOps

from .. import data, primitives, registry


# Single-character ramps: bright -> dark. `wide` doubles columns so 2:1 cells
# render at roughly the source aspect ratio.
_RAMPS = {
    "ascii": (data.ASCII_RAMP, True),
    "dense": (data.DENSE_RAMP, True),
    "blocks": (" ░▒▓█", True),
    "binary": (" 01", True),
    "dots": (" ·•●", True),
    "shade": (" ▁▂▃▄▅▆▇█", True),
    "halftone": ("●•∙· ", True),  # inverse of dots: dark pixels grow.
    "morse": (" .-/·", True),
    "crosshatch": ("#X/ ", True),
    "hiragana": (data.HIRAGANA_RAMP, False),  # CJK glyphs are double-width.
}

# PIL transforms feeding the ASCII ramp. Edge-like filters invert the ramp so
# bright glyphs mark edges.
_FILTERS = {
    "edges": (lambda i: i.filter(ImageFilter.FIND_EDGES), True),
    "emboss": (lambda i: i.filter(ImageFilter.EMBOSS), True),
    "contour": (lambda i: i.filter(ImageFilter.CONTOUR), False),
    "mirror": (ImageOps.mirror, False),
    "flip": (ImageOps.flip, False),
    "sharpen": (lambda i: i.filter(ImageFilter.SHARPEN), False),
    "smooth": (lambda i: i.filter(ImageFilter.SMOOTH), False),
    "detail": (lambda i: i.filter(ImageFilter.DETAIL), False),
}


def _def_basic_ramps_and_filters():
    """Import time creation of many basic lut-ramp and filter styles to reduce boilerplate."""

    def _ramp_renderer(ramp, wide):
        """Closure: render `name` as `ramp` glyphs, wide doubling column count."""

        def fn(fetch, name, size):
            w = 2 * size if wide else size
            primitives.lut_grid(
                fetch(name, w, size, "L"), primitives.char_lut(ramp)
            )

        return fn


    def _filter_renderer(xform, invert):
        """Closure: run PIL `xform` then ASCII ramp; invert ramp for edge filters."""
        ramp = data.ASCII_RAMP[::-1] if invert else data.ASCII_RAMP

        def fn(fetch, name, size):
            primitives.ascii_filter(fetch, name, size, xform, ramp)

        return fn


    for _name, (_ramp, _wide) in _RAMPS.items():
        name = _name.upper()
        registry.STYLES[name] = _ramp_renderer(_ramp, _wide)
        registry.TILE.add(name)

    for _name, (_xform, _invert) in _FILTERS.items():
        name = _name.upper()
        registry.STYLES[name] = _filter_renderer(_xform, _invert)
        registry.TILE.add(name)


_def_basic_ramps_and_filters()


@registry.style()
def render_atkinson(fetch, name, size):
    # Atkinson diffuses only 6/8 of the error into a fixed forward neighborhood,
    # giving a lighter, higher-contrast result than PIL's `convert("1")` (FS).
    img = fetch(name, 2 * size, size, "L")
    px = img.load()
    w, h = img.width, img.height
    buf = [[px[x, y] for x in range(w)] for y in range(h)]
    rows = []
    for y in range(h):
        row = []
        for x in range(w):
            old = buf[y][x]
            new = 255 if old > 128 else 0
            err = (old - new) // 8
            row.append("█" if new else " ")
            for dx, dy in data.ATKINSON_OFFSETS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    buf[ny][nx] = max(0, min(255, buf[ny][nx] + err))
        rows.append("".join(row))
    sys.stdout.write("\n".join(rows) + "\n")


@registry.style()
def render_braille(fetch, name, size):
    img = fetch(name, 4 * size, 4 * size, "L").point(
        lambda p: 255 if p > 128 else 0, "1"
    )
    px = img.load()
    w, h = img.width, img.height
    rows = []
    for by in range(0, h, 4):
        row = []
        for bx in range(0, w, 2):
            v = 0
            # Source is 4*size by 4*size so every bx+dx, by+dy is in range.
            for dx, dy, bit in data.BRAILLE_BITS:
                if px[bx + dx, by + dy]:
                    v |= 1 << bit
            row.append(chr(0x2800 + v))
        rows.append("".join(row))

    while rows and rows[0].strip(chr(0x2800)) == "":
        rows.pop(0)
    while rows and rows[-1].strip(chr(0x2800)) == "":
        rows.pop()

    sys.stdout.write("\n".join(rows) + "\n")


@registry.style(colored=True)
def render_halfblock(fetch, name, size):
    sys.stdout.write(
        primitives.halfblock_text(fetch(name, 2 * size, 2 * size, "RGB"))
    )


@registry.style(colored=True)
def render_quadrant(fetch, name, size):
    img = fetch(name, 4 * size, 2 * size, "RGB")
    px = img.load()
    out = []
    for y in range(0, img.height, 2):
        for x in range(0, img.width, 2):
            pixels = [px[x, y], px[x + 1, y], px[x, y + 1], px[x + 1, y + 1]]
            lums = [0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2] for p in pixels]
            mean = sum(lums) / 4
            mask, fg, bg = 0, [], []
            for i, (p, lum) in enumerate(zip(pixels, lums)):
                if lum >= mean:
                    mask |= 1 << i
                    fg.append(p)
                else:
                    bg.append(p)
            fg = fg or bg
            bg = bg or fg
            fr, fgc, fb = (sum(c[i] for c in fg) // len(fg) for i in range(3))
            br, bgc, bb = (sum(c[i] for c in bg) // len(bg) for i in range(3))
            out.append(
                f"\033[38;2;{fr};{fgc};{fb};48;2;{br};{bgc};{bb}m"
                f"{data.QUADRANT_GLYPHS[mask]}"
            )
        out.append(primitives.RESET + "\n")
    sys.stdout.write("".join(out))


@registry.style(colored=True)
def render_rotate(fetch, name, size):
    k = random.choice([1, 2, 3])
    img = fetch(name, 2 * size, 2 * size, "RGB").rotate(90 * k, expand=True)
    sys.stdout.write(primitives.halfblock_text(img))
