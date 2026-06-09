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

# Výstrahy — dvě varianty
ALERT_URL_POI = API_BASE + "/cap/data/poi"          # ?poiId=
ALERT_URL_POINT = API_BASE + "/cap/data/point"      # ?x=lon&y=lat
ALERT_URL_ALL_POI = API_BASE + "/cap/data/all/poi"  # ?poiId=

# Veřejná stránka meteogramu (pro configuration_url)
PUBLIC_URL_POI = "https://www.chmi.cz/meteogram/{poi_id}-{slug}"
PUBLIC_URL_POINT = "https://www.chmi.cz/predpoved-pocasi/meteogramy-aladin/meteogram-pro-bod-na-mape"

USER_AGENT = "ha-chmu-meteogram/0.3 (+https://github.com/hruskin/ha-chmu-meteogram)"
