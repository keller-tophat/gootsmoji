"""Shared fixtures and helpers."""

import io

import pytest
from PIL import Image


def gradient(w, h, mode):
    """Non-uniform image so renderers exercise color/luma branches."""
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        for x in range(w):
            px[x, y] = ((x * 31) % 256, (y * 53) % 256, ((x + y) * 17) % 256)

    return img.convert(mode)


def png_bytes(size=4, color=(50, 60, 70)):
    """Encode a solid-color PNG and return its bytes."""
    buf = io.BytesIO()
    Image.new("RGB", (size, size), color).save(buf, format="PNG")

    return buf.getvalue()


class Resp:
    """Minimal stand-in for `requests.Response`."""

    def __init__(self, *, json=None, content=None):
        self._json = json
        self.content = content

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class Session:
    """A `requests`-shaped session built from one or more URL handlers.

    Each handler is `(substring, callable(url) -> Resp)`. The first handler
    whose substring is in the request URL wins.
    """

    def __init__(self, *handlers):
        self.handlers = handlers
        self.calls = []

    def get(self, url, *_a, **_k):
        self.calls.append(url)
        for needle, fn in self.handlers:
            if needle in url:
                return fn(url)

        raise AssertionError(f"no handler for {url}")


@pytest.fixture
def fetch():
    """A `cache.fetch`-shaped callable that returns a gradient image."""

    def _fetch(_name, w, h, mode):
        return gradient(w, h, mode)

    return _fetch
