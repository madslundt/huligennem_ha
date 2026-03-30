"""Tests for HULiGENNEM services."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import ServiceCall

from custom_components.huligennem.services import (
    async_handle_get_episodes,
    async_handle_get_live,
    async_handle_search_series,
)

from .conftest import (
    SAMPLE_PLAYLIST,
    SAMPLE_PLAYLIST_EPISODIC,
    SAMPLE_PLAYLIST_MULTIPART,
    SAMPLE_SERIES_PAGE_1,
)


@pytest.fixture
def api_mock():
    """Create a mock API."""
    api = AsyncMock()
    api.async_get_series = AsyncMock(return_value=SAMPLE_SERIES_PAGE_1["props"]["series"]["data"])
    api.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST)
    api.async_get_episode_url = AsyncMock(
        return_value="https://api.spreaker.com/v2/episodes/999001/play.mp3"
    )
    api.async_get_live = AsyncMock(
        return_value={
            "title": "Live Show Now",
            "stream_url": "https://stream.example.com/live.m3u8",
            "planned_starts_at": "2026-03-27T14:00:00.000000Z",
            "planned_ends_at": "2026-03-27T17:00:00.000000Z",
        }
    )
    return api


@pytest.fixture
def mock_call(api_mock):
    """Create a factory for mock ServiceCall objects."""
    hass = MagicMock()
    entry = MagicMock()
    entry.runtime_data = MagicMock(api=api_mock)
    hass.config_entries.async_entries = MagicMock(return_value=[entry])

    def make_call(data: dict | None = None) -> ServiceCall:
        call = MagicMock(spec=ServiceCall)
        call.hass = hass
        call.data = data or {}
        return call

    return make_call


class TestSearchSeries:
    """Tests for search_series service."""

    @pytest.mark.asyncio
    async def test_search_with_query(self, mock_call):
        """Test searching series with a query filter."""
        call = mock_call({"query": "ultra"})
        result = await async_handle_search_series(call)

        assert len(result["series"]) == 1
        assert result["series"][0]["title"] == "Ultra Nansen"

    @pytest.mark.asyncio
    async def test_search_without_query(self, mock_call):
        """Test searching series without a query returns all."""
        call = mock_call({})
        result = await async_handle_search_series(call)

        assert len(result["series"]) == 2

    @pytest.mark.asyncio
    async def test_search_no_match(self, mock_call):
        """Test searching with non-matching query returns empty."""
        call = mock_call({"query": "nonexistent"})
        result = await async_handle_search_series(call)

        assert len(result["series"]) == 0

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, mock_call):
        """Test that search is case-insensitive."""
        call = mock_call({"query": "ULTRA"})
        result = await async_handle_search_series(call)

        assert len(result["series"]) == 1

    @pytest.mark.asyncio
    async def test_search_returns_poster_url(self, mock_call):
        """Test that search results include poster URL."""
        call = mock_call({"query": "ultra"})
        result = await async_handle_search_series(call)

        assert result["series"][0]["poster_url"] == "https://cdn.example.com/poster1.jpg"


class TestGetEpisodes:
    """Tests for get_episodes service."""

    @pytest.mark.asyncio
    async def test_get_episodes(self, mock_call):
        """Test getting episodes for a series."""
        call = mock_call({"serie_id": 48})
        result = await async_handle_get_episodes(call)

        assert len(result["episodes"]) == 3
        assert result["episodes"][0]["title"] == "Episode 1"
        assert result["episodes"][0]["media_url"] == (
            "https://api.spreaker.com/v2/episodes/999001/play.mp3"
        )
        assert result["episodes"][0]["duration_seconds"] == 600
        assert result["episodes"][0]["season"] == "Sæson 1"

    @pytest.mark.asyncio
    async def test_get_episodes_episodic_series(self, mock_call, api_mock):
        """Test getting episodes for an episodic series (top-level episodes, no seasons)."""
        api_mock.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST_EPISODIC)
        call = mock_call({"serie_id": 2})
        result = await async_handle_get_episodes(call)

        assert len(result["episodes"]) == 2
        assert result["episodes"][0]["title"] == "Episode 1"
        assert result["episodes"][0]["season"] is None
        assert result["episodes"][0]["duration_seconds"] == 600


class TestGetEpisodesMultiPart:
    """Tests for multi-part episode annotation in get_episodes."""

    @pytest.fixture
    def multipart_mock_call(self, api_mock):
        """Return a mock_call factory wired to SAMPLE_PLAYLIST_MULTIPART."""
        api_mock.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST_MULTIPART)
        api_mock.async_get_episode_url = AsyncMock(return_value=None)
        hass = MagicMock()
        entry = MagicMock()
        entry.runtime_data = MagicMock(api=api_mock)
        hass.config_entries.async_entries = MagicMock(return_value=[entry])

        def make_call(data: dict | None = None) -> ServiceCall:
            call = MagicMock(spec=ServiceCall)
            call.hass = hass
            call.data = data or {}
            return call

        return make_call

    @pytest.mark.asyncio
    async def test_del_parts_are_annotated(self, multipart_mock_call):
        """del N episodes in the same season get part/prev/next metadata."""
        call = multipart_mock_call({"serie_id": 4})
        result = await async_handle_get_episodes(call)
        eps = {ep["id"]: ep for ep in result["episodes"]}

        assert eps[1688]["part"] == 1
        assert eps[1688]["prev_part_id"] is None
        assert eps[1688]["next_part_id"] == 1689

        assert eps[1689]["part"] == 2
        assert eps[1689]["prev_part_id"] == 1688
        assert eps[1689]["next_part_id"] is None

    @pytest.mark.asyncio
    async def test_del_matching_is_case_insensitive(self, multipart_mock_call):
        """'del 1' and 'Del 2' are matched as the same group."""
        call = multipart_mock_call({"serie_id": 4})
        result = await async_handle_get_episodes(call)
        eps = {ep["id"]: ep for ep in result["episodes"]}

        assert eps[1688]["part"] == 1
        assert eps[1689]["part"] == 2

    @pytest.mark.asyncio
    async def test_ratio_parts_are_annotated(self, multipart_mock_call):
        """N:M episodes in the same season get part/prev/next metadata."""
        call = multipart_mock_call({"serie_id": 4})
        result = await async_handle_get_episodes(call)
        eps = {ep["id"]: ep for ep in result["episodes"]}

        assert eps[1691]["part"] == 1
        assert eps[1691]["prev_part_id"] is None
        assert eps[1691]["next_part_id"] == 1692

        assert eps[1692]["part"] == 2
        assert eps[1692]["prev_part_id"] == 1691
        assert eps[1692]["next_part_id"] is None

    @pytest.mark.asyncio
    async def test_regular_episode_has_no_part_fields(self, multipart_mock_call):
        """Episodes without a part suffix get no part/prev/next keys."""
        call = multipart_mock_call({"serie_id": 4})
        result = await async_handle_get_episodes(call)
        eps = {ep["id"]: ep for ep in result["episodes"]}

        assert "part" not in eps[1690]
        assert "prev_part_id" not in eps[1690]
        assert "next_part_id" not in eps[1690]

    @pytest.mark.asyncio
    async def test_lone_part_is_not_annotated(self, multipart_mock_call):
        """A lone 'del 1' with no matching 'del 2' in the same season is not annotated."""
        call = multipart_mock_call({"serie_id": 4})
        result = await async_handle_get_episodes(call)
        eps = {ep["id"]: ep for ep in result["episodes"]}

        assert "part" not in eps[1693]

    @pytest.mark.asyncio
    async def test_parts_are_not_linked_across_seasons(self, multipart_mock_call):
        """Episodes with the same base title in different seasons are not linked."""
        call = multipart_mock_call({"serie_id": 4})
        result = await async_handle_get_episodes(call)
        eps = {ep["id"]: ep for ep in result["episodes"]}

        # ep 1693 is "Afsnit 8 del 1" in Sæson 1, ep 1694 is the same title in Sæson 2
        assert "part" not in eps[1693]
        assert "part" not in eps[1694]


class TestGetLive:
    """Tests for get_live service."""

    @pytest.mark.asyncio
    async def test_get_live_available(self, mock_call):
        """Test getting live when stream is available."""
        call = mock_call({})
        result = await async_handle_get_live(call)

        assert result["available"] is True
        assert result["title"] == "Live Show Now"
        assert result["stream_url"] == "https://stream.example.com/live.m3u8"

    @pytest.mark.asyncio
    async def test_get_live_unavailable(self, mock_call, api_mock):
        """Test getting live when stream is not available."""
        api_mock.async_get_live = AsyncMock(return_value=None)
        call = mock_call({})
        result = await async_handle_get_live(call)

        assert result["available"] is False
