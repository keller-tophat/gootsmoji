"""Renderer registry.

Renderers register themselves via the `@style` decorator when their module
is imported. `toots/renderers/__init__.py` auto-imports every submodule
so the registry is populated by the time anything here is consulted.
"""

STYLES = {}  # name -> render_* function
TILE = set()  # styles safe for compositional renderers to embed
ANIMATED = set()  # styles that drive their own redraw loop (unsafe off-tty)
COLORED = set()  # styles that emit ANSI color escapes


def style(*, tile=True, animated=False, colored=False):
    """Register a `render_*` function under its uppercased short name.

    `tile=False` excludes the style from compositional embeddings (mosaic,
    diptych, ...). `animated=True` flags styles that use cursor-control
    escapes so callers can skip them on non-tty output. `colored=True`
    flags styles that emit ANSI color escapes. Animated styles are
    implicitly non-tile.
    """

    def deco(fn):
        name = fn.__name__[len("render_") :].upper()
        STYLES[name] = fn
        if animated:
            ANIMATED.add(name)
        if colored:
            COLORED.add(name)
        if tile and not animated:
            TILE.add(name)

        return fn

    return deco


def drop(names):
    """Remove `names` from every registry set so they cannot be picked."""
    for n in list(names):
        STYLES.pop(n, None)
        TILE.discard(n)
        ANIMATED.discard(n)
        COLORED.discard(n)
