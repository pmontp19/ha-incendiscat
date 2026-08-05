# Feature spec — `ha-avisoscat`

Especificació funcional de la integració d'avisos de temps sever del Meteocat.
Deriva de [`01-data-sources.md`](01-data-sources.md) i [`02-existing-integrations.md`](02-existing-integrations.md).

---

## 1. Visió general

**Nom d'usuari:** "Avisos Meteocat" · **Domini HA:** `avisoscat` · **Repositori:** `ha-avisoscat`

Segueix els **avisos de Situació Meteorològica de Perill (SMP)** que afecten la comarca de
l'usuari i els converteix en entitats i events perquè s'hi puguin fer automacions en temps
real: tancar persianes abans d'una ventada, recollir tendals davant d'un avís de pedra,
avisar la gent gran en una onada de calor, o reaccionar quan Protecció Civil activa
l'INUNCAT.

### Principis

1. **Sense fricció per defecte.** Funciona sense API key, sondejant la font pública cada
   10 minuts. L'API key és opcional i només canvia la font.
2. **L'estat útil és el grau de perill vigent ARA**, no si hi ha un episodi obert. Les
   franges de 6 h fan que un avís s'activi i es desactivi sense cap canvi a la font: la
   vigència es recalcula cada cicle contra el rellotge.
3. **Events per a automacions.** El valor diferencial respecte de `figorr/meteocat`.
4. **Honestedat territorial.** L'avís és per comarca. La UI i el README ho han de dir.
5. **Cap dependència de PyPI** (`requirements: []`), igual que `ha-incendiscat`.

### Fora d'abast (v1)

- Entitat `weather` amb predicció municipal → ja la cobreix bé `figorr/meteocat`.
- Dades d'estació (XEMA), llamps (XDDE), UVI.
- Avisos d'AEMET (autoritat diferent, zones diferents).

---

## 2. Config flow

Multi-entrada: es poden crear **N entrades per a N comarques** (casa, feina, casa dels
pares). A diferència d'`ha-incendiscat`, **no** es declara `single_config_entry`.
`unique_id` de l'entrada = `str(id_comarca)` (i `mar-{id}` si és una zona marítima), amb
`_abort_if_unique_id_configured()`.

### Passa 1 — Ubicació

- `LocationSelector` **sense radi**, preomplert amb `zone.home`.
- En enviar: resolució *point-in-polygon* sobre `comarquesAmbMar.json` → comarca.
- Si el punt cau fora de Catalunya: error `location_outside_catalonia` amb el desplegable
  de comarques com a alternativa.
- Alternativa sempre disponible: `SelectSelector` amb les 43 comarques, per si algú vol
  seguir una comarca on no viu.
- El títol de l'entrada serà el nom de la comarca ("Avisos Meteocat — Osona").

### Passa 2 — Opcions

| Camp | Tipus | Default | Notes |
| --- | --- | --- | --- |
| `api_key` | text (opcional) | buit | Si s'omple, es valida amb `/quotes/v1/consum-actual` i es passa a la font oficial |
| `meteors` | multi-select | tots | Quins meteors seguir (crea/omet els sensors per meteor) |
| `severe_threshold` | 1–6 | `3` | Grau a partir del qual `binary_sensor.severe_warning` s'encén (3 = "Alt") |
| `include_sea` | bool | `false` | Afegeix la zona marítima adjacent (només si la comarca en té) |
| `include_civil_protection` | bool | `true` | Sensors del CECAT |
| `scan_interval` | 10–120 min | `10` | Mínim 10 min: la font té `cache-control: max-age=600` |

Quan hi ha API key, el `scan_interval` efectiu es limita per la quota (vegeu §6).

### Options flow

Tot el de la passa 2 excepte `api_key`, que es gestiona per **reauth** quan el servidor
retorna `403`.

### Reconfiguració

`async_step_reconfigure` reobre la passa 1 per moure la ubicació / canviar de comarca.

---

## 3. Entitats

Un dispositiu per entrada, `DeviceInfo.entry_type = SERVICE`:
`name = "Avisos Meteocat — {comarca}"`, `manufacturer = "Servei Meteorològic de Catalunya"`,
`model = "Situació Meteorològica de Perill"`.

Tots els noms visibles surten de `_attr_translation_key` + `translations/{ca,es,en}.json`
(el català és la llengua de referència). Els `entity_id` que apareixen aquí corresponen a
una instància en català.

### 3.1 `sensor.avisos_meteocat_<comarca>_nivell_d_avis` ⭐

Grau més alt **vigent ara** a la comarca, projectat al codi semafòric.

- `device_class: ENUM`, `options: ["cap", "moderat", "alt", "molt_alt"]`
- `translation_key: warning_level`

| Atribut | Descripció |
| --- | --- |
| `perill` | Grau numèric 0–6 |
| `meteor` | Meteor que provoca el màxim (`vent`, `pluja_30min`, …) |
| `tipus` | `avis` / `vigilancia` / `temps_violent` |
| `llindar` | Text literal del llindar (p. ex. `Intensitat > 20 mm / 30 minuts`) |
| `nivell` | `1` (llindar baix) o `2` (llindar alt) |
| `periode` | Franja vigent (`12-18`) |
| `distribucio_geografica` | `LOCAL` / `EXTENSA` / `GENERAL` |
| `comentari` | Text del predictor. **Text extern no fiable** |
| `data_inici`, `data_fi` | ISO 8601 UTC de l'avís |
| `data_emissio` | Quan l'SMC el va emetre |

### 3.2 `sensor.avisos_meteocat_<comarca>_avisos_actius`

Nombre d'avisos vigents ara. `state_class: MEASUREMENT`, `unit: "avisos"`.
Atribut `avisos`: llista de `{meteor, perill, tipus, periode, llindar}`.

### 3.3 `sensor.avisos_meteocat_<comarca>_grau_maxim_avui`

Grau màxim 0–6 previst per a **qualsevol franja d'avui**, encara que ara no hi hagi res
vigent. És el sensor per a l'automació matinal ("avui hi ha avís de calor a la tarda").
Atributs: `meteor`, `periode`, `nivell`, `llindar`.

### 3.4 `sensor.avisos_meteocat_<comarca>_avis_<meteor>` (×10) ⭐

Un per meteor, creats només per als meteors seleccionats. Mateixa forma que §3.1
(`ENUM` amb `cap`/`moderat`/`alt`/`molt_alt`) però restringit a aquell meteor.

| `translation_key` | Meteor SMP |
| --- | --- |
| `warning_wind` | Vent |
| `warning_rain_30min` | Intensitat de pluja en 30 minuts |
| `warning_rain_3h` | Intensitat de pluja en 3 hores |
| `warning_rain_accumulated` | Acumulació de pluja |
| `warning_snow` | Neu |
| `warning_sea` | Estat de la mar |
| `warning_cold` | Fred |
| `warning_heat` | Calor |
| `warning_night_heat` | Calor nocturna |
| `warning_violent_weather` | Temps violent |

Atributs: `perill`, `nivell`, `llindar`, `periode`, `distribucio_geografica`, `comentari`,
`data_inici`, `data_fi`, `graus_per_periode` (dict `{"00-06": 0, "06-12": 0, "12-18": 2,
"18-00": 1}` del dia en curs, per pintar una barra a un dashboard).

Estat `cap` quan no hi ha avís d'aquell meteor. Si el meteor arriba amb un nom que no
reconeixem, warning al log i s'ignora — mai una excepció (trap #5 de `01-data-sources.md`).

### 3.5 `sensor.avisos_meteocat_<comarca>_preavis`

Grau màxim del preavís vigent **a escala de Catalunya** (els preavisos no tenen comarca).
`ENUM` igual que la resta. Atributs: `meteor`, `perill`, `llindar`, `data_inici`,
`data_fi`, `comentari`.

### 3.6 `sensor.avisos_meteocat_<comarca>_avis_maritim`

Només si `include_sea`. Grau vigent a la zona marítima adjacent (`idComarca` 88–99).
Atributs: `zona` (`Mar Maresme`), `perill`, `llindar`, `periode`.

### 3.7 `sensor.avisos_meteocat_<comarca>_plans_activats`

Només si `include_civil_protection`. Nombre de plans del CECAT activats.
Atributs: un per pla activat (`inuncat`, `ventcat`, `neucat`, `procicat`, …) amb
`{fase, data_hora, comunicat_url, descripcio}`, més `fase_maxima`
(`prealerta` < `alerta` < `emergencia`).

### 3.8 `binary_sensor.avisos_meteocat_<comarca>_avis_actiu`

`device_class: SAFETY`. `on` si hi ha algun avís vigent ara (grau ≥ 1).
Atributs quan és `on`: `meteor_principal`, `perill_maxim`, `nombre_avisos`.

### 3.9 `binary_sensor.avisos_meteocat_<comarca>_avis_greu`

`device_class: SAFETY`. `on` si `perill ≥ severe_threshold` (default 3 = "Alt").
Aquest és el disparador recomanat per a automacions de protecció.

### 3.10 `binary_sensor.avisos_meteocat_<comarca>_temps_violent`

`device_class: SAFETY`. `on` mentre hi hagi un **Avís de Vigilància per Temps Violent**
dins de la seva finestra de 2 h. Atributs: `probabilitat` (`alta`/`mitjana`), `llindar`,
`data_emissio`, `valid_fins`.

### 3.11 `binary_sensor.avisos_meteocat_<comarca>_proteccio_civil_alerta`

`device_class: SAFETY`. `on` si algun pla del CECAT està en `ALERTA` o `EMERGÈNCIA`
(no per `PREALERTA`). Atributs: `plans`, `fase_maxima`.

### 3.12 Entitats de diagnòstic

Necessàries perquè la font principal no és una API oficialment suportada.

| Entitat | Descripció |
| --- | --- |
| `binary_sensor.…_servei_connectat` | `on` si l'última consulta ha anat bé |
| `sensor.…_darrera_actualitzacio` | `device_class: TIMESTAMP` de l'última sincronització correcta |
| `sensor.…_estat_de_la_darrera_actualitzacio` | `success` o `error_<codi>` (`error_timeout`, `error_http_403`, `error_parse`) |
| `sensor.…_quota_restant` | Només amb API key: `consultesRestants` del pla de Predicció. Atributs `max_consultes`, `consultes_realitzades`, `periode` |

Diagnostics (`diagnostics.py`) ha de **redactar** `latitude`, `longitude` i `api_key`.

---

## 4. Events

El motiu de ser de la integració. Es disparen a `hass.bus` i s'usen amb `trigger: event`.

### 4.1 `avisoscat_warning_issued`

Un avís nou passa a estar vigent per a la comarca (o el meteor entra per primera vegada).

```json
{
  "comarca": "Osona",
  "id_comarca": 24,
  "meteor": "pluja_30min",
  "meteor_nom": "Intensitat de pluja en 30 minuts",
  "tipus": "avis",
  "perill": 3,
  "nivell_text": "alt",
  "nivell": 1,
  "llindar": "Intensitat > 20 mm / 30 minuts",
  "periode": "12-18",
  "distribucio_geografica": "LOCAL",
  "comentari": "Els xàfecs aniran acompanyats de tempesta.",
  "data_inici": "2026-08-04T12:00:00+00:00",
  "data_fi": "2026-08-06T17:59:00+00:00",
  "data_emissio": "2026-08-04T15:30:00+00:00"
}
```

### 4.2 `avisoscat_warning_upgraded` / `avisoscat_warning_downgraded`

El grau d'un avís ja vigent puja o baixa (inclou el canvi de franja que en modifica el
grau).

```json
{
  "comarca": "Osona",
  "id_comarca": 24,
  "meteor": "vent",
  "perill_anterior": 2,
  "perill": 4,
  "nivell_text_anterior": "moderat",
  "nivell_text": "alt",
  "periode": "18-00",
  "llindar": "Ratxa màxima > 108 km/h (30 m/s)"
}
```

### 4.3 `avisoscat_warning_cleared`

Un avís vigent deixa de ser-ho (final de franja, final de l'avís, o l'SMC el tanca).

```json
{
  "comarca": "Osona",
  "id_comarca": 24,
  "meteor": "vent",
  "perill_final": 4,
  "durada_min": 372,
  "motiu": "expirat"
}
```

`motiu`: `expirat` (`dataFi` superada o franja acabada) o `retirat` (ha desaparegut de la
font abans d'hora).

### 4.4 `avisoscat_violent_weather` ⭐

Avís de Vigilància per Temps Violent que afecta la comarca. És el més urgent: 2 h de
vigència, emès a partir del *lightning jump* de la XDDE.

```json
{
  "comarca": "Osona",
  "id_comarca": 24,
  "probabilitat": "alta",
  "llindar": "Pedra de diàmetre > 2 cm",
  "comentari": "",
  "data_emissio": "2026-08-05T16:12:00+00:00",
  "valid_fins": "2026-08-05T18:12:00+00:00"
}
```

### 4.5 `avisoscat_civil_protection_phase_change`

Un pla del CECAT canvia de fase (inclou activació i desactivació).

```json
{
  "pla": "INUNCAT",
  "fase_anterior": "PREALERTA",
  "fase": "ALERTA",
  "activat": true,
  "data_hora": "2026-08-05T13:18:00+02:00",
  "descripcio": "Avís intensitat pluja fins al 04/08",
  "comunicat_url": "https://documents.dadesobertes.gencat.cat/cecat/docs/I-125912_...pdf"
}
```

### 4.6 `avisoscat_service_degraded`

La font falla de forma persistent (3 cicles seguits amb el mateix tipus d'error, p. ex.
el payload ja no es pot extreure de la pàgina, o `403` repetit). Es crea també una
*repair issue* amb enllaç al repositori.

```json
{ "source": "meteocat_public", "error": "parse", "consecutive_failures": 3 }
```

---

## 5. Blueprint

`blueprints/automation/avisoscat_warning_notification.yaml`:

| Camp | Tipus | Descripció |
| --- | --- | --- |
| `notification_service` | selector | Servei de notificació (`notify.notify` per defecte) |
| `meteors` | multi-select | Quins meteors notificar (tots per defecte) |
| `minimum_perill` | 1–6 | Grau mínim per notificar (3 per defecte) |
| `include_upgrades` | bool | Notificar també quan un avís puja de grau |
| `include_cleared` | bool | Notificar quan es resol |
| `include_violent_weather` | bool | Notificar `avisoscat_violent_weather` (per defecte sí) |
| `critical_alert` | bool | Notificació crítica que travessa el mode No molestar |

---

## 6. Estratègia de sondeig

| Font configurada | Interval | Justificació |
| --- | --- | --- |
| Pública (sense clau) | `scan_interval`, mín. **10 min** | `cache-control: max-age=600`; sondejar més sovint no aporta dades noves |
| API key, quota > 500/mes | 30 min | ~48 peticions/dia |
| API key, quota 200–500 | 2 h | ~12 peticions/dia |
| API key, quota ≤ 200 | 8 h | ~3 peticions/dia — el límit real del pla ciutadà |

Amb API key es llegeix `/quotes/v1/consum-actual` **un cop al dia** i l'interval s'ajusta
sol. Si `consultesRestants` baixa per sota del 10%, l'interval es duplica i s'emet un
warning al log.

⚠️ **La vigència es recalcula cada minut, no cada poll.** Les franges de 6 h canvien sense
que canviï la font: cal un `async_track_time_change` (o recàlcul al `_handle_coordinator_update`
amb un temporitzador) perquè `warning_level` i els events reflecteixin el canvi de franja
al moment.

---

## 7. Dashboard d'exemple

```yaml
type: vertical-stack
cards:
  - type: glance
    entities:
      - sensor.avisos_meteocat_osona_nivell_d_avis
      - sensor.avisos_meteocat_osona_avisos_actius
      - sensor.avisos_meteocat_osona_grau_maxim_avui
      - binary_sensor.avisos_meteocat_osona_avis_greu
  - type: markdown
    title: Avisos vigents
    content: |
      {% set a = state_attr('sensor.avisos_meteocat_osona_avisos_actius','avisos') or [] %}
      {% if a | count == 0 %}_Cap avís vigent._{% else %}
      | Meteor | Grau | Franja | Llindar |
      |:--|--:|:--|:--|
      {% for w in a %}
      | {{ w.meteor }} | {{ w.perill }} | {{ w.periode }} | {{ w.llindar }} |
      {% endfor %}
      {% endif %}
```

> El `comentari` i el `llindar` són text extern: mai `allow_html: true` en una Markdown card.

---

## 8. Patrons d'automació

1. **Tancar persianes i recollir tendals** quan `avisoscat_warning_issued` porta
   `meteor: vent` i `perill >= 4`.
2. **Alerta immediata de pedra/tornado** amb `avisoscat_violent_weather` i notificació
   crítica.
3. **Avís matinal** llegint `sensor.…_grau_maxim_avui` entre les 07:00 i les 09:00.
4. **Onada de calor**: `sensor.…_avis_calor` a `alt` → encendre el climatitzador i avisar
   la gent gran de casa.
5. **Escalada real**: `binary_sensor.…_proteccio_civil_alerta` a `on` amb `INUNCAT` →
   apagar el reg, tancar la clau de pas del garatge.
6. **Combinació amb `ha-incendiscat`**: avís de vent alt **i** risc del Pla Alfa ≥ 3 →
   notificació de risc extrem d'incendi.
