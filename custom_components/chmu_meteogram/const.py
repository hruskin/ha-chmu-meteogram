"""Konstanty pro integraci Počasí ČHMÚ (Meteogram)."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "chmu_meteogram"

PLATFORMS = ["sensor", "binary_sensor", "weather"]

# config keys
CONF_MODE = "mode"  # "home" | "poi"
CONF_LOCATION_ID = "location_id"  # jen pro mode=poi
CONF_ALERTS_ENABLED = "alerts_enabled"

MODE_HOME = "home"
MODE_POI = "poi"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

# JSON API ČHMÚ (Liferay portlet "ChmiGraph" + map-component)
API_BASE = "https://data-provider.chmi.cz/api"

# Meteogram — dvě varianty (POI vs libovolný bod)
METEOGRAM_URL_POI = API_BASE + "/graphs/graf.meteogram/{poi_id}"
METEOGRAM_URL_POINT = API_BASE + "/graphs/graf.meteogram"  # ?x=lon&y=lat

# Výstrahy: data-provider /cap/data/* vrací jen base64 PNG mapu a štítek
# závažnosti — texty tam nejsou. Skutečná strukturovaná data (description.cz,
# instruction.cz) jsou v JSON mapy výstrah, členěná po krajích a ORP.
ALERTS_URL = "https://vystrahy-cr.chmi.cz/data/alerts.json"

# Kategorie, které přeskakujeme:
#  - outlook: vícedenní výhled, ne výstraha
#  - ozone/dust/nitrogen-dioxide/sulfur-dioxide: kvalita ovzduší má jiné
#    členění oblastí (cz.chmi.o3:N, cz.chmi.pm10:N…), ne kraje/ORP
ALERT_SKIP_CATEGORIES = frozenset(
    {"outlook", "ozone", "dust", "nitrogen-dioxide", "sulfur-dioxide"}
)

ALERT_REGION_PREFIX = "cz.chmi.region:"

SEVERITY_ORDER = {"Extreme": 0, "Severe": 1, "Moderate": 2, "Minor": 3}

# Kategorie výstrahy → čitelný název a ikona. `phenomenon` v datech je jen
# varianta se stupněm (moderate-heat-stress), kategorie je stabilní klíč.
ALERT_CATEGORY_LABELS = {
    "heat": "Vysoké teploty",
    "heat-stress": "Zátěž teplem",
    "cold": "Nízké teploty",
    "cold-stress": "Zátěž chladem",
    "wind": "Vítr",
    "rain": "Déšť",
    "snow": "Sněžení",
    "thunderstorms": "Bouřky",
    "floods": "Povodně",
    "fires": "Riziko požárů",
    "ice-load": "Námraza",
    "slippery-roads": "Náledí",
    "another-phenomena": "Jiné jevy",
}

ALERT_CATEGORY_ICONS = {
    "heat": "mdi:thermometer-high",
    "heat-stress": "mdi:sun-thermometer",
    "cold": "mdi:thermometer-low",
    "cold-stress": "mdi:snowflake-thermometer",
    "wind": "mdi:weather-windy",
    "rain": "mdi:weather-pouring",
    "snow": "mdi:weather-snowy-heavy",
    "thunderstorms": "mdi:weather-lightning",
    "floods": "mdi:home-flood",
    "fires": "mdi:fire",
    "ice-load": "mdi:snowflake-alert",
    "slippery-roads": "mdi:car-brake-alert",
    "another-phenomena": "mdi:alert",
}

ALERT_FALLBACK_ICON = "mdi:alert"

# Barva dle závažnosti — pro Mushroom/karty i MeteoalarmCard
SEVERITY_COLORS = {
    "Minor": "yellow",
    "Moderate": "orange",
    "Severe": "red",
    "Extreme": "purple",
}

# Veřejná stránka meteogramu (pro configuration_url)
PUBLIC_URL_POI = "https://www.chmi.cz/meteogram/{poi_id}-{slug}"
PUBLIC_URL_POINT = "https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/meteogram-pro-bod-na-mape"

USER_AGENT = "ha-chmu-meteogram/0.3 (+https://github.com/hruskin/ha-chmu-meteogram)"
