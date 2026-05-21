# toots

Print goots in your terminal.

## Usage

Run via `uv run toots`.

    uv run toots                          # random goot, random style
    uv run toots --name honk.png          # pick a goot by filename
    uv run toots --style ASCII            # pick a style
    uv run toots --size 48                # bigger
    uv run toots --no-anim --no-color     # static, monochrome
    uv run toots --no-cache               # always hit the network
    uv run toots --mute --no-info         # quiet and chromeless

Run with no arguments to discover styles; the info header above each render shows what was picked.

## Layout

    cli.py          Argparse, goot/style selection, cursor hiding, honking.
    cache.py        ~/.cache/goots: index sync, fetch, on-disk + remote modes.
    data.py         Char ramps, glyph tables, indexed palettes, gradient stops.
    primitives.py   ANSI escapes, grid walkers, animation helpers.
    registry.py     @style decorator; STYLES / TILE / ANIMATED / COLORED sets.
    renderers/      One module per renderer family; auto-imported on package load.
        ramps.py        ASCII, blocks, braille, halftone, hiragana, ...
        color.py        Truecolor, palette quantization (GameBoy, NES, ...), tints.
        spatial.py      Chroma shifts, blueprints, edge detection, geometry.
        animated.py     Typewriter, rainbow, glitch, rain, spin, sparkle, ...
        composition.py  Mosaic and friends: arrange other renderers' output.
    tests/          pytest suite.
    honk-sound.mp3  Honk!

`toots` is provided by the project entry point (`toots.cli:main`). Use `uv run toots` in the repo,
or just `toots` after installation.

## Cache

By default goots are mirrored under `$XDG_CACHE_HOME/goots` (falling back to `~/.cache/goots`). The
index is re-checked once per day; new goots download on demand. `--no-cache` bypasses disk entirely
and always pulls from GitHub.
