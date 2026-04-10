"""Constants for the HULiGENNEM integration.

Defines base URLs for the dererhuligennem.dk platform APIs,
cache TTL values, and other configuration constants.
"""

DOMAIN = "huligennem"
"""Integration domain identifier used throughout Home Assistant."""

BASE_URL = "https://dererhuligennem.dk"
"""Base URL for the HULiGENNEM website."""

SERIES_URL = f"{BASE_URL}/serier"
"""URL for paginated series listing (Inertia.js HTML with embedded JSON)."""

PLAYLIST_URL = f"{BASE_URL}/web/support/player/playlist"
"""URL prefix for series playlist API (clean JSON). Append /{serie_id}."""

LIVE_URL = f"{BASE_URL}/live"
"""URL for live stream page (Inertia.js HTML with embedded JSON)."""

SERIES_CACHE_TTL = 3600
"""Time-to-live in seconds for series and playlist caches (1 hour)."""

LIVE_STATUS_CACHE_TTL = 55
"""Time-to-live in seconds for the full live-status cache.

Short enough that user-triggered plays and coordinator polls get timely data
without hammering the API."""

MAX_PLAYLIST_CACHE_SIZE = 100
"""Maximum number of playlist entries to keep in the in-memory cache."""

REQUEST_TIMEOUT_SECONDS = 10
"""HTTP request timeout in seconds to prevent blocking the HA event loop."""

USER_AGENT = "HomeAssistant"
"""User-Agent header sent with all HTTP requests for play tracking."""
