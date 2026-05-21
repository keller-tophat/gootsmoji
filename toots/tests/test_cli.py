"""CLI: arg parsing, validation, off-tty guard, info line, honk fork."""

import argparse
import sys

import pytest
from PIL import Image

from toots import cli, registry


def test_parse_args(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["toots", "--goot-name", "g.png", "--art-style", "rgb"]
    )
    args = cli.parse_args()

    assert args.size == 32  # default
    assert args.info is True
    assert args.cache is True
    assert args.name == "g.png"  # alias for --name
    assert args.style == "RGB"  # --style is upper-cased by argparse


def test_validate_rejects_unknown_goot(capsys):
    args = argparse.Namespace(name="nope.png", style=None)

    with pytest.raises(SystemExit) as e:
        cli.validate(args, ["a.png", "b.png", "c.png"], tty=True)

    assert e.value.code == 1
    assert "no such goot" in capsys.readouterr().err


def test_validate_style_rejects_unknown_style(capsys):
    args = argparse.Namespace(style="NOSUCH", anim=True, color=True)

    with pytest.raises(SystemExit):
        cli.validate_style(args)

    assert "no such style" in capsys.readouterr().err


def test_validate_style_rejects_animated_under_no_anim(capsys):
    style = next(iter(registry.ANIMATED))
    args = argparse.Namespace(style=style, anim=False, color=True)

    with pytest.raises(SystemExit):
        cli.validate_style(args)

    err = capsys.readouterr().err
    assert "animated" in err and "--no-anim" in err


def test_validate_style_rejects_colored_under_no_color(capsys):
    style = next(iter(registry.COLORED - registry.ANIMATED))
    args = argparse.Namespace(style=style, anim=True, color=False)

    with pytest.raises(SystemExit):
        cli.validate_style(args)

    err = capsys.readouterr().err
    assert "colored" in err and "--no-color" in err


def test_validate_rejects_animated_off_tty(capsys):
    style = next(iter(registry.ANIMATED))
    args = argparse.Namespace(name=None, style=style)

    with pytest.raises(SystemExit):
        cli.validate(args, ["a.png"], tty=False)

    assert "animated" in capsys.readouterr().err


def test_pick_style_off_tty_never_animated():
    # The off-tty branch must never pick animated, period.
    args = argparse.Namespace(style=None)
    assert cli.pick_style(args, False) not in registry.ANIMATED


def test_print_info_centers_header(capsys):
    cli.print_info("g.png", "RGB", 40)

    out = capsys.readouterr().out
    assert "--style RGB" in out
    assert "--name g.png" in out
    # Centered in 2 * size cells.
    assert len(out.rstrip("\n")) == 80


def test_honk_honk_parent_returns_immediately(monkeypatch):
    # Pretend we are the parent (non-zero pid). The child-only playsound
    # call must not fire on this branch.
    def boom(*_a, **_k):
        raise AssertionError("child-only path reached in parent")

    monkeypatch.setattr(cli.os, "fork", lambda: 1234)
    monkeypatch.setattr(cli.signal, "signal", lambda *a: None)
    monkeypatch.setattr(cli.playsound3, "playsound", boom)

    cli.honk_honk()


def test_main_runs_chosen_style(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        "toots --no-cache --no-info --mute --style TRUECOLOR --size 2".split(),
    )
    monkeypatch.setattr(cli.cache, "remote_goots", lambda _s: ["g.png"])
    monkeypatch.setattr(
        cli.cache,
        "fetch",
        lambda _name, w, h, mode, session, use_cache: Image.new(
            mode, (w, h), 0
        ),
    )

    calls = []
    monkeypatch.setitem(
        registry.STYLES,
        "TRUECOLOR",
        lambda _fetch, name, size: calls.append((name, size)),
    )

    cli.main()

    assert calls == [("g.png", 2)]
