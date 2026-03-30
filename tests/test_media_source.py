"""Tests for HULiGENNEM media source."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.components.media_source import (
    MediaSourceItem,
    Unresolvable,
)
from homeassistant.components.media_source.error import MediaSourceError

from custom_components.huligennem.media_source import HuligennemMediaSource

from .conftest import (
    SAMPLE_PLAYLIST,
    SAMPLE_PLAYLIST_EPISODIC,
    SAMPLE_PLAYLIST_SINGLE_SEASON,
    SAMPLE_SERIES_PAGE_1,
)


@pytest.fixture
def api_mock():
    """Create a mock API."""
    api = AsyncMock()
    api.async_get_series = AsyncMock(return_value=SAMPLE_SERIES_PAGE_1["props"]["series"]["data"])
    api.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST)
    api.async_get_episode_url = AsyncMock(return_value=None)
    api.async_get_live = AsyncMock(
        return_value={
            "title": "Live Show",
            "stream_url": "https://stream.example.com/live.m3u8",
            "planned_starts_at": "2026-03-27T14:00:00.000000Z",
            "planned_ends_at": "2026-03-27T17:00:00.000000Z",
        }
    )
    return api


@pytest.fixture
def media_source(api_mock):
    """Create a media source with a mocked API."""
    hass = MagicMock()
    entry = MagicMock()
    entry.runtime_data = MagicMock(api=api_mock)
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    source = HuligennemMediaSource(hass)
    return source


def _item(identifier: str | None = None) -> MediaSourceItem:
    """Create a MediaSourceItem."""
    item = MagicMock(spec=MediaSourceItem)
    item.identifier = identifier
    return item


class TestBrowseMedia:
    """Tests for browse_media."""

    @pytest.mark.asyncio
    async def test_browse_root(self, media_source: HuligennemMediaSource):
        """Test browsing root returns live + series."""
        result = await media_source.async_browse_media(_item(None))

        assert result.title == "HULiGENNEM"
        assert len(result.children) == 3  # live + 2 series
        assert result.children[0].title == "Live Radio"
        assert result.children[0].identifier == "live"
        assert result.children[1].title == "Ultra Nansen"
        assert result.children[2].title == "Dansen med DR"

    @pytest.mark.asyncio
    async def test_browse_root_thumbnails(self, media_source: HuligennemMediaSource):
        """Test that series with poster get thumbnails, null posters don't crash."""
        result = await media_source.async_browse_media(_item(None))

        # Series with poster dict
        assert result.children[1].thumbnail == "https://cdn.example.com/poster1.jpg"

    @pytest.mark.asyncio
    async def test_browse_series_multi_season(self, media_source: HuligennemMediaSource):
        """Test browsing a series with multiple seasons shows seasons."""
        result = await media_source.async_browse_media(_item("series/1"))

        assert result.title == "Ultra Nansen"
        assert len(result.children) == 2
        assert result.children[0].title == "Sæson 1"
        assert result.children[1].title == "Sæson 2"
        assert "season/10" in result.children[0].identifier

    @pytest.mark.asyncio
    async def test_browse_series_multi_season_thumbnails(self, media_source: HuligennemMediaSource):
        """Test that season items use the first episode poster as thumbnail."""
        result = await media_source.async_browse_media(_item("series/1"))

        assert result.children[0].thumbnail == "https://cdn.example.com/ep1.jpg"
        assert result.children[1].thumbnail == "https://cdn.example.com/s2ep1.jpg"

    @pytest.mark.asyncio
    async def test_browse_series_single_season(self, media_source: HuligennemMediaSource, api_mock):
        """Test browsing a series with single season shows episodes."""
        api_mock.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST_SINGLE_SEASON)
        result = await media_source.async_browse_media(_item("series/1"))

        assert len(result.children) == 1
        assert result.children[0].can_play is True
        assert "episode/" in result.children[0].identifier

    @pytest.mark.asyncio
    async def test_browse_season(self, media_source: HuligennemMediaSource):
        """Test browsing a season shows episodes."""
        result = await media_source.async_browse_media(_item("series/1/season/10"))

        assert result.title == "Sæson 1"
        assert len(result.children) == 2
        assert result.children[0].can_play is True
        assert "Episode 1" in result.children[0].title

    @pytest.mark.asyncio
    async def test_browse_invalid_identifier(self, media_source: HuligennemMediaSource):
        """Test browsing with invalid identifier raises error."""
        with pytest.raises(MediaSourceError):
            await media_source.async_browse_media(_item("invalid/path"))

    @pytest.mark.asyncio
    async def test_browse_series_episodic(self, media_source: HuligennemMediaSource, api_mock):
        """Test browsing an episodic series (top-level episodes, no seasons) shows episodes."""
        api_mock.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST_EPISODIC)
        result = await media_source.async_browse_media(_item("series/1"))

        assert result.title == "Morgenknas"
        assert len(result.children) == 2
        assert result.children[0].can_play is True
        assert result.children[0].title == "Episode 1 (10 min)"
        assert "episode/100" in result.children[0].identifier

    @pytest.mark.asyncio
    async def test_browse_series_invalid_id(self, media_source: HuligennemMediaSource):
        """Test browsing series with non-numeric ID raises error."""
        with pytest.raises(MediaSourceError, match="Invalid series"):
            await media_source.async_browse_media(_item("series/abc"))


class TestResolveMedia:
    """Tests for resolve_media."""

    @pytest.mark.asyncio
    async def test_resolve_episode_uses_spreaker_url(
        self, media_source: HuligennemMediaSource, api_mock
    ):
        """Test that episode resolution uses the Spreaker hosted URL."""
        api_mock.async_get_episode_url = AsyncMock(
            return_value="https://api.spreaker.com/v2/episodes/999001/play.mp3"
        )
        result = await media_source.async_resolve_media(_item("episode/100/serie/1"))

        assert result.url == "https://api.spreaker.com/v2/episodes/999001/play.mp3"
        assert result.mime_type == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_resolve_episode_fallback_to_playlist(self, media_source: HuligennemMediaSource):
        """Test fallback to playlist CDN URL when no Spreaker URL available (seasonal)."""
        result = await media_source.async_resolve_media(_item("episode/100/serie/1"))

        assert result.url == "https://huligennem-production.imgix.net/ep1.mp3"
        assert result.mime_type == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_resolve_episode_fallback_episodic(
        self, media_source: HuligennemMediaSource, api_mock
    ):
        """Test fallback to playlist CDN URL for episodic series (top-level episodes)."""
        api_mock.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST_EPISODIC)
        result = await media_source.async_resolve_media(_item("episode/100/serie/1"))

        assert result.url == "https://huligennem-production.imgix.net/ep1.mp3"
        assert result.mime_type == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_resolve_live(self, media_source: HuligennemMediaSource):
        """Test resolving live stream returns HLS URL."""
        result = await media_source.async_resolve_media(_item("live"))

        assert result.url == "https://stream.example.com/live.m3u8"
        assert result.mime_type == "application/x-mpegURL"

    @pytest.mark.asyncio
    async def test_resolve_live_unavailable(self, media_source: HuligennemMediaSource, api_mock):
        """Test resolving live when unavailable raises error."""
        api_mock.async_get_live = AsyncMock(return_value=None)

        with pytest.raises(Unresolvable, match="not currently available"):
            await media_source.async_resolve_media(_item("live"))

    @pytest.mark.asyncio
    async def test_resolve_no_identifier(self, media_source: HuligennemMediaSource):
        """Test resolving with no identifier raises error."""
        with pytest.raises(Unresolvable, match="No identifier"):
            await media_source.async_resolve_media(_item(None))

    @pytest.mark.asyncio
    async def test_resolve_unknown_identifier(self, media_source: HuligennemMediaSource):
        """Test resolving unknown identifier raises error."""
        with pytest.raises(Unresolvable, match="Unknown media"):
            await media_source.async_resolve_media(_item("unknown/thing"))

    @pytest.mark.asyncio
    async def test_resolve_episode_not_found(self, media_source: HuligennemMediaSource):
        """Test resolving non-existent episode raises error."""
        with pytest.raises(Unresolvable, match="not found"):
            await media_source.async_resolve_media(_item("episode/999/serie/1"))

    @pytest.mark.asyncio
    async def test_resolve_episode_invalid_id(self, media_source: HuligennemMediaSource):
        """Test resolving episode with non-numeric ID raises error."""
        with pytest.raises(Unresolvable, match="Invalid episode"):
            await media_source.async_resolve_media(_item("episode/abc/serie/xyz"))
