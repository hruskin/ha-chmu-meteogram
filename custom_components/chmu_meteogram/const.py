"""Konstanty pro integraci Počasí ČHMÚ (Meteogram)."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "chmu_meteogram"

PLATFORMS = ["sensor", "binary_sensor"]

CONF_LOCATION_ID = "location_id"
CONF_ALERTS_ENABLED = "alerts_enabled"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

# JSON API ČHMÚ (Liferay portlet "ChmiGraph" + map-component)
API_BASE = "https://data-provider.chmi.cz/api"
METEOGRAM_URL = API_BASE + "/graphs/graf.meteogram/{poi_id}"
ALERT_URL = API_BASE + "/cap/data/poi"  # ?poiId=
ALERT_URL_ALL = API_BASE + "/cap/data/all/poi"  # ?poiId=  (vrátí seznam aktivních výstrah)

# Veřejná stránka meteogramu pro daný POI (pro configuration_url)
PUBLIC_URL = "https://www.chmi.cz/meteogram/{poi_id}-{slug}"

USER_AGENT = "ha-chmu-meteogram/0.2 (+https://github.com/hruskin/ha-chmu-meteogram)"
