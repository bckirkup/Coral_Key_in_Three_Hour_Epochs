"""Tests for the Coral Key command-line entry point."""

from __future__ import annotations

import pytest

from coral_key.cli import main


def test_console_script_uses_sys_argv(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["coral-key", "sim", "--epochs", "3"],
    )

    main()

    assert "Epochs: 3" in capsys.readouterr().out
