# Agent instructions for ha-incendiscat

Operational rules for working in this repo. For project description, entities, config flow, etc. see `README.md`. For architectural detail see `docs/`. General contribution conventions (environment setup, commit format, release cycle, test conventions, CI gates) live in `CONTRIBUTING.md`; this file only captures what is specific to ha-incendiscat.

## Commits

See `CONTRIBUTING.md` §"Missatges de commit" and §"Cicle de release" for the Conventional Commits format, the no-task-number rule, and the rule that `version` in `pyproject.toml` and `custom_components/incendiscat/manifest.json` is owned by release-please.

## Code

- Comments and identifiers in English. User-facing strings (config flow, entity names) go through `_attr_translation_key` + `translations/{ca,es,en}.json`; Catalan is the reference language. Any new entity or config-flow field needs a key in **all three** files or `hassfest` fails.
- Integration state lives in `entry.runtime_data` (typed alias `IncendiscatConfigEntry`), never in `hass.data[DOMAIN]`.
- `DeviceInfo.entry_type=SERVICE` (cloud service, not a physical device).
- ArcGIS FeatureServer data (Bombers/Pla Alfa) is not from an official API and may change without notice: read fields with `.get()` + default, never direct indexing; any change must preserve this tolerance (docs/04-architecture.md §9).
- External text fields (`municipi`, `tipus_desc`, etc.) are untrusted: never `allow_html` or interpolate HTML directly. Diagnostics must keep redacting `latitude`/`longitude` before export.
- Integration is config-flow-only; do not reintroduce YAML (`configuration.yaml`) support.

## Tests, coverage, and CI gates

See `CONTRIBUTING.md` §"Tests" for test conventions (pytest-homeassistant-custom-component + aioresponses, the `clock` fixture, real ArcGIS fixtures at `tests/fixtures/`) and §"Entorn de desenvolupament" for the 95% coverage gate and the exact `ruff`/`pytest` commands that mirror `ci.yml`/`validate.yml`.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
