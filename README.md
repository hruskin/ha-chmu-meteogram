# Počasí ČHMÚ — Meteogram pro Home Assistant

Neoficiální custom integrace pro Home Assistant, která stahuje **meteogram modelu ALADIN**
z webu Českého hydrometeorologického ústavu (ČHMÚ) a zobrazuje ho v dashboardu.
Lokalita se vybírá automaticky jako nejbližší ALADIN bod k zóně `home`.

> **Status**: Fáze 1 (MVP) — meteogram jako obrázek + výstrahy ČHMÚ.
> Fáze 2 (strukturovaná data pro automatizace) v plánu.

## Funkce

- 📈 **`image.chmu_meteogram_*`** — meteogram ALADIN (teplota, srážky, vítr, vlhkost, tlak)
  obnovovaný podle běhů modelu (00/06/12/18 UTC)
- ⚠️ **`binary_sensor.chmu_vystrahy_*`** — výstrahy ČHMÚ (CAP 1.2) kompatibilní
  s [MeteoalarmCard](https://github.com/MrBartusek/MeteoalarmCard)
- 🗺️ **Automatický výběr lokality** podle souřadnic Home Assistantu

## Instalace

### Přes HACS (custom repository)

1. HACS → Integrations → ⋮ → Custom repositories
2. Repository: `https://github.com/hruskin/ha-chmu-meteogram`, Category: Integration
3. Nainstaluj **Počasí ČHMÚ (Meteogram)** a restartuj Home Assistant
4. Nastavení → Zařízení a služby → **Přidat integraci** → „Počasí ČHMÚ"

### Ručně

Zkopíruj adresář `custom_components/chmu_meteogram/` do `config/custom_components/`
ve své instalaci HA a restartuj.

## Použití v dashboardu

```yaml
type: picture-entity
entity: image.chmu_meteogram_praha
show_state: false
show_name: false
```

## Zdroje dat

- Meteogram PNG: `https://www.chmi.cz/files/portal/docs/meteo/ov/aladin/results/public/meteogramy/data/`
- Výstrahy CAP: `https://vystrahy-cr.chmi.cz/data/XOCZ50_OKPR.xml`

## Disclaimer

Projekt není přidružen k ČHMÚ ani jím sponzorován. Data jsou veřejně dostupná na webu chmi.cz.
Respektuj prosím servery ČHMÚ — výchozí interval obnovení je 30 minut s ETag/Last-Modified kontrolou.

## Licence

Apache 2.0
