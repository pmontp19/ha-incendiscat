# ha-bomberscat

> Integració de Home Assistant per al seguiment d'**incendis forestals a Catalunya** en temps real, amb dades dels **Bombers de la Generalitat**, el **Pla Alfa** (Agents Rurals) i el **mapa de perill d'incendi** (Departament d'Agricultura).

Estat: **investigació i disseny**. Aquest repositori recull tota la recerca de fonts de dades, integracions de referència i el disseny final de la integració. Encara no hi ha codi.

## Per què aquesta integració

Catalunya disposa d'una font pública **explotable i estructurada** d'incendis en temps real (un `FeatureServer` ArcGIS del cos de Bombers), però ningú l'ha portada a Home Assistant. Mentrestant, existeixen integracions equivalents per a Califòrnia (`ha-wildfire-monitor`) i Portugal (`ha-pyrovigil`) que demostren que el patró funciona.

Aquest projecte neix per cobrir aquest buit, agafant **el millor de les dues integracions de referència** i adaptant-lo a l'ecosistema de dades català (que té particularitats interessants: fases pròpies `Actiu/Estabilitzat/Controlat/Extingit`, Pla Alfa, etc.).

## Què farà la integració (resum)

- **Mapa** amb cada incendi actiu dins del radi configurat (`geo_location` entities a la Map card nativa de HA).
- **Dispositiu agregat** amb: nombre d'incendis per fase, distància al més proper, municipi més proper, municipis afectats, recursos desplegats.
- **Alerta binària** `fire_nearby` dins d'un radi d'alerta configurable.
- **Risc d'incendi** diari (Pla Alfa / perill d'incendi d'Agricultura) amb llindar configurable.
- **Events** per a automacions (`bomberscat_fire_detected`, `bomberscat_fire_resolved`, `bomberscat_phase_change`).
- **Blueprint** de notificacions sense YAML.
- Filtrat per **tipologia** (forestal `VF` / agrícola `VA` / urbana `VU`).

## Fonts de dades (totes públiques, sense API key)

| Font | Ús | Estructurada | Disponibilitat |
| --- | --- | :---: | --- |
| Bombers de la Generalitat — `ACTUACIONS_URGENTS_online_PRO_AMB_FASE_VIEW` | Incendis en temps real (punts + fase + recursos) | ✅ ArcGIS FeatureServer | Live |
| Agents Rurals — Pla Alfa (6 FeatureServers `Pla_Alfa_*`) | Perill diari 0-4 per municipi i comarca (avui i demà) + tancaments | ✅ ArcGIS FeatureServer | Diari (00:00 + 9:30h) |
| Departament d'Agricultura — SAPIF | Risc d'incendi (raster) | ❌ GIF + PDF | — |
| Dades Obertes (`bks7-dkfd`, `crs7-idxi`, `9r29-e8ha`) | Històric validat d'incendis 2011-2026 | ✅ Socrata API | Anual/diari (post-mòrit) |
| 112 / Protecció Civil — INFOCAT | Activació del pla especial | ❌ notes de premsa | — |

**Conclusió**: Bombers + Pla Alfa cobreixen tot el que necessitem. La font SAPIF/Agricultura queda descartada perquè el Pla Alfa (que se'n alimenta) ja és estructurat i amb granularitat municipal.

Detalls tècnics complets a [`docs/01-data-sources.md`](docs/01-data-sources.md).

## Integracions de referència

S'han analitzat en profunditat dues integracions HACS existents per aprendre'n els patrons:

| Integració | Regió | Fonts | Estat |
| --- | --- | --- | --- |
| [`johnbr/ha-wildfire-monitor`](https://github.com/johnbr/ha-wildfire-monitor) | Califòrnia | CAL FIRE API REST | Activa, ahir mateix actualitzada |
| [`Duarte-Mercedes-Santos/ha-pyrovigil`](https://github.com/Duarte-Mercedes-Santos/ha-pyrovigil) | Portugal | ANEPC ArcGIS + IPMA RCM | Activa, v0.1.2 (fa una setmana) |

**Pyrovigil és el model arquitectural directe** perquè Portugal fa servir el mateix patró ArcGIS FeatureServer que Catalunya — la migració és bàsicament un canvi d'URL i de mapeig de camps.

Anàlisi comparativa completa a [`docs/02-existing-integrations.md`](docs/02-existing-integrations.md).

## Documentació

- [`docs/01-data-sources.md`](docs/01-data-sources.md) — Fonts de dades catalanes (ArcGIS, schema, Pla Alfa, estàndards)
- [`docs/02-existing-integrations.md`](docs/02-existing-integrations.md) — Anàlisi de `ha-wildfire-monitor` i `ha-pyrovigil`
- [`docs/03-feature-spec.md`](docs/03-feature-spec.md) — **Feature map definitiu** (el que construirem)
- [`docs/04-architecture.md`](docs/04-architecture.md) — Arquitectura tècnica de la integració

## Decisions clau

- **Llengua**: documentació i noms d'entities en català (és una integració per a Catalunya); codi i comentaris en anglès per convenció HA.
- **Llicència**: MIT (alineada amb les integracions de referència).
- **Distribució**: HACS custom repository.
- **Python**: seguiment de la versió suportada per la versió mínima de HA suportada.
- **No afegirem cap dependència pesada**: només `aiohttp` (ja a HA core) per cridar el FeatureServer.

## Pròxims passos

1. Validar el FeatureServer dels Bombers amb polling continuat (quina cadència admet sense throttling).
2. Confirmar si hi ha servei estructurat pel Pla Alfa o cal fer scraping d'Experience.
3. Confirmar l'origen del mapa de perill d'incendi (Agricultura).
4. Especificar el `config_flow` i el schema d'opcions.
5. Scaffold del `custom_components/bomberscat/`.

## Descàrrec

Aquest projecte **no està afiliat ni aprovat** pel cos de Bombers de la Generalitat de Catalunya, els Agents Rurals, el Departament d'Agricultura ni cap altra institució de la Generalitat. Les dades són públiques però el FeatureServer no es publica com a API oficialment suportada — pot canviar sense avís.

## Llicència

MIT.
