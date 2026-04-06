"""Import-time execution probe for backend extensions.

Python entry points execute module-level code at import time — before any ABC
conformance check or permission gate. A malicious ``__init__.py`` can open
files, make network connections, or spawn subprocesses before ``tag()`` is
ever called.

``probe_extension`` loads the extension module once inside a fresh spawn-
context subprocess with dangerous builtins and stdlib symbols stubbed out.
Any call to a stubbed symbol during import raises immediately; the subprocess
reports the violation and the extension is rejected before it is added to the
active registry.

This is a heuristic, not a complete sandbox — it catches the obvious module-
level exfiltration pattern. OS-level sandboxing (TASK-87) is the complete
solution. Legitimate extensions that only define classes and read package
metadata will pass without issue.
"""

from __future__ import annotations

import builtins
import importlib
import logging
import multiprocessing
import os
import queue
import socket
import subprocess as _subprocess_module
from typing import Any

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Worker (runs inside the isolated subprocess)
# ---------------------------------------------------------------------------

# Symbols to stub during the probe.  Each entry is (module_object, attr_name).
# We patch at the object level so sub-imports that already hold a reference to
# e.g. ``open`` still hit the stub.
_STUB_TARGETS: list[tuple[Any, str]] = [
    (builtins, "open"),
    (socket, "socket"),
    (_subprocess_module, "Popen"),
    (_subprocess_module, "run"),
    (_subprocess_module, "call"),
    (os, "system"),
]


def _make_stub(symbol_name: str, result_q: Any) -> Any:
    """Return a callable that reports *symbol_name* as a violation."""

    def _stub(*args: Any, **kwargs: Any) -> None:
        result_q.put(("violation", symbol_name))
        raise RuntimeError(
            f"Extension probe: call to restricted symbol '{symbol_name}' "
            f"detected at import time"
        )

    return _stub


def _probe_worker(module_name: str, result_q: Any) -> None:
    """Subprocess entry point: import *module_name* with dangerous symbols stubbed.

    Puts one of:
    - ``("ok", None)`` — import succeeded with no violations
    - ``("violation", symbol_name)`` — a stubbed symbol was called during import
    - ``("error", detail)`` — the module failed to import for another reason
    """
    # Install stubs before importing anything from the extension.
    originals: list[tuple[Any, str, Any]] = []
    for obj, attr in _STUB_TARGETS:
        originals.append((obj, attr, getattr(obj, attr)))
        setattr(obj, attr, _make_stub(attr, result_q))

    try:
        importlib.import_module(module_name)
        result_q.put(("ok", None))
    except RuntimeError:
        # Violation already placed on result_q by the stub — no second put needed.
        pass
    except Exception as exc:  # noqa: BLE001
        result_q.put(("error", str(exc)))
    finally:
        # Restore originals so the subprocess exits cleanly.
        for obj, attr, original in originals:
            setattr(obj, attr, original)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def probe_extension(module_name: str, package_name: str = "") -> bool:
    """Probe *module_name* for import-time execution of restricted symbols.

    Spawns an isolated subprocess, imports the module with dangerous builtins
    stubbed, and returns True if the import is clean. Returns False (and logs
    an error) if any stubbed symbol is called or the import fails unexpectedly.

    Args:
        module_name: Dotted module name to import (e.g. ``"my_ext.tagger"``).
        package_name: Human-readable package name for log messages. Defaults
            to *module_name* if omitted.

    Returns:
        True if the extension passed the probe, False if it was rejected.
    """
    label = package_name or module_name
    mp_ctx = multiprocessing.get_context("spawn")
    result_q: Any = mp_ctx.Queue()
    proc = mp_ctx.Process(target=_probe_worker, args=(module_name, result_q))
    proc.start()
    proc.join()

    # Non-zero exit without a result_q entry — subprocess crashed during probe.
    if proc.exitcode != 0:
        try:
            status, value = result_q.get_nowait()
        except queue.Empty:
            _logger.error(
                "Extension probe for %r crashed (exit code %d)",
                label,
                proc.exitcode,
            )
            return False
    else:
        try:
            status, value = result_q.get_nowait()
        except queue.Empty:
            _logger.error(
                "Extension probe for %r exited without a result",
                label,
            )
            return False

    if status == "violation":
        _logger.error(
            "Extension %r rejected: module-level call to restricted symbol %r",
            label,
            value,
        )
        return False

    if status == "error":
        _logger.error(
            "Extension %r probe import failed: %s",
            label,
            value,
        )
        return False

    return True
