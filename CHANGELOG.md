# Changelog

Formát vychází z [Keep a Changelog](https://keepachangelog.com/cs/1.1.0/),
verzování drží [SemVer](https://semver.org/lang/cs/). Do 1.0.0 se zásadní
(breaking) změny značí zvýšením podverze (0.X.0).

## 0.13.1 — 2026-09-22

### Změněno

- Výběr zdroje lokality (Home / POI) v nastavení je nově dvojjazyčný (cs/en)
  přes překlady, místo natvrdo české volby. Zbytek UI a stavy entit už
  dvojjazyčné byly. Texty výstrah zůstávají česky — ČHMÚ je jen v češtině dává.

## 0.13.0 — 2026-09-22

### Zásadní změny (breaking)

- **Radarové entity sloučeny do jedné.** Místo pěti entit
  (`binary_sensor.*_raining`, `binary_sensor.*_rain_expected`,
  `sensor.*_rain_starts_in`, `sensor.*_rain_ends_in`,
  `sensor.*_radar_intensity`) je nově **jeden** `sensor.*_dest`
  (`translation_key: rain`, `device_class: enum`) se stavem
  `dry` / `rain_expected` / `raining`. Vše ostatní (intenzita mm/h, dbz,
  pokrytí, trend, minuty do začátku i konce deště, radarová předpověď
  +10…+60 min, prahy, čas snímku) je v atributech té jedné entity.

### Migrace

- Starých pět entit se přestane vytvářet a v registru zůstanou jako
  nedostupné — smažte je v Nastavení → Zařízení a služby → ČHMÚ.
- Automatizace a karty přepište na `sensor.<místo>_dest`:
  - prší: `is_state('sensor.<místo>_dest', 'raining')`
  - bude pršet: `is_state('sensor.<místo>_dest', 'rain_expected')`
  - intenzita: `state_attr('sensor.<místo>_dest', 'intensity_mm_h')`
  - minuty do deště: `state_attr('sensor.<místo>_dest', 'starts_in_minutes')`
  - minuty do konce: `state_attr('sensor.<místo>_dest', 'ends_in_minutes')`

### Změněno

- Stav dešťové entity je vícejazyčný (cs/en) přes překlady; klíče stavu jsou
  strojové, bez diakritiky (`dry` / `rain_expected` / `raining`), takže
  automatizace se píšou na klíč, ne na zobrazený text.

## Starší verze

Zásadní změna byla i v 0.12.0 (desetidenní výhled a rozdělené weather entity).
Kompletní historii verzí najdete v [GitHub Releases](https://github.com/hruskin/ha-chmu-meteogram/releases).
