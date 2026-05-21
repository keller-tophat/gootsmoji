# Tutorial: Adding a Goots Style

This walks through `toots/primitives.py` by building a new animated style, `CRAIG`, that frames the
goot in a classic 007 gun-barrel intro: a small white iris pans across the screen, lands on center,
then opens to reveal goots.

By the end you'll know:

- what each primitive does and when to reach for it
- how an animated renderer is structured
- how a style registers itself with the rest of the program


## What we're building

The 007 gun barrel has three beats:

1. A small white circle pans from the right edge toward the center.
2. The circle stops and dilates outward, revealing goots inside.
3. Goots stands proud on its own.

We'll build it incrementally. Each step adds one idea and ends with you running
`uv run toots --style CRAIG` and seeing real progress on screen. Everything lives in
`toots/renderers/animated.py` alongside the existing animated styles.


## Step 0: style not found

Try running `uv run toots --style CRAIG` and you should see:

    > uv run toots --style CRAIG
    error: no such style 'CRAIG'

If not, you may need to install the uv package manager or do some other troubleshooting.

All set? Let's begin!

## Step 1: an empty renderer

Every renderer in `toots` is a plain function with this shape:

    def render_craig(fetch, name, size):
        ...

A few things to notice:

- The function is named `render_craig`. The framework picks renderers up by name. Anything in
  `toots/renderers/` whose function starts with `render_` and is decorated with `@registry.style`
  gets auto-discovered at import time (see `renderers/__init__.py`), and the style is registered as
  the uppercased suffix -- so `render_craig` becomes the `CRAIG` style.
- `fetch(name, w, h, mode)` is a callback that hands you a PIL `Image` of the goot, already resized
  to `w x h` and converted to `mode` (`"RGB"`, `"L"`, etc.). You almost never call PIL directly; let
  `fetch` do it.
- `name` is the `--name` given by the user or chosen at random (e.g. `"angry.png"`) -- pass it
  through to `fetch`.
- `size` is whatever the user typed for `--size`. It's a hint about how big to draw, in *terminal
  cells*. You'll see in step 2 why "cells" matter.

Open `toots/renderers/animated.py` and add this near the bottom:

    @registry.style(animated=True, colored=True)
    def render_craig(fetch, name, size):
        print("Hello, World!")

The decorator is how the renderer announces itself to the rest of the program. Its flags:

- `animated=True` -- this renderer uses cursor-control escapes (more on those in step 4). The CLI
  refuses to run animated styles when stdout isn't a tty, because the escapes would land in the
  captured output as garbage.
- `colored=True` -- emits ANSI color escapes. The CLI's `--no-color` will skip it.
- `tile=True` (the default) -- whether the style is safe to embed inside a *compositional* renderer.
  A compositional renderer is one that runs other renderers and pastes their output into a grid (see
  `renderers/composition.py` -- `render_mosaic` for example). Animated styles can't compose (they
  redraw the screen, which doesn't survive being captured into a grid cell), so `registry.style`
  quietly forces `tile=False` whenever `animated=True`. You don't have to think about this for
  `CRAIG`.

Now run it:

    uv run toots --style CRAIG

You should see `Hello, World!` print and the program exit. The renderer is registered, the decorator
is doing its job, and the CLI found it by name. That's a real renderer -- just a very boring one.


## Step 2: a black square

Time to actually draw something. Terminals don't speak pixels; they speak *characters*. To paint a
"pixel" we color the background of a character cell. The trick is that terminal cells are about
twice as tall as they are wide -- so a single character looks like a tall skinny rectangle. Use
*two* characters side by side and you get something roughly square. That's a "cell" in this
codebase: two spaces with a background color attached.

To set that background color we emit an *ANSI escape sequence*: a literal ESC byte (`\033`) followed
by `[`, some parameters, and a final letter. The terminal interprets these instead of printing them.
The two you'll use constantly:

    \033[0m              # reset all styling
    \033[48;2;R;G;Bm     # set background to 24-bit RGB color R,G,B

Once you set a color, *everything* printed after it has that background until you change it or
reset. That's where the gotcha lives: an "empty" two-space cell next to a colored one will inherit
the previous color and smear across the screen. So `primitives` gives you two constants:

    primitives.RESET   # "\033[0m"; ends any active color
    primitives.BLANK   # RESET + "  "; safe empty cell next to a colored one

And a helper for the common case of "paint one cell this color":

    primitives.bg(r, g, b)      # 24-bit truecolor swatch (no trailing reset)
    primitives.bg256(r, g, b)   # same idea, but quantized to a 256-color palette
    primitives.bg16(idx)        # one of the 16 standard ANSI named colors

If you're coming from the web, think of `bg(255, 0, 0)` as `background: #ff0000`. The catch is that
not every terminal supports it. Truecolor (`\033[48;2;...m`) is the modern 24-bit path, and it's
what every example here uses -- it's the equivalent of any hex color you'd write in CSS. Older
terminals only spoke a 256-color cube (`bg256`), and the original ANSI standard only had 16 named
colors (`bg16`). The reason "palettized" output exists at all is that on a small canvas, snapping
every pixel to a tight, hand-picked palette often looks *better* than truecolor, not worse -- like
dithered GIFs vs JPEGs. We won't need those for `CRAIG`, but you'll see them across the other
renderers.

Replace the body of `render_craig` with a black square of the requested size:

    @registry.style(animated=True, colored=True)
    def render_craig(fetch, name, size):
        black = (0, 0, 0)

        for _ in range(size):
            for _ in range(size):
                sys.stdout.write(primitives.bg(*black))
            sys.stdout.write(primitives.RESET + "\n")

`sys.stdout` is already imported at the top of `animated.py`. We loop `size` rows by `size` columns
because one cell is two characters wide and one row tall, so a `size x size` grid of cells renders
as roughly a square on screen.

Run it:

    uv run toots --style CRAIG --size 16

A 16-tall black rectangle. Now we're getting somewhere!


## Step 3: an expanding circle

Now we add the second beat of the gun-barrel: a white iris that grows outward from the center of a
grey background. We'll come back and add the pan (beat 1) and the goot reveal (beat 3) in later
steps.

Two new primitives do most of the work.

**`paint_frame(w, h, cell)`** walks a `w x h` grid in row-major order and calls `cell(x, y)` for
every position, gluing the results together with row terminators and writing the whole thing to
stdout. You give it a function; it gives you a frame. That's the workhorse for any animation where
each cell's contents depend on its position. We always pass `size, size` since our canvas is square.

**`animate(rows, frames, delay, draw)`** is the redraw loop. It calls `draw(f)` for `f` in
`0..frames`, and between frames it emits a cursor-up escape so the next frame overwrites the last.
Two contracts you must respect:

- `draw(f)` must emit *exactly* `rows` lines. If it emits more or fewer, the cursor-up count is off
  and your frames will smear up the scrollback.
- `rows` is *terminal rows*, not image pixels. For a full-cell renderer (like ours) they're the
  same. For `halfblock_text` (step 6) one terminal row packs two image rows, so it's `h // 2`.

We use `delay = 1.0 / 24` -- 24 fps. Smooth enough that the eye sees motion, slow enough that the
CPU doesn't spin and the terminal can keep up. `animate` uses *deadline scheduling*: if a frame
takes too long to draw, the next deadline snaps to "now" so we don't accumulate debt.

Now: how do we draw a circle? A point `(x, y)` is inside a circle of radius `r` centered at
`(cx, cy)` when its distance from the center is at most `r`. Distance is Pythagoras:

    d = sqrt((x - cx)^2 + (y - cy)^2)

So for each cell we compute `d`. If `d > r`, it's outside the iris -- paint it grey background. If
`d` is within a couple of cells of `r`, paint it white -- that's the rim of the lens. Inside the
rim, paint black for now (we'll put the goot there in step 5).

One more concept: the **cell factory**. `paint_frame` takes a single `cell(x, y)` function, but that
function needs to know the current frame's circle parameters (`cx`, `cy`, `r`). We solve that with a
closure: a small outer function `cell_for(...)` captures the per-frame parameters and returns a
fresh `cell` closure each frame. This is a pattern you'll see everywhere in `animated.py`.

Replace your `render_craig` with:

    @registry.style(animated=True, colored=True)
    def render_craig(fetch, name, size):
        black = (0, 0, 0)
        grey = (40, 40, 40)
        white = (255, 255, 255)
        cx, cy = size // 2, size // 2
        frames = 24

        def cell_for(r):
            edge = max(1, r // 8)

            def cell(x, y):
                dx, dy = x - cx, y - cy
                d = (dx * dx + dy * dy) ** 0.5
                if d > r:
                    return primitives.bg(*grey)
                if d > r - edge:
                    return primitives.bg(*white)
                return primitives.bg(*black)

            return cell

        def draw(f):
            r = 1 + int((size - 1) * (f / (frames - 1)))
            primitives.paint_frame(size, size, cell_for(r))

        primitives.animate(size, frames, 1.0 / 24, draw)

`r` interpolates from 1 to `size` over `frames` steps. `edge = max(1, r // 8)` keeps the rim
proportional to the circle's size -- a fat rim on a big circle, a thin one on a small circle.

Run it:

    uv run toots --style CRAIG

You should see a white ring expand outward from the center. That's animation!

Please take some time to play with that code. Really understand what's going on before continuing.


## Step 4: the three beats

Right now there's only beat 2 (the dilation). Let's give the iris a path: a small circle pans in
from the right, then opens, then holds.

A natural way to express this is a small function that, given a frame number, hands back
*everything* that varies that frame:

    cx, cy, r, reveal = beat(f, size)

- `cx, cy`: where the iris is centered this frame
- `r`: current radius
- `reveal`: should we show the goot inside the iris? (False during the pan, True after.)

That keeps `draw` mechanical -- one call to `beat`, one call to `paint_frame` -- and puts all the
timing logic in one place where it's easy to tweak.

The beat function is just a small state machine. We pick frame counts for each phase and compute
parameters by interpolating within the current phase:

- **Phase 1 (pan)**: `cx` slides from the right edge `size - 1` to the center `size // 2`. Linear
  interpolation: at `t = 0` we're at the right, at `t = 1` we're at the center. The radius stays
  small.
- **Phase 2 (open)**: the iris is locked at the center and `r` grows from the small pan radius to
  `size` (enough to cover the whole canvas).
- **Phase 3 (hold)**: everything is at its end-of-phase-2 values for a few extra frames so the
  reveal lingers.

Pick frame counts for each phase and a small radius for the pan, then keep both the constants and
`beat` inside `render_craig` -- same shape as step 3, just with one more nested helper:

    @registry.style(animated=True, colored=True)
    def render_craig(fetch, name, size):
        black = (0, 0, 0)
        grey = (40, 40, 40)
        white = (255, 255, 255)
        pan_frames, open_frames, hold_frames = 14, 10, 6
        small_r = 4
        total = pan_frames + open_frames + hold_frames

        def beat(f):
            cy = size // 2
            if f < pan_frames:
                # phase 1: t goes 0 -> 1 across the pan; cx slides right -> center.
                t = f / max(1, pan_frames - 1)
                cx = int(size - 1 - t * (size - 1 - size // 2))
                return cx, cy, small_r, False

            f -= pan_frames
            if f < open_frames:
                # phase 2: radius grows from small_r to cover the whole canvas.
                t = (f + 1) / open_frames
                r = small_r + int(t * (size - small_r))
                return size // 2, cy, r, True

            # phase 3: fully open, hold on the canvas.
            return size // 2, cy, size, True

        def cell_for(cx, cy, r, reveal):
            edge = max(1, r // 8)

            def cell(x, y):
                dx, dy = x - cx, y - cy
                d = (dx * dx + dy * dy) ** 0.5
                if d > r:
                    return primitives.bg(*grey)
                if d > r - edge:
                    return primitives.bg(*white)
                return primitives.bg(*black)

            return cell

        def draw(f):
            cx, cy, r, reveal = beat(f)
            primitives.paint_frame(size, size, cell_for(cx, cy, r, reveal))

        primitives.animate(size, total, 1.0 / 24, draw)

Compared to step 3 we swapped the single `frames = 24` for three phase counts, added `beat` to turn
a frame number into iris parameters, and changed `cell_for` to take `cx, cy, r` as arguments instead
of reading them from the enclosing scope. `reveal` is unused for now -- we wire it up in the next
step.

Run it:

    uv run toots --style CRAIG

The iris pans in from the right, parks at the center, then dilates open. Again, don't be afraid to
play with this code to understand all the parts. That's how you learn.


## Step 5: revealing the goot

Time to put something inside the iris. We need pixel data from the goot image, which means calling
`fetch` and reading individual pixels.

`primitives.load` is sugar around exactly that:

    img, px = primitives.load(fetch, name, size, mode="RGB")

It calls `fetch(name, size, size, mode)` and then `img.load()` -- the latter returns a PIL "pixel
access" object, which behaves like a 2D array indexed `px[x, y]`. For `"RGB"` images you get back
`(r, g, b)` tuples; for `"L"` (grayscale) you get a single int 0..255. That's all `load` does -- you
could call `fetch` and `img.load()` yourself, but every renderer ends up doing it, so it's a
primitive.

Sizing matters: `load(fetch, name, size)` asks `fetch` to resize the image to exactly `size x size`.
Since our canvas is `size x size` cells, every cell maps to exactly one pixel. (`load` is
intentionally square -- the renderers that need a non-square image, like the half-block and ASCII
ramps, call `fetch` directly.)

The update is small. We load `px` once at the start of the renderer (the closure captures it for
every frame), then when `reveal` is true and the cell is inside the iris's rim, we paint the goot
pixel at that position:

    @registry.style(animated=True, colored=True)
    def render_craig(fetch, name, size):
        black = (0, 0, 0)
        white = (255, 255, 255)
        _, px = primitives.load(fetch, name, size)
        pan_frames, open_frames, hold_frames = 14, 10, 6
        small_r = 4
        total = pan_frames + open_frames + hold_frames

        def beat(f):
            cy = size // 2
            if f < pan_frames:
                t = f / max(1, pan_frames - 1)
                cx = int(size - 1 - t * (size - 1 - size // 2))
                return cx, cy, small_r, False

            f -= pan_frames
            if f < open_frames:
                t = (f + 1) / open_frames
                r = small_r + int(t * (size - small_r))
                return size // 2, cy, r, True

            return size // 2, cy, size, True

        def cell_for(cx, cy, r, reveal):
            edge = max(1, r // 8)

            def cell(x, y):
                dx, dy = x - cx, y - cy
                d = (dx * dx + dy * dy) ** 0.5
                if d > r:
                    return primitives.bg(*black)
                if d > r - edge:
                    return primitives.bg(*white)
                if reveal:
                    return primitives.bg(*px[x, y])
                return primitives.bg(*black)

            return cell

        def draw(f):
            cx, cy, r, reveal = beat(f)
            primitives.paint_frame(size, size, cell_for(cx, cy, r, reveal))

        primitives.animate(size, total, 1.0 / 24, draw)

Two changes from step 4: we call `primitives.load` once up front to grab a pixel-access object, and
`cell` paints `px[x, y]` inside the rim when `reveal` is true. We also dropped `grey` and fall back
to `black` outside the iris -- black is what reads as "gun barrel".

Run it:

    uv run toots --style CRAIG

The iris pans in, stops, opens, and there's goots! That's `CRAIG`!


## Step 6: bonus -- half-block resolution

One cell per pixel is fine, but `CRAIG` is leaving half its vertical resolution on the floor. The
trick: print the unicode half-block character `▀` with both a foreground and a background color, and
the terminal shows the top half of the cell in the foreground and the bottom half in the background.
Two stacked colored pixels in a single terminal row.

The escape is the same shape as `bg`, with an extra `38;2;...` for the foreground:

    \033[38;2;Rt;Gt;Bt;48;2;Rb;Gb;Bbm▀

`primitives.halfblock_text(img)` does this for a static image -- the existing `HALFBLOCK` style in
`renderers/ramps.py` is a one-liner around it. We can't reuse that here because our pixels are
computed per frame, not pulled from a fixed image. But the iris math doesn't care what we do with
the colors; we just need to compute *two* pixel colors per terminal cell instead of one and glue
them into a half-block escape.

The sizing is the thing to keep straight: each terminal cell is now one image-pixel wide and *two*
image-pixels tall. So we render onto a `2*size` wide by `2*size` tall image grid, but the terminal
grid passed to `paint_frame`/`animate` is `2*size` wide by `size` tall.

Split the per-pixel logic out of `cell_for` so we can call it twice per cell:

    @registry.style(animated=True, colored=True)
    def render_craig(fetch, name, size):
        black = (0, 0, 0)
        white = (255, 255, 255)
        ipx = 2 * size  # image-pixel canvas is square; terminal grid is ipx wide x size tall.
        _, px = primitives.load(fetch, name, ipx)
        pan_frames, open_frames, hold_frames = 14, 10, 6
        small_r = 8
        total = pan_frames + open_frames + hold_frames

        def beat(f):
            cy = ipx // 2
            if f < pan_frames:
                t = f / max(1, pan_frames - 1)
                cx = int(ipx - 1 - t * (ipx - 1 - ipx // 2))
                return cx, cy, small_r, False

            f -= pan_frames
            if f < open_frames:
                t = (f + 1) / open_frames
                r = small_r + int(t * (ipx - small_r))
                return ipx // 2, cy, r, True

            return ipx // 2, cy, ipx, True

        def cell_for(cx, cy, r, reveal):
            edge = max(1, r // 8)

            def pixel(x, y):
                dx, dy = x - cx, y - cy
                d = (dx * dx + dy * dy) ** 0.5
                if d > r:
                    return black
                if d > r - edge:
                    return white
                if reveal:
                    return px[x, y]
                return black

            def cell(x, ty):
                tr, tg, tb = pixel(x, 2 * ty)
                br, bg_, bb = pixel(x, 2 * ty + 1)
                return f"\033[38;2;{tr};{tg};{tb};48;2;{br};{bg_};{bb}m▀"

            return cell

        def draw(f):
            cx, cy, r, reveal = beat(f)
            primitives.paint_frame(ipx, size, cell_for(cx, cy, r, reveal))

        primitives.animate(size, total, 1.0 / 24, draw)

What changed from step 5:

- `ipx = 2 * size` is the image-pixel canvas, used by `beat`, `pixel`, and the goot we load.
- `small_r` doubled to `8` so the iris looks the same size as before despite the finer grid.
- The old `cell` got split: `pixel(x, y)` returns an `(r, g, b)` triple, and the new `cell(x, ty)`
  calls it twice (top and bottom image rows) and builds the half-block escape.
- `paint_frame` is called with `(ipx, size)` -- the terminal grid -- and `animate` uses `size` rows.

Run it:

    uv run toots --style CRAIG

Same three beats, twice the vertical detail.


## A tour of the rest of `primitives.py`

Now that you've used the core ones, the rest of `primitives.py` falls into place. Skim these when
you're picking a tool for a new renderer.

**Color math.** `lerp(a, b, t)` interpolates two RGB triples. `gradient(stops, t)` samples a
piecewise-linear gradient across many stops. `rgb_to_ansi_256` quantizes to the xterm 256-color
cube.

**Fast grid walkers.** `paint_frame` is the per-cell workhorse, but if your output depends only on
the source image (no per-frame logic), there are C-accelerated paths:

- `lut_grid(img, lut)` -- "L"-mode image plus a 256-entry string LUT. The ASCII ramps use this.
- `bg_grid(img)` -- "RGB" image straight to truecolor bg cells. Static color renderers use this.
- `palette_grid(img, palette, bg_strings=None)` -- quantize to a fixed palette in C and emit
  per-index strings. Use this for `GAMEBOY`, `CGA`, `ROYGBIV` looks.

If you find yourself calling `bg(...)` thousands of times per frame, look at `bg_grid` or
`palette_grid`: both move the inner loop into C and can be 10x faster.

**Single-character cells.** If you're using a glyph instead of `"  "` (ASCII ramps, braille), one
cell is one character wide. To keep the output roughly square you need twice as many columns:
`2 * size` wide by `size` tall. `renderers/ramps.py` is full of examples.


## Where to go from here

Once `CRAIG` is in, the other animated styles read as variations on the same shape. Each is worth
opening and skimming -- they're small, and each demonstrates one technique you can lift into your
own renderer:

- **`render_pulse`** modulates brightness with `cos(frame)`. The trick is sampling a smooth function
  at integer frame numbers so motion looks continuous even though it's discrete. Good template for
  any "breathing" or oscillating effect.
- **`render_dissolve`** keeps a `revealed` set that grows by a chunk of pixels per frame, in
  shuffled order. Template for any "reveal over time" effect (typewriter, fade-in, wipe).
- **`render_explode`** pre-computes a per-pixel velocity vector at startup, then plots each pixel at
  `start + velocity * frame` per frame. Template for particle systems -- precompute what you can,
  keep the inner loop pure arithmetic.
- **`_plot`** at the top of `animated.py` is a handy helper when your cells come from a sparse point
  cloud rather than a dense grid: pass an iterable of `(x, y, bg_str)` and it builds the frame for
  you.

A small exercise to anchor those: pick *one* of them and write a new style that combines it with
`CRAIG`. For instance, `CRAIG_PULSE` could brighten/darken the iris's white rim using `pulse`'s
`cos` trick. Or `CRAIG_DISSOLVE` could replace the iris dilation with a dissolve reveal of the goot
pixels. They're 10-20 line tweaks and they'll lock in the patterns.

A few more notes worth keeping in your head:

- The renderer registers itself automatically -- `renderers/__init__.py` imports every submodule at
  package load, and `@registry.style` adds it to the styles table. You never edit a list.
- The renderer test (`test_renderer_runs` in `toots/tests/test_renderers.py`) iterates every
  registered style and asserts it produces output, so `CRAIG` is covered the moment it's registered.
  Time-based renderers don't actually sleep in tests -- the `_no_sleep` fixture monkeypatches
  `primitives.time.sleep`.
- Animated styles refuse to render when stdout isn't a tty. Piping `--style CRAIG` to a file
  produces:

      error: style 'CRAIG' is animated and only renders correctly on a tty.

  Use `--mute` for a quiet smoke test in a terminal:

      uv run toots --style CRAIG --mute

- `render_craig` keeps its constants and helpers nested inside the function -- fine while the
  renderer fits on a screen. If `beat`, `cell_for`, the phase counts etc. start to crowd it, the
  existing convention in `animated.py` is to lift them to module-private helpers (leading
  underscore: `_beat`, `_PAN_FRAMES`) at the top of the file. Truly static data (palettes, glyph
  tables, ramps) lives in `toots/data.py` -- look at how `ASCII_RAMP` and `GAMEBOY` are defined
  there and imported by the renderers that use them.
