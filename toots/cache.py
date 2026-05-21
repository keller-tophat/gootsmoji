"""Goot index + image fetch, with an on-disk cache under ~/.cache/goots."""

import datetime
import io
import os
import pathlib
import sys

import requests
from PIL import Image

GOOTS_REPO = "christrotter/gootsmoji"
GOOTS_LIST_URL = f"https://api.github.com/repos/{GOOTS_REPO}/contents/goots"
GOOTS_URL = f"https://raw.githubusercontent.com/{GOOTS_REPO}/refs/heads/main/goots/{{}}"

CACHE = (
    pathlib.Path(
        os.environ.get("XDG_CACHE_HOME") or pathlib.Path.home() / ".cache"
    )
    / "goots"
)

# Touched once per successful sync; its mtime says when we last checked.
STAMP = CACHE / ".last_check"


def index_unreachable(e, hint):
    """Print a uniform \"can't reach the index\" error and exit."""
    print(f"error: could not reach the goots index: {e}", file=sys.stderr)
    print(hint, file=sys.stderr)
    sys.exit(1)


def remote_goots(session=requests):
    """Fetch the authoritative goot filenames from GitHub.

    The contents endpoint caps at 1000 entries; switch to the Git Trees API
    if gootsmoji ever grows past that.
    """
    r = session.get(GOOTS_LIST_URL, timeout=5)
    r.raise_for_status()

    return [e["name"] for e in r.json() if e["type"] == "file"]


def list_goots():
    """Goot filenames currently on disk, sorted; hidden entries skipped."""
    try:
        entries = CACHE.iterdir()
    except (FileNotFoundError, NotADirectoryError):
        return []

    return sorted(e.name for e in entries if not e.name.startswith("."))


def sync_cache(session=requests):
    """Refresh the local cache; download any missing goots.

    Skips work when today's check already happened. Falls back to disk if
    the network is unreachable; only bails if the cache is also empty.
    """
    on_disk = set(list_goots())

    try:
        stamped = (
            datetime.date.fromtimestamp(STAMP.stat().st_mtime)
            == datetime.date.today()
        )
    except OSError:
        stamped = False

    if on_disk and stamped:
        return

    try:
        names = set(remote_goots(session))
    except requests.RequestException as e:
        if on_disk:
            return
        index_unreachable(
            e, f"try again with a network, or pre-populate {CACHE}"
        )

    missing = names - on_disk
    if missing:
        print(f"fetching {len(missing)} new goots...", file=sys.stderr)
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            print(f"error: could not create {CACHE}: {e}", file=sys.stderr)
            sys.exit(1)

        # Skip the stamp if anything failed so we'll retry next run.
        if sum(_download(n, session=session) is None for n in missing):
            return

    try:
        STAMP.touch()
    except OSError:
        pass


def _download(name, save=True, session=requests):
    """Fetch one goot and return its bytes, or None on failure.

    Network and disk errors are reported here so callers stay linear.
    """
    try:
        r = session.get(GOOTS_URL.format(name), timeout=5)
        r.raise_for_status()
        if save:
            CACHE.mkdir(parents=True, exist_ok=True)
            (CACHE / name).write_bytes(r.content)
    except (requests.RequestException, OSError) as e:
        print(f"  skipped {name}: {e}", file=sys.stderr)
        return None

    return r.content


def fetch(name, w, h, mode, session=requests, use_cache=True):
    """Resize and convert a goot. Pulls from disk when `use_cache`, else network."""
    data = None
    if use_cache:
        try:
            data = (CACHE / name).read_bytes()
        except FileNotFoundError:
            pass

    if data is None:
        data = _download(name, save=use_cache, session=session)

    if data is None:
        sys.exit(1)

    return _render(data, w, h, mode)


def _render(data, w, h, mode):
    img = Image.open(io.BytesIO(data))

    # PIL warns on resize for palette images with transparency unless we
    # upgrade them first.
    if img.mode == "P" and "transparency" in img.info:
        img = img.convert("RGBA")

    return img.resize((w, h)).convert(mode)
