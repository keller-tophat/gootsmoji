"""Smoke test: every registered style runs against a fake fetch."""

import pytest

from toots import cache, primitives, registry
from toots.renderers import composition

SIZE = 4


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """Animated styles call time.sleep; collapse it for fast tests."""
    monkeypatch.setattr(primitives.time, "sleep", lambda _d: None)


@pytest.fixture(autouse=True)
def _cache_pool(monkeypatch):
    """carousel and rolodex enumerate the on-disk cache; return a fixed list."""
    monkeypatch.setattr(cache, "list_goots", lambda: ["g.png", "other.png"])


@pytest.mark.parametrize("style_name", sorted(registry.STYLES))
def test_renderer_runs(style_name, fetch, capsys):
    registry.STYLES[style_name](fetch, "g.png", SIZE)

    out = capsys.readouterr().out
    assert out.count("\n") >= 1, f"{style_name} produced no rows"


def test_capture_rejects_non_tile(fetch):
    animated = next(iter(registry.ANIMATED))
    with pytest.raises(ValueError):
        composition.capture(fetch, animated, "g.png", 4)
