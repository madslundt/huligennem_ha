# HULiGENNEM for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![CI](https://github.com/madslundt/huligennem_ha/actions/workflows/ci.yml/badge.svg)](https://github.com/madslundt/huligennem_ha/actions/workflows/ci.yml)

Listen to podcasts and live radio from [dererhuligennem.dk](https://dererhuligennem.dk) directly in Home Assistant.

HULiGENNEM is a Danish public-service children's and youth audio platform with 63+ series, seasonal episodes, and live radio.

## Features

- **Media Browser** — Browse all series, seasons, and episodes with thumbnails
- **Live Radio** — Listen to the live HULiGENNEM radio stream (HLS)
- **Direct Playback** — Episodes play as direct MP3 on any media player entity
- **Play statistics** — Every play is routed through HULiGENNEM's streaming infrastructure, so it counts in their official listener statistics
- **Services** — Search series, get episodes, and check live status via HA services
- **Automations** — Play specific episodes or live radio on any speaker via automations

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots menu → **Custom repositories**
3. Add `https://github.com/madslundt/huligennem_ha` as an **Integration**
4. Search for "HULiGENNEM" and install
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/huligennem` folder to your Home Assistant `custom_components/` directory
2. Restart Home Assistant

## Setup

[![Add integration to my Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=huligennem)

Or manually:

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **HULiGENNEM**
3. Click **Submit** to confirm

No configuration is needed — the integration works out of the box.

## Usage

### Media Browser

Open **Media** in the sidebar → select **HULiGENNEM** to browse:

- **Live Radio** — Play the live stream (when on-air)
- **Series** — Browse all available series → seasons → episodes

Click any episode to play it on a connected media player.

### Playing on a media player

You can send any episode or the live stream to a `media_player` entity
using the `media_player.play_media` action. The `media_content_id` uses the
`media-source://` URI scheme.

#### Play a specific episode

To play an episode, you need the **episode ID** and the **series ID**.
You can find these using the `huligennem.get_episodes` service (see below).

```yaml
action: media_player.play_media
target:
  entity_id: media_player.kitchen_speaker
data:
  media_content_type: audio/mpeg
  media_content_id: media-source://huligennem/episode/729/serie/48
```

#### Play the live radio

```yaml
action: media_player.play_media
target:
  entity_id: media_player.living_room
data:
  media_content_type: application/x-mpegURL
  media_content_id: media-source://huligennem/live
```

> **Note:** Live radio requires the stream to be on-air. Check with
> `huligennem.get_live` first, or wrap it in a condition.

#### Browse via media_player

You can also open the media browser programmatically:

```yaml
action: media_player.browse_media
target:
  entity_id: media_player.kitchen_speaker
data:
  media_content_type: ""
  media_content_id: media-source://huligennem
```

### Finding episode IDs

Use the `huligennem.get_episodes` service to look up IDs:

```yaml
action: huligennem.get_episodes
data:
  serie_id: 48
response_variable: result
```

The response contains all episodes with their IDs:

```json
{
  "episodes": [
    {
      "id": 729,
      "title": "Far togene Elliot til at sige \"WAUW\"?",
      "season": "\"WAUW\" med Frederik",
      "media_url": "https://api.spreaker.com/v2/episodes/12345678/play.mp3",
      "duration_seconds": 3918
    }
  ]
}
```

Then use `episode/{id}/serie/{serie_id}` in the `media_content_id`.

### Services

All services return response data directly (use `response_variable` to capture).

#### `huligennem.search_series`

Search for series by title (case-insensitive substring match).

```yaml
action: huligennem.search_series
data:
  query: "ultra"
response_variable: results
```

#### `huligennem.get_episodes`

Get all episodes for a given series.

```yaml
action: huligennem.get_episodes
data:
  serie_id: 48
response_variable: episodes
```

#### `huligennem.get_live`

Get current live stream information.

```yaml
action: huligennem.get_live
response_variable: live
```

### Automation Examples

> Every play triggered via automation (or any other method) routes through HULiGENNEM's streaming infrastructure and counts in their official listener statistics — so playing from Home Assistant directly supports the platform.

#### Play a morning podcast for the kids

```yaml
automation:
  - alias: "Morning HULiGENNEM podcast"
    trigger:
      - platform: time
        at: "07:30:00"
    condition:
      - condition: time
        weekday: [mon, tue, wed, thu, fri]
    action:
      - action: media_player.play_media
        target:
          entity_id: media_player.kitchen_speaker
        data:
          media_content_type: audio/mpeg
          media_content_id: media-source://huligennem/episode/729/serie/48
```

#### Play live radio when it's on-air

```yaml
automation:
  - alias: "HULiGENNEM live radio"
    trigger:
      - platform: time
        at: "14:30:00"
    action:
      - action: huligennem.get_live
        response_variable: live_info
      - condition: template
        value_template: "{{ live_info.available }}"
      - action: media_player.play_media
        target:
          entity_id: media_player.living_room
        data:
          media_content_type: application/x-mpegURL
          media_content_id: media-source://huligennem/live

```

#### Search and play a random episode from a series

```yaml
script:
  play_random_huligennem:
    alias: "Play random HULiGENNEM episode"
    sequence:
      - action: huligennem.get_episodes
        data:
          serie_id: 48
        response_variable: result
      - variables:
          random_ep: >
            {{ result.episodes | random }}
      - action: media_player.play_media
        target:
          entity_id: media_player.bedroom_speaker
        data:
          media_content_type: audio/mpeg
          media_content_id: >
            media-source://huligennem/episode/{{ random_ep.id }}/serie/48
```

## Development

This project uses [uv](https://docs.astral.sh/uv/) for dependency management
and [ruff](https://docs.astral.sh/ruff/) for linting.

```bash
# Install dependencies
uv sync --group dev

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check .

# Format
uv run ruff format .
```
