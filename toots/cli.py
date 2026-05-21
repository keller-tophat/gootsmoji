"""Command-line entry point and argument parsing."""

import argparse
import contextlib
import functools
import os
import random
import signal
import sys
import threading
import time

import playsound3
import requests

from . import cache, registry


def main():
    """Parse args, pick a goot and style, render it, then honk."""
    args = parse_args()

    # Validate before dropping, otherwise an explicit --style that conflicts
    # with --no-anim / --no-color would look like an unknown style.
    validate_style(args)
    if not args.anim:
        registry.drop(registry.ANIMATED)
    if not args.color:
        registry.drop(registry.COLORED)

    with requests.Session() as session:
        goots, fetch = resolve_source(args.cache, session)
        tty = sys.stdout.isatty()
        validate(args, goots, tty)

        goot = args.name or random.choice(goots)
        style = pick_style(args, tty)

        # Start the honk before rendering so sound and goot land together.
        if not args.mute:
            honk_honk()

        if args.info:
            print_info(goot, style, args.size)

        with hidden_cursor(tty):
            registry.STYLES[style](fetch, goot, args.size)


def resolve_source(use_cache, session):
    """Return (goot names, fetch callable) for the chosen backend.

    The returned fetch has `session` and `use_cache` bound so renderers stay
    HTTP-agnostic.
    """
    bound = functools.partial(
        cache.fetch, session=session, use_cache=use_cache
    )

    if use_cache:
        cache.sync_cache(session)
        return cache.list_goots(), bound

    try:
        return cache.remote_goots(session), bound
    except requests.RequestException as e:
        cache.index_unreachable(
            e,
            "try again with a network, or drop --no-cache to use the local cache.",
        )


@contextlib.contextmanager
def hidden_cursor(tty):
    """Hide the terminal cursor for the duration; always restore it."""
    if not tty:
        yield
        return

    sys.stdout.write("\033[?25l")
    sys.stdout.flush()
    try:
        yield
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def validate_style(args):
    """Reject unknown styles and styles excluded by --no-anim / --no-color."""
    if not args.style:
        return

    if args.style not in registry.STYLES:
        print(f"error: no such style '{args.style}'", file=sys.stderr)
        sys.exit(1)

    if not args.anim and args.style in registry.ANIMATED:
        print(
            f"error: style '{args.style}' is animated; "
            "drop --no-anim to use it.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.color and args.style in registry.COLORED:
        print(
            f"error: style '{args.style}' is colored; "
            "drop --no-color to use it.",
            file=sys.stderr,
        )
        sys.exit(1)


def validate(args, goots, tty):
    """Reject unknown goots and animated styles off-tty."""
    if args.name and args.name not in goots:
        print(f"error: no such goot '{args.name}'", file=sys.stderr)
        sys.exit(1)

    if args.style in registry.ANIMATED and not tty:
        print(
            f"error: style '{args.style}' is animated and only renders "
            "correctly on a tty.",
            file=sys.stderr,
        )
        sys.exit(1)


def pick_style(args, tty):
    """Return the user's --style, or a weighted random pick.

    Animated styles are flashy but slow; weight them at ~10%. Off-tty,
    skip animated and colored styles (both lean on ANSI escapes).
    """
    if args.style:
        return args.style

    still = registry.STYLES.keys() - registry.ANIMATED
    if not tty:
        return random.choice(list(still - registry.COLORED))

    if random.random() < 0.1:
        return random.choice(list(registry.ANIMATED))

    return random.choice(list(still))


def parse_args():
    """Build the argparse parser and return the parsed CLI args."""
    p = argparse.ArgumentParser(
        prog="toots",
        description="Print goots in the terminal.",
    )
    add = p.add_argument
    add(
        "--name",
        "--goot-name",
        dest="name",
        metavar="NAME",
        help="Name of the goots to print.",
    )
    add(
        "--style",
        "--art-style",
        dest="style",
        type=str.upper,
        metavar="STYLE",
        help="Art style. Run with no args to discover; "
        f"{len(registry.STYLES)} styles available.",
    )
    add("--size", type=int, default=32, help="Size of the goot (default: 32).")
    add("--mute", action=argparse.BooleanOptionalAction, help="Mute the goot.")
    add(
        "--info",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show how to resummon goots (default: on).",
    )
    add(
        "--cache",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Use the local goots cache (default: on).",
    )
    add(
        "--anim",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow animated goots (default: on).",
    )
    add(
        "--color",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Allow colored goots (default: on).",
    )

    return p.parse_args()


def honk_honk():
    """Play two honks alongside rendering.

    Prefer fork on Unix: the parent returns immediately and SIG_IGN on
    SIGCHLD lets the kernel reap the child. Fall back to a non-daemon
    thread elsewhere (e.g. Windows) so the interpreter waits for the
    honks to finish before exiting.
    """
    if not hasattr(os, "fork") or not hasattr(signal, "SIGCHLD"):
        threading.Thread(target=_play_honks, daemon=False).start()
        return

    signal.signal(signal.SIGCHLD, signal.SIG_IGN)
    if os.fork():
        return
    try:
        _play_honks()
    finally:
        # Load-bearing: returning normally would re-enter main(). Use
        # os._exit so we don't flush stdio buffers inherited from the
        # parent (which would duplicate its output) or run atexit hooks
        # the parent still owns.
        os._exit(0)


def _play_honks():
    sound = os.path.join(os.path.dirname(__file__), "honk-sound.mp3")
    playsound3.playsound(sound, block=False)
    time.sleep(0.5)
    playsound3.playsound(sound)


def print_info(goot, style, size):
    """Print a centered header above the goot."""
    text = f"--style {style}  --name {goot}"
    print(text.center(2 * size))
    sys.stdout.flush()
