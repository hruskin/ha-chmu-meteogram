# Počasí ČHMÚ — Meteogram pro Home Assistant

Neoficiální custom integrace pro Home Assistant, která stahuje **strukturovaná data meteogramu modelu ALADIN**
z veřejného JSON API Českého hydrometeorologického ústavu (ČHMÚ).
Lokalita se vybírá automaticky jako nejbližší ALADIN POI k zóně `home`.

> **Status**: 0.2.0 — strukturovaná data jako HA sensory + výstrahy ČHMÚ.

## Co dostaneš

Pro vybranou lokalitu (jednu z 830+ ALADIN POI: obce, lyžařská střediska, vodní plochy, letiště) integrace vytvoří:

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
- `binary_sensor.chmu_<misto>_vystrahy_chmu` — aktivní výstraha pro danou obec

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

> Pozn.: Apex zobrazí jen historické hodnoty. Pro plnohodnotný "meteogram"
> s celou předpovědí přidáme později `WeatherEntity` s `async_forecast_hourly`.

## API endpointy

| Účel | URL |
|---|---|
| Meteogram (JSON, 73 hodin) | `https://data-provider.chmi.cz/api/graphs/graf.meteogram/{poi_id}` |
| Výstraha pro POI | `https://data-provider.chmi.cz/api/cap/data/poi?poiId={poi_id}` |
| Seznam POI (per kategorie) | `https://data-provider.chmi.cz/api/poi/data/map/{obce\|voda\|lyze\|letiste}/4` |

POI IDs jsou převzaty z mapového komponentu chmi.cz; integrace si vede vlastní snapshot
v `data/aladin_locations.json`, který jde obnovit přes `tools/scrape_locations.py`.

## Disclaimer

Projekt není přidružen k ČHMÚ ani jím sponzorován. Data jsou veřejně dostupná na webu chmi.cz.
Update interval je 30 minut.

## Licence

Apache 2.0
