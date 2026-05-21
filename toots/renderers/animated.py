"""Animated renderers: cursor-up redraw loops, scrolls, transitions, particle effects."""

import colorsys
import math
import random
import sys
import time

from .. import cache, data, primitives, registry


def _plot(w, h, points):
    """Paint a frame from an iterable of (x, y, bg_str); clip out-of-bounds."""
    canvas = [[primitives.BLANK] * w for _ in range(h)]
    for x, y, s in points:
        if 0 <= x < w and 0 <= y < h:
            canvas[y][x] = s
    primitives.paint_frame(w, h, lambda x, y: canvas[y][x])


def _typewrite(img, draw_cell, end_of_row):
    """Per-row deadline-scheduled write loop."""
    delay = 1.0 / img.height
    deadline = time.monotonic()
    for y in range(img.height):
        for x in range(img.width):
            sys.stdout.write(draw_cell(x, y))
        sys.stdout.write(end_of_row)
        sys.stdout.flush()
        deadline += delay
        slack = deadline - time.monotonic()
        if slack > 0:
            time.sleep(slack)


def _frame_animate(w, h, frames, delay, cell_for):
    """Per frame: build a cell function via cell_for(frame), paint w x h."""
    primitives.animate(
        h,
        frames,
        delay,
        lambda f: primitives.paint_frame(w, h, cell_for(f)),
    )


@registry.style(animated=True)
def render_typewriter(fetch, name, size):
    img = fetch(name, 2 * size, size, "L")
    lut = primitives.char_lut(data.ASCII_RAMP)
    _typewrite(img, lambda x, y: lut[img.getpixel((x, y))], "\n")


@registry.style(animated=True, colored=True)
def render_typewriter_color(fetch, name, size):
    img, px = primitives.load(fetch, name, size)
    _typewrite(
        img, lambda x, y: primitives.bg(*px[x, y]), primitives.RESET + "\n"
    )


@registry.style(animated=True, colored=True)
def render_rainbow(fetch, name, size):
    _, px = primitives.load(fetch, name, size, "L")

    def cell_for(frame):
        def cell(x, y):
            r, g, b = colorsys.hsv_to_rgb(
                ((x + y + frame) % 60) / 60, 1.0, px[x, y] / 255
            )
            return primitives.bg(int(r * 255), int(g * 255), int(b * 255))

        return cell

    _frame_animate(size, size, 20, 0.05, cell_for)


@registry.style(animated=True, colored=True)
def render_glitch(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell_for(_):
        # Pre-shift each row so the cell function is a pure lookup.
        shifts = [
            random.randint(-1, 1) if random.random() < 0.3 else 0
            for _ in range(size)
        ]

        def cell(x, y):
            sx = (x - shifts[y]) % size
            if random.random() < 0.01:
                return primitives.bg(
                    random.randint(0, 255),
                    random.randint(0, 255),
                    random.randint(0, 255),
                )
            return primitives.bg(*px[sx, y])

        return cell

    _frame_animate(size, size, 10, 0.1, cell_for)


@registry.style(animated=True, colored=True)
def render_dissolve(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    cells = [(x, y) for y in range(size) for x in range(size)]
    random.shuffle(cells)
    steps = 24
    per = len(cells) // steps + 1

    def cell_for(step):
        revealed = set(cells[: per * step])
        return lambda x, y: (
            primitives.bg(*px[x, y])
            if (x, y) in revealed
            else primitives.BLANK
        )

    _frame_animate(size, size, steps + 1, 0.04, cell_for)


@registry.style(animated=True, colored=True)
def render_wave(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell_for(frame):
        shifts = [int(2 * math.sin((y + frame) / 4)) for y in range(size)]
        return lambda x, y: primitives.bg(*px[(x - shifts[y]) % size, y])

    _frame_animate(size, size, 20, 0.05, cell_for)


@registry.style(animated=True, colored=True)
def render_shake(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell_for(frame):
        sx = random.randint(-1, 1) if frame < 11 else 0
        sy = random.randint(-1, 1) if frame < 11 else 0

        def cell(x, y):
            cx = max(0, min(size - 1, x + sx))
            cy = max(0, min(size - 1, y + sy))
            return primitives.bg(*px[cx, cy])

        return cell

    _frame_animate(size, size, 17, 0.06, cell_for)


@registry.style(animated=True, colored=True)
def render_zoom(fetch, name, size):
    src = fetch(name, size, size, "RGB")
    steps = list(range(max(2, size // 8), size + 1, max(1, size // 8)))
    delay = 1.0 / max(1, len(steps))
    for i, s in enumerate(steps):
        if i:
            sys.stdout.write(f"\033[{steps[i - 1]}A\033[J")
        primitives.bg_grid(src.resize((s, s)))
        sys.stdout.flush()
        time.sleep(delay)


@registry.style(animated=True, colored=True)
def render_pulse(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell_for(frame):
        # Two full->black->full cycles: cos sweeps 0..4*pi across 21 frames,
        # so f starts and ends at 1 and dips to 0 twice in between.
        f = 0.5 + 0.5 * math.cos(frame * math.pi / 5)

        def cell(x, y):
            r, g, b = px[x, y]
            return primitives.bg(int(r * f), int(g * f), int(b * f))

        return cell

    _frame_animate(size, size, 21, 0.05, cell_for)


@registry.style(animated=True, colored=True)
def render_marquee(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell_for(frame):
        shift = frame % size
        return lambda x, y: primitives.bg(*px[(x + shift) % size, y])

    frames = 2 * size
    _frame_animate(size, size, frames, 1.0 / frames, cell_for)


@registry.style(animated=True, colored=True)
def render_scan(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell_for(frame):
        def cell(x, y):
            p = px[x, y]
            if y == frame:
                return primitives.bg(
                    min(255, p[0] + 80),
                    min(255, p[1] + 80),
                    min(255, p[2] + 80),
                )
            return primitives.bg(*p)

        return cell

    frames = size + 4
    _frame_animate(size, size, frames, 1.0 / frames, cell_for)


@registry.style(animated=True, colored=True)
def render_rain(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    drops = [random.randint(0, size - 1) for _ in range(size)]

    def cell_for(_):
        for i in range(size):
            drops[i] = (drops[i] + 1) % size

        def cell(x, y):
            tail = (drops[x] - y) % size
            if tail == 0:
                return primitives.bg(180, 255, 180)
            if tail < 4:
                f = 1 - tail / 4
                return primitives.bg(0, int(180 * f), 0)
            return primitives.bg(*px[x, y])

        return cell

    _frame_animate(size, size, 17, 0.06, cell_for)


@registry.style(animated=True, colored=True)
def render_spin(fetch, name, size):
    src = fetch(name, 2 * size, 2 * size, "RGB")
    # 36 frames * 10 degrees = one full rotation.
    frames = 36
    primitives.animate(
        src.height // 2,
        frames,
        1.0 / frames,
        lambda frame: sys.stdout.write(
            primitives.halfblock_text(src.rotate(frame * 10))
        ),
    )


@registry.style(animated=True, colored=True)
def render_carousel(fetch, name, size):
    pool = cache.list_goots() or [name]
    picks = random.sample(pool, min(5, len(pool)))
    # halfblock collapses 2 image rows into 1 terminal row, so size lines.
    for i, pick in enumerate(picks):
        if i:
            time.sleep(1.0 / len(picks))
            sys.stdout.write(f"\033[{size}A\033[J")
        sys.stdout.write(
            primitives.halfblock_text(fetch(pick, 2 * size, 2 * size, "RGB"))
        )
        sys.stdout.flush()


@registry.style(animated=True, colored=True)
def render_bounce(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    pad = max(4, size // 4)
    canvas_w = size + 2 * pad
    frames = 25
    # (1 - cos) sweeps 0 -> 2 -> 0 across one cycle: the image starts left,
    # bounces to the right edge at the midpoint, returns left at the end.
    step = 2 * math.pi / (frames - 1)

    def cell_for(frame):
        offset = round(pad * (1 - math.cos(frame * step)))

        def cell(x, y):
            ix = x - offset
            return (
                primitives.bg(*px[ix, y])
                if 0 <= ix < size
                else primitives.BLANK
            )

        return cell

    _frame_animate(canvas_w, size, frames, 0.04, cell_for)


@registry.style(animated=True, colored=True)
def render_explode(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    cx, cy = size / 2, size / 2
    pixels = []
    for y in range(size):
        for x in range(size):
            dx, dy = x - cx, y - cy
            d = max(0.5, math.hypot(dx, dy))
            pixels.append((x, y, primitives.bg(*px[x, y]), dx / d, dy / d))

    def draw(frame):
        _plot(
            size,
            size,
            (
                (int(x0 + vx * frame * 0.6), int(y0 + vy * frame * 0.6), s)
                for x0, y0, s, vx, vy in pixels
            ),
        )

    primitives.animate(size, 17, 0.06, draw)


@registry.style(animated=True, colored=True)
def render_assemble(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    targets = [
        (
            random.randint(0, size - 1),
            random.randint(0, size - 1),
            x,
            y,
            primitives.bg(*px[x, y]),
        )
        for y in range(size)
        for x in range(size)
    ]
    frames = 18

    def draw(frame):
        t = frame / frames
        _plot(
            size,
            size,
            (
                (int(sx + (tx - sx) * t), int(sy + (ty - sy) * t), s)
                for sx, sy, tx, ty, s in targets
            ),
        )

    primitives.animate(size, frames + 1, 0.05, draw)


@registry.style(animated=True, colored=True)
def render_sparkle(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    base = [
        [primitives.bg(*px[x, y]) for x in range(size)] for y in range(size)
    ]
    white = primitives.bg(255, 255, 255)

    def cell_for(_):
        sparks = {
            (random.randint(0, size - 1), random.randint(0, size - 1))
            for _ in range(max(1, size // 4))
        }
        return lambda x, y: white if (x, y) in sparks else base[y][x]

    _frame_animate(size, size, 12, 0.08, cell_for)


@registry.style(animated=True, colored=True)
def render_rolodex(fetch, name, size):
    other = random.choice(
        [g for g in cache.list_goots() if g != name] or [name]
    )
    _, a_px = primitives.load(fetch, name, size)
    _, b_px = primitives.load(fetch, other, size)

    def cell_for(split):
        return lambda x, y: primitives.bg(*(b_px if y < split else a_px)[x, y])

    frames = size + 1
    _frame_animate(size, size, frames, 1.0 / frames, cell_for)
