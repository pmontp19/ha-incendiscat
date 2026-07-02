# ha-bomberscat

> Integració de Home Assistant per al seguiment d'**incendis forestals a Catalunya** en temps real: mapa, sensors agregats, alertes i un blueprint de notificacions, amb dades públiques dels **Bombers de la Generalitat** i el **Pla Alfa** (Agents Rurals).

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
![GitHub release (latest by date)](https://img.shields.io/github/v/release/pmontp19/ha-bomberscat)
![CI](https://github.com/pmontp19/ha-bomberscat/actions/workflows/ci.yml/badge.svg)
![License](https://img.shields.io/github/license/pmontp19/ha-bomberscat)

<!-- TODO: captura de pantalla de la Map card amb els incendis actius -->

## Instal·lació

### Via HACS (recomanat)

1. HACS → **Integrations** → menú (⋮) → **Custom repositories**.
2. Afegeix `https://github.com/pmontp19/ha-bomberscat`, categoria **Integration**.
3. Cerca **"Bombers de Catalunya"** dins HACS i instal·la-la.
4. Reinicia Home Assistant.
5. **Configuració → Dispositius i serveis → Afegeix integració** → cerca **"Bombers de Catalunya"**.

### Manual

1. Copia `custom_components/bomberscat/` d'aquest repositori dins la carpeta `custom_components/` de la teva instal·lació de Home Assistant.
2. Reinicia Home Assistant.
3. Afegeix la integració des de **Configuració → Dispositius i serveis**.

## Configuració

El flux de configuració té dues passes:

1. **Ubicació i radis** — mapa amb marcador arrossegable, preomplert amb `zone.home`. Dos radis:
   - **Radi de seguiment** (el cercle del mapa, 5–200 km, per defecte 100 km): quins incendis es fan seguir — generen `geo_location` i compten als sensors agregats.
   - **Radi d'alerta** (per defecte 30 km, no pot ser més gran que el de seguiment): quins incendis activen `binary_sensor.bomberscat_fire_nearby` i els events de proximitat.

   Distingir-los permet veure tots els incendis de Catalunya al mapa però rebre alertes només dels que són realment a prop.

2. **Filtres i sondeig** — subtipus a incloure (`VF`/`VA`/`VU`, per defecte només forestal), fases considerades "actives" (per defecte `Actiu`+`Estabilitzat`), interval de sondeig en minuts (1–60, per defecte 5) i nombre mínim de vehicles per considerar un incident.

Un cop configurada, **Configuració → Dispositius i serveis → Bombers de Catalunya → Configurar** obre les opcions: els mateixos filtres més el **llindar de risc alt** (0–4 del Pla Alfa, per defecte 3 = Alt).

Per moure la ubicació vigilada (no els filtres) fes servir **Reconfigurar** a la mateixa integració, que reobre la passa 1.

## Entitats

Totes les entitats agregades pengen d'un únic dispositiu **"Bombers de Catalunya"**. A més, hi ha una entitat `geo_location` per cada incendi actiu dins del radi de seguiment.

| Entitat | Descripció |
| --- | --- |
| `sensor.bomberscat_active_fires` | Nombre d'incendis actius (fases configurades) dins el radi de seguiment. Atributs: `last_updated`, `total_in_track_radius`, `total_in_alert_radius`. |
| `sensor.bomberscat_nearest_fire_distance` | Distància en km a l'incendi actiu més proper. `-1` si no n'hi ha cap. |
| `sensor.bomberscat_nearest_fire_municipi` | Municipi de l'incendi actiu més proper. `"—"` si no n'hi ha cap. |
| `sensor.bomberscat_fires_per_fase` | Total d'incendis en seguiment; atributs `actiu`, `estabilitzat`, `controlat`, `extingit`. |
| `sensor.bomberscat_fires_per_tipus` | Total d'incendis en seguiment; atributs `vf`, `va`, `vu`. |
| `sensor.bomberscat_total_vehicles` | Suma de vehicles desplegats als incendis en seguiment. |
| `sensor.bomberscat_fire_risk` | Nivell de risc Pla Alfa (0–4) del municipi de la ubicació configurada. Atributs: `nivell_text`, `comarca`, `municipi`, `data_vigencia`, `hora_vigencia`, `perill_dema`. |
| `binary_sensor.bomberscat_fire_nearby` | `on` si hi ha un incendi actiu dins el radi d'alerta. Atributs (quan `on`): `nearest_act_num`, `nearest_distance_km`, `nearest_municipi`, `nearest_fase`. |
| `binary_sensor.bomberscat_high_risk` | `on` si `fire_risk` ≥ llindar configurat. |
| `geo_location.bomberscat_<act_num>` | Un per incendi en seguiment; estat = distància en km. Atributs: `source` (`"bomberscat"`), `latitude`, `longitude`, `act_num`, `fase`, `tipus`, `tipus_desc`, `municipi`, `data_inici`, `data_fi`, `vehicles`, `situacio`, `updated_at`, `url`. |

Entitats de diagnòstic (necessàries perquè la font no és una API oficial i pot fallar):

| Entitat | Descripció |
| --- | --- |
| `binary_sensor.bomberscat_service_connected` | `on` si l'última consulta al FeatureServer dels Bombers ha anat bé. |
| `sensor.bomberscat_last_update` | Marca de temps de l'última sincronització correcta. |
| `sensor.bomberscat_last_update_status` | `success` o `error_<codi>` (p.ex. `error_timeout`, `error_http_404`). |

## Events

Es disparen a `hass.bus` per fer-los servir en automacions (`trigger: event`):

| Event | Quan es dispara |
| --- | --- |
| `bomberscat_fire_detected` | Un incendi nou compleix els filtres i entra al radi de seguiment. |
| `bomberscat_fire_resolved` | Un incendi en seguiment passa a `Extingit` (o el flux de fases el resol). |
| `bomberscat_phase_change` | Un incendi en seguiment canvia de fase (p.ex. `Actiu → Estabilitzat`). |
| `bomberscat_service_degraded` | El FeatureServer falla de forma persistent (3 errors seguits del mateix tipus, p.ex. 404) — es crea també una incidència de reparació (repair issue). |

Payload de `bomberscat_fire_detected`:

```json
{
  "act_num": "262311630",
  "distance_km": 12.4,
  "municipi": "Sant Quirze Safaja",
  "fase": "Actiu",
  "tipus": "VF",
  "tipus_desc": "Incendi vegetació forestal",
  "vehicles": 4,
  "in_alert_radius": true,
  "latitude": 41.72388,
  "longitude": 2.16657,
  "url": "https://experience.arcgis.com/experience/f6172fd2d6974bc0a8c51e3a6bc2a735"
}
```

Payload de `bomberscat_phase_change`:

```json
{
  "act_num": "262311630",
  "municipi": "Sant Quirze Safaja",
  "old_fase": "Actiu",
  "new_fase": "Estabilitzat",
  "distance_km": 12.4
}
```

Payload de `bomberscat_fire_resolved`:

```json
{
  "act_num": "262311630",
  "municipi": "Sant Quirze Safaja",
  "duration_min": 187,
  "final_fase": "Extingit"
}
```

## Blueprint

La integració inclou un blueprint d'automació a [`blueprints/automation/bomberscat_fire_notification.yaml`](blueprints/automation/bomberscat_fire_notification.yaml) que notifica quan hi ha un incendi nou (o, opcionalment, canvis de fase o resolucions), amb botó per obrir el mapa.

[![Open your Home Assistant instance and show the blueprint import dialog.](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fraw.githubusercontent.com%2Fpmontp19%2Fha-bomberscat%2Fmain%2Fblueprints%2Fautomation%2Fbomberscat_fire_notification.yaml)

Manualment: **Configuració → Automacions i escenes → Blueprints → Importa un blueprint** i enganxa l'URL anterior, o copia el fitxer a `blueprints/automation/bomberscat/` de la teva instal·lació.

Opcions del blueprint:

| Camp | Tipus | Descripció |
| --- | --- | --- |
| `notification_service` | selector | Servei de notificació a fer servir (`notify.notify` per defecte). |
| `minimum_fase` | selector | Fase mínima per notificar (`Actiu`/`Estabilitzat`/`Controlat`/`Extingit`). Per defecte `Actiu`. |
| `minimum_vehicles` | int | Filtre de magnitud. Per defecte 0. |
| `maximum_distance` | int | Km màxims (0 = usa el radi d'alerta configurat). |
| `critical_alert` | bool | Notificació crítica que travessa el mode No molestar. Per defecte fals. |
| `include_resolved` | bool | Notifica també quan un incendi es resol. Per defecte fals. |
| `include_phase_changes` | bool | Notifica els canvis de fase. Per defecte fals. |
| `open_map_url` | select | Mapa a obrir des del botó: visor oficial dels Bombers, Google Maps o OpenStreetMap. |

## Dashboard d'exemple

```yaml
type: vertical-stack
cards:
  - type: map
    auto_fit: true
    entities:
      - zone.home
    geo_location_sources:
      - bomberscat
  - type: glance
    entities:
      - sensor.bomberscat_active_fires
      - sensor.bomberscat_nearest_fire_distance
      - sensor.bomberscat_nearest_fire_municipi
      - sensor.bomberscat_total_vehicles
      - binary_sensor.bomberscat_fire_nearby
  - type: markdown
    title: Incendis actius
    content: |
      {% set fires = states.geo_location | selectattr('attributes.source','eq','bomberscat') | list %}
      {% if fires | count == 0 %}_No hi ha incendis actius a la zona._{% else %}
      | # | Municipi | Fase | km | Veh | Tipus |
      |--:|:--|:--|--:|--:|:--|
      {% for f in fires | sort(attribute='state') %}
      | {{ loop.index }} | {{ f.attributes.municipi }} | {{ f.attributes.fase }} | {{ f.state | round(1) }} | {{ f.attributes.vehicles }} | {{ f.attributes.tipus }} |
      {% endfor %}
      {% endif %}
```

## Patrons d'automació

1. **Notificació push quan apareix un foc nou dins X km** — fes servir el blueprint (secció anterior).
2. **Encendre aspersors o tancar persianes** quan `binary_sensor.bomberscat_fire_nearby` passa a `on`.
3. **Avís al matí si avui hi ha risc alt** — `binary_sensor.bomberscat_high_risk` passa a `on`.
4. **Registre per a postmortem** — `bomberscat_phase_change` cap a una notificació silenciosa o un `logbook.log`.
5. **Tancament automàtic de finestres** si `fire_nearby` és `on` i la qualitat de l'aire (sensor PM2.5) és dolenta.

Exemple: avís matinal de risc alt (patró 3):

```yaml
alias: Avisa si avui hi ha risc alt d'incendi
trigger:
  - platform: state
    entity_id: binary_sensor.bomberscat_high_risk
    to: "on"
condition:
  - condition: time
    after: "07:00:00"
    before: "10:00:00"
action:
  - service: notify.notify
    data:
      title: "🔥 Risc alt d'incendi avui"
      message: >
        Nivell {{ state_attr('sensor.bomberscat_fire_risk', 'nivell_text') }}
        a {{ state_attr('sensor.bomberscat_fire_risk', 'municipi') }}. Evita fer foc.
```

Exemple: tancar persianes quan hi ha un incendi a prop (patró 2):

```yaml
alias: Tanca persianes si hi ha un incendi a prop
trigger:
  - platform: state
    entity_id: binary_sensor.bomberscat_fire_nearby
    to: "on"
action:
  - service: cover.close_cover
    target:
      entity_id: cover.persianes_exterior
```

## Fonts de dades

| Font | Ús | Cadència |
| --- | --- | --- |
| Bombers de la Generalitat — FeatureServer `ACTUACIONS_URGENTS` | Incendis en temps real (punts, fase, recursos) | Sondeig configurable, 1–60 min (per defecte 5 min) |
| Agents Rurals — Pla Alfa (FeatureServers `Pla_Alfa_*`) | Risc d'incendi diari (0–4) per municipi/comarca | Sondeig fix cada 6 h (l'oficial s'actualitza a les 00:00 i 9:30h) |

Detalls tècnics complets (schemas, glossaris, endpoints) a [`docs/01-data-sources.md`](docs/01-data-sources.md).

**Cap d'aquestes fonts és una API oficialment suportada** — són FeatureServers públics d'ArcGIS que poden canviar d'adreça o d'esquema sense avís. Quan això passa:

- `binary_sensor.bomberscat_service_connected` passa a `off`.
- Després de 3 errors seguits del mateix tipus, es dispara l'event `bomberscat_service_degraded` i s'obre una incidència de reparació (repair issue) a Home Assistant amb enllaç a [GitHub Issues](https://github.com/pmontp19/ha-bomberscat/issues).
- Les dades ja carregades es mantenen (no s'esborren) fins que el servei torna.

## Seguretat i dades

- Les coordenades de la ubicació configurada (`zone.home` o la que triïs) només s'envien als endpoints de *point-in-polygon* del Pla Alfa (Agents Rurals) — és el disseny esperat, cal per determinar el municipi/comarca i el nivell de risc.
- Les entitats de diagnòstic redacten `latitude`/`longitude` (i altres camps identificatius de la configuració) abans d'exportar-se.
- Camps com `municipi` o `tipus_desc` provenen d'un servei extern no oficial i s'han de tractar com a text no fiable: no els renderitzis amb `allow_html: true` en targetes personalitzades (p.ex. Markdown card).

## Desenvolupament

```bash
uv venv --python 3.13 .venv
uv pip install --python .venv/bin/python -r requirements_dev.txt

.venv/bin/pytest
.venv/bin/ruff check .
.venv/bin/ruff format --check .
```

Documentació d'arquitectura i disseny a [`docs/`](docs/): [fonts de dades](docs/01-data-sources.md), [integracions de referència](docs/02-existing-integrations.md), [especificació funcional](docs/03-feature-spec.md), [arquitectura](docs/04-architecture.md), [pla d'implementació](docs/05-implementation-plan.md).

## Integracions de referència

S'han analitzat en profunditat dues integracions HACS existents per aprendre'n els patrons: [`johnbr/ha-wildfire-monitor`](https://github.com/johnbr/ha-wildfire-monitor) (Califòrnia, CAL FIRE API REST) i [`Duarte-Mercedes-Santos/ha-pyrovigil`](https://github.com/Duarte-Mercedes-Santos/ha-pyrovigil) (Portugal, ANEPC ArcGIS + IPMA), aquesta última especialment rellevant perquè fa servir el mateix patró ArcGIS FeatureServer que Catalunya. Anàlisi completa a [`docs/02-existing-integrations.md`](docs/02-existing-integrations.md).

## Descàrrec

Aquest projecte **no està afiliat ni aprovat** pel cos de Bombers de la Generalitat de Catalunya, els Agents Rurals, el Departament d'Agricultura ni cap altra institució de la Generalitat. Les dades són públiques però el FeatureServer no es publica com a API oficialment suportada — pot canviar sense avís.

## Llicència

MIT.
