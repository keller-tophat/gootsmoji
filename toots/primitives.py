"""Small helpers shared by every renderer: ANSI escapes, grid walkers, animation."""

import sys
import time

from PIL import Image

from . import data

# SGR reset; emitted once per row so cells themselves don't have to.
RESET = "\033[0m"

# Use this instead of bare "  " when an empty cell sits next to a colored one,
# otherwise the terminal will fill the gap with the previous cell's bg color.
BLANK = RESET + "  "


def load(fetch, name, size, mode="RGB"):
    """Fetch a size x size goot; return (image, pixel access)."""
    img = fetch(name, size, size, mode)

    return img, img.load()


def bg(r, g, b):
    """Two-cell truecolor swatch. No trailing reset; row writer emits one."""
    return f"\033[48;2;{r};{g};{b}m  "


def bg256(r, g, b):
    """Two-cell swatch quantized to the 256-color xterm cube."""
    return f"\033[48;5;{rgb_to_ansi_256(r, g, b)}m  "


def bg16(idx):
    """Two-cell swatch for one of the 16 standard ANSI colors."""
    code = 40 + idx if idx < 8 else 100 + idx - 8

    return f"\033[{code}m  "


def rgb_to_ansi_256(r, g, b):
    """Quantize an (r, g, b) triple to an xterm 256-color index.

    Pure grays land in the 232..255 grayscale ramp; everything else maps into
    the 6x6x6 color cube starting at index 16.
    """
    if r == g == b:
        return 232 + int((r / 255) * 23)

    return 16 + (r // 51) * 36 + (g // 51) * 6 + (b // 51)


def lerp(a, b, t):
    """Linearly interpolate two RGB triples at t in [0, 1]."""
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(stops, t):
    """Sample a piecewise-linear gradient defined by RGB `stops` at t in [0, 1]."""
    if t >= 1:
        return stops[-1]
    pos = t * (len(stops) - 1)
    i = int(pos)

    return lerp(stops[i], stops[i + 1], pos - i)


def char_lut(chars):
    """256-entry lookup mapping a luma byte to one glyph from `chars`."""
    last = len(chars) - 1

    return [chars[i * last // 255] for i in range(256)]


def lut_grid(img, lut):
    """Render an "L"-mode image by indexing a 256-entry string LUT.

    Faster than `paint_frame` when output depends only on luma: one C-level
    `tobytes()` and a pure list build with no Python-level callbacks.
    """
    buf = img.tobytes()
    w, h = img.width, img.height
    out = []
    for y in range(h):
        row = buf[y * w : (y + 1) * w]
        out.extend(lut[b] for b in row)
        out.append(RESET + "\n")
    sys.stdout.write("".join(out))


def bg_grid(img):
    """Render an "RGB" image as truecolor bg cells, inlined for speed."""
    buf = img.tobytes()
    w, h = img.width, img.height
    out = []
    for y in range(h):
        base = y * w * 3
        for x in range(w):
            i = base + x * 3
            out.append(f"\033[48;2;{buf[i]};{buf[i + 1]};{buf[i + 2]}m  ")
        out.append(RESET + "\n")
    sys.stdout.write("".join(out))


def palette_grid(img, palette, bg_strings=None):
    """Quantize an "RGB" image to `palette` and emit per-index bg strings.

    Pillow's C quantizer is orders of magnitude faster than a per-pixel
    nearest-neighbor loop. `bg_strings` defaults to truecolor swatches; pass
    custom strings (e.g. `bg16(i)`) for ANSI-indexed palettes.
    """
    if bg_strings is None:
        bg_strings = [bg(*c) for c in palette]
    # Pillow requires a 256-entry palette. Pad the tail with palette[-1]
    # (not zeros) so any stray index lands on a real color rather than black
    # -- matters for palettes without black, like ROYGBIV. With padding,
    # every index is in range so the inner loop needs no clamp.
    flat = [v for c in palette for v in c]
    flat.extend(palette[-1] * ((768 - len(flat)) // 3))
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(flat)
    q = img.quantize(palette=pal_img, dither=0)

    buf = q.tobytes()
    w, h = q.width, q.height
    out = []
    for y in range(h):
        row = buf[y * w : (y + 1) * w]
        out.extend(bg_strings[b] for b in row)
        out.append(RESET + "\n")
    sys.stdout.write("".join(out))


def paint_frame(w, h, cell):
    """Walk a w x h grid row-major and write `cell(x, y)` for each position."""
    out = []
    for y in range(h):
        for x in range(w):
            out.append(cell(x, y))
        out.append(RESET + "\n")
    sys.stdout.write("".join(out))


def halfblock_text(img):
    """Render `img` as half-block glyphs, packing two image rows per terminal row.

    Walks `tobytes()` directly: one C-level copy plus integer indexing beats
    `getpixel` by ~10x on the inner loop.
    """
    w, h = img.width, img.height
    buf = img.tobytes()
    stride = w * 3
    pad = bytes(stride)  # virtual all-black row when h is odd
    out = []
    for y in range(0, h, 2):
        top = buf[y * stride : (y + 1) * stride]
        bot = buf[(y + 1) * stride : (y + 2) * stride] if y + 1 < h else pad
        for i in range(0, stride, 3):
            out.append(
                f"\033[38;2;{top[i]};{top[i+1]};{top[i+2]};"
                f"48;2;{bot[i]};{bot[i+1]};{bot[i+2]}m▀"
            )
        out.append(RESET + "\n")

    return "".join(out)


def ascii_filter(fetch, name, size, op, chars=data.ASCII_RAMP):
    """Apply a PIL `op` to the grayscale goot and print it through a char ramp."""
    lut_grid(op(fetch(name, 2 * size, size, "L")), char_lut(chars))


def animate(rows, frames, delay, draw):
    """Cursor-up redraw loop; `draw(frame)` must emit exactly `rows` lines.

    Deadline scheduling keeps slow draws from compounding into ever-later
    frames. If we fall a whole frame behind, the deadline snaps to now.
    """
    deadline = time.monotonic()
    for f in range(frames):
        if f:
            sys.stdout.write(f"\033[{rows}A")
        draw(f)
        sys.stdout.flush()
        deadline += delay
        now = time.monotonic()
        if deadline < now:
            deadline = now
        else:
            time.sleep(deadline - now)
