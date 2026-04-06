"""Tests for the import-time execution probe (probe.py)."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from kamp_daemon.ext.probe import _probe_worker, probe_extension

# ---------------------------------------------------------------------------
# Helpers — write tiny modules into tmp_path and inject into sys.path
# ---------------------------------------------------------------------------


def _write_module(tmp_path: Path, name: str, source: str) -> Path:
    mod = tmp_path / f"{name}.py"
    mod.write_text(source)
    return mod


# ---------------------------------------------------------------------------
# _probe_worker tests (inline, no subprocess spawned)
# ---------------------------------------------------------------------------


class _FakeQ:
    """Minimal queue substitute for in-process worker tests."""

    def __init__(self) -> None:
        self._items: list[Any] = []

    def put(self, item: Any) -> None:
        self._items.append(item)

    def get_nowait(self) -> Any:
        if not self._items:
            raise Exception("empty")
        return self._items.pop(0)

    @property
    def first(self) -> Any:
        return self._items[0] if self._items else None


def test_probe_worker_clean_module_puts_ok(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "_probe_clean",
        "class MyClass:\n    pass\n",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        q: _FakeQ = _FakeQ()
        _probe_worker("_probe_clean", q)
        status, _ = q.get_nowait()
        assert status == "ok"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_probe_clean", None)


def test_probe_worker_open_call_puts_violation(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "_probe_open",
        "f = open('/dev/null', 'r')\n",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        q: _FakeQ = _FakeQ()
        _probe_worker("_probe_open", q)
        status, symbol = q.get_nowait()
        assert status == "violation"
        assert symbol == "open"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_probe_open", None)


def test_probe_worker_socket_call_puts_violation(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "_probe_socket",
        "import socket as _s\n_s.socket()\n",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        q: _FakeQ = _FakeQ()
        _probe_worker("_probe_socket", q)
        status, symbol = q.get_nowait()
        assert status == "violation"
        assert symbol == "socket"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_probe_socket", None)


def test_probe_worker_subprocess_run_puts_violation(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "_probe_subprocess",
        "import subprocess\nsubprocess.run(['true'])\n",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        q: _FakeQ = _FakeQ()
        _probe_worker("_probe_subprocess", q)
        status, symbol = q.get_nowait()
        assert status == "violation"
        assert symbol == "run"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_probe_subprocess", None)


def test_probe_worker_os_system_puts_violation(tmp_path: Path) -> None:
    _write_module(
        tmp_path,
        "_probe_os_system",
        "import os\nos.system('true')\n",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        q: _FakeQ = _FakeQ()
        _probe_worker("_probe_os_system", q)
        status, symbol = q.get_nowait()
        assert status == "violation"
        assert symbol == "system"
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_probe_os_system", None)


def test_probe_worker_import_error_puts_error(tmp_path: Path) -> None:
    # Module that raises a non-RuntimeError at import time
    _write_module(
        tmp_path,
        "_probe_import_err",
        "raise ValueError('bad module')\n",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        q: _FakeQ = _FakeQ()
        _probe_worker("_probe_import_err", q)
        status, detail = q.get_nowait()
        assert status == "error"
        assert "bad module" in detail
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("_probe_import_err", None)


# ---------------------------------------------------------------------------
# probe_extension public API — inline worker, no real subprocess
# ---------------------------------------------------------------------------


class _FakeProc:
    def __init__(self, exitcode: int = 0) -> None:
        self.exitcode = exitcode

    def start(self) -> None:
        pass

    def join(self) -> None:
        pass


def _make_inline_probe(tmp_path: Path, module_name: str) -> Any:
    """Return a side_effect for mp_ctx.Process that runs the worker inline."""
    import queue as _queue_module

    class _InlineProcess:
        def __init__(self, target: Any, args: tuple[Any, ...]) -> None:
            self._target = target
            self._args = args
            self.exitcode = 0

        def start(self) -> None:
            sys.path.insert(0, str(tmp_path))
            try:
                self._target(*self._args)
            finally:
                sys.path.remove(str(tmp_path))
                sys.modules.pop(module_name, None)

        def join(self) -> None:
            pass

    return _InlineProcess


def _make_inline_ctx(tmp_path: Path, module_name: str) -> Any:
    """Return a fake mp_ctx that runs the worker inline with a stdlib Queue.

    The spawn-context Queue uses OS pipes + a feeder thread; get_nowait() can
    miss items when the worker runs inline (no real subprocess). A stdlib Queue
    is synchronous and avoids the race entirely.
    """
    import queue as _stdlib_queue

    inline_q: Any = _stdlib_queue.Queue()

    class _FakeProcess:
        def __init__(self, target: Any, args: tuple[Any, ...], **kw: Any) -> None:
            self._target = target
            self._args = args
            self.exitcode = 0

        def start(self) -> None:
            sys.path.insert(0, str(tmp_path))
            try:
                self._target(*self._args)
            finally:
                sys.path.remove(str(tmp_path))
                sys.modules.pop(module_name, None)

        def join(self) -> None:
            pass

    class _FakeCtx:
        def Queue(self) -> Any:
            return inline_q

        def Process(self, **kw: Any) -> _FakeProcess:
            return _FakeProcess(**kw)

    return _FakeCtx()


def test_probe_extension_clean_returns_true(tmp_path: Path) -> None:
    _write_module(tmp_path, "_pext_clean", "class Good:\n    pass\n")
    fake_ctx = _make_inline_ctx(tmp_path, "_pext_clean")
    with patch(
        "kamp_daemon.ext.probe.multiprocessing.get_context", return_value=fake_ctx
    ):
        result = probe_extension("_pext_clean", package_name="test-pkg")
    assert result is True


def test_probe_extension_violation_returns_false(tmp_path: Path, caplog: Any) -> None:
    _write_module(tmp_path, "_pext_bad", "open('/dev/null')\n")
    fake_ctx = _make_inline_ctx(tmp_path, "_pext_bad")
    with (
        patch(
            "kamp_daemon.ext.probe.multiprocessing.get_context", return_value=fake_ctx
        ),
        caplog.at_level("ERROR", logger="kamp_daemon.ext.probe"),
    ):
        result = probe_extension("_pext_bad", package_name="evil-pkg")
    assert result is False
    # AC #4 — error includes package name and stubbed symbol
    assert "evil-pkg" in caplog.text
    assert "open" in caplog.text
