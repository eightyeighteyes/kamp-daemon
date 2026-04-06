"""Tests for extension hash pinning (TASK-84)."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kamp_daemon.ext.pins import _hash_file, _pins_path, verify_or_pin

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dist(name: str, version: str, files: dict[str, bytes]) -> MagicMock:
    """Build a mock Distribution with the given file contents.

    *files* maps relative path strings to raw bytes.  The mock's locate_file()
    returns a real tmp Path so _hash_file can open it.
    """
    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": name, "Version": version}

    pkg_paths = []
    for rel_str in files:
        pp = MagicMock()
        pp.__str__ = lambda self, r=rel_str: r
        pkg_paths.append(pp)

    dist.files = pkg_paths
    return dist


def _write_dist_files(tmp_path: Path, files: dict[str, bytes]) -> dict[str, Path]:
    """Write *files* under *tmp_path* and return {rel_str: abs_path}."""
    abs_paths: dict[str, Path] = {}
    for rel_str, content in files.items():
        abs_p = tmp_path / rel_str
        abs_p.parent.mkdir(parents=True, exist_ok=True)
        abs_p.write_bytes(content)
        abs_paths[rel_str] = abs_p
    return abs_paths


def _dist_with_real_files(
    tmp_path: Path, name: str, version: str, files: dict[str, bytes]
) -> tuple[MagicMock, dict[str, Path]]:
    """Return (mock dist, abs_paths) where locate_file resolves into tmp_path."""
    abs_paths = _write_dist_files(tmp_path, files)
    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": name, "Version": version}

    pkg_paths = []
    for rel_str in files:
        pp = MagicMock()
        pp.__str__ = lambda self, r=rel_str: r
        # locate_file(pp) returns the real abs path
        pkg_paths.append(pp)

    dist.files = pkg_paths
    dist.locate_file = lambda pp: abs_paths[str(pp)]
    return dist, abs_paths


# ---------------------------------------------------------------------------
# _hash_file
# ---------------------------------------------------------------------------


def test_hash_file_returns_sha256_hex(tmp_path: Path) -> None:
    p = tmp_path / "test.py"
    content = b"print('hello')"
    p.write_bytes(content)
    expected = hashlib.sha256(content).hexdigest()
    assert _hash_file(p) == expected


def test_hash_file_differs_for_different_content(tmp_path: Path) -> None:
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_bytes(b"x = 1")
    b.write_bytes(b"x = 2")
    assert _hash_file(a) != _hash_file(b)


# ---------------------------------------------------------------------------
# verify_or_pin — first discovery auto-pins
# ---------------------------------------------------------------------------


def test_first_discovery_pins_and_returns_true(tmp_path: Path) -> None:
    pins_path = tmp_path / "extension-pins.json"
    dist, _ = _dist_with_real_files(
        tmp_path, "my-ext", "1.0.0", {"my_ext/__init__.py": b"# init"}
    )

    result = verify_or_pin("my-ext", dist, pins_path)

    assert result is True
    pins = json.loads(pins_path.read_text())
    assert "my-ext" in pins
    assert pins["my-ext"]["version"] == "1.0.0"
    assert "my_ext/__init__.py" in pins["my-ext"]["files"]


def test_first_discovery_creates_parent_dirs(tmp_path: Path) -> None:
    pins_path = tmp_path / "sub" / "dir" / "extension-pins.json"
    dist, _ = _dist_with_real_files(tmp_path, "ext", "1.0", {"ext.py": b""})
    verify_or_pin("ext", dist, pins_path)
    assert pins_path.exists()


# ---------------------------------------------------------------------------
# verify_or_pin — matching hashes pass
# ---------------------------------------------------------------------------


def test_matching_hashes_return_true(tmp_path: Path) -> None:
    pins_path = tmp_path / "extension-pins.json"
    dist, _ = _dist_with_real_files(
        tmp_path, "my-ext", "1.0.0", {"my_ext/tagger.py": b"class T: pass"}
    )
    # First call pins
    verify_or_pin("my-ext", dist, pins_path)
    # Second call verifies — same files, should pass
    assert verify_or_pin("my-ext", dist, pins_path) is True


# ---------------------------------------------------------------------------
# verify_or_pin — hash mismatch blocks load
# ---------------------------------------------------------------------------


def test_hash_mismatch_returns_false(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pins_path = tmp_path / "extension-pins.json"
    file_path = tmp_path / "my_ext" / "tagger.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_bytes(b"class T: pass")

    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": "my-ext", "Version": "1.0.0"}
    pp = MagicMock()
    pp.__str__ = lambda self: "my_ext/tagger.py"
    dist.files = [pp]
    dist.locate_file = lambda _: file_path

    # Pin with original content
    verify_or_pin("my-ext", dist, pins_path)

    # Tamper with the file
    file_path.write_bytes(b"import os; os.system('evil')")

    import logging

    with caplog.at_level(logging.ERROR, logger="kamp_daemon.ext.pins"):
        result = verify_or_pin("my-ext", dist, pins_path)

    assert result is False
    assert "my-ext" in caplog.text
    assert "my_ext/tagger.py" in caplog.text


def test_hash_mismatch_message_names_extension(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pins_path = tmp_path / "extension-pins.json"
    file_path = tmp_path / "evil_ext.py"
    file_path.write_bytes(b"original")

    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": "evil-ext", "Version": "2.3.4"}
    pp = MagicMock()
    pp.__str__ = lambda self: "evil_ext.py"
    dist.files = [pp]
    dist.locate_file = lambda _: file_path

    verify_or_pin("evil-ext", dist, pins_path)
    file_path.write_bytes(b"tampered")

    import logging

    with caplog.at_level(logging.ERROR, logger="kamp_daemon.ext.pins"):
        verify_or_pin("evil-ext", dist, pins_path)

    assert "evil-ext" in caplog.text


# ---------------------------------------------------------------------------
# verify_or_pin — version change re-pins (legitimate upgrade)
# ---------------------------------------------------------------------------


def test_version_change_repins_and_returns_true(tmp_path: Path) -> None:
    pins_path = tmp_path / "extension-pins.json"
    file_path = tmp_path / "ext.py"
    file_path.write_bytes(b"v1")

    def _make_dist_v(version: str) -> MagicMock:
        dist = MagicMock(spec=importlib.metadata.Distribution)
        dist.metadata = {"Name": "my-ext", "Version": version}
        pp = MagicMock()
        pp.__str__ = lambda self: "ext.py"
        dist.files = [pp]
        dist.locate_file = lambda _: file_path
        return dist

    # Pin v1
    verify_or_pin("my-ext", _make_dist_v("1.0.0"), pins_path)

    # Upgrade: new content, new version
    file_path.write_bytes(b"v2 new content")
    result = verify_or_pin("my-ext", _make_dist_v("2.0.0"), pins_path)

    assert result is True
    pins = json.loads(pins_path.read_text())
    assert pins["my-ext"]["version"] == "2.0.0"
    # New hash recorded
    assert (
        pins["my-ext"]["files"]["ext.py"]
        == hashlib.sha256(b"v2 new content").hexdigest()
    )


def test_same_version_tampered_content_blocked(tmp_path: Path) -> None:
    """Same version string + different bytes = block (not a legitimate upgrade)."""
    pins_path = tmp_path / "extension-pins.json"
    file_path = tmp_path / "ext.py"
    file_path.write_bytes(b"original")

    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": "my-ext", "Version": "1.0.0"}
    pp = MagicMock()
    pp.__str__ = lambda self: "ext.py"
    dist.files = [pp]
    dist.locate_file = lambda _: file_path

    verify_or_pin("my-ext", dist, pins_path)
    file_path.write_bytes(b"tampered, same version")

    assert verify_or_pin("my-ext", dist, pins_path) is False


# ---------------------------------------------------------------------------
# verify_or_pin — dist.files is None (editable install / unusual package)
# ---------------------------------------------------------------------------


def test_no_record_warns_and_allows(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    pins_path = tmp_path / "extension-pins.json"
    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": "weird-ext", "Version": "1.0.0"}
    dist.files = None  # no RECORD

    import logging

    with caplog.at_level(logging.WARNING, logger="kamp_daemon.ext.pins"):
        result = verify_or_pin("weird-ext", dist, pins_path)

    assert result is True
    assert "weird-ext" in caplog.text


# ---------------------------------------------------------------------------
# verify_or_pin — pyc / __pycache__ files are excluded from hashing
# ---------------------------------------------------------------------------


def test_pycache_files_excluded(tmp_path: Path) -> None:
    pins_path = tmp_path / "extension-pins.json"

    py_file = tmp_path / "ext.py"
    pyc_file = tmp_path / "__pycache__" / "ext.cpython-313.pyc"
    py_file.write_bytes(b"code")
    pyc_file.parent.mkdir()
    pyc_file.write_bytes(b"compiled")

    dist = MagicMock(spec=importlib.metadata.Distribution)
    dist.metadata = {"Name": "ext", "Version": "1.0"}
    pp_py = MagicMock()
    pp_py.__str__ = lambda self: "ext.py"
    pp_pyc = MagicMock()
    pp_pyc.__str__ = lambda self: "__pycache__/ext.cpython-313.pyc"
    dist.files = [pp_py, pp_pyc]

    paths = {"ext.py": py_file, "__pycache__/ext.cpython-313.pyc": pyc_file}
    dist.locate_file = lambda pp: paths[str(pp)]

    verify_or_pin("ext", dist, pins_path)
    pins = json.loads(pins_path.read_text())
    assert "__pycache__/ext.cpython-313.pyc" not in pins["ext"]["files"]
    assert "ext.py" in pins["ext"]["files"]


# ---------------------------------------------------------------------------
# _pins_path
# ---------------------------------------------------------------------------


def test_pins_path_is_outside_site_packages() -> None:
    """The pins file must not live inside any site-packages directory."""
    p = _pins_path()
    assert "site-packages" not in str(p)
