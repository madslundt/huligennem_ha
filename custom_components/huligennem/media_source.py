"""Media source implementation for HULiGENNEM.

Exposes the HULiGENNEM podcast catalog and live radio as a browsable
media source in Home Assistant's Media Browser. Supports a three-level
hierarchy: Series -> Seasons -> Episodes, with single-season series
flattened to skip the season level.

Media identifiers:
    - ``live`` -> HLS live stream
    - ``episode/{episode_id}/serie/{serie_id}`` -> Direct MP3
    - ``series/{id}`` -> Browse series (seasons or episodes)
    - ``series/{id}/season/{season_id}`` -> Browse season episodes
"""

from __future__ import annotations

from homeassistant.components.media_player import MediaClass
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.components.media_source.error import MediaSourceError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .api import HuligennemApiError
from .const import DOMAIN
from .services import get_api


async def async_get_media_source(hass: HomeAssistant) -> HuligennemMediaSource:
    """Set up and return the HULiGENNEM media source."""
    return HuligennemMediaSource(hass)


class HuligennemMediaSource(MediaSource):
    """Provide HULiGENNEM podcasts and live radio as a media source.

    Integrates with HA's Media Browser to allow users to browse
    series, seasons, and episodes with thumbnails.
    """

    name = "HULiGENNEM"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item identifier to a playable URL.

        Args:
            item: Media source item with an identifier string.

        Returns:
            PlayMedia with the direct URL and MIME type.

        Raises:
            Unresolvable: If the identifier is invalid or the media
                cannot be found.

        """
        identifier = item.identifier
        if not identifier:
            raise Unresolvable("No identifier provided")

        if identifier == "live":
            return await self._resolve_live(item.target_media_player)

        if identifier.startswith("episode/"):
            return await self._resolve_episode(identifier)

        raise Unresolvable(f"Unknown media identifier: {identifier}")

    async def _resolve_live(self, target_media_player: str | None = None) -> PlayMedia:
        """Resolve the live stream to a playable URL.

        Returns an ``hls-radio://`` URL with content type ``music`` when the
        target is a Sonos device, which requires this scheme to play HLS
        streams via its built-in live player. All other players receive the
        standard ``https://`` URL with ``application/x-mpegURL``.
        """
        api = get_api(self.hass)
        try:
            live = await api.async_get_live()
        except HuligennemApiError as err:
            raise Unresolvable(f"Failed to fetch live stream: {err}") from err
        if not live:
            raise Unresolvable("Live stream is not currently available")

        stream_url = live["stream_url"]

        if self._is_sonos(target_media_player):
            stream_url = stream_url.replace("https://", "hls-radio://", 1)
            stream_url = stream_url.replace("http://", "hls-radio://", 1)
            return PlayMedia(stream_url, "music")

        return PlayMedia(stream_url, "application/x-mpegURL")

    async def _resolve_episode(self, identifier: str) -> PlayMedia:
        """Resolve an episode identifier to its direct MP3 URL.

        Expected format: ``episode/{episode_id}/serie/{serie_id}``

        Prefers the Spreaker-hosted URL (registers plays in HULiGENNEM's
        statistics) and falls back to the backup CDN URL from the playlist API.
        """
        parts = identifier.split("/")
        if len(parts) != 4:
            raise Unresolvable(f"Invalid episode identifier: {identifier}")

        try:
            episode_id = int(parts[1])
            serie_id = int(parts[3])
        except ValueError as err:
            raise Unresolvable(f"Invalid episode identifier: {identifier}") from err

        api = get_api(self.hass)

        # Prefer the Spreaker-hosted URL — it counts as a play in HULiGENNEM's stats.
        url = await api.async_get_episode_url(serie_id, episode_id)
        if url:
            return PlayMedia(url, "audio/mpeg")

        # Fall back to the playlist API (backup CDN URL).
        try:
            playlist = await api.async_get_playlist(serie_id)
        except HuligennemApiError as err:
            raise Unresolvable(f"Failed to fetch episode: {err}") from err
        data = playlist.get("data", {})

        # Episodic series: episodes at top level
        for episode in data.get("episodes", []):
            if episode.get("id") == episode_id:
                media_url = episode.get("media", {}).get("url")
                if media_url:
                    return PlayMedia(media_url, "audio/mpeg")
                raise Unresolvable("Episode has no media URL")

        # Seasonal series: episodes nested under seasons
        for season in data.get("seasons", []):
            for episode in season.get("episodes", []):
                if episode.get("id") == episode_id:
                    media_url = episode.get("media", {}).get("url")
                    if media_url:
                        return PlayMedia(media_url, "audio/mpeg")
                    raise Unresolvable("Episode has no media URL")

        raise Unresolvable(f"Episode {episode_id} not found in series {serie_id}")

    def _is_sonos(self, entity_id: str | None) -> bool:
        """Return True if the target media player is a Sonos device."""
        if not entity_id:
            return False
        entity_reg = er.async_get(self.hass)
        entry = entity_reg.async_get(entity_id)
        return entry is not None and entry.platform == "sonos"

    async def async_browse_media(self, item: MediaSourceItem) -> BrowseMediaSource:
        """Browse the media hierarchy.

        Routes based on the identifier prefix to the appropriate
        browse handler (root, series, or season).
        """
        identifier = item.identifier

        if not identifier:
            return await self._browse_root()

        if identifier.startswith("series/") and "/season/" in identifier:
            return await self._browse_season(identifier)

        if identifier.startswith("series/"):
            return await self._browse_series(identifier)

        raise MediaSourceError(f"Unknown browse identifier: {identifier}")

    async def _browse_root(self) -> BrowseMediaSource:
        """Browse the root level: live radio + all series."""
        api = get_api(self.hass)
        series = await api.async_get_series()

        children: list[BrowseMediaSource] = []

        children.append(
            BrowseMediaSource(
                domain=DOMAIN,
                identifier="live",
                media_class=MediaClass.CHANNEL,
                media_content_type="audio/mpeg",
                title="Live Radio",
                can_play=True,
                can_expand=False,
                thumbnail=None,
            )
        )

        for serie in series:
            poster = serie.get("poster")
            thumbnail = poster.get("media_url") if isinstance(poster, dict) else None
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"series/{serie['id']}",
                    media_class=MediaClass.PODCAST,
                    media_content_type="",
                    title=serie.get("title", "Unknown"),
                    can_play=False,
                    can_expand=True,
                    thumbnail=thumbnail,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type="",
            title="HULiGENNEM",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_series(self, identifier: str) -> BrowseMediaSource:
        """Browse a series: show seasons, or episodes if single season."""
        try:
            serie_id = int(identifier.split("/")[1])
        except (ValueError, IndexError) as err:
            raise MediaSourceError(f"Invalid series identifier: {identifier}") from err

        api = get_api(self.hass)
        playlist = await api.async_get_playlist(serie_id)

        data = playlist.get("data", {})
        serie_title = data.get("title", "Unknown")
        seasons = data.get("seasons", [])
        top_episodes = data.get("episodes", [])

        children: list[BrowseMediaSource] = []

        if top_episodes and not seasons:
            # Episodic series: episodes live at the top level, no season grouping
            for episode in top_episodes:
                children.append(self._episode_to_browse(episode, serie_id))
        elif len(seasons) == 1:
            for episode in seasons[0].get("episodes", []):
                children.append(self._episode_to_browse(episode, serie_id))
        else:
            for season in seasons:
                episodes = season.get("episodes", [])
                season_thumbnail = episodes[0].get("poster") if episodes else None
                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=f"series/{serie_id}/season/{season['id']}",
                        media_class=MediaClass.PODCAST,
                        media_content_type="",
                        title=season.get("title", f"Season {season.get('id')}"),
                        can_play=False,
                        can_expand=True,
                        thumbnail=season_thumbnail,
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.PODCAST,
            media_content_type="",
            title=serie_title,
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_season(self, identifier: str) -> BrowseMediaSource:
        """Browse a season: show its episodes."""
        parts = identifier.split("/")
        try:
            serie_id = int(parts[1])
            season_id = int(parts[3])
        except (ValueError, IndexError) as err:
            raise MediaSourceError(f"Invalid season identifier: {identifier}") from err

        api = get_api(self.hass)
        playlist = await api.async_get_playlist(serie_id)

        season_title = "Unknown"
        children: list[BrowseMediaSource] = []

        for season in playlist.get("data", {}).get("seasons", []):
            if season.get("id") == season_id:
                season_title = season.get("title", f"Season {season_id}")
                for episode in season.get("episodes", []):
                    children.append(self._episode_to_browse(episode, serie_id))
                break

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=identifier,
            media_class=MediaClass.PODCAST,
            media_content_type="",
            title=season_title,
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _episode_to_browse(self, episode: dict, serie_id: int) -> BrowseMediaSource:
        """Convert an episode dict to a browsable media source item."""
        media = episode.get("media", {})
        duration = media.get("duration_in_seconds")
        title = episode.get("title", "Unknown")
        if duration:
            minutes = duration // 60
            title = f"{title} ({minutes} min)"

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"episode/{episode['id']}/serie/{serie_id}",
            media_class=MediaClass.PODCAST,
            media_content_type="audio/mpeg",
            title=title,
            can_play=True,
            can_expand=False,
            thumbnail=episode.get("poster"),
        )
