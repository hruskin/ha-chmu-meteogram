<img src="custom_components/chmu_meteogram/brand/logo.png" align="right" height="64" alt="logo">

# Počasí ČHMÚ — Meteogram pro Home Assistant

Neoficiální custom integrace pro Home Assistant, která stahuje **strukturovaná data meteogramu modelu ALADIN**
z veřejného JSON API Českého hydrometeorologického ústavu (ČHMÚ).
Lokalita se vybírá automaticky jako nejbližší ALADIN POI k zóně `home`.

> **Status**: 0.3.x — point-based meteogram pro libovolné souřadnice (HA `home` = default),
> sensory, výstrahy a `WeatherEntity` s hodinovým forecastem.

## Vývojový workflow

Release jsou automatické — když bumpneš `version` v `manifest.json` a pushneš
na `main`, GitHub Action vytvoří tag `vX.Y.Z` a publishne Release s auto-notes
z commitů. HACS pak verzi vidí okamžitě (po Redownload / Reload data).
Konfigurace v `.github/workflows/release.yml`.

## Co dostaneš

Pro vybranou lokalitu — buď **přesné souřadnice tvého HA `home`** (default, ALADIN grid 2,3 km
funguje pro libovolný bod ČR — ani malá vesnice jako Křížkový Újezdec není problém),
nebo **pojmenované POI** ze seznamu ČHMÚ (571 obcí, 144 lyžařských středisek, 23 vodních ploch,
92 letišť) — integrace vytvoří:

**Sensory** (aktuální hodnota = nejbližší hodina forecastu):
- `sensor.chmu_<misto>_teplota` — `t2m` (°C)
- `sensor.chmu_<misto>_vlhkost` — `rh2m` (%)
- `sensor.chmu_<misto>_srazky` — `prec` (mm/h)
- `sensor.chmu_<misto>_tlak` — `mslp` (hPa, MSLP)
- `sensor.chmu_<misto>_rychlost_vetru` — `windSpeed` (m/s)
- `sensor.chmu_<misto>_narazy_vetru` — `windGustSpeed` (m/s)
- `sensor.chmu_<misto>_smer_vetru` — `windDirection` (°)
- `sensor.chmu_<misto>_oblacnost` — `cloudsTot` (%)
- `sensor.chmu_<misto>_snih` — `snow` (mm/h)

**Binary sensor:**
- `binary_sensor.chmu_<misto>_vystrahy_chmu` — aktivní výstrahy **s plnými texty**
  (`description`, `instruction`, závažnost, platnost od/do) pro ORP, ve kterém
  lokalita leží. Atributy jsou kompatibilní s
  [MeteoalarmCard](https://github.com/MrBartusek/MeteoalarmCard).

**Weather entita:**
- `weather.chmu_<misto>_predpoved` — aktuální podmínky + **hodinový forecast 73 h**
  (`async_forecast_hourly`) — funguje s nativní HA `weather-forecast` kartou nebo
  s [Hourly Weather Card](https://github.com/decompil3d/lovelace-hourly-weather)

Každý sensor má v atributech `validity_time`, `forecast_points` (73 = 3 dny po hodině) a `elevation_m`.

## Instalace

### Ručně (vývojový režim)

```bash
cp -r custom_components/chmu_meteogram /path/to/ha/config/custom_components/
# restart Home Assistant
```

Pak Nastavení → Zařízení a služby → **Přidat integraci** → „Počasí ČHMÚ".

### Přes HACS

Repo je private, HACS [private repa nepodporuje](https://www.hacs.xyz/docs/faq/private_repositories/).
Pokud bude public: HACS → ⋮ → Custom repositories → URL → Type **Integration**.

## Použití v dashboardu

```yaml
type: entities
entities:
  - sensor.chmu_brno_teplota
  - sensor.chmu_brno_srazky
  - sensor.chmu_brno_rychlost_vetru
  - binary_sensor.chmu_brno_vystrahy_chmu
```

Pro pěkný graf (hodinový průběh) doporučujeme [ApexCharts Card](https://github.com/RomRider/apexcharts-card):

```yaml
type: custom:apexcharts-card
header:
  title: Meteogram ČHMÚ
graph_span: 72h
series:
  - entity: sensor.chmu_brno_teplota
    name: Teplota
  - entity: sensor.chmu_brno_srazky
    name: Srážky
    type: column
    yaxis_id: prec
```

> Pozn.: Apex zobrazí jen historické hodnoty sensorů. Pro celou předpověď
> použij `weather.chmu_<misto>_predpoved` s nativní `weather-forecast` kartou.

Výstrahy s texty:

```yaml
type: markdown
content: >
  {% set a = state_attr('binary_sensor.chmu_brno_vystrahy_chmu', 'alerts') %}
  {% if a %}{% for x in a %}
  **{{ x.label }}** ({{ x.severity }})
  {{ x.description }}
  {% endfor %}{% else %}Žádné výstrahy{% endif %}
```

### Atributy `binary_sensor.*_vystrahy_chmu`

| Atribut | Popis |
|---|---|
| `alert_count` | počet aktivních výstrah |
| `severity` | nejvyšší závažnost (`Minor`/`Moderate`/`Severe`/`Extreme`) |
| `color` | barva dle závažnosti (`yellow`/`orange`/`red`/`purple`) |
| `headline` | „Zátěž teplem · Bouřky" — hotové do `secondary` v kartě |
| `labels` | seznam názvů, např. `["Zátěž teplem", "Bouřky"]` |
| `label`, `alert_icon`, `description`, `instruction` | nejzávažnější výstraha rozbalená |
| `alerts` | seznam všech (`label`, `icon`, `category`, `severity`, `description`, `instruction`, `start`, `end`, …) |
| `orp`, `region`, `area` | kam lokalita spadá (např. Říčany / CZ020 / Středočeský kraj) |
| `awareness_level` | pro [MeteoalarmCard](https://github.com/MrBartusek/MeteoalarmCard) |

Ikona entity se mění podle nejzávažnější výstrahy (`mdi:weather-lightning`, `mdi:fire`…),
mimo výstrahy je `mdi:shield-check`. Kategorie → název/ikona je v `const.py`
(`ALERT_CATEGORY_LABELS`, `ALERT_CATEGORY_ICONS`), takže karta nemusí nic mapovat.

## API endpointy

| Účel | URL |
|---|---|
| Meteogram pro POI (JSON, 73 h) | `https://data-provider.chmi.cz/api/graphs/graf.meteogram/{poi_id}` |
| Meteogram pro libovolný bod | `https://data-provider.chmi.cz/api/graphs/graf.meteogram?x=<lon>&y=<lat>` |
| Výstrahy (texty, členěné kraj/ORP) | `https://vystrahy-cr.chmi.cz/data/alerts.json` |
| Seznam POI (per kategorie) | `https://data-provider.chmi.cz/api/poi/data/map/{obce\|voda\|lyze\|letiste}/4` |
| Hranice ORP (offline snapshot) | `https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` — vrstva `ORP_P` |

POI IDs jsou převzaty z mapového komponentu chmi.cz; integrace si vede vlastní snapshot
v `data/aladin_locations.json`, obnovitelný přes `tools/scrape_locations.py`.

### Proč ne `data-provider.chmi.cz/api/cap/data/*`

Ten endpoint texty výstrah **nevrací** — jen base64 PNG mapu ČR a štítek závažnosti
(„Nízký stupeň"). Oficiální web z něj renderuje jen obrázek a větu „Je vydána výstraha".
Skutečná strukturovaná data (`description.cz`, `instruction.cz`, platnost) jsou
v `alerts.json` mapy výstrah, členěná po krajích a ORP.

### Jak se páruje lokalita s výstrahou

Výstrahy jsou vázané na kraje a ORP, ne na souřadnice. Integrace proto obsahuje
zjednodušené hranice ORP z RÚIAN (ČÚZK, CC-BY 4.0) v `data/orp_boundaries.json`
(206 ORP, ~500 KB, Douglas-Peucker ~200 m) a dělá point-in-polygon čistě v Pythonu
(`orp.py`, ray casting) — **žádné závislosti navíc a žádné privátní API**.
Hranice obnovíš přes `tools/fetch_orp_boundaries.py` (vyžaduje `pyshp` + `pyproj`).

Pozn.: RÚIAN uvádí Prahu jako NUTS3 `CZ010`, ČHMÚ používá `CZ090` — skript to přemapuje.

## Disclaimer

Projekt není přidružen k ČHMÚ ani jím sponzorován. Data jsou veřejně dostupná.
Hranice ORP © ČÚZK (CC-BY 4.0). Update interval je 30 minut.

## Licence

Apache 2.0
