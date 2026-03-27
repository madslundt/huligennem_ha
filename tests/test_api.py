"""Tests for HULiGENNEM API client."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.huligennem.api import HuligennemAPI, HuligennemApiError
from custom_components.huligennem.const import SERIES_CACHE_TTL

from .conftest import (
    SAMPLE_LIVE_WITH_STREAM,
    SAMPLE_LIVE_WITHOUT_STREAM,
    SAMPLE_PLAYLIST,
    SAMPLE_SERIES_PAGE_1,
    SAMPLE_SERIES_PAGE_2,
    SAMPLE_SINGLE_PAGE_SERIES,
    make_inertia_html,
)


def _make_ctx(resp):
    """Wrap a mock response in an async context manager."""
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=resp)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


def _mock_response(text: str = "", json_data: dict | None = None, status: int = 200):
    """Create a mock aiohttp response."""
    resp = AsyncMock()
    resp.status = status
    resp.text = AsyncMock(return_value=text)
    if json_data is not None:
        resp.json = AsyncMock(return_value=json_data)
    return resp


class TestParseInertiaPage:
    """Tests for _parse_inertia_page."""

    def test_valid_html(self, mock_api: HuligennemAPI):
        html = make_inertia_html({"props": {"test": True}})
        result = mock_api._parse_inertia_page(html)
        assert result == {"props": {"test": True}}

    def test_html_entities_unescaped(self, mock_api: HuligennemAPI):
        html = make_inertia_html({"props": {"title": "Test & More"}})
        result = mock_api._parse_inertia_page(html)
        assert result["props"]["title"] == "Test & More"

    def test_missing_data_page(self, mock_api: HuligennemAPI):
        with pytest.raises(HuligennemApiError, match="Could not find data-page"):
            mock_api._parse_inertia_page("<div>No data page here</div>")

    def test_malformed_json(self, mock_api: HuligennemAPI):
        html = '<div data-page="not valid json"></div>'
        with pytest.raises(HuligennemApiError, match="Failed to parse Inertia JSON"):
            mock_api._parse_inertia_page(html)


class TestAsyncGetSeries:
    """Tests for async_get_series."""

    @pytest.mark.asyncio
    async def test_multi_page_fetch(self):
        """Test fetching series across multiple pages."""
        session = MagicMock()
        page1_html = make_inertia_html(SAMPLE_SERIES_PAGE_1)
        page2_html = make_inertia_html(SAMPLE_SERIES_PAGE_2)

        responses = [
            _mock_response(text=page1_html),
            _mock_response(text=page2_html),
        ]
        call_count = 0

        def side_effect(url, **kwargs):
            nonlocal call_count
            resp = responses[call_count]
            call_count += 1
            return _make_ctx(resp)

        session.get = MagicMock(side_effect=side_effect)

        api = HuligennemAPI(session)
        series = await api.async_get_series()

        assert len(series) == 3
        assert series[0]["title"] == "Ultra Nansen"
        assert series[2]["title"] == "Historier fra havet"

    @pytest.mark.asyncio
    async def test_single_page(self):
        """Test fetching series with only one page."""
        session = MagicMock()
        page_html = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)

        resp = _mock_response(text=page_html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        series = await api.async_get_series()

        assert len(series) == 1
        assert series[0]["title"] == "Ultra Nansen"

    @pytest.mark.asyncio
    async def test_caching(self):
        """Test that second call returns cached data."""
        session = MagicMock()
        page_html = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)

        resp = _mock_response(text=page_html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        series1 = await api.async_get_series()
        series2 = await api.async_get_series()

        assert series1 is series2
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_http_error(self):
        """Test HTTP error handling."""
        session = MagicMock()
        resp = _mock_response(status=500)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        with pytest.raises(HuligennemApiError, match="HTTP 500"):
            await api.async_get_series()


class TestAsyncGetPlaylist:
    """Tests for async_get_playlist."""

    @pytest.mark.asyncio
    async def test_fetch_playlist(self):
        """Test fetching a playlist."""
        session = MagicMock()
        resp = _mock_response(json_data=SAMPLE_PLAYLIST)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        playlist = await api.async_get_playlist(48)

        assert len(playlist["data"]["seasons"]) == 2
        assert playlist["data"]["seasons"][0]["episodes"][0]["title"] == "Episode 1"

    @pytest.mark.asyncio
    async def test_playlist_caching(self):
        """Test that playlist is cached per series."""
        session = MagicMock()
        resp = _mock_response(json_data=SAMPLE_PLAYLIST)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        p1 = await api.async_get_playlist(48)
        p2 = await api.async_get_playlist(48)

        assert p1 is p2
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_playlist_http_error(self):
        """Test HTTP error when fetching playlist."""
        session = MagicMock()
        resp = _mock_response(status=404)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        with pytest.raises(HuligennemApiError, match="HTTP 404"):
            await api.async_get_playlist(999)

    @pytest.mark.asyncio
    async def test_playlist_cache_evicts_expired(self):
        """Test that expired entries are evicted from playlist cache."""
        session = MagicMock()
        resp = _mock_response(json_data=SAMPLE_PLAYLIST)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        await api.async_get_playlist(1)

        # Manually expire the cache entry (set timestamp far in the past)
        expired_time = time.monotonic() - SERIES_CACHE_TTL - 1
        api._playlist_cache[1] = (expired_time, api._playlist_cache[1][1])

        # Fetch a different playlist — should evict the expired one
        await api.async_get_playlist(2)
        assert 1 not in api._playlist_cache
        assert 2 in api._playlist_cache


class TestAsyncGetLive:
    """Tests for async_get_live."""

    @pytest.mark.asyncio
    async def test_live_with_stream(self):
        """Test live stream when available."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITH_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        live = await api.async_get_live()

        assert live is not None
        assert live["title"] == "Live Show Now"
        assert live["stream_url"] == "https://stream.example.com/live.m3u8"
        assert live["planned_starts_at"] == "2026-03-27T14:00:00.000000Z"

    @pytest.mark.asyncio
    async def test_live_without_stream(self):
        """Test live stream when not available."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITHOUT_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        live = await api.async_get_live()

        assert live is None

    @pytest.mark.asyncio
    async def test_live_countdown_null(self):
        """Test live when countdown is null."""
        session = MagicMock()
        html = make_inertia_html({"props": {"countdown": None}})
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        live = await api.async_get_live()

        assert live is None

    @pytest.mark.asyncio
    async def test_live_caching(self):
        """Test that live data is cached."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITH_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        live1 = await api.async_get_live()
        live2 = await api.async_get_live()

        assert live1 is live2
        assert session.get.call_count == 1
