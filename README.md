# RD4 Afvalkalender for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

Brings your [RD4](https://www.rd4.nl) waste collection calendar into Home Assistant:
a calendar, a sensor per waste type, and a "next pickup" summary. Configured entirely in
the UI, no YAML.

> **Unofficial.** This integration is not affiliated with RD4. It reads the same public
> JSON API that powers <https://mijn.rd4.nl/kalender>. That API is undocumented and may
> change without notice. Data is refreshed twice a day.

## Installation

### HACS (recommended)

1. HACS → ⋮ → **Custom repositories** → add `https://github.com/dash82/ha-rd4-afval`
   as category **Integration**.
2. Download **RD4 Afvalkalender**, then restart Home Assistant.
3. **Settings → Devices & services → Add integration → RD4 Afvalkalender**. A form opens asking for your
   postcode, house number and (optionally) house number extension, see [Configuration](#configuration).

### Manual

Copy `custom_components/rd4_afval` into your Home Assistant `custom_components` folder and restart.

## Configuration

| Field | Example | Notes |
|---|---|---|
| Postcode | `1234 AB` | Spaces and lower case are fine |
| House number | `12` | Number only |
| Extension | `A` | Optional. If RD4 doesn't recognise it, the form lists the extensions it knows |

Add the integration once per address. **Settings → Devices & services → RD4 → ⋮ → Reconfigure** moves an
entry to another address.

## Entities

For each address you get one device with:

| Entity | State | Attributes |
|---|---|---|
| `calendar.…_waste_collection` | on while a pickup is today | all pickups as all-day events |
| `sensor.…_<waste type>` (date) | next pickup of that type | `days_until`, `upcoming` (next 5 dates) |
| `sensor.…_next_pickup` (date) | next collection day | `days_until`, `waste_types`, `waste_type_names` |
| `sensor.…_next_pickup_types` | e.g. `GFT en etensresten, PMD-verpakkingen` | |

Waste types currently supported: residual waste, GFT, paper, pruning waste, PMD, BEST bag, Christmas trees,
textile. Only the types that exist for your address get a sensor, and new types RD4 adds later appear
automatically. Names are available in English and Dutch (following your Home Assistant language).

**Pruning waste is by appointment** (*snoeiafval op afspraak*). It has its own sensor and calendar events, but
is left out of the "next pickup" summary so reminders don't fire for a collection you haven't booked.

The next-pickup states roll over at midnight without calling RD4 again.

## Reminder blueprint

[![Import blueprint](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fdash82%2Fha-rd4-afval%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Frd4_afval%2Fpickup_reminder.yaml)

Pick the two summary sensors, a time and how many days ahead, then add your own notify action. Inside it,
`{{ pickup_text }}` and `{{ days_until }}` are available, for example:

```yaml
action: notify.mobile_app_phone
data:
  message: "Tomorrow: {{ pickup_text }}"
```

## Example dashboard card

```yaml
type: entities
entities:
  - entity: sensor.rd4_1234_ab_12_next_pickup
  - entity: sensor.rd4_1234_ab_12_next_pickup_types
```

## Troubleshooting

* **Address not found**: check the postcode, number and extension on <https://mijn.rd4.nl/kalender>.
* **Calendar for next year is empty in December**: RD4 publishes it late. The integration picks it up
  automatically once available.
* Download diagnostics from the integration page when reporting an issue. Your address is redacted.

## Development

```bash
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements_test.txt
ruff check . && ruff format --check . && pytest
```

CI runs hassfest, HACS validation, Ruff and pytest (`.github/workflows/validate.yml`).

### Releasing

On every push to `main` the GitHub workflow runs hassfest, HACS validation, Ruff and pytest. If all pass, it
publishes a GitHub release `v<version>` when that tag doesn't exist yet. To ship a new version, bump `version`
in `custom_components/rd4_afval/manifest.json` and push to `main`.

### Getting into the default HACS store

Once the repo is public, has a release, passes the HACS and hassfest workflows and has topics set
(`home-assistant`, `hacs`, `integration`), open a PR against
[hacs/default](https://github.com/hacs/default). Brand images live in
`custom_components/rd4_afval/brand/`.

## License

MIT
