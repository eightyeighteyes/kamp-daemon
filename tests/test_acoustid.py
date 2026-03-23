"""Tests for kamp_daemon.acoustid."""

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from kamp_daemon.acoustid import fingerprint_file, lookup_recording_mbids


class TestFingerprintFile:
    def test_returns_none_when_fpcalc_missing(self, tmp_path: Path) -> None:
        path = tmp_path / "track.mp3"
        path.touch()
        with patch("shutil.which", return_value=None):
            assert fingerprint_file(path) is None

    def test_returns_none_on_fpcalc_failure(self, tmp_path: Path) -> None:
        path = tmp_path / "track.mp3"
        path.touch()
        result = MagicMock()
        result.returncode = 1
        with (
            patch("shutil.which", return_value="/usr/bin/fpcalc"),
            patch("subprocess.run", return_value=result),
        ):
            assert fingerprint_file(path) is None

    def test_parses_json_output(self, tmp_path: Path) -> None:
        path = tmp_path / "track.mp3"
        path.touch()
        fpcalc_output = json.dumps(
            {"duration": 287.6, "fingerprint": "AQADtEqkSIqkSA=="}
        )
        result = MagicMock()
        result.returncode = 0
        result.stdout = fpcalc_output
        with (
            patch("shutil.which", return_value="/usr/bin/fpcalc"),
            patch("subprocess.run", return_value=result),
        ):
            fp = fingerprint_file(path)
        assert fp is not None
        duration, fingerprint = fp
        assert duration == pytest.approx(287.6)
        assert fingerprint == "AQADtEqkSIqkSA=="

    def test_invokes_fpcalc_with_json_flag(self, tmp_path: Path) -> None:
        path = tmp_path / "track.mp3"
        path.touch()
        fpcalc_output = json.dumps({"duration": 180.0, "fingerprint": "abc"})
        result = MagicMock()
        result.returncode = 0
        result.stdout = fpcalc_output
        with (
            patch("shutil.which", return_value="/usr/bin/fpcalc"),
            patch("subprocess.run", return_value=result) as mock_run,
        ):
            fingerprint_file(path)
        mock_run.assert_called_once_with(
            ["fpcalc", "-json", str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )


class TestLookupRecordingMbids:
    def test_returns_empty_when_no_key_embedded(self) -> None:
        # Patch _KEY to empty bytes (simulates dev build with no CI substitution)
        with patch("kamp_daemon.acoustid._KEY", b""):
            assert lookup_recording_mbids(180.0, "AQADtEq") == []

    def test_returns_empty_on_no_results(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "results": []}
        with (
            patch("kamp_daemon.acoustid._KEY", b"\x0e\x07\x14\x16"),  # "kamp" XOR'd
            patch("requests.get", return_value=mock_resp),
        ):
            assert lookup_recording_mbids(180.0, "AQADtEq") == []

    def test_extracts_recording_mbids(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "status": "ok",
            "results": [
                {
                    "id": "fp-1",
                    "score": 1.0,
                    "recordings": [
                        {"id": "rec-aaa"},
                        {"id": "rec-bbb"},
                    ],
                },
                {
                    "id": "fp-2",
                    "score": 0.8,
                    "recordings": [{"id": "rec-ccc"}],
                },
            ],
        }
        with (
            patch("kamp_daemon.acoustid._KEY", b"\x0e\x07\x14\x16"),
            patch("requests.get", return_value=mock_resp),
        ):
            mbids = lookup_recording_mbids(180.0, "AQADtEq")
        assert mbids == ["rec-aaa", "rec-bbb", "rec-ccc"]

    def test_calls_acoustid_api_with_correct_params(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok", "results": []}
        # _KEY that decodes to "test" (XOR with b"kamp")
        # 't'^'k'=0x1f, 'e'^'a'=0x04, 's'^'m'=0x1e, 't'^'p'=0x04
        test_key_encoded = bytes([0x1F, 0x04, 0x1E, 0x04])
        with (
            patch("kamp_daemon.acoustid._KEY", test_key_encoded),
            patch("requests.get", return_value=mock_resp) as mock_get,
        ):
            lookup_recording_mbids(287.0, "AQADtEqkSA==")
        mock_get.assert_called_once_with(
            "https://api.acoustid.org/v2/lookup",
            params={
                "client": "test",
                "meta": "recordingids",
                "duration": 287,
                "fingerprint": "AQADtEqkSA==",
            },
            timeout=15,
        )
