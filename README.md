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

**Meteoradar** (CZRAD, obnova po 5 min):
- `binary_sensor.chmu_<misto>_prsi` — prší podle radaru v okolí lokality
- `binary_sensor.chmu_<misto>_bude_prset` — radarová předpověď hlásí déšť do hodiny
- `sensor.chmu_<misto>_dest_za` — za kolik minut déšť dorazí (0 = prší, jinak prázdné)
- `sensor.chmu_<misto>_intenzita_srazek_radar_` — mm/h odvozené z odrazivosti

**Binary sensor:**
- `binary_sensor.chmu_<misto>_vystrahy_chmu` — aktivní výstrahy **s plnými texty**
  (`description`, `instruction`, závažnost, platnost od/do) pro ORP, ve kterém
  lokalita leží. Atributy jsou kompatibilní s
  [MeteoalarmCard](https://github.com/MrBartusek/MeteoalarmCard).

**Weather entita:**
- `weather.chmu_<misto>_predpoved` — aktuální podmínky + **hodinový forecast 73 h**
  a **denní forecast** (agregace na 3–4 dny: max/min teplota, srážky, vítr).
  Podmínky (jasno/oblačno/déšť/bouřka, den/noc) se odvozují přímo z ČHMÚ ikony.
  Funguje s nativní HA `weather-forecast` kartou (hourly i daily) nebo
  s [Hourly Weather Card](https://github.com/decompil3d/lovelace-hourly-weather).

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
| Radar — aktuální | `https://opendata.chmi.cz/.../radar/composite/maxz/png/pacz2gmaps3.z_max3d.<YYYYMMDD.HHMM>.0.png` |
| Radar — předpověď | `https://opendata.chmi.cz/.../radar/composite/fct_maxz/png/pacz2gmaps3.fct_z_max.<YYYYMMDD.HHMM>.ft60s10.tar` |
| Hranice ORP (offline snapshot) | `https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` — vrstva `ORP_P` |

POI IDs jsou převzaty z mapového komponentu chmi.cz; integrace si vede vlastní snapshot
v `data/aladin_locations.json`, obnovitelný přes `tools/scrape_locations.py`.

### Proč ne `data-provider.chmi.cz/api/cap/data/*`

Ten endpoint texty výstrah **nevrací** — jen base64 PNG mapu ČR a štítek závažnosti
(„Nízký stupeň"). Oficiální web z něj renderuje jen obrázek a větu „Je vydána výstraha".
Skutečná strukturovaná data (`description.cz`, `instruction.cz`, platnost) jsou
v `alerts.json` mapy výstrah, členěná po krajích a ORP.

### Jak funguje radar

Radarový kompozit CZRAD je paletové PNG 680×460 (~0,8 km/px). Hlavní mapa je
výřez `[82:460, 0:597]` — okolo jsou svislé/vodorovné řezy a popisky, které se
nesmí číst. Paletové indexy **182–195** nesou odrazivost (nižší index = silnější
echo, `dBZ ≈ 4·(196−index)`, tj. 4–56 dBZ); ostatní indexy jsou rámeček a
anotace. Intenzita se počítá Marshall-Palmerem (`Z = 200·R^1.6`).

Georeference je ověřená překrytím s hranicemi ORP (viz `tools/`), převod bodu na
pixel je ve Web Mercatoru. Čte se **okolí** lokality (výchozí poloměr 3 km,
nastavitelné 1–25 km), protože radar je zrnitý.

PNG se dekóduje čistě v Pythonu přes `zlib` ze standardní knihovny (~1 ms),
takže integrace ani kvůli radaru nemá žádné závislosti. Předpověď (tar se šesti
snímky +10…+60 min) se stahuje jen tehdy, když je echo do 60 km — za jasného
počasí tím odpadne ~100 kB na každou aktualizaci.

Práh pro hlášení deště je 12 dBZ (≈ 0,2 mm/h); slabší echa bývají virga nebo šum.

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
