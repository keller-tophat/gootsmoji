"""Cache: index fetch, sync semantics, and image decoding."""

# pylint: disable=redefined-outer-name,unused-argument

import io

import pytest
import requests
from PIL import Image

from toots import cache
from toots.tests import conftest


def _index(*names):
    return conftest.Resp(json=[{"name": n, "type": "file"} for n in names])


def _blob(content):
    return conftest.Resp(content=content)


def _offline(_url):
    raise requests.ConnectionError("offline")


@pytest.fixture
def _root(tmp_path, monkeypatch):
    """Point CACHE and STAMP at a fresh tmp dir; return the dir."""
    monkeypatch.setattr(cache, "CACHE", tmp_path)
    monkeypatch.setattr(cache, "STAMP", tmp_path / ".last_check")

    return tmp_path


def test_remote_goots_filters_to_files():
    payload = [
        {"name": "a.png", "type": "file"},
        {"name": "subdir", "type": "dir"},
        {"name": "b.png", "type": "file"},
    ]
    session = conftest.Session(
        ("api.github.com", lambda _u: conftest.Resp(json=payload))
    )

    assert cache.remote_goots(session) == ["a.png", "b.png"]


def test_list_goots_skips_hidden(_root):
    (_root / "a.png").write_bytes(b"x")
    (_root / "b.png").write_bytes(b"x")
    (_root / ".last_check").write_bytes(b"")

    assert cache.list_goots() == ["a.png", "b.png"]


def test_sync_cache_short_circuits_when_stamped_today(_root):
    (_root / "have.png").write_bytes(b"x")
    (_root / ".last_check").touch()

    def boom(_url):
        raise AssertionError("network must not be touched")

    session = conftest.Session(("", boom))

    cache.sync_cache(session)  # would raise if the short-circuit failed
    assert session.calls == []


def test_sync_cache_downloads_missing(_root):
    blob = conftest.png_bytes()
    (_root / "a.png").write_bytes(b"have")
    session = conftest.Session(
        ("api.github.com", lambda _u: _index("a.png", "b.png")),
        ("raw.githubusercontent.com", lambda _u: _blob(blob)),
    )

    cache.sync_cache(session)

    assert (_root / "b.png").read_bytes() == blob
    assert (_root / "a.png").read_bytes() == b"have"  # untouched
    assert (_root / ".last_check").exists()


def test_sync_cache_stamps_when_nothing_missing(_root):
    # Without the stamp, the next run would re-hit the network even though
    # the cache is already complete.
    (_root / "a.png").write_bytes(b"x")
    session = conftest.Session(("api.github.com", lambda _u: _index("a.png")))

    cache.sync_cache(session)

    assert (_root / ".last_check").exists()


def test_sync_cache_does_not_stamp_on_failure(_root):
    session = conftest.Session(
        ("api.github.com", lambda _u: _index("a.png")),
        ("raw.githubusercontent.com", _offline),
    )

    cache.sync_cache(session)

    assert not (_root / ".last_check").exists()


def test_sync_cache_offline_with_local_cache_returns(_root):
    # No stamp on disk: sync still attempts the network, hits the error,
    # and falls back to the local cache.
    (_root / "a.png").write_bytes(b"x")
    session = conftest.Session(("", _offline))

    cache.sync_cache(session)  # must not raise or exit


def test_sync_cache_offline_no_cache_exits(_root):
    session = conftest.Session(("", _offline))

    with pytest.raises(SystemExit):
        cache.sync_cache(session)


def test_fetch_reads_disk(_root):
    (_root / "g.png").write_bytes(conftest.png_bytes())

    img = cache.fetch("g.png", 5, 6, "RGB")

    assert img.size == (5, 6)
    assert img.mode == "RGB"


def test_fetch_downloads_on_miss(_root):
    session = conftest.Session(("", lambda _u: _blob(conftest.png_bytes())))

    img = cache.fetch("missing.png", 3, 3, "L", session=session)

    assert img.size == (3, 3)
    assert (_root / "missing.png").exists()


def test_fetch_no_cache_does_not_touch_disk(_root):
    session = conftest.Session(("", lambda _u: _blob(conftest.png_bytes())))

    img = cache.fetch("g.png", 4, 4, "RGB", session=session, use_cache=False)

    assert img.size == (4, 4)
    assert not (_root / "g.png").exists()


def test_fetch_handles_palette_with_transparency(_root):
    # Palette mode with a transparency entry warns on resize unless we
    # upgrade to RGBA first; verify fetch handles it end-to-end.
    src = Image.new("P", (8, 8))
    src.info["transparency"] = 0
    buf = io.BytesIO()
    src.save(buf, format="PNG")
    (_root / "t.png").write_bytes(buf.getvalue())

    img = cache.fetch("t.png", 4, 4, "RGB")

    assert img.size == (4, 4)
    assert img.mode == "RGB"
