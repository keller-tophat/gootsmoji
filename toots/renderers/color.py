"""Color renderers: truecolor, color transforms, palette quantization, gradients."""

import colorsys
import random

from PIL import ImageOps

from .. import data, primitives, registry


@registry.style(colored=True)
def render_rgb(fetch, name, size):
    _, px = primitives.load(fetch, name, size)
    primitives.paint_frame(
        size, size, lambda x, y: primitives.bg256(*px[x, y])
    )


@registry.style(colored=True)
def render_truecolor(fetch, name, size):
    primitives.bg_grid(fetch(name, size, size, "RGB"))


@registry.style(colored=True)
def render_matrix(fetch, name, size):
    primitives.lut_grid(
        fetch(name, size, size, "L"),
        [primitives.bg(0, i, 0) for i in range(256)],
    )


@registry.style(colored=True)
def render_grayscale_rgb(fetch, name, size):
    primitives.lut_grid(
        fetch(name, size, size, "L"),
        [primitives.bg(i, i, i) for i in range(256)],
    )


@registry.style(colored=True)
def render_sepia(fetch, name, size):
    _, px = primitives.load(fetch, name, size)

    def cell(x, y):
        r, g, b = px[x, y]
        return primitives.bg(
            min(255, int(0.393 * r + 0.769 * g + 0.189 * b)),
            min(255, int(0.349 * r + 0.686 * g + 0.168 * b)),
            min(255, int(0.272 * r + 0.534 * g + 0.131 * b)),
        )

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_heat(fetch, name, size):
    lut = []
    for i in range(256):
        t = i / 255
        lut.append(
            primitives.bg(
                int(255 * t),
                int(255 * (1 - abs(2 * t - 1))),
                int(255 * (1 - t)),
            )
        )
    primitives.lut_grid(fetch(name, size, size, "L"), lut)


@registry.style(colored=True)
def render_neon(fetch, name, size):
    _, px = primitives.load(fetch, name, size, "HSV")

    def cell(x, y):
        h_, _, v = px[x, y]
        r, g, b = colorsys.hsv_to_rgb(h_ / 255, 1.0, max(v, 80) / 255)
        return primitives.bg(int(r * 255), int(g * 255), int(b * 255))

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_posterize(fetch, name, size):
    primitives.bg_grid(ImageOps.posterize(fetch(name, size, size, "RGB"), 2))


@registry.style(colored=True)
def render_solarize(fetch, name, size):
    primitives.bg_grid(ImageOps.solarize(fetch(name, size, size, "RGB"), 128))


@registry.style(colored=True)
def render_invert(fetch, name, size):
    primitives.bg_grid(ImageOps.invert(fetch(name, size, size, "RGB")))


@registry.style(colored=True)
def render_hue_shift(fetch, name, size):
    _hue_shift(fetch, name, size, random.randint(0, 255))


@registry.style(colored=True)
def render_complement(fetch, name, size):
    _hue_shift(fetch, name, size, 128)


def _hue_shift(fetch, name, size, shift):
    _, px = primitives.load(fetch, name, size, "HSV")

    def cell(x, y):
        h_, s, v = px[x, y]
        r, g, b = colorsys.hsv_to_rgb(
            ((h_ + shift) % 256) / 255, s / 255, v / 255
        )
        return primitives.bg(int(r * 255), int(g * 255), int(b * 255))

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_monochrome(fetch, name, size):
    tr, tg, tb = colorsys.hsv_to_rgb(random.random(), 1.0, 1.0)
    lut = [
        primitives.bg(int(tr * i), int(tg * i), int(tb * i))
        for i in range(256)
    ]
    primitives.lut_grid(fetch(name, size, size, "L"), lut)


@registry.style(colored=True)
def render_nightvision(fetch, name, size):
    _, px = primitives.load(fetch, name, size, "L")

    def cell(x, y):
        v = max(0, min(255, px[x, y] + random.randint(-25, 25)))
        return primitives.bg(0, v, 0)

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_deep_fried(fetch, name, size):
    img = ImageOps.autocontrast(fetch(name, size, size, "RGB"), cutoff=2)
    px = img.load()

    def cell(x, y):
        r, g, b = px[x, y]
        return primitives.bg(
            min(255, int(r * 1.4) + 30),
            min(255, int(g * 1.1)),
            max(0, int(b * 0.9) - 10),
        )

    primitives.paint_frame(size, size, cell)


@registry.style(colored=True)
def render_gameboy(fetch, name, size):
    lut = [
        primitives.bg(*data.GAMEBOY[min(3, i * 4 // 256)]) for i in range(256)
    ]
    primitives.lut_grid(
        ImageOps.autocontrast(fetch(name, size, size, "L"), cutoff=2),
        lut,
    )


@registry.style(colored=True)
def render_cga(fetch, name, size):
    primitives.palette_grid(fetch(name, size, size, "RGB"), data.CGA)


@registry.style(colored=True)
def render_c64(fetch, name, size):
    primitives.palette_grid(fetch(name, size, size, "RGB"), data.C64)


@registry.style(colored=True)
def render_nes(fetch, name, size):
    primitives.palette_grid(fetch(name, size, size, "RGB"), data.NES)


@registry.style(colored=True)
def render_pico8(fetch, name, size):
    primitives.palette_grid(fetch(name, size, size, "RGB"), data.PICO8)


@registry.style(colored=True)
def render_terminal16(fetch, name, size):
    primitives.palette_grid(
        fetch(name, size, size, "RGB"),
        data.TERMINAL16,
        [primitives.bg16(i) for i in range(16)],
    )


@registry.style(colored=True)
def render_roygbiv(fetch, name, size):
    primitives.palette_grid(
        fetch(name, size, size, "RGB"), data.ROYGBIV_PALETTE
    )


@registry.style(colored=True)
def render_vaporwave(fetch, name, size):
    primitives.lut_grid(
        fetch(name, size, size, "L"), _gradient_lut(data.VAPORWAVE_STOPS)
    )


@registry.style(colored=True)
def render_frost(fetch, name, size):
    primitives.lut_grid(
        fetch(name, size, size, "L"), _gradient_lut(data.FROST_STOPS)
    )


@registry.style(colored=True)
def render_duotone(fetch, name, size):
    a = tuple(random.randint(0, 255) for _ in range(3))
    b = tuple(random.randint(0, 255) for _ in range(3))
    primitives.lut_grid(
        fetch(name, size, size, "L"),
        [primitives.bg(*primitives.lerp(a, b, i / 255)) for i in range(256)],
    )


@registry.style(colored=True)
def render_gradient(fetch, name, size):
    h1, h2 = random.random(), random.random()
    lut = []
    for i in range(256):
        t = i / 255
        hue = h1 + (h2 - h1) * t
        r, g, b = colorsys.hsv_to_rgb(hue % 1.0, 0.8, 0.3 + 0.7 * t)
        lut.append(primitives.bg(int(r * 255), int(g * 255), int(b * 255)))
    primitives.lut_grid(fetch(name, size, size, "L"), lut)


@registry.style(colored=True)
def render_thermal(fetch, name, size):
    primitives.lut_grid(
        fetch(name, size, size, "L"), _gradient_lut(data.THERMAL_STOPS)
    )


@registry.style(colored=True)
def render_thermal_hot(fetch, name, size):
    black = primitives.bg(0, 0, 0)
    lut = [
        (
            black
            if i < 100
            else primitives.bg(
                *primitives.gradient(data.THERMAL_STOPS, (i - 100) / 155)
            )
        )
        for i in range(256)
    ]
    primitives.lut_grid(fetch(name, size, size, "L"), lut)


@registry.style(colored=True)
def render_cyanotype(fetch, name, size):
    primitives.lut_grid(
        fetch(name, size, size, "L"), _gradient_lut(data.CYAN_STOPS)
    )


def _gradient_lut(stops):
    """256-entry bg() lut sampling `stops` linearly across luma."""
    return [
        primitives.bg(*primitives.gradient(stops, i / 255)) for i in range(256)
    ]
