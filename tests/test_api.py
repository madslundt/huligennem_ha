"""Tests for HULiGENNEM API client."""

from __future__ import annotations

import contextlib
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.huligennem.api import HuligennemAPI, HuligennemApiError
from custom_components.huligennem.const import LIVE_STATUS_CACHE_TTL, SERIES_CACHE_TTL, USER_AGENT

from .conftest import (
    SAMPLE_LIVE_WITH_STREAM,
    SAMPLE_LIVE_WITHOUT_STREAM,
    SAMPLE_PLAYLIST,
    SAMPLE_SERIES_DETAIL_EPISODIC,
    SAMPLE_SERIES_DETAIL_NO_HOSTED_URL,
    SAMPLE_SERIES_DETAIL_SEASONAL,
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

        assert live1 == live2
        assert session.get.call_count == 1


class TestAsyncGetLiveStatus:
    """Tests for async_get_live_status."""

    @pytest.mark.asyncio
    async def test_status_on_air(self):
        """Test full status when live stream is active."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITH_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        status = await api.async_get_live_status()

        assert status["on_air"] is True
        assert status["stream_url"] == "https://stream.example.com/live.m3u8"
        assert status["title"] == "Live Show Now"
        assert status["planned_starts_at"] == "2026-03-27T14:00:00.000000Z"
        assert status["planned_ends_at"] == "2026-03-27T17:00:00.000000Z"

    @pytest.mark.asyncio
    async def test_status_off_air_has_countdown(self):
        """Test that countdown data is returned even when not on-air."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITHOUT_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        status = await api.async_get_live_status()

        assert status["on_air"] is False
        assert status["stream_url"] is None
        assert status["planned_starts_at"] == "2026-03-28T14:00:00.000000Z"
        assert status["planned_ends_at"] == "2026-03-28T17:00:00.000000Z"

    @pytest.mark.asyncio
    async def test_status_caching(self):
        """Test that full status is cached and only one HTTP request is made."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITH_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        status1 = await api.async_get_live_status()
        status2 = await api.async_get_live_status()

        assert status1 is status2
        assert session.get.call_count == 1

    @pytest.mark.asyncio
    async def test_status_null_countdown(self):
        """Test that null countdown does not raise and returns None timestamps."""
        session = MagicMock()
        html = make_inertia_html({"props": {"onAir": None, "countdown": None}})
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        status = await api.async_get_live_status()

        assert status["on_air"] is False
        assert status["planned_starts_at"] is None
        assert status["planned_ends_at"] is None

    @pytest.mark.asyncio
    async def test_status_cache_expires(self):
        """Test that cached status is refreshed after TTL expires."""
        session = MagicMock()
        html = make_inertia_html(SAMPLE_LIVE_WITH_STREAM)
        resp = _mock_response(text=html)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        await api.async_get_live_status()

        # Manually expire the cache
        import time
        api._live_status_cache_time = time.monotonic() - LIVE_STATUS_CACHE_TTL - 1

        await api.async_get_live_status()
        assert session.get.call_count == 2


class TestAsyncGetEpisodeUrl:
    """Tests for async_get_episode_url."""

    def _make_session(self, *html_responses):
        """Return a mock session that serves HTML responses in order."""
        session = MagicMock()
        responses = [_mock_response(text=html) for html in html_responses]
        idx = 0

        def side_effect(url, **kwargs):
            nonlocal idx
            resp = responses[idx % len(responses)]
            idx += 1
            return _make_ctx(resp)

        session.get = MagicMock(side_effect=side_effect)
        return session

    @pytest.mark.asyncio
    async def test_episodic_series_returns_hosted_url(self):
        """Test that episodic series returns the Spreaker hosted_url."""
        series_page = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)
        detail_page = make_inertia_html(SAMPLE_SERIES_DETAIL_EPISODIC)
        session = self._make_session(series_page, detail_page)

        api = HuligennemAPI(session)
        url = await api.async_get_episode_url(1, 100)

        assert url == "https://api.spreaker.com/v2/episodes/999001/play.mp3"

    @pytest.mark.asyncio
    async def test_seasonal_series_returns_hosted_url(self):
        """Test that seasonal series (nested episodes) returns the Spreaker hosted_url."""
        series_page = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)
        detail_page = make_inertia_html(SAMPLE_SERIES_DETAIL_SEASONAL)
        session = self._make_session(series_page, detail_page)

        api = HuligennemAPI(session)
        url = await api.async_get_episode_url(1, 100)

        assert url == "https://api.spreaker.com/v2/episodes/999001/play.mp3"

    @pytest.mark.asyncio
    async def test_falls_back_to_media_url_when_hosted_url_null(self):
        """Test fallback to media_url when hosted_url is null."""
        series_page = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)
        detail_page = make_inertia_html(SAMPLE_SERIES_DETAIL_NO_HOSTED_URL)
        session = self._make_session(series_page, detail_page)

        api = HuligennemAPI(session)
        url = await api.async_get_episode_url(1, 100)

        assert url == "https://huligennem-production.imgix.net/ep1.mp3"

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_episode(self):
        """Test returns None when episode ID is not in the series."""
        series_page = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)
        detail_page = make_inertia_html(SAMPLE_SERIES_DETAIL_EPISODIC)
        session = self._make_session(series_page, detail_page)

        api = HuligennemAPI(session)
        url = await api.async_get_episode_url(1, 999)

        assert url is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unknown_serie(self):
        """Test returns None when serie ID is not in the series list."""
        series_page = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)
        session = MagicMock()
        resp = _mock_response(text=series_page)
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        url = await api.async_get_episode_url(999, 100)

        assert url is None

    @pytest.mark.asyncio
    async def test_caches_episode_url_map(self):
        """Test that the episode URL map is cached per-series."""
        series_page = make_inertia_html(SAMPLE_SINGLE_PAGE_SERIES)
        detail_page = make_inertia_html(SAMPLE_SERIES_DETAIL_EPISODIC)
        session = self._make_session(series_page, detail_page)

        api = HuligennemAPI(session)
        url1 = await api.async_get_episode_url(1, 100)
        url2 = await api.async_get_episode_url(1, 101)

        assert url1 == "https://api.spreaker.com/v2/episodes/999001/play.mp3"
        assert url2 == "https://api.spreaker.com/v2/episodes/999002/play.mp3"
        # Series page fetched once + detail page fetched once = 2 total calls
        assert session.get.call_count == 2


class TestUserAgentHeader:
    """Tests that all requests include the custom User-Agent header."""

    @pytest.mark.asyncio
    async def test_fetch_sends_user_agent(self):
        """Test that _fetch passes the User-Agent header."""
        session = MagicMock()
        resp = _mock_response(text="<div></div>")
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        with contextlib.suppress(Exception):
            await api._fetch("https://example.com")

        _, kwargs = session.get.call_args
        assert kwargs.get("headers", {}).get("User-Agent") == USER_AGENT

    @pytest.mark.asyncio
    async def test_fetch_json_sends_user_agent(self):
        """Test that _fetch_json passes the User-Agent header."""
        session = MagicMock()
        resp = _mock_response(json_data={"ok": True})
        session.get = MagicMock(return_value=_make_ctx(resp))

        api = HuligennemAPI(session)
        await api._fetch_json("https://example.com")

        _, kwargs = session.get.call_args
        assert kwargs.get("headers", {}).get("User-Agent") == USER_AGENT
