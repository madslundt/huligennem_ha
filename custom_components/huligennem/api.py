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
    LIVE_CACHE_TTL,
    LIVE_URL,
    MAX_PLAYLIST_CACHE_SIZE,
    PLAYLIST_URL,
    REQUEST_TIMEOUT_SECONDS,
    SERIES_CACHE_TTL,
    SERIES_URL,
)

_LOGGER = logging.getLogger(__name__)

DATA_PAGE_PATTERN = re.compile(r'data-page="([^"]+)"')
_REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT_SECONDS)


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
        self._live_cache: dict[str, Any] | None = None
        self._live_cache_time: float = 0
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
            async with self._session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
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
            async with self._session.get(url, timeout=_REQUEST_TIMEOUT) as resp:
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
        if (
            self._series_cache is not None
            and (now - self._series_cache_time) < SERIES_CACHE_TTL
        ):
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
            last_page = (
                first_page.get("props", {}).get("series", {}).get("last_page", 1)
            )

            if last_page > 1:
                pages_html = await asyncio.gather(
                    *(
                        self._fetch(f"{SERIES_URL}?page={page}")
                        for page in range(2, last_page + 1)
                    )
                )
                for page_html in pages_html:
                    page_data = self._parse_inertia_page(page_html)
                    series_data.extend(
                        page_data.get("props", {})
                        .get("series", {})
                        .get("data", [])
                    )

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
        expired = [
            k
            for k, (t, _) in self._playlist_cache.items()
            if (now - t) >= SERIES_CACHE_TTL
        ]
        for k in expired:
            del self._playlist_cache[k]

        # Cap cache size as a safety net
        if len(self._playlist_cache) >= MAX_PLAYLIST_CACHE_SIZE:
            oldest_key = min(
                self._playlist_cache, key=lambda k: self._playlist_cache[k][0]
            )
            del self._playlist_cache[oldest_key]

        self._playlist_cache[serie_id] = (now, data)
        return data

    async def async_get_live(self) -> dict[str, Any] | None:
        """Fetch current live stream information.

        Parses the Inertia HTML at ``/live`` for
        ``props.countdown.live_show.stream_url``. Concurrent calls are
        serialized via an asyncio lock. Cached for ``LIVE_CACHE_TTL`` seconds.

        Returns:
            Dict with ``title``, ``stream_url``, ``planned_starts_at``,
            and ``planned_ends_at`` if a stream is available, else ``None``.

        """
        now = time.monotonic()
        if (
            self._live_cache is not None
            and (now - self._live_cache_time) < LIVE_CACHE_TTL
        ):
            return self._live_cache

        async with self._live_lock:
            # Re-check cache under lock
            now = time.monotonic()
            if (
                self._live_cache is not None
                and (now - self._live_cache_time) < LIVE_CACHE_TTL
            ):
                return self._live_cache

            live_html = await self._fetch(LIVE_URL)
            page_data = self._parse_inertia_page(live_html)
            props = page_data.get("props", {})

            countdown = props.get("countdown")
            live_show = (
                countdown.get("live_show") if isinstance(countdown, dict) else None
            )

            if live_show and live_show.get("stream_url"):
                result: dict[str, Any] = {
                    "title": live_show.get("title", "HULiGENNEM Live"),
                    "stream_url": live_show["stream_url"],
                    "planned_starts_at": countdown.get("planned_starts_at"),
                    "planned_ends_at": countdown.get("planned_ends_at"),
                }
            else:
                result = None

            self._live_cache = result
            self._live_cache_time = time.monotonic()
            return result
