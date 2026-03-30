"""API client for the HULiGENNEM platform.

Fetches series, playlists, and live stream data from dererhuligennem.dk.
The site uses Inertia.js, so HTML pages contain embedded JSON in a
``data-page`` attribute which this client extracts via regex.

All public methods include in-memory caching with configurable TTLs
and use asyncio locks to prevent duplicate concurrent fetches.
"""

from __future__ import annotations

import asyncio
import html
import json
import logging
import re
import time
from typing import Any

import aiohttp

from .const import (
    LIVE_STATUS_CACHE_TTL,
    LIVE_URL,
    MAX_PLAYLIST_CACHE_SIZE,
    PLAYLIST_URL,
    REQUEST_TIMEOUT_SECONDS,
    SERIES_CACHE_TTL,
    SERIES_URL,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)

DATA_PAGE_PATTERN = re.compile(r'data-page="([^"]+)"')
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)
_HEADERS = {"User-Agent": USER_AGENT}


def _collect_episode_url(url_map: dict[int, str], episode: dict[str, Any]) -> None:
    """Extract and store the best playback URL for an episode dict."""
    ep_id = episode.get("id")
    if not ep_id:
        return
    audio = episode.get("audio") or {}
    url = audio.get("hosted_url") or audio.get("media_url")
    if url:
        url_map[ep_id] = url


class HuligennemApiError(Exception):
    """Raised when an API request or response parsing fails."""


class HuligennemAPI:
    """Async client for the HULiGENNEM website APIs.

    Args:
        session: An aiohttp client session (typically from HA's
            ``async_get_clientsession``).

    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the API client with an aiohttp session."""
        self._session = session
        self._series_cache: list[dict[str, Any]] | None = None
        self._series_cache_time: float = 0
        self._playlist_cache: dict[int, tuple[float, dict[str, Any]]] = {}
        self._episode_url_cache: dict[int, tuple[float, dict[int, str]]] = {}
        self._live_status_cache: dict[str, Any] | None = None
        self._live_status_cache_time: float = 0
        self._series_lock = asyncio.Lock()
        self._live_lock = asyncio.Lock()

    def _parse_inertia_page(self, html_content: str) -> dict[str, Any]:
        """Extract and parse Inertia.js JSON from an HTML page.

        Args:
            html_content: Raw HTML string containing a ``data-page`` attribute.

        Returns:
            Parsed JSON dict from the Inertia page data.

        Raises:
            HuligennemApiError: If the attribute is missing or JSON is malformed.

        """
        match = DATA_PAGE_PATTERN.search(html_content)
        if not match:
            raise HuligennemApiError("Could not find data-page attribute in HTML")
        try:
            raw = html.unescape(match.group(1))
            return json.loads(raw)
        except (json.JSONDecodeError, ValueError) as err:
            raise HuligennemApiError(f"Failed to parse Inertia JSON: {err}") from err

    async def _fetch(self, url: str) -> str:
        """Fetch a URL and return the response body as text.

        Raises:
            HuligennemApiError: On non-200 status or connection error.

        """
        try:
            async with self._session.get(url, timeout=_REQUEST_TIMEOUT, headers=_HEADERS) as resp:
                if resp.status != 200:
                    raise HuligennemApiError(f"HTTP {resp.status} from {url}")
                return await resp.text()
        except aiohttp.ClientError as err:
            raise HuligennemApiError(f"Request failed for {url}: {err}") from err

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        """Fetch a URL and return the response body as parsed JSON.

        Raises:
            HuligennemApiError: On non-200 status or connection error.

        """
        try:
            async with self._session.get(url, timeout=_REQUEST_TIMEOUT, headers=_HEADERS) as resp:
                if resp.status != 200:
                    raise HuligennemApiError(f"HTTP {resp.status} from {url}")
                return await resp.json()
        except aiohttp.ClientError as err:
            raise HuligennemApiError(f"Request failed for {url}: {err}") from err

    async def async_get_series(self) -> list[dict[str, Any]]:
        """Fetch all series from the website.

        Parses paginated Inertia HTML pages at ``/serier?page=N``.
        Results are cached for ``SERIES_CACHE_TTL`` seconds. Concurrent
        calls are serialized via an asyncio lock to prevent duplicate fetches.

        Returns:
            List of series dicts, each containing ``id``, ``title``,
            ``slug``, and ``poster`` keys.

        """
        now = time.monotonic()
        if self._series_cache is not None and (now - self._series_cache_time) < SERIES_CACHE_TTL:
            return self._series_cache

        async with self._series_lock:
            # Re-check cache under lock (another coroutine may have refreshed)
            now = time.monotonic()
            if (
                self._series_cache is not None
                and (now - self._series_cache_time) < SERIES_CACHE_TTL
            ):
                return self._series_cache

            first_html = await self._fetch(f"{SERIES_URL}?page=1")
            first_page = self._parse_inertia_page(first_html)

            series_data: list[dict[str, Any]] = list(
                first_page.get("props", {}).get("series", {}).get("data", [])
            )
            last_page = first_page.get("props", {}).get("series", {}).get("last_page", 1)

            if last_page > 1:
                pages_html = await asyncio.gather(
                    *(self._fetch(f"{SERIES_URL}?page={page}") for page in range(2, last_page + 1))
                )
                for page_html in pages_html:
                    page_data = self._parse_inertia_page(page_html)
                    series_data.extend(page_data.get("props", {}).get("series", {}).get("data", []))

            self._series_cache = series_data
            self._series_cache_time = time.monotonic()
            return series_data

    async def async_get_playlist(self, serie_id: int) -> dict[str, Any]:
        """Fetch the playlist (seasons + episodes) for a series.

        Uses the clean JSON API at ``/web/support/player/playlist/{serie_id}``.
        Results are cached per-series for ``SERIES_CACHE_TTL`` seconds.
        Expired entries are evicted on each insert, and total cache size
        is capped at ``MAX_PLAYLIST_CACHE_SIZE``.

        Args:
            serie_id: Numeric series identifier.

        Returns:
            Playlist dict with ``data.seasons[].episodes[]`` structure.

        """
        now = time.monotonic()
        if serie_id in self._playlist_cache:
            cache_time, cached_data = self._playlist_cache[serie_id]
            if (now - cache_time) < SERIES_CACHE_TTL:
                return cached_data

        data = await self._fetch_json(f"{PLAYLIST_URL}/{serie_id}")

        # Evict expired entries to prevent unbounded growth
        expired = [k for k, (t, _) in self._playlist_cache.items() if (now - t) >= SERIES_CACHE_TTL]
        for k in expired:
            del self._playlist_cache[k]

        # Cap cache size as a safety net
        if len(self._playlist_cache) >= MAX_PLAYLIST_CACHE_SIZE:
            oldest_key = min(self._playlist_cache, key=lambda k: self._playlist_cache[k][0])
            del self._playlist_cache[oldest_key]

        self._playlist_cache[serie_id] = (now, data)
        return data

    async def async_get_live_status(self) -> dict[str, Any]:
        """Fetch full live status including scheduled times.

        Always returns a dict (never ``None``). Includes countdown data even
        when not on-air so sensors can show the next scheduled broadcast.
        Concurrent calls are serialized via ``_live_lock``. Cached for
        ``LIVE_STATUS_CACHE_TTL`` seconds (slightly under the 60-second
        coordinator poll interval).

        Returns:
            Dict with ``on_air`` (bool), ``title``, ``stream_url``,
            ``planned_starts_at``, and ``planned_ends_at``.

        """
        now = time.monotonic()
        if (
            self._live_status_cache is not None
            and (now - self._live_status_cache_time) < LIVE_STATUS_CACHE_TTL
        ):
            return self._live_status_cache

        async with self._live_lock:
            now = time.monotonic()
            if (
                self._live_status_cache is not None
                and (now - self._live_status_cache_time) < LIVE_STATUS_CACHE_TTL
            ):
                return self._live_status_cache

            live_html = await self._fetch(LIVE_URL)
            page_data = self._parse_inertia_page(live_html)
            props = page_data.get("props", {})

            on_air_raw = props.get("onAir")
            live_show = props.get("liveShow") if on_air_raw else None
            countdown = props.get("countdown")

            on_air = bool(live_show and live_show.get("stream_url"))
            result: dict[str, Any] = {
                "on_air": on_air,
                "title": live_show.get("title", "HULiGENNEM Live")
                if on_air and live_show
                else None,
                "stream_url": live_show.get("stream_url") if on_air and live_show else None,
                "planned_starts_at": countdown.get("planned_starts_at")
                if isinstance(countdown, dict)
                else None,
                "planned_ends_at": countdown.get("planned_ends_at")
                if isinstance(countdown, dict)
                else None,
            }
            self._live_status_cache = result
            self._live_status_cache_time = time.monotonic()
            return result

    async def async_get_live(self) -> dict[str, Any] | None:
        """Fetch current live stream information.

        Delegates to ``async_get_live_status()`` and returns a subset dict
        when on-air, or ``None`` when not currently live.

        Returns:
            Dict with ``title``, ``stream_url``, ``planned_starts_at``,
            and ``planned_ends_at`` if a stream is available, else ``None``.

        """
        status = await self.async_get_live_status()
        if not status["on_air"]:
            return None
        return {
            "title": status["title"],
            "stream_url": status["stream_url"],
            "planned_starts_at": status["planned_starts_at"],
            "planned_ends_at": status["planned_ends_at"],
        }

    async def async_get_episode_url(self, serie_id: int, episode_id: int) -> str | None:
        """Return the best playback URL for an episode.

        Fetches the series detail page (``/serier/{slug}``) which exposes both a
        Spreaker-hosted URL (``audio.hosted_url``) that registers plays in
        HULiGENNEM's statistics, and a backup CDN URL (``audio.media_url``).
        Prefers ``hosted_url`` when available.

        Handles both episodic series (flat episode list in ``props.data``) and
        seasonal series (season objects with nested ``episodes`` in ``props.data``).

        Results are cached per-series for ``SERIES_CACHE_TTL`` seconds.

        Args:
            serie_id: Numeric series identifier.
            episode_id: Numeric episode identifier.

        Returns:
            Playback URL string, or ``None`` if not found.

        """
        now = time.monotonic()
        if serie_id in self._episode_url_cache:
            cache_time, url_map = self._episode_url_cache[serie_id]
            if (now - cache_time) < SERIES_CACHE_TTL:
                return url_map.get(episode_id)

        series = await self.async_get_series()
        slug = next((s.get("slug") for s in series if s.get("id") == serie_id), None)
        if not slug:
            return None

        try:
            serie_html = await self._fetch(f"{SERIES_URL}/{slug}")
            page_data = self._parse_inertia_page(serie_html)
        except HuligennemApiError as err:
            _LOGGER.debug("Could not fetch series detail page for %s: %s", slug, err)
            return None

        url_map: dict[int, str] = {}
        for item in page_data.get("props", {}).get("data", []):
            if "audio" in item:
                # Episodic series: item is a direct episode
                _collect_episode_url(url_map, item)
            elif "episodes" in item:
                # Seasonal series: item is a season containing episodes
                for ep in item.get("episodes", []):
                    _collect_episode_url(url_map, ep)

        self._episode_url_cache[serie_id] = (now, url_map)
        return url_map.get(episode_id)
