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

SAMPLE_PLAYLIST_EPISODIC = {
    "data": {
        "id": 2,
        "title": "Morgenknas",
        "type": "podcast",
        "seasons": [],
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
    }
}

SAMPLE_PLAYLIST_MULTIPART = {
    "data": {
        "id": 4,
        "title": "Multi-Part Test Show",
        "type": "podcast",
        "seasons": [
            {
                "id": 20,
                "title": "Sæson 1",
                "episodes": [
                    # Multi-part "del N" pair
                    {
                        "id": 1688,
                        "title": "Afsnit 5 del 1",
                        "poster": "https://cdn.example.com/ep1688.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1688.mp3",
                            "duration_in_seconds": 1800,
                        },
                    },
                    {
                        "id": 1689,
                        "title": "Afsnit 5 Del 2",
                        "poster": "https://cdn.example.com/ep1689.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1689.mp3",
                            "duration_in_seconds": 2100,
                        },
                    },
                    # Regular episode (no part)
                    {
                        "id": 1690,
                        "title": "Afsnit 6",
                        "poster": "https://cdn.example.com/ep1690.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1690.mp3",
                            "duration_in_seconds": 3000,
                        },
                    },
                    # Multi-part "N:M" pair
                    {
                        "id": 1691,
                        "title": "Afsnit 7 1:2",
                        "poster": "https://cdn.example.com/ep1691.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1691.mp3",
                            "duration_in_seconds": 1200,
                        },
                    },
                    {
                        "id": 1692,
                        "title": "Afsnit 7 2:2",
                        "poster": "https://cdn.example.com/ep1692.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1692.mp3",
                            "duration_in_seconds": 1500,
                        },
                    },
                    # Lone "del 1" — no matching "del 2" in this season
                    {
                        "id": 1693,
                        "title": "Afsnit 8 del 1",
                        "poster": "https://cdn.example.com/ep1693.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1693.mp3",
                            "duration_in_seconds": 900,
                        },
                    },
                ],
            },
            {
                "id": 21,
                "title": "Sæson 2",
                "episodes": [
                    # Same base title as the lone ep above — must NOT be cross-linked
                    {
                        "id": 1694,
                        "title": "Afsnit 8 del 1",
                        "poster": "https://cdn.example.com/ep1694.jpg",
                        "media": {
                            "url": "https://huligennem-production.imgix.net/ep1694.mp3",
                            "duration_in_seconds": 950,
                        },
                    },
                ],
            },
        ],
    }
}

SAMPLE_LIVE_WITH_STREAM = {
    "props": {
        "onAir": True,
        "liveShow": {
            "id": 2,
            "title": "Live Show Now",
            "stream_url": "https://stream.example.com/live.m3u8",
        },
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
        },
    }
}

SAMPLE_LIVE_WITHOUT_STREAM = {
    "props": {
        "onAir": None,
        "liveShow": None,
        "countdown": {
            "id": 1,
            "title": "Next Show",
            "planned_starts_at": "2026-03-28T14:00:00.000000Z",
            "planned_ends_at": "2026-03-28T17:00:00.000000Z",
            "live_show": {
                "id": 2,
                "title": "Next Show",
                "stream_url": "https://stream.example.com/live.m3u8",
            },
        },
    }
}


SAMPLE_SERIES_DETAIL_EPISODIC = {
    "props": {
        "data": [
            {
                "id": 100,
                "title": "Episode 1",
                "audio": {
                    "hosted_url": "https://api.spreaker.com/v2/episodes/999001/play.mp3",
                    "media_url": "https://huligennem-production.imgix.net/ep1.mp3",
                    "length_in_seconds": 600,
                },
            },
            {
                "id": 101,
                "title": "Episode 2",
                "audio": {
                    "hosted_url": "https://api.spreaker.com/v2/episodes/999002/play.mp3",
                    "media_url": "https://huligennem-production.imgix.net/ep2.mp3",
                    "length_in_seconds": 900,
                },
            },
        ]
    }
}

SAMPLE_SERIES_DETAIL_SEASONAL = {
    "props": {
        "data": [
            {
                "id": 10,
                "title": "Sæson 1",
                "episodes": [
                    {
                        "id": 100,
                        "title": "Episode 1",
                        "audio": {
                            "hosted_url": "https://api.spreaker.com/v2/episodes/999001/play.mp3",
                            "media_url": "https://huligennem-production.imgix.net/ep1.mp3",
                            "length_in_seconds": 600,
                        },
                    }
                ],
            }
        ]
    }
}

SAMPLE_SERIES_DETAIL_NO_HOSTED_URL = {
    "props": {
        "data": [
            {
                "id": 100,
                "title": "Episode 1",
                "audio": {
                    "hosted_url": None,
                    "media_url": "https://huligennem-production.imgix.net/ep1.mp3",
                    "length_in_seconds": 600,
                },
            }
        ]
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
