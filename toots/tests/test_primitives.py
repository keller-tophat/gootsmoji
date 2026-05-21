"""Primitives: ANSI math, grid walkers, animate loop."""

from PIL import Image

from toots import primitives


def test_rgb_to_ansi_256_color_cube():
    # Pure red maps somewhere into the 6x6x6 cube.
    idx = primitives.rgb_to_ansi_256(255, 0, 0)
    assert 16 <= idx <= 231


def test_lut_grid_uses_luma_lookup(capsys):
    img = Image.new("L", (3, 2))
    img.putdata([0, 128, 255, 0, 128, 255])
    lut = ["."] * 256
    lut[0] = "a"
    lut[128] = "b"
    lut[255] = "c"

    primitives.lut_grid(img, lut)

    out = capsys.readouterr().out
    assert "abc" in out
    assert out.count("\n") == 2


def test_palette_grid_quantizes_to_palette(capsys):
    # Palette without black: the output must contain no black swatch even
    # though Pillow pads palettes to 256 entries with zeros.
    img = Image.new("RGB", (4, 4))
    px = img.load()
    for y in range(4):
        for x in range(4):
            px[x, y] = ((x * 31) % 256, (y * 53) % 256, ((x + y) * 17) % 256)

    palette = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    primitives.palette_grid(img, palette)

    out = capsys.readouterr().out
    assert out.count("\n") == 4
    assert primitives.bg(0, 0, 0) not in out


def test_halfblock_text_handles_odd_height():
    img = Image.new("RGB", (1, 3), (10, 20, 30))

    text = primitives.halfblock_text(img)

    # Odd height pads to one extra terminal row.
    assert text.count("\n") == 2
    assert "\u2580" in text  # upper half block


def test_animate_calls_draw_once_per_frame(monkeypatch):
    # `animate(rows, frames, delay, draw)` drives `draw(f)` for f in range(frames).
    monkeypatch.setattr(primitives.time, "sleep", lambda _d: None)
    seen = []

    primitives.animate(rows=3, frames=4, delay=0.01, draw=seen.append)

    assert seen == [0, 1, 2, 3]


def test_animate_catches_up_when_draw_is_slow(monkeypatch):
    # A draw that exceeds the per-frame budget must not accumulate debt:
    # the deadline snaps to `now`, and subsequent sleeps stay non-negative.
    times = iter([0.0, 1.0, 2.0, 3.0])
    monkeypatch.setattr(primitives.time, "monotonic", lambda: next(times))
    sleeps = []
    monkeypatch.setattr(primitives.time, "sleep", sleeps.append)

    primitives.animate(rows=1, frames=3, delay=0.01, draw=lambda _f: None)

    assert sleeps == []  # every deadline was already in the past


def test_ascii_filter_writes_text(capsys):
    def fetch(_n, w, h, mode):
        return Image.new(mode, (w, h), 128)

    primitives.ascii_filter(fetch, "x", 2, lambda i: i, chars="ab")

    out = capsys.readouterr().out
    # Width is 2*size cells, height is `size` rows.
    assert out.count("\n") == 2
