"""Konstanty pro integraci Počasí ČHMÚ (Meteogram)."""
from __future__ import annotations

from datetime import timedelta

DOMAIN = "chmu_meteogram"

PLATFORMS = ["image", "binary_sensor"]

CONF_LOCATION_ID = "location_id"
CONF_LOCATION_NAME = "location_name"
CONF_LATITUDE = "latitude"
CONF_LONGITUDE = "longitude"
CONF_ALERTS_ENABLED = "alerts_enabled"

DEFAULT_SCAN_INTERVAL = timedelta(minutes=30)

# URL šablony — meteogram PNG
# Pattern: .../data/YYYYMMDDHH/<id>.png, kde HH je běh modelu (00/06/12/18 UTC)
METEOGRAM_BASE_URL = (
    "https://www.chmi.cz/files/portal/docs/meteo/ov/aladin/results/"
    "public/meteogramy/data"
)

# Hodiny běhů modelu ALADIN (UTC)
ALADIN_RUN_HOURS = (0, 6, 12, 18)
# Typické zpoždění mezi během modelu a publikací výstupu
ALADIN_PUBLISH_DELAY_HOURS = 3

# CAP XML s výstrahami ČHMÚ pro celou ČR
ALERTS_URL = "https://vystrahy-cr.chmi.cz/data/XOCZ50_OKPR.xml"

USER_AGENT = "ha-chmu-meteogram/0.1 (+https://github.com/hruskin/ha-chmu-meteogram)"
