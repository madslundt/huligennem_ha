"""Shared fixtures for HULiGENNEM tests."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from custom_components.huligennem.api import HuligennemAPI

SAMPLE_SERIES_PAGE_1 = {
    "props": {
        "series": {
            "data": [
                {
                    "id": 1,
                    "title": "Ultra Nansen",
                    "slug": "ultra-nansen",
                    "poster": {"media_url": "https://cdn.example.com/poster1.jpg"},
                },
                {
                    "id": 2,
                    "title": "Dansen med DR",
                    "slug": "dansen-med-dr",
                    "poster": {"media_url": "https://cdn.example.com/poster2.jpg"},
                },
            ],
            "last_page": 2,
        }
    }
}

SAMPLE_SERIES_PAGE_2 = {
    "props": {
        "series": {
            "data": [
                {
                    "id": 3,
                    "title": "Historier fra havet",
                    "slug": "historier-fra-havet",
                    "poster": None,
                },
            ],
            "last_page": 2,
        }
    }
}

SAMPLE_SINGLE_PAGE_SERIES = {
    "props": {
        "series": {
            "data": [
                {
                    "id": 1,
                    "title": "Ultra Nansen",
                    "slug": "ultra-nansen",
                    "poster": {"media_url": "https://cdn.example.com/poster1.jpg"},
                },
            ],
            "last_page": 1,
        }
    }
}

SAMPLE_PLAYLIST = {
    "data": {
        "id": 1,
        "title": "Ultra Nansen",
        "type": "podcast",
        "seasons": [
            {
                "id": 10,
                "title": "Sæson 1",
                "episodes": [
                    {
                        "id": 100,
                        "title": "Episode 1",
                        "poster": "https://cdn.example.com/ep1.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1.mp3",
                            "duration_in_seconds": 600,
                        },
                    },
                    {
                        "id": 101,
                        "title": "Episode 2",
                        "poster": "https://cdn.example.com/ep2.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep2.mp3",
                            "duration_in_seconds": 900,
                        },
                    },
                ],
            },
            {
                "id": 11,
                "title": "Sæson 2",
                "episodes": [
                    {
                        "id": 200,
                        "title": "Episode 1",
                        "poster": "https://cdn.example.com/s2ep1.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/s2ep1.mp3",
                            "duration_in_seconds": 720,
                        },
                    },
                ],
            },
        ],
    }
}

SAMPLE_PLAYLIST_SINGLE_SEASON = {
    "data": {
        "id": 1,
        "title": "Ultra Nansen",
        "type": "podcast",
        "seasons": [
            {
                "id": 10,
                "title": "Sæson 1",
                "episodes": [
                    {
                        "id": 100,
                        "title": "Episode 1",
                        "poster": "https://cdn.example.com/ep1.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1.mp3",
                            "duration_in_seconds": 600,
                        },
                    },
                ],
            },
        ],
    }
}

SAMPLE_LIVE_WITH_STREAM = {
    "props": {
        "countdown": {
            "id": 1,
            "title": "Live Show Now",
            "planned_starts_at": "2026-03-27T14:00:00.000000Z",
            "planned_ends_at": "2026-03-27T17:00:00.000000Z",
            "live_show": {
                "id": 2,
                "title": "Live Show Now",
                "stream_url": "https://stream.example.com/live.m3u8",
            },
        }
    }
}

SAMPLE_LIVE_WITHOUT_STREAM = {
    "props": {
        "countdown": {
            "id": 1,
            "title": "Next Show",
            "planned_starts_at": "2026-03-28T14:00:00.000000Z",
            "planned_ends_at": "2026-03-28T17:00:00.000000Z",
            "live_show": None,
        }
    }
}


def make_inertia_html(data: dict) -> str:
    """Create a fake Inertia.js HTML page with data-page attribute."""
    escaped = json.dumps(data).replace('"', "&quot;").replace("<", "&lt;")
    return f'<div id="app" data-page="{escaped}"></div>'


@pytest.fixture
def mock_session():
    """Create a mock aiohttp ClientSession."""
    return MagicMock()


@pytest.fixture
def mock_api(mock_session):
    """Create a HuligennemAPI with a mock session."""
    return HuligennemAPI(mock_session)


@pytest.fixture
def mock_config_entry():
    """Create a mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry_id"
    entry.data = {}
    entry.title = "HULiGENNEM"
    return entry
