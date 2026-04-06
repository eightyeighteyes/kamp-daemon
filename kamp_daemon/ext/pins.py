"""Extension hash pinning — record and verify SHA-256 hashes of installed files.

At first discovery, each extension distribution's files are hashed and the
results written to a JSON file outside the extensions directory.  On every
subsequent load the recorded hashes are compared against the current on-disk
content.  A mismatch (same version, different bytes) means the files were
tampered with after install and the extension is blocked.

If the installed version has changed (legitimate upgrade via pip), the hashes
are refreshed automatically so the user is not interrupted by a false positive.

The pins file is stored in the same directory as the kamp config file
(~/.config/kamp/ on macOS/Linux) so extension code — which runs inside an
isolated subprocess — cannot modify it by writing to the extension package
directory.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import importlib.metadata

_logger = logging.getLogger(__name__)

_PINS_FILENAME = "extension-pins.json"


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _pins_path() -> Path:
    """Return the platform-appropriate path for the extension pins file."""
    if sys.platform == "win32":  # pragma: no cover
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "kamp" / _PINS_FILENAME
    return Path("~/.config/kamp").expanduser() / _PINS_FILENAME


# ---------------------------------------------------------------------------
# Hashing utilities
# ---------------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    """Return the SHA-256 hex digest of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _should_hash(rel_str: str) -> bool:
    """Return True if *rel_str* should be included in the pin record.

    Excludes compiled bytecode caches (__pycache__ / .pyc) because they are
    deterministically generated from the .py files that are already hashed.
    """
    return "__pycache__" not in rel_str and not rel_str.endswith(".pyc")


def _compute_dist_hashes(dist: "importlib.metadata.Distribution") -> dict[str, str]:
    """Return ``{relative_path: sha256hex}`` for all hashable files in *dist*."""
    result: dict[str, str] = {}
    files = dist.files or []
    for pkg_path in files:
        rel_str = str(pkg_path)
        if not _should_hash(rel_str):
            continue
        abs_path = Path(str(dist.locate_file(pkg_path)))
        if abs_path.is_file():
            result[rel_str] = _hash_file(abs_path)
    return result


# ---------------------------------------------------------------------------
# Pins file I/O
# ---------------------------------------------------------------------------


def _load_pins(pins_path: Path) -> dict[str, dict]:  # type: ignore[type-arg]
    if not pins_path.exists():
        return {}
    with open(pins_path) as f:
        return json.load(f)  # type: ignore[no-any-return]


def _save_pins(pins: dict[str, dict], pins_path: Path) -> None:  # type: ignore[type-arg]
    pins_path.parent.mkdir(parents=True, exist_ok=True)
    with open(pins_path, "w") as f:
        json.dump(pins, f, indent=2)
        f.write("\n")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def verify_or_pin(
    dist_name: str,
    dist: "importlib.metadata.Distribution",
    pins_path: Path | None = None,
) -> bool:
    """Verify the installed files of *dist* against stored hashes, or pin on first use.

    Behaviour:
    - ``dist.files`` is None (e.g. editable install): warn and allow through.
    - Extension not yet pinned: hash all files, record them, return True.
    - Pinned version differs from installed version: re-pin (legitimate upgrade), return True.
    - Pinned version matches, all hashes match: return True.
    - Pinned version matches, any hash differs: log an error identifying each
      mismatched file and return False (caller must block the load).

    Args:
        dist_name: Human-readable distribution name (used in log messages).
        dist: The ``importlib.metadata.Distribution`` for the extension package.
        pins_path: Path to the pins JSON file.  Defaults to ``_pins_path()``.

    Returns:
        True if the extension is safe to load, False if it must be blocked.
    """
    if pins_path is None:
        pins_path = _pins_path()

    if dist.files is None:
        # Can't enumerate files — editable install or unusual packaging.
        # Warn but allow: blocking here would prevent all editable-install
        # development workflows with no security benefit (the RECORD is absent,
        # so there is nothing to verify against).
        _logger.warning(
            "Extension %r has no RECORD file — hash verification skipped "
            "(editable install or unusual packaging)",
            dist_name,
        )
        return True

    pins = _load_pins(pins_path)
    try:
        installed_version: str = dist.metadata["Version"] or "unknown"
    except KeyError:
        installed_version = "unknown"

    # --- First discovery or version upgrade: pin (or re-pin) ---
    if dist_name not in pins or pins[dist_name]["version"] != installed_version:
        hashes = _compute_dist_hashes(dist)
        pins[dist_name] = {"version": installed_version, "files": hashes}
        _save_pins(pins, pins_path)
        _logger.info(
            "Pinned extension %r at version %s (%d file(s))",
            dist_name,
            installed_version,
            len(hashes),
        )
        return True

    # --- Same version: verify hashes ---
    stored_files: dict[str, str] = pins[dist_name]["files"]
    current_hashes = _compute_dist_hashes(dist)

    mismatches: list[str] = []
    for rel_str, expected in stored_files.items():
        actual = current_hashes.get(rel_str)
        if actual is None:
            mismatches.append(f"{rel_str} (missing)")
        elif actual != expected:
            mismatches.append(f"{rel_str} (hash mismatch)")

    if mismatches:
        _logger.error(
            "Extension %r blocked — files were modified after pinning:\n  %s\n"
            "If this is a legitimate update, reinstall the package to refresh the pin.",
            dist_name,
            "\n  ".join(mismatches),
        )
        return False

    return True
