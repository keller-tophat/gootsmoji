"""Position-aware, spatial-filter, and geometry renderers."""

import colorsys
import math
import sys

from PIL import Image, ImageFilter, ImageOps

from .. import data, primitives, registry


@registry.style(colored=True)
def render_chroma(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell(x, y):
        return primitives.bg(
            px[max(0, x - 1), y][0],
            px[x, y][1],
            px[min(size - 1, x + 1), y][2],
        )

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_blueprint(fetch, name, size):
    _, px = primitives.load(fetch, name, size, "L")

    def cell(x, y):
        c = primitives.gradient(data.CYAN_STOPS, px[x, y] / 255)
        if x % 4 == 0 or y % 4 == 0:
            c = tuple(int(v * 0.7) for v in c)
        return primitives.bg(*c)

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_vignette(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    cx, cy = size / 2, size / 2
    max_d = math.hypot(cx, cy)

    def cell(x, y):
        p = px[x, y]
        f = max(0.1, 1 - (math.hypot(x - cx, y - cy) / max_d) ** 2)
        return primitives.bg(int(p[0] * f), int(p[1] * f), int(p[2] * f))

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_radial(fetch, name, size):
    _, px = primitives.load(fetch, name, size, "L")
    cx, cy = size / 2, size / 2

    def cell(x, y):
        angle = (math.atan2(y - cy, x - cx) / (2 * math.pi)) + 0.5
        r, g, b = colorsys.hsv_to_rgb(angle, 1.0, px[x, y] / 255)
        return primitives.bg(int(r * 255), int(g * 255), int(b * 255))

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_scan_lines(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell(x, y):
        p = px[x, y]
        f = 0.5 if y % 2 else 1.0
        return primitives.bg(int(p[0] * f), int(p[1] * f), int(p[2] * f))

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_crt(fetch, name, size):
    # CHROMA + scan lines in a single pass.
    _, px = primitives.load(fetch, name, size)

    def cell(x, y):
        f = 0.6 if y % 2 else 1.0
        r = px[max(0, x - 1), y][0]
        g = px[x, y][1]
        b = px[min(size - 1, x + 1), y][2]
        return primitives.bg(int(r * f), int(g * f), int(b * f))

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_outline(fetch, name, size):
    color, px = primitives.load(fetch, name, size)
    epx = color.convert("L").filter(ImageFilter.FIND_EDGES).load()

    # BLANK resets bg before the empty cell so the previous edge's colour
    # doesn't bleed across the gap.
    def cell(x, y):
        return primitives.bg(*px[x, y]) if epx[x, y] > 60 else primitives.BLANK

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_pixelate(fetch, name, size):
    chunky = max(4, size // 4)
    img = fetch(name, chunky, chunky, "RGB").resize(
        (size, size), Image.NEAREST
    )
    primitives.bg_grid(img)


@registry.style(colored=True)
def render_motion_blur(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell(x, y):
        r = g = b = 0
        for dx in (-2, -1, 0, 1, 2):
            sp = px[max(0, min(size - 1, x + dx)), y]
            r += sp[0]
            g += sp[1]
            b += sp[2]
        return primitives.bg(r // 5, g // 5, b // 5)

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_glow(fetch, name, size):
    img, px = primitives.load(fetch, name, size)
    bpx = img.filter(ImageFilter.GaussianBlur(3)).load()

    def cell(x, y):
        p = px[x, y]
        b = bpx[x, y]
        return primitives.bg(
            min(255, p[0] + b[0] // 2),
            min(255, p[1] + b[1] // 2),
            min(255, p[2] + b[2] // 2),
        )

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_oil_paint(fetch, name, size):
    img = fetch(name, size, size, "RGB").filter(ImageFilter.MedianFilter(5))
    img = ImageOps.posterize(img, 3)
    primitives.bg_grid(img)


@registry.style(colored=True)
def render_pixelsort(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    out = []
    for y in range(size):
        row = [px[x, y] for x in range(size)]
        row.sort(key=lambda p: 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2])
        for p in row:
            out.append(primitives.bg(*p))
        out.append(primitives.RESET + "\n")
    sys.stdout.write("".join(out))


@registry.style(colored=True)
def render_tilt(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    out = []
    for y in range(size):
        row = [px[x, y] for x in range(size)]
        shift = (y - size // 2) // 3
        # Negative shifts roll right (tail prepended), positive roll left.
        if shift:
            row = row[shift:] + row[:shift]
        for p in row:
            out.append(primitives.bg(*p))
        out.append(primitives.RESET + "\n")
    sys.stdout.write("".join(out))


@registry.style(colored=True)
def render_shear(fetch, name, size):
    img = fetch(name, size, size, "RGB").transform(
        (size, size),
        Image.AFFINE,
        (1, 0, 0, 0.3, 1, -size * 0.15),
        Image.BILINEAR,
    )
    primitives.bg_grid(img)
