# Integracions de referència — avisos meteorològics

Anàlisi de què hi ha ja per a Catalunya i Espanya, i de quins patrons val la pena copiar.
Recerca feta el 2026-08-05 (llista `hacs/default`, HA core `dev`, codi font llegit
directament).

---

## 1. Panorama

| Integració | Distribució | Estat | Cobreix avisos SMP? |
| --- | --- | --- | :---: |
| [`figorr/meteocat`](https://github.com/figorr/meteocat) | **HACS default** | Activa (v4.2.0) | **Parcialment** |
| [`meteoalarm`](https://www.home-assistant.io/integrations/meteoalarm/) | HA core | `quality_scale: legacy`, només YAML | No (EUMETNET/AEMET) |
| [`aemet`](https://www.home-assistant.io/integrations/aemet/) | HA core | Activa | No |
| [`geosphere_austria_warnings`](https://www.home-assistant.io/integrations/geosphere_austria_warnings) | HA core | Activa, `bronze` | — (Àustria) |
| [`karasu/meteocat`](https://github.com/karasu/meteocat) | GitHub | Abandonada | No |
| [`Danieldiazi/homeassistant-meteogalicia`](https://github.com/Danieldiazi/homeassistant-meteogalicia) | HACS default | Activa | — (Galícia) |

**Conclusió: no existeix cap integració d'avisos SMP orientada a automacions en temps
real.** El buit és real.

---

## 2. `figorr/meteocat` — el competidor directe

L'única integració que consumeix `api.meteo.cat`. És a la llista **HACS default**, molt
completa i mantinguda. Cal ser honestos: fa moltes coses bé i **no volem duplicar-la**.

### Què fa

Requereix API key amb **tres plans** simultanis (`Dades de la XEMA`, `Dades de la XDDE`,
`Dades de Predicció`). El config flow demana clau → municipi → estació XEMA → límits de
quota → àrea. Genera sensors d'observació (XEMA), predicció municipal, UVI, llamps (XDDE),
ETo, quotes i **alertes SMP**.

Dependències externes: `meteocatpy`, `solarmoonpy`, `gardenpy-meteocat`, `packaging`,
`wrapt`. `dependencies: ["persistent_notification", "http"]`. Cache en fitxers JSON al disc.

### Com exposa els avisos SMP

Dos tipus de sensor, ambdós lligats al `region_id` (comarca) del municipi triat:

`MeteocatAlertRegionSensor` — estat = nombre d'alertes actives; atributs `alert_1`,
`alert_2`, … amb el nom normalitzat del meteor.

`MeteocatAlertMeteorSensor` — un per meteor (`alert_wind`, `alert_rain_intensity_30_min`,
`alert_rain_intensity_3_hours`, `alert_rain`, `alert_snow`, `alert_sea`, `alert_cold`,
`alert_warm`, `alert_warm_night`):

```python
@property
def native_value(self):
    ...
    estado_original = meteor_data.get("estado", "Tancat")
    return self.STATE_MAPPING.get(estado_original, "unknown")   # "opened" / "closed"

@property
def extra_state_attributes(self):
    return { "inicio": …, "fin": …, "fecha": …, "periodo": …,
             "umbral": umbral_convertido, "nivel": …, "peligro": …, "comentari": … }
```

Té taules de mapatge molt completes (`UMBRAL_MAPPING` amb ~40 llindars literals) i,
notablement, **avisa amb un warning quan troba un meteor o un llindar desconegut** en lloc
de petar — la mateixa filosofia de tolerància que volem.

### Per què no ens serveix

| Limitació | Impacte |
| --- | --- |
| **L'estat del sensor és `opened`/`closed` de l'episodi**, no el grau de perill de la teva comarca ara | `peligro` queda com a atribut. Una automació ha de fer `state_attr(...)` i comparar números en lloc de reaccionar a un canvi d'estat |
| **Sense binary sensors i sense events** | No hi ha *edge trigger* net per a "acaba d'entrar un avís greu". El patró event-driven de HA no s'aprofita |
| **Sense distinció "ara" vs "més tard avui"** | Els atributs porten franja i dia, però l'estat no diu si l'avís està vigent en aquest moment |
| **No cobreix Preavís, Avís Vigilància ni Temps Violent** | Es perd precisament l'avís més urgent (2 h de vigència, *lightning jump*) |
| **Exigeix 3 plans d'API** | No pots tenir només els avisos; instal·lar-la per als avisos t'obliga a XEMA i XDDE |
| **Temps real impossible amb quota ciutadana** | `ALERT_VALIDITY_MULTIPLIER_100 = 12` sobre `DEFAULT_ALERT_VALIDITY_TIME = 120` min → refresc **cada 24 h** quan `limit_prediccio <= 100` (el default) |
| Cache en fitxers, `http` i `persistent_notification` com a dependències, 5 deps de PyPI | Superfície de manteniment gran per a qui només vol avisos |
| Historial de *breaking changes* d'`entity_id` (v3.0.0) i `entity_id` fixats a mà | — |

### Què n'agafem

- La llista de meteors i la taula de llindars literals (§1.3 de `01-data-sources.md`).
- El patró "meteor/llindar desconegut → warning + `unknown`, mai excepció".
- El sensor de quota a partir de `/quotes/v1/consum-actual`.
- La idea de fer l'interval **dependent de la quota** quan hi ha API key.

### Coexistència

Les dues integracions han de poder conviure a la mateixa instància: dominis diferents
(`meteocat` vs `avisoscat`), `unique_id` diferents, i cap col·lisió d'`entity_id` (els seus
són `sensor.meteocat_{station_id}_{town}_{sensor}`). El README ho ha de dir explícitament:
*si vols predicció i estació XEMA, fes servir `figorr/meteocat`; això només fa avisos, i
sense clau*.

---

## 3. `geosphere_austria_warnings` (HA core) — el model a copiar ⭐

Integració d'avisos oficials d'Àustria, acceptada a core amb `quality_scale: bronze`. És
l'exemple canònic de com HA vol que es modelin els avisos meteorològics avui.

### Model d'entitats — deliberadament petit

```python
SENSORS = (
    GeoSphereSensorDescription(
        key="warning_level",
        translation_key="warning_level",
        device_class=SensorDeviceClass.ENUM,
        options=[LEVEL_NONE, "yellow", "orange", "red"],
        value_fn=_max_level,
    ),
    GeoSphereSensorDescription(
        key="active_warnings",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=len,
    ),
)
```

Dues entitats per municipi: **el nivell més alt vigent com a `SensorDeviceClass.ENUM`** i
**el recompte**. Res més. El `device_class=ENUM` amb `options` és el que fa que el nivell
sigui usable directament en automacions i targetes.

### Coordinator — precomprovació barata

```python
UPDATE_INTERVAL = timedelta(minutes=5)

async def _async_update_data(self) -> GeoSphereData:
    last_modified = await self.client.get_last_modified()
    if self.data is None or last_modified != self._last_modified:
        location_warnings = await self.client.get_warnings_for_coords(lat, lon)
    else:
        location_warnings = self.data.location_warnings
    ...
    return GeoSphereData(
        location_warnings=location_warnings,
        active_warnings=[w for w in location_warnings.warnings if w.is_active(now)],
    )
```

Dues idees clau:

1. **Precomprovació barata abans de la descàrrega completa.** Nosaltres no tenim `ETag` ni
   `Last-Modified` (verificat), així que no la podem fer igual — però sí que podem
   comparar un hash del payload extret per evitar recalcular estat i emetre events
   espuris.
2. **`is_active(now)` calculat al coordinator, no a l'entitat.** L'estat "vigent ara" es
   deriva del rellotge, no només de les dades: cal recalcular-lo encara que el payload no
   canviï. Per a nosaltres és crític, perquè les franges de 6 h fan que un avís s'activi i
   es desactivi **sense cap canvi a la font**.

### Altres detalls

`integration_type: "service"`, `iot_class: cloud_polling`, `runtime_data` amb àlies tipat,
una entry per municipi amb prevenció de duplicats, i el `const.py` documenta la llicència
de les dades. Tot això ho volem igual.

**On ens en separem**: dues entitats no basten per al SMP. El grau de perill no és
"groc/taronja/vermell" sinó una escala 0–6 que es projecta a 4 categories, i l'usuari vol
saber **quin** meteor (tancar persianes per vent ≠ recollir tendals per pedra ≠ hidratar
la gent gran per calor). Per això afegim un sensor per meteor i events al bus.

---

## 4. `meteoalarm` (HA core) — el que no s'ha de fer

Integració genèrica europea (EUMETNET) que per a Espanya serveix avisos **d'AEMET**, no del
Meteocat, a granularitat de província.

- **Només YAML** (`PLATFORM_SCHEMA` amb `country`/`province`), sense config flow.
- `quality_scale: legacy`.
- Limitació coneguda i documentada: **quan hi ha diverses alertes actives per a una regió,
  només se n'obté la primera** ([core#65699](https://github.com/home-assistant/core/issues/65699)).
- Depèn de `meteoalertapi==0.3.1`, un paquet de tercers poc mantingut.

És l'alternativa que un usuari català fa servir avui, i és clarament pitjor que llegir el
SMP directament: dades d'una altra agència, granularitat de província i una sola alerta.

---

## 5. `aemet` (HA core)

Integració oficial d'AEMET OpenData: predicció i observació, **sense avisos**. Incloure'ls
és una *feature request* oberta i no implementada.

AEMET publica avisos CAP a `opendata.aemet.es` (`/api/avisos_cap/ultimoelaborado/area/cat`)
amb una quota molt més generosa que el Meteocat. **No l'usem**: són avisos d'AEMET amb
zones pròpies, no les SMP per comarca del Meteocat, i barrejar-los confondria l'usuari
sobre quina autoritat ha emès què. Queda anotat com a possible *fallback* futur si la font
del Meteocat es tanca.

---

## 6. Decisions derivades

| Decisió | Origen |
| --- | --- |
| `SensorDeviceClass.ENUM` amb `options` per al nivell d'avís | `geosphere_austria_warnings` |
| Vigència "ara" recalculada cada cicle amb el rellotge, no només amb el payload | `geosphere_austria_warnings` + franges de 6 h del SMP |
| Un sensor per meteor, a més dels agregats | `figorr/meteocat` (però amb el **grau** com a estat, no `opened`/`closed`) |
| Events al bus per a automacions en temps real | Buit detectat: cap integració catalana en té |
| Sensor de quota només si hi ha API key | `figorr/meteocat` |
| Meteor/llindar desconegut → warning + `unknown` | `figorr/meteocat` |
| Sense dependències de PyPI | `ha-incendiscat` (`requirements: []`) |
| Multi-entrada (N comarques) | `geosphere_austria_warnings` (N municipis) |
