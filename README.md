<img src="custom_components/chmu_meteogram/brand/logo.png" align="right" height="64" alt="logo">

# Počasí ČHMÚ pro Home Assistant

Předpověď počasí, výstrahy a meteoradar Českého hydrometeorologického ústavu
přímo ve vašem Home Assistantu — pro vaši adresu, ne pro nejbližší velké město.

Bez registrace, bez API klíčů, zdarma.

## Co to umí

**🌡️ Předpověď na 3 dny** z modelu ALADIN
Teplota, srážky, vítr a nárazy, vlhkost, tlak, oblačnost, sníh — po hodinách
i po dnech. Model počítá v síti 2,3 km, takže i malá vesnice dostane vlastní
předpověď.

**⚠️ Výstrahy ČHMÚ s plnými texty**
Bouřky, vysoké teploty, vítr, povodně… včetně doporučení, co dělat, a doby
platnosti. Výstrahy platí pro obec s rozšířenou působností, do které spadáte —
ne pro celou republiku.

**🌧️ Meteoradar — prší / bude pršet**
Obnovuje se po 5 minutách a odpoví na to nejpraktičtější: *prší u nás teď?*
a *za jak dlouho začne, případně přestane?* Ideální pro automatizace typu
„zavři okna, než přijde déšť". V zimě zachytí i sněžení.

## Instalace

### Přes HACS (doporučeno)

1. HACS → **⋮** → **Custom repositories**
2. Vložte `https://github.com/hruskin/ha-chmu-meteogram`, kategorie **Integration**
3. Nainstalujte a restartujte Home Assistant
4. **Nastavení → Zařízení a služby → Přidat integraci → „Počasí ČHMÚ"**

### Ručně

Zkopírujte složku `custom_components/chmu_meteogram` do adresáře
`custom_components` ve své konfiguraci a restartujte Home Assistant.

## Nastavení

Při přidání integrace zvolíte, odkud se bere lokalita:

- **Home** *(doporučeno)* — použijí se přesné souřadnice vašeho Home Assistantu
- **POI ze seznamu** — konkrétní místo ze seznamu ČHMÚ (obce, lyžařská
  střediska, vodní plochy, letiště). Hodí se, když vás zajímá třeba sjezdovka.

Později můžete v **Konfigurovat** doladit meteoradar:

| Volba | Výchozí | Co dělá |
|---|---|---|
| Poloměr sledovaného okolí | 3 km | Jak velké okolí se kolem vás sleduje |
| Práh pro „Prší" | 12 dBZ | Citlivost na aktuální srážky (≈ mrholení) |
| Práh pro „Bude pršet" | 18 dBZ | Citlivost předpovědi (≈ slabé srážky) |

> **Tip:** Když vám „Bude pršet" hlásí plané poplachy, zvyšte práh na 22–24 dBZ.
> Naopak když vám utíkají přeháňky, snižte na 14–16.
> Orientačně: 12 dBZ ≈ mrholení · 28 dBZ ≈ vydatné srážky · 40 dBZ ≈ liják.

## Co dostanete

Vše je pod jedním zařízením **ČHMÚ &lt;místo&gt;**.

### Počasí
| Entita | Popis |
|---|---|
| `weather.…_predpoved` | Předpověď po hodinách i dnech pro standardní kartu počasí |
| `sensor.…_teplota` | Teplota (°C) |
| `sensor.…_srazky` | Srážky (mm/h) |
| `sensor.…_vlhkost` | Relativní vlhkost (%) |
| `sensor.…_tlak` | Tlak přepočtený na hladinu moře (hPa) |
| `sensor.…_rychlost_vetru`, `…_narazy_vetru`, `…_smer_vetru` | Vítr |
| `sensor.…_oblacnost` | Oblačnost (%) |
| `sensor.…_snih` | Sněžení (mm/h) |

### Meteoradar
| Entita | Popis |
|---|---|
| `binary_sensor.…_prsi` | Ve vašem okolí právě padají srážky |
| `binary_sensor.…_bude_prset` | Srážky se blíží (do hodiny) |
| `sensor.…_dest_za` | Za kolik minut začnou |
| `sensor.…_dest_skonci_za` | Za kolik minut přestanou |
| `sensor.…_intenzita_srazek` | Jak silně prší nebo sněží (mm/h) |
| `image.…_meteoradar` | Radarový snímek okolí se značkou vaší polohy |

### Výstrahy
| Entita | Popis |
|---|---|
| `binary_sensor.…_vystrahy_chmu` | Je vydána výstraha; texty najdete v atributech |

## Na dashboard

**Předpověď** — stačí standardní karta počasí:

```yaml
type: weather-forecast
entity: weather.chmu_home_predpoved
forecast_type: daily     # nebo hourly
```

**Radar s aktuální situací:**

```yaml
type: picture-entity
entity: image.chmu_home_meteoradar
camera_view: auto
```

**Přehled deště:**

```yaml
type: entities
title: Déšť
entities:
  - binary_sensor.chmu_home_prsi
  - sensor.chmu_home_dest_za
  - sensor.chmu_home_dest_skonci_za
  - sensor.chmu_home_intenzita_srazek
```

**Výstrahy s texty:**

```yaml
type: markdown
content: >
  {% set a = state_attr('binary_sensor.chmu_home_vystrahy_chmu', 'alerts') %}
  {% if a %}{% for x in a %}
  ### {{ x.label }}
  {{ x.description }}

  {% if x.instruction %}**Doporučení:** {{ x.instruction }}{% endif %}
  {% endfor %}{% else %}Žádné výstrahy{% endif %}
```

Výstrahy fungují i s hotovou kartou
[MeteoalarmCard](https://github.com/MrBartusek/MeteoalarmCard).

## Příklady automatizací

**Zavřít okna, než začne pršet:**

```yaml
triggers:
  - trigger: numeric_state
    entity_id: sensor.chmu_home_dest_za
    below: 15
actions:
  - action: cover.close_cover
    target:
      entity_id: cover.okna
```

**Upozornit na výstrahu:**

```yaml
triggers:
  - trigger: state
    entity_id: binary_sensor.chmu_home_vystrahy_chmu
    to: "on"
actions:
  - action: notify.mobile_app
    data:
      title: >
        Výstraha ČHMÚ: {{ state_attr(trigger.entity_id, 'headline') }}
      message: "{{ state_attr(trigger.entity_id, 'description') }}"
```

**Nezalévat, když prší nebo bude pršet:**

```yaml
conditions:
  - condition: state
    entity_id: binary_sensor.chmu_home_prsi
    state: "off"
  - condition: state
    entity_id: binary_sensor.chmu_home_bude_prset
    state: "off"
```

## Časté dotazy

**Jak často se data obnovují?**
Radar po 5 minutách, předpověď a výstrahy po 30 minutách.

**Radar hlásí srážky, ale venku nic (nebo naopak).**
Radar měří srážky ve výšce — část se cestou k zemi vypaří, jindy prší jen kousek
vedle. Pomůže doladit poloměr a prahy v nastavení (viz výše).

**Rozliší radar déšť od sněhu?**
Ne — měří jen intenzitu srážek, ne jejich druh. Proto entity mluví o dešti,
i když v zimě jde o sněžení. Typ srážek napoví předpověď
(`sensor.…_snih`) nebo teplota.

**Předpověď se liší od aplikace Počasí ČHMÚ.**
Data jsou stejná. Aplikace ale ukazuje předpověď pro vybrané město, kdežto tady
se počítá pro vaše souřadnice.

**„Déšť za" je prázdné.**
To je v pořádku — znamená to, že se do hodiny žádný déšť nečeká.

**V HACS chybí ikona integrace.**
HACS bere ikony z centrálního katalogu, který ikony neoficiálních integrací
nepřijímá. V samotném Home Assistantu (Zařízení a služby) se ikona zobrazuje
normálně.

## Poznámky

Neoficiální projekt, není přidružený k ČHMÚ ani jím podporovaný. Data jsou
veřejně dostupná; hranice správních obvodů © ČÚZK (CC-BY 4.0).

Zajímá vás, jak to uvnitř funguje? Podívejte se do
[technické dokumentace](docs/TECHNICAL.md).

Licence: Apache 2.0
