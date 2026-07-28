"""Meteoradar ČHMÚ (CZRAD) — čtení srážek pro konkrétní bod.

Zdroj: veřejná opendata ČHMÚ (žádná autentizace):
  aktuální   .../radar/composite/maxz/png/pacz2gmaps3.z_max3d.YYYYMMDD.HHMM.0.png
  předpověď  .../radar/composite/fct_maxz/png/
             pacz2gmaps3.fct_z_max.YYYYMMDD.HHMM.ft60s10.tar
             (tar = 6 PNG pro +10…+60 min)

Snímky jsou paletové PNG 680×460. Hlavní mapa je výřez [82:460, 0:597]; okolo
jsou svislé/vodorovné řezy a popisky, které se nesmí číst. Paletové indexy
182–195 nesou odrazivost (nižší index = silnější echo), ostatní indexy jsou
rámeček a anotace.

PNG se dekóduje čistě v Pythonu přes zlib (stdlib) — integrace tak nemá žádné
další závislosti. Snímky používají filtr 0 (None), dekódování trvá ~1 ms.
"""
from __future__ import annotations

import io
import logging
import math
import struct
import tarfile
import zlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from aiohttp import ClientSession, ClientTimeout

from .const import USER_AGENT

_LOGGER = logging.getLogger(__name__)
_TIMEOUT = ClientTimeout(total=30)

BASE = "https://opendata.chmi.cz/meteorology/weather/radar/composite"
_MAXZ = BASE + "/maxz/png/pacz2gmaps3.z_max3d.{stamp}.0.png"
_FCT = BASE + "/fct_maxz/png/pacz2gmaps3.fct_z_max.{stamp}.ft60s10.tar"

# Výřez hlavní mapy z celého snímku (zbytek jsou řezy a popisky).
CROP_X0, CROP_Y0 = 0, 82
CROP_W, CROP_H = 597, 378

# Geografické hranice výřezu (GroundOverlay konstanty oficiální aplikace),
# ověřeno překrytím s hranicemi ORP.
LAT_S, LAT_N = 48.478043, 51.101113
LON_W, LON_E = 12.028653, 18.927311

# Paletové indexy nesoucí odrazivost. Nižší index = vyšší dBZ.
IDX_MAX_ECHO, IDX_MIN_ECHO = 182, 195
_DBZ_STEP = 4  # dBZ = 4 × (196 − index) → 4…56 dBZ

# Slabá echa bývají virga nebo šum — pod tímto prahem neohlásíme déšť.
DEFAULT_DBZ_THRESHOLD = 12  # ≈ 0,2 mm/h — mrholení, které ale reálně padá
# Pro předpověď je práh vyšší: slabá echa se cestou často rozpustí, takže by
# hlásila plané poplachy.
DEFAULT_FORECAST_DBZ_THRESHOLD = 18  # ≈ 0,5 mm/h
DEFAULT_RADIUS_KM = 3.0

# Okruh, ve kterém hledáme echa, než se vyplatí stahovat předpověď.
# Bouřka se přesune ~30–50 km/h, takže hodinová předpověď dosáhne zhruba sem.
SCAN_RADIUS_KM = 60.0

FORECAST_STEPS = (10, 20, 30, 40, 50, 60)


def dbz_from_index(idx: int) -> float | None:
    """Odrazivost v dBZ pro paletový index, nebo None mimo škálu."""
    if not IDX_MAX_ECHO <= idx <= IDX_MIN_ECHO:
        return None
    return float(_DBZ_STEP * (IDX_MIN_ECHO + 1 - idx))


def rain_rate(dbz: float) -> float:
    """dBZ → mm/h dle Marshall-Palmer (Z = 200·R^1.6)."""
    return (10 ** (dbz / 10) / 200) ** (1 / 1.6)


def _merc(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


_M_N, _M_S = _merc(LAT_N), _merc(LAT_S)


def latlon_to_px(lat: float, lon: float) -> tuple[float, float]:
    """Bod → pixel ve výřezu (Web Mercator, jak snímek kreslí mapová vrstva)."""
    x = (lon - LON_W) / (LON_E - LON_W) * CROP_W
    y = (_M_N - _merc(lat)) / (_M_N - _M_S) * CROP_H
    return x, y


def px_per_km(lat: float) -> tuple[float, float]:
    """Kolik pixelů odpovídá kilometru ve vodorovném a svislém směru."""
    km_per_deg_lon = 111.320 * math.cos(math.radians(lat))
    x = CROP_W / ((LON_E - LON_W) * km_per_deg_lon)
    # svisle bereme lokální měřítko Mercatoru
    dlat = 0.01
    y = abs(latlon_to_px(lat + dlat, lon=LON_W)[1] - latlon_to_px(lat, LON_W)[1]) / (
        dlat * 110.574
    )
    return x, y


# ---------------------------------------------------------------- PNG dekodér


def _png_chunks(raw: bytes) -> tuple[int, int, int, bytes, bytes | None]:
    """Vrátí (šířka, výška, colorType, IDAT, tRNS)."""
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("není PNG")
    pos = 8
    width = height = color_type = 0
    idat = bytearray()
    trns: bytes | None = None
    while pos + 8 <= len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        ctype = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        if ctype == b"IHDR":
            width, height, bit_depth, color_type = struct.unpack(">IIBB", data[:10])
            if bit_depth != 8:
                raise ValueError(f"nepodporovaná bitová hloubka {bit_depth}")
        elif ctype == b"IDAT":
            idat += data
        elif ctype == b"tRNS":
            trns = data
        elif ctype == b"IEND":
            break
        pos += 12 + length
    return width, height, color_type, bytes(idat), trns


def _unfilter(data: bytes, width: int, channels: int, rows_needed: int) -> list[bytes]:
    """Odstraní PNG filtry; dekóduje jen prvních `rows_needed` řádků."""
    stride = width * channels
    out: list[bytes] = []
    prev = bytearray(stride)
    for r in range(rows_needed):
        off = r * (stride + 1)
        if off + stride + 1 > len(data):
            break
        ftype = data[off]
        line = bytearray(data[off + 1 : off + 1 + stride])
        if ftype == 1:  # Sub
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif ftype == 2:  # Up
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 0xFF
        elif ftype == 3:  # Average
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + prev[i]) >> 1)) & 0xFF
        elif ftype == 4:  # Paeth
            for i in range(stride):
                a = line[i - channels] if i >= channels else 0
                b = prev[i]
                c = prev[i - channels] if i >= channels else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                pred = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pred) & 0xFF
        elif ftype != 0:
            raise ValueError(f"neznámý filtr {ftype}")
        out.append(bytes(line))
        prev = line
    return out


@dataclass
class RadarFrame:
    """Dekódovaný snímek — jen paletové indexy hlavní mapy."""

    rows: list[bytes]  # řádky celého snímku (indexy palety)
    channels: int

    def index_at(self, x: int, y: int) -> int | None:
        """Paletový index na pozici ve výřezu, None mimo mapu."""
        if not (0 <= x < CROP_W and 0 <= y < CROP_H):
            return None
        row = CROP_Y0 + y
        if row >= len(self.rows):
            return None
        col = (CROP_X0 + x) * self.channels
        line = self.rows[row]
        if col >= len(line):
            return None
        return line[col]


def decode_frame(raw: bytes, rows_needed: int | None = None) -> RadarFrame:
    width, height, color_type, idat, _ = _png_chunks(raw)
    channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    if color_type != 3:
        _LOGGER.debug("radarový snímek není paletový (colorType %s)", color_type)
    need = height if rows_needed is None else min(height, rows_needed)
    stride = width * channels
    data = zlib.decompressobj().decompress(idat, (stride + 1) * need + 4096)
    return RadarFrame(rows=_unfilter(data, width, channels, need), channels=channels)


# ------------------------------------------------------------------- odečet


@dataclass
class Sample:
    """Výsledek odečtu radaru v okolí bodu."""

    max_dbz: float | None  # nejsilnější echo v okolí
    rate_mm_h: float | None  # odpovídající intenzita
    coverage: float  # podíl okolí se srážkami (0–1)

    @property
    def has_echo(self) -> bool:
        return self.max_dbz is not None


def sample_area(
    frame: RadarFrame, lat: float, lon: float, radius_km: float = DEFAULT_RADIUS_KM
) -> Sample:
    """Najde nejsilnější echo v okruhu kolem bodu.

    Radar je zrnitý a poloha nemusí být přesná, proto se čte okolí, ne
    jediný pixel.
    """
    cx, cy = latlon_to_px(lat, lon)
    sx, sy = px_per_km(lat)
    rx, ry = max(1, round(radius_km * sx)), max(1, round(radius_km * sy))

    best: int | None = None
    hits = total = 0
    for dy in range(-ry, ry + 1):
        for dx in range(-rx, rx + 1):
            # elipsa v pixelech ≈ kruh v kilometrech
            if (dx / rx) ** 2 + (dy / ry) ** 2 > 1.0:
                continue
            idx = frame.index_at(round(cx) + dx, round(cy) + dy)
            if idx is None:
                continue
            total += 1
            if IDX_MAX_ECHO <= idx <= IDX_MIN_ECHO:
                hits += 1
                if best is None or idx < best:  # nižší index = silnější
                    best = idx
    if not total:
        return Sample(None, None, 0.0)
    if best is None:
        return Sample(None, None, 0.0)
    dbz = dbz_from_index(best)
    return Sample(dbz, round(rain_rate(dbz), 2) if dbz else None, hits / total)


# -------------------------------------------------------------------- stahování


def _stamps(now: datetime, count: int = 5) -> list[str]:
    """Časové značky snímků od nejnovější (po 5 min zpět)."""
    base = now.astimezone(timezone.utc).replace(second=0, microsecond=0)
    base -= timedelta(minutes=base.minute % 5)
    return [(base - timedelta(minutes=5 * i)).strftime("%Y%m%d.%H%M") for i in range(count)]


@dataclass
class RadarData:
    observed_at: datetime | None
    now: Sample | None
    forecast: list[tuple[int, Sample]]  # (minut dopředu, odečet)
    threshold_dbz: float = DEFAULT_DBZ_THRESHOLD
    forecast_threshold_dbz: float = DEFAULT_FORECAST_DBZ_THRESHOLD

    @staticmethod
    def _over(sample: Sample | None, threshold: float) -> bool:
        return bool(
            sample and sample.max_dbz is not None and sample.max_dbz >= threshold
        )

    @property
    def raining(self) -> bool:
        return self._over(self.now, self.threshold_dbz)

    @property
    def starts_in(self) -> int | None:
        """Za kolik minut dorazí déšť; None když se nečeká (0 = prší už teď)."""
        if self.raining:
            return 0
        for minutes, sample in self.forecast:
            if self._over(sample, self.forecast_threshold_dbz):
                return minutes
        return None

    @property
    def rain_expected(self) -> bool:
        return self.starts_in is not None


class RadarClient:
    """Stahuje a vyhodnocuje radarové snímky pro jeden bod."""

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._headers = {"User-Agent": USER_AGENT}

    async def _get(self, url: str) -> bytes | None:
        try:
            async with self._session.get(
                url, headers=self._headers, timeout=_TIMEOUT
            ) as resp:
                if resp.status == 404:
                    return None
                resp.raise_for_status()
                return await resp.read()
        except Exception as err:  # noqa: BLE001
            _LOGGER.debug("radar %s: %s", url, err)
            return None

    async def fetch(
        self,
        lat: float,
        lon: float,
        radius_km: float = DEFAULT_RADIUS_KM,
        with_forecast: bool = True,
        threshold_dbz: float = DEFAULT_DBZ_THRESHOLD,
        forecast_threshold_dbz: float = DEFAULT_FORECAST_DBZ_THRESHOLD,
    ) -> RadarData:
        now = datetime.now(timezone.utc)
        observed: datetime | None = None
        current: Sample | None = None
        stamp_used: str | None = None
        nearby = False

        for stamp in _stamps(now):
            raw = await self._get(_MAXZ.format(stamp=stamp))
            if raw is None:
                continue
            frame = decode_frame(raw)
            current = sample_area(frame, lat, lon, radius_km)
            # Předpověď má smysl stahovat jen když je vůbec co přitáhnout;
            # za bezoblačné situace tím ušetříme ~100 kB na každou aktualizaci.
            nearby = sample_area(frame, lat, lon, SCAN_RADIUS_KM).has_echo
            observed = datetime.strptime(stamp, "%Y%m%d.%H%M").replace(
                tzinfo=timezone.utc
            )
            stamp_used = stamp
            break

        forecast: list[tuple[int, Sample]] = []
        if with_forecast and stamp_used and nearby:
            raw = await self._get(_FCT.format(stamp=stamp_used))
            if raw is None:  # předpověď může vzniknout se zpožděním
                for stamp in _stamps(now)[1:3]:
                    raw = await self._get(_FCT.format(stamp=stamp))
                    if raw is not None:
                        break
            if raw is not None:
                forecast = self._read_forecast(raw, lat, lon, radius_km)

        return RadarData(
            observed_at=observed,
            now=current,
            forecast=forecast,
            threshold_dbz=threshold_dbz,
            forecast_threshold_dbz=forecast_threshold_dbz,
        )

    def _read_forecast(
        self, raw: bytes, lat: float, lon: float, radius_km: float
    ) -> list[tuple[int, Sample]]:
        out: list[tuple[int, Sample]] = []
        try:
            with tarfile.open(fileobj=io.BytesIO(raw)) as tar:
                for member in tar.getmembers():
                    if not member.isfile() or not member.name.endswith(".png"):
                        continue
                    # …fct_z_max.YYYYMMDD.HHMM.<offset>.png
                    parts = member.name.rsplit("/", 1)[-1].split(".")
                    try:
                        minutes = int(parts[-2])
                    except (IndexError, ValueError):
                        continue
                    handle = tar.extractfile(member)
                    if handle is None:
                        continue
                    frame = decode_frame(handle.read())
                    out.append((minutes, sample_area(frame, lat, lon, radius_km)))
        except (tarfile.TarError, ValueError, zlib.error) as err:
            _LOGGER.debug("radarová předpověď: %s", err)
        out.sort(key=lambda it: it[0])
        return out
