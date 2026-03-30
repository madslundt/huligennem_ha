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
- **Live Status Sensors** — `binary_sensor` for on-air state and `sensor` entities for next scheduled start/end times, enabling native HA automations
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

### Live Status Entities

Three entities are automatically created under a **HULiGENNEM** device:

| Entity | Type | Description |
|--------|------|-------------|
| `binary_sensor.huligennem_on_air` | Binary sensor | `on` when broadcasting live, `off` otherwise |
| `sensor.huligennem_next_live_start` | Sensor (timestamp) | Scheduled start of the next/current live show |
| `sensor.huligennem_next_live_end` | Sensor (timestamp) | Scheduled end of the next/current live show |

The binary sensor and timestamp sensors use event-driven polling: the next check is scheduled based on when a state change is expected.

- **Off air, future start known** — polls 1 minute before `planned_starts_at` to catch the show going live
- **On air, future end known** — polls 1 minute after `planned_ends_at` to catch the show ending
- **No schedule available** — falls back to polling every 24 hours (minimum once a day)

The timestamp sensors are populated from the API's `countdown` data, so `next_live_start` and `next_live_end` are available even when the show is not currently on air, letting you see when the next broadcast is scheduled.

### Automation Examples

> Every play triggered via automation (or any other method) routes through HULiGENNEM's streaming infrastructure and counts in their official listener statistics — so playing from Home Assistant directly supports the platform.

#### Auto-start live radio when the show goes live

```yaml
automation:
  - alias: "Start HULiGENNEM when live begins"
    trigger:
      - platform: state
        entity_id: binary_sensor.huligennem_on_air
        from: "off"
        to: "on"
    action:
      - action: media_player.play_media
        target:
          entity_id: media_player.living_room
        data:
          media_content_type: application/x-mpegURL
          media_content_id: media-source://huligennem/live
```

#### Notify before the live show starts

```yaml
automation:
  - alias: "Notify 5 minutes before HULiGENNEM live"
    trigger:
      - platform: template
        value_template: >
          {{ (as_timestamp(states('sensor.huligennem_next_live_start')) - as_timestamp(now())) | int < 300
             and states('binary_sensor.huligennem_on_air') == 'off' }}
    action:
      - action: notify.mobile_app_my_phone
        data:
          message: "HULiGENNEM goes live in 5 minutes!"
```

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

#### Play live radio when it's on-air (sensor-based)

```yaml
automation:
  - alias: "HULiGENNEM live radio"
    trigger:
      - platform: state
        entity_id: binary_sensor.huligennem_on_air
        to: "on"
    action:
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
