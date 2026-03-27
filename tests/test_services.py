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
    SAMPLE_SERIES_PAGE_1,
)


@pytest.fixture
def api_mock():
    """Create a mock API."""
    api = AsyncMock()
    api.async_get_series = AsyncMock(
        return_value=SAMPLE_SERIES_PAGE_1["props"]["series"]["data"]
    )
    api.async_get_playlist = AsyncMock(return_value=SAMPLE_PLAYLIST)
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
    entry.runtime_data = api_mock
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
            "https://huligennem-production.imgix.net/ep1.mp3"
        )
        assert result["episodes"][0]["duration_seconds"] == 600
        assert result["episodes"][0]["season"] == "Sæson 1"


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
