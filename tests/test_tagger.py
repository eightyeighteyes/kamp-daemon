"""Tests for tune_shifter.tagger."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import mutagen.id3 as id3
import mutagen.mp4
import pytest

from tune_shifter.tagger import ReleaseInfo, TaggingError, TrackInfo, tag_directory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_RELEASE: dict[str, Any] = {
    "release-list": [
        {
            "id": "abc-123",
            "title": "Great Album",
            "date": "2020-04-01",
            "ext:score": "100",
            "artist-credit": [{"artist": {"name": "Cool Artist"}}],
            "medium-list": [
                {
                    "position": "1",
                    "track-list": [
                        {
                            "number": "1",
                            "position": "1",
                            "recording": {"title": "First Track"},
                        },
                        {
                            "number": "2",
                            "position": "2",
                            "recording": {"title": "Second Track"},
                        },
                    ],
                }
            ],
        }
    ]
}

# Full release detail returned by get_release_by_id — includes date, tracks, release-group.
SAMPLE_RELEASE_DETAIL: dict[str, Any] = {
    "release": {
        "id": "abc-123",
        "title": "Great Album",
        "date": "2020-04-01",
        "artist-credit": [{"artist": {"name": "Cool Artist"}}],
        "release-group": {"id": "rg-456"},
        "medium-list": [
            {
                "position": "1",
                "track-list": [
                    {
                        "number": "1",
                        "position": "1",
                        "recording": {"title": "First Track"},
                    },
                    {
                        "number": "2",
                        "position": "2",
                        "recording": {"title": "Second Track"},
                    },
                ],
            }
        ],
    }
}


def _make_mp3(
    path: Path, artist: str = "Old Artist", album: str = "Old Album", track: int = 1
) -> None:
    """Write a minimal ID3-tagged MP3 stub."""
    tags = id3.ID3()
    tags["TPE1"] = id3.TPE1(encoding=3, text=artist)
    tags["TALB"] = id3.TALB(encoding=3, text=album)
    tags["TRCK"] = id3.TRCK(encoding=3, text=str(track))
    # Write tags to a file that looks like an MP3 (just needs the tag header)
    path.write_bytes(b"\xff\xfb" * 64)  # minimal fake MP3 frame
    tags.save(str(path))


def _make_m4a(
    path: Path, artist: str = "Old Artist", album: str = "Old Album", track: int = 1
) -> None:
    """Write a minimal M4A stub — we can't easily make a real one, so mock mutagen."""
    path.write_bytes(b"\x00" * 32)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTagDirectory:
    def test_raises_on_no_audio_files(self, tmp_path: Path) -> None:
        with pytest.raises(TaggingError, match="No audio files found"):
            tag_directory(tmp_path, [])

    def test_raises_when_musicbrainz_fails(self, tmp_path: Path) -> None:
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3)

        import musicbrainzngs

        with patch.object(
            musicbrainzngs,
            "search_releases",
            side_effect=musicbrainzngs.WebServiceError("network error"),
        ):
            with pytest.raises(TaggingError, match="MusicBrainz search failed"):
                tag_directory(tmp_path, [mp3])

    def test_raises_when_no_results(self, tmp_path: Path) -> None:
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3)

        with patch("musicbrainzngs.search_releases", return_value={"release-list": []}):
            with pytest.raises(TaggingError, match="No MusicBrainz results"):
                tag_directory(tmp_path, [mp3])

    def test_mp3_tags_written(self, tmp_path: Path) -> None:
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3, track=1)

        with patch("musicbrainzngs.search_releases", return_value=SAMPLE_RELEASE):
            with patch(
                "musicbrainzngs.get_release_by_id", return_value=SAMPLE_RELEASE_DETAIL
            ):
                release = tag_directory(tmp_path, [mp3])

        assert release.mbid == "abc-123"
        assert release.release_group_mbid == "rg-456"
        assert release.title == "Great Album"
        assert release.year == "2020"

        tags = id3.ID3(str(mp3))
        assert str(tags["TALB"]) == "Great Album"
        assert str(tags["TPE1"]) == "Cool Artist"
        assert str(tags["TDRC"]) == "2020"
        assert str(tags["TXXX:MusicBrainz Release Id"]) == "abc-123"

    def test_selects_highest_score(self, tmp_path: Path) -> None:
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3)

        multi_result: dict[str, Any] = {
            "release-list": [
                {
                    "id": "low",
                    "title": "Low Score",
                    "date": "",
                    "ext:score": "50",
                    "artist-credit": [{"artist": {"name": "A"}}],
                    "medium-list": [],
                },
                {
                    "id": "high",
                    "title": "High Score",
                    "date": "2021",
                    "ext:score": "99",
                    "artist-credit": [{"artist": {"name": "B"}}],
                    "medium-list": [],
                },
            ]
        }

        with patch("musicbrainzngs.search_releases", return_value=multi_result):
            with patch(
                "musicbrainzngs.get_release_by_id", return_value=SAMPLE_RELEASE_DETAIL
            ) as mock_get:
                tag_directory(tmp_path, [mp3])

        # The winning MBID ("high") must be passed to get_release_by_id
        assert mock_get.call_args[0][0] == "high"


class TestEditionSuffixRetry:
    def test_retries_with_cleaned_album_name(self, tmp_path: Path) -> None:
        """First search with "(Deluxe Edition)" returns nothing; retry with stripped
        name succeeds and tags are written."""
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3, album="Great Album (Deluxe Edition)", track=1)

        empty: dict[str, Any] = {"release-list": []}

        with patch(
            "musicbrainzngs.search_releases", side_effect=[empty, SAMPLE_RELEASE]
        ) as mock_search:
            with patch(
                "musicbrainzngs.get_release_by_id", return_value=SAMPLE_RELEASE_DETAIL
            ):
                release = tag_directory(tmp_path, [mp3])

        assert release.mbid == "abc-123"
        # First call used the full name; second used the stripped name
        assert mock_search.call_count == 2
        first_call_album = mock_search.call_args_list[0].kwargs["release"]
        second_call_album = mock_search.call_args_list[1].kwargs["release"]
        assert "Deluxe Edition" in first_call_album
        assert "Deluxe Edition" not in second_call_album

    def test_no_retry_when_album_has_no_suffix(self, tmp_path: Path) -> None:
        """Album names without an edition suffix do not trigger a second search."""
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3, album="Great Album", track=1)

        with patch(
            "musicbrainzngs.search_releases", return_value={"release-list": []}
        ) as mock_search:
            with pytest.raises(TaggingError):
                tag_directory(tmp_path, [mp3])

        assert mock_search.call_count == 1

    def test_raises_when_retry_also_finds_nothing(self, tmp_path: Path) -> None:
        """If both the original and cleaned name return no results, TaggingError is raised."""
        mp3 = tmp_path / "01.mp3"
        _make_mp3(mp3, album="Obscure Album (Remastered)", track=1)

        empty: dict[str, Any] = {"release-list": []}

        with patch("musicbrainzngs.search_releases", return_value=empty):
            with pytest.raises(TaggingError, match="No MusicBrainz results"):
                tag_directory(tmp_path, [mp3])


class TestReadExistingMetadata:
    def test_raises_when_no_tags_and_directory_not_artist_album(
        self, tmp_path: Path
    ) -> None:
        """No readable tags + directory name not 'Artist - Album' → TaggingError
        raised before any MusicBrainz call is made."""
        album_dir = tmp_path / "Psalm 69 The Way to Succeed"
        album_dir.mkdir()
        mp3 = album_dir / "01.mp3"
        # Write a valid MP3 with no artist or album tag
        mp3.write_bytes(b"\xff\xfb" * 64)
        id3.ID3().save(str(mp3))

        with patch("musicbrainzngs.search_releases") as mock_search:
            with pytest.raises(
                TaggingError, match="Could not determine artist or album"
            ):
                tag_directory(album_dir, [mp3])

        mock_search.assert_not_called()


class TestTagDirectoryM4a:
    def test_m4a_tags_written(self, tmp_path: Path) -> None:
        """MusicBrainz metadata is written to M4A tag fields."""
        m4a = tmp_path / "01.m4a"
        m4a.write_bytes(b"\x00" * 64)

        # Simulate an iTunes M4A that already has artist/album/track tags
        initial_tags: dict[str, Any] = {
            "\xa9ART": ["Old Artist"],
            "\xa9alb": ["Old Album"],
            "trkn": [(1, 0)],
        }
        mock_mp4 = MagicMock()
        mock_mp4.tags = initial_tags

        with patch("tune_shifter.tagger.mutagen.mp4.MP4", return_value=mock_mp4):
            with patch("musicbrainzngs.search_releases", return_value=SAMPLE_RELEASE):
                with patch(
                    "musicbrainzngs.get_release_by_id",
                    return_value=SAMPLE_RELEASE_DETAIL,
                ):
                    release = tag_directory(tmp_path, [m4a])

        assert release.mbid == "abc-123"
        assert initial_tags["\xa9ART"] == ["Cool Artist"]
        assert initial_tags["\xa9alb"] == ["Great Album"]
        assert initial_tags["\xa9day"] == ["2020"]
        assert "----:com.apple.iTunes:MusicBrainz Release Id" in initial_tags
        mock_mp4.save.assert_called()
