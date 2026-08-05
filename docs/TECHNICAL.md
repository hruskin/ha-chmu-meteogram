# Technická dokumentace

Zápisky pro vývoj a údržbu. Uživatelský popis je v [README](../README.md).

## Zdroje dat

| Účel | URL |
|---|---|
| Meteogram pro POI (JSON, 73 h) | `https://data-provider.chmi.cz/api/graphs/graf.meteogram/{poi_id}` |
| Meteogram pro libovolný bod | `https://data-provider.chmi.cz/api/graphs/graf.meteogram?x=<lon>&y=<lat>` |
| Výstrahy (texty, členěné kraj/ORP) | `https://vystrahy-cr.chmi.cz/data/alerts.json` |
| Seznam POI (per kategorie) | `https://data-provider.chmi.cz/api/poi/data/map/{obce\|voda\|lyze\|letiste}/4` |
| Radar — aktuální | `https://opendata.chmi.cz/.../radar/composite/maxz/png/pacz2gmaps3.z_max3d.<YYYYMMDD.HHMM>.0.png` |
| Radar — předpověď | `https://opendata.chmi.cz/.../radar/composite/fct_maxz/png/pacz2gmaps3.fct_z_max.<YYYYMMDD.HHMM>.ft60s10.tar` |
| Hranice ORP (offline snapshot) | `https://services.cuzk.gov.cz/shp/stat/epsg-5514/1.zip` — vrstva `ORP_P` |

Vše je veřejné, bez autentizace. POI IDs pocházejí z mapového komponentu
chmi.cz; integrace si vede vlastní snapshot v `data/aladin_locations.json`,
obnovitelný přes `tools/scrape_locations.py`.

### Proč ne `data-provider.chmi.cz/api/cap/data/*`

Ten endpoint texty výstrah **nevrací** — jen base64 PNG mapu ČR a štítek
závažnosti („Nízký stupeň"). Oficiální web z něj renderuje pouze obrázek a větu
„Je vydána výstraha". Skutečná strukturovaná data (`description.cz`,
`instruction.cz`, platnost) jsou v `alerts.json` mapy výstrah, členěná po
krajích a ORP.

Navíc: query parametr `?poiId=` ten endpoint **tiše ignoruje** a vrací výchozí
odpověď „žádné nebezpečí" — web používá cestu, ne query. Kvůli tomu hlásila
integrace v POI režimu vždy „bez výstrah".

## Desetidenní výhled

ALADIN počítá na tři dny. Delší výhled vydává ČHMÚ zvlášť a veřejná opendata
ho nemají — jsou tam jen slovní předpovědi po krajích, ze kterých by se čísla
musela tahat regexem z vět typu „24 až 19 °C, na západě kolem 17".

Strukturovaně ho vrací backend mobilní aplikace:

```
POST https://chmu.rails.cz/api/v1/jwt/login
     {"device": {"device_token": "<cokoli>", "platform": "android"}}
  → {"access_token": …, "refresh_token": …}

GET  https://chmu.rails.cz/api/v1/weather_bulletins/cr
     Authorization: Bearer <token>
```

Token je anonymní — `device_token` se neověřuje, posílá se náhodné UUID.
Platí řádově týdny; klient si ho obnovuje po sedmi dnech a hned při 401.

Odpověď je pole dnů. Spolehlivě naplněné je jen `date_at`,
`temperature_min`/`max`, `cloudiness_value` a `phenomenon_value`; pole pro
vítr, pravděpodobnost srážek, pocitovou teplotu a biopředpověď v odpovědi jsou,
ale bývají `null`. Stav počasí se odvozuje ze slovního popisu (jev má přednost
před oblačností), ne z `*_icon` — ikonový číselník neznáme celý.

Denní řada vzniká složením obou zdrojů. Model má u své lokality přednost, ale
jen u dnů, kde se dá věřit extrémům: meteogram končí uprostřed dne, takže jeho
poslední den bývá jen pár nočních hodin a „maximum" by z nich vyšlo jako
nejteplejší noční hodnota (viděno: 17,8–18,4 °C proti 13–27 °C ve výhledu).

Den z modelu se proto použije jen tehdy, když pokrývá ranní okno (4–7) i
odpolední (13–16) — tam extrémy nastávají. Výjimkou je **první den**, který se
bere i osekaný: ukazuje, co ze dne ještě zbývá, a to je užitečnější než
celodenní hodnota odjinud. Rozhodnutí je v `daily.py`, mimo Home Assistant,
aby šlo testovat samostatně.

Výhled pak doplní všechny dny, které model nepokryl — nejen ty za koncem řady,
ale i den, který kvůli tomuto pravidlu vypadl. Páruje se podle data.

Není to dokumentované rozhraní, takže výpadek nesmí ovlivnit zbytek integrace —
`async_refresh` se nechá selhat a předpověď zůstane jen na třech dnech.

## Radar (CZRAD)

Kompozit je paletové PNG 680×460 (~0,8 km/px). Hlavní mapa je výřez
`[82:460, 0:597]`; okolo jsou svislé a vodorovné řezy a popisky, které se nesmí
číst.

Paletové indexy **182–195** nesou odrazivost — nižší index = silnější echo,
`dBZ ≈ 4·(196−index)`, tj. 4–56 dBZ. Ostatní indexy jsou anotace: **145** je
rámeček a titulek, **242** šedý roh. Kdyby se nefiltrovaly, dělaly by falešný
déšť (a v náhledu ošklivé čáry). Intenzita se počítá Marshall-Palmerem
(`Z = 200·R^1.6`).

Georeference je ověřená překrytím s hranicemi ORP; převod bodu na pixel je ve
Web Mercatoru a `px ↔ lat/lon` round-trip vychází na 0,00 px. Čte se **okolí**
lokality (výchozí 3 km), protože radar je zrnitý.

PNG se dekóduje i zapisuje čistě přes `zlib` ze standardní knihovny (~1 ms).
Předpověď (tar se šesti snímky +10…+60 min) se stahuje jen tehdy, když je echo
do 60 km — za jasného počasí tím odpadne ~100 kB na každou aktualizaci.

Konec deště bere první snímek pod prahem, po kterém se srážky ve zbytku
předpovědi už nevrátí, takže krátká pauza mezi přeháňkami se nepočítá. Trend
vyžaduje změnu aspoň 4 dBZ — škála je kvantovaná po 4 dBZ, menší rozdíl je šum.

## Párování výstrah s lokalitou

Výstrahy jsou vázané na kraje a ORP, ne na souřadnice. Integrace proto obsahuje
zjednodušené hranice ORP z RÚIAN (ČÚZK, CC-BY 4.0) v `data/orp_boundaries.json`
(206 ORP, ~500 kB, Douglas-Peucker ~200 m) a dělá point-in-polygon čistě
v Pythonu (`orp.py`, ray casting).

Párování v `alerts.json` jde přes `cz.chmi.region:{NUTS3}` plus `whole_area`
nebo název ORP mezi `subareas`. Ověřeno, že všech 141 živých názvů subareas
odpovídá ČÚZK přesně.

Pozn.: RÚIAN uvádí Prahu jako NUTS3 `CZ010`, ČHMÚ používá `CZ090` — skript
`tools/fetch_orp_boundaries.py` to přemapuje.

## Ikony počasí

`weather.condition` se neodvozuje z oblačnosti, ale přímo z pole `icon`
meteogramu: desítky = oblačnost (1 jasno … 8 zataženo, 9 bouřka), jednotky =
srážky, `+100` = noční varianta. Ověřeno na živých datech (60 = oblačno,
81 = zataženo s deštěm, 110 = jasná noc, 91 = bouřka s deštěm).

## Závislosti

Integrace nemá **žádné** — `requirements` v `manifest.json` je prázdné.
I věci, které by závislost obvykle vyžadovaly, řeší standardní knihovna:

| Úloha | Obvyklé řešení | Zde |
|---|---|---|
| Dekódování a zápis PNG | Pillow | `zlib` |
| Bod v polygonu ORP | shapely | ray casting v `orp.py` |
| Rozbalení předpovědi | — | `tarfile` |

Balíčky potřebují jen vývojářské nástroje (`requirements-dev.txt`) a testy
(`requirements-test.txt`); do Home Assistantu se neinstaluje nic z toho.

## Bezpečnostní pojistky

Integrace jen čte veřejná data přes HTTPS, nikam neposílá přihlašovací údaje a
nic nezapisuje na disk mimo vlastní adresář. Protože si ale data parsuje
vlastními parsery, má limity proti vyčerpání paměti:

| Pojistka | Limit | Reálně |
|---|---|---|
| Velikost odpovědi | 8 MB | ≤ 110 kB |
| Rozměry snímku z hlavičky PNG | 4096 px | 680×460 |
| Počet souborů v archivu | 32 | 6 |
| Velikost souboru v archivu | 4 MB | ~25 kB |
| Dekomprese zlib | dle rozměrů snímku | — |
| Časový limit dotazu | 20 s / 30 s | — |

Archiv se nikdy nerozbaluje na disk, čte se jen do paměti — podvržené cesty
v názvech (`../`) tedy nemají kam uškodit.

Pozor na `aiohttp`: `content.read(n)` vrací jen právě dostupný blok, ne celých
`n` bajtů. `net.read_limited` proto čte po blocích a hlídá průběžný součet;
deklarovanému `Content-Length` se nevěří.

## Vývojový workflow

Release jsou automatické — po bumpnutí `version` v `manifest.json` a pushi na
`main` vytvoří GitHub Action tag `vX.Y.Z` a publishne Release s auto-notes
z commitů (`.github/workflows/release.yml`). HACS verzi vidí hned po
Redownload / Reload data.

Při každém pushi a PR běží `Hassfest`, `HACS validation` a `Pytest`
(`.github/workflows/validate.yml`); validace jede i týdně, aby zachytila změny
pravidel na jejich straně.

`ignore: brands` v HACS validaci je trvalý — `home-assistant/brands` už ikony
custom integrací nepřijímá, od HA 2026.3 se dodávají lokálně v
`custom_components/<domain>/brand/`.

## Nástroje

| Skript | K čemu |
|---|---|
| `tools/fetch_orp_boundaries.py` | obnoví hranice ORP z ČÚZK |
| `tools/scrape_locations.py` | obnoví seznam ALADIN POI |
| `tools/process_icon.py` | vygeneruje brand ikony ze `brand_src.png` |
