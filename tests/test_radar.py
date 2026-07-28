"""Testy radaru — škála, geo mapování, vyhodnocení."""
import math

import pytest

from chmu_meteogram import radar


def test_dbz_scale_bounds():
    assert radar.dbz_from_index(195) == 4.0    # nejslabší echo
    assert radar.dbz_from_index(182) == 56.0   # nejsilnější
    assert radar.dbz_from_index(0) is None     # průhledné pozadí
    assert radar.dbz_from_index(145) is None   # rámeček snímku
    assert radar.dbz_from_index(242) is None   # šedý roh


def test_dbz_monotonic():
    """Nižší paletový index musí znamenat silnější echo."""
    vals = [radar.dbz_from_index(i) for i in range(182, 196)]
    assert vals == sorted(vals, reverse=True)


@pytest.mark.parametrize(
    "dbz,lo,hi",
    [(12, 0.1, 0.4), (28, 1.5, 3.0), (44, 15.0, 30.0), (52, 50.0, 90.0)],
)
def test_rain_rate_ranges(dbz, lo, hi):
    """Marshall-Palmer musí dávat meteorologicky rozumné intenzity."""
    assert lo < radar.rain_rate(dbz) < hi


def _px_to_latlon(x, y):
    lon = radar.LON_W + x / radar.CROP_W * (radar.LON_E - radar.LON_W)
    m = radar._M_N - y / radar.CROP_H * (radar._M_N - radar._M_S)
    return math.degrees(2 * math.atan(math.exp(m)) - math.pi / 2), lon


@pytest.mark.parametrize(
    "lat,lon",
    [(50.088, 14.426), (49.195, 16.607), (49.821, 18.262), (48.759, 16.882)],
)
def test_latlon_px_roundtrip(lat, lon):
    x, y = radar.latlon_to_px(lat, lon)
    back_lat, back_lon = _px_to_latlon(x, y)
    assert abs(back_lat - lat) < 1e-6
    assert abs(back_lon - lon) < 1e-6


def test_czech_places_inside_crop():
    for lat, lon in [(50.088, 14.426), (49.195, 16.607), (50.73, 15.74)]:
        x, y = radar.latlon_to_px(lat, lon)
        assert 0 <= x < radar.CROP_W
        assert 0 <= y < radar.CROP_H


def test_resolution_about_800m():
    """Kontrola měřítka — CZRAD kompozit má ~1 km pixel."""
    sx, sy = radar.px_per_km(50.0)
    assert 1.0 < sx < 1.6
    assert 1.0 < sy < 1.6


class _FakeFrame:
    """Snímek s jedním echem uprostřed."""

    def __init__(self, idx, hit_x, hit_y):
        self.idx, self.hx, self.hy = idx, hit_x, hit_y

    def index_at(self, x, y):
        if not (0 <= x < radar.CROP_W and 0 <= y < radar.CROP_H):
            return None
        return self.idx if (x, y) == (self.hx, self.hy) else 0


def test_sample_area_finds_echo():
    lat, lon = 50.0, 15.0
    cx, cy = radar.latlon_to_px(lat, lon)
    frame = _FakeFrame(190, round(cx), round(cy))
    s = radar.sample_area(frame, lat, lon, radius_km=3)
    assert s.has_echo
    assert s.max_dbz == 24.0
    assert 0 < s.coverage < 0.2  # jediný pixel z okolí


def test_sample_area_ignores_annotation_indices():
    lat, lon = 50.0, 15.0
    cx, cy = radar.latlon_to_px(lat, lon)
    for junk in (145, 242):
        s = radar.sample_area(_FakeFrame(junk, round(cx), round(cy)), lat, lon, 3)
        assert not s.has_echo, f"index {junk} nesmí být brán jako srážky"


def _data(now_dbz=None, forecast=(), threshold=None, fc_threshold=None):
    def mk(d):
        return radar.Sample(d, radar.rain_rate(d) if d else None, 1.0 if d else 0.0)

    return radar.RadarData(
        observed_at=None,
        now=mk(now_dbz),
        forecast=[(m, mk(d)) for m, d in forecast],
        threshold_dbz=threshold if threshold is not None else radar.DEFAULT_DBZ_THRESHOLD,
        forecast_threshold_dbz=(
            fc_threshold if fc_threshold is not None else radar.DEFAULT_FORECAST_DBZ_THRESHOLD
        ),
    )


def test_default_thresholds():
    """Předpověď je přísnější — slabá echa se cestou rozpustí."""
    assert radar.DEFAULT_DBZ_THRESHOLD == 12
    assert radar.DEFAULT_FORECAST_DBZ_THRESHOLD == 18


def test_raining_respects_threshold():
    assert _data(now_dbz=20).raining
    assert _data(now_dbz=12).raining         # mrholení, ale reálně padá
    assert not _data(now_dbz=8).raining      # pod prahem = virga/šum
    assert not _data(now_dbz=None).raining


def test_forecast_uses_stricter_threshold():
    """Echo 12–17 dBZ stačí na „prší", ale ne na hlášení příchozího deště."""
    d = _data(now_dbz=None, forecast=[(10, 14), (20, 16)])
    assert d.starts_in is None
    assert not d.rain_expected
    assert _data(now_dbz=14).raining


def test_starts_in_picks_first_over_threshold():
    d = _data(now_dbz=None, forecast=[(10, 4), (20, 16), (30, 30), (40, 40)])
    assert d.starts_in == 30
    assert d.rain_expected


def test_starts_in_zero_when_raining():
    assert _data(now_dbz=30, forecast=[(10, 30)]).starts_in == 0


def test_no_rain_expected_when_all_weak():
    d = _data(now_dbz=None, forecast=[(10, 4), (20, 8)])
    assert d.starts_in is None
    assert not d.rain_expected


def test_ends_in_first_dry_frame():
    d = _data(now_dbz=30, forecast=[(10, 30), (20, 20), (30, 4), (40, 0)])
    assert d.ends_in == 30


def test_ends_in_ignores_gap_between_showers():
    """Krátká pauza mezi přeháňkami není konec deště."""
    d = _data(now_dbz=30, forecast=[(10, 4), (20, 30), (30, 4), (40, 0)])
    assert d.ends_in == 30


def test_ends_in_none_when_rain_persists():
    d = _data(now_dbz=30, forecast=[(10, 30), (20, 30), (30, 30)])
    assert d.ends_in is None


def test_ends_in_none_when_not_raining():
    assert _data(now_dbz=None, forecast=[(10, 0)]).ends_in is None


def test_trend_rising_falling_steady():
    assert _data(now_dbz=12, forecast=[(10, 30), (20, 30)]).trend == "rising"
    assert _data(now_dbz=40, forecast=[(10, 20), (20, 12)]).trend == "falling"
    assert _data(now_dbz=20, forecast=[(10, 20), (20, 20)]).trend == "steady"


def test_trend_none_when_dry():
    assert _data(now_dbz=None, forecast=[(10, 0), (20, 0)]).trend is None
    assert _data(now_dbz=None, forecast=[]).trend is None


def test_trend_looks_only_half_hour_ahead():
    """Déšť za hodinu ještě neznamená, že intenzita roste teď."""
    d = _data(now_dbz=20, forecast=[(10, 20), (20, 20), (30, 20), (60, 50)])
    assert d.trend == "steady"


def test_encode_decode_indexed_png_roundtrip():
    palette = bytearray(768)
    palette[3:6] = b"\xff\x00\xff"
    rows = [bytearray([0, 1, 1, 0]), bytearray([1, 0, 0, 1])]
    png = radar.encode_indexed_png([bytearray(r) for r in rows], bytes(palette), None)
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    frame = radar.decode_frame(png)
    assert [bytes(r) for r in frame.rows] == [bytes(r) for r in rows]
    assert frame.palette[3:6] == b"\xff\x00\xff"


def test_render_preview_marks_position_and_keeps_echo():
    lat, lon = 50.0, 15.0
    cx, cy = radar.latlon_to_px(lat, lon)
    palette = bytearray(768)
    palette[190 * 3 : 190 * 3 + 3] = b"\x00\xbc\x00"
    rows = [bytearray(680) for _ in range(460)]
    # echo přímo nad lokalitou + rámeček, který se do náhledu nesmí dostat
    rows[radar.CROP_Y0 + round(cy)][radar.CROP_X0 + round(cx)] = 190
    for x in range(680):
        rows[radar.CROP_Y0 + round(cy) + 20][x] = 145  # anotace snímku
    frame = radar.RadarFrame(
        rows=[bytes(r) for r in rows], channels=1, palette=bytes(palette)
    )
    png = radar.render_preview(frame, lat, lon, width=60, height=40)
    assert png is not None
    out = radar.decode_frame(png)
    used = {v for row in out.rows for v in row}
    assert 190 in used, "echo musí zůstat"
    assert 145 not in used, "rámeček snímku se nesmí vykreslit"
    assert len(used) >= 4, "chybí podklad, kružnice nebo značka"


def _png_with_ihdr(width, height, bit_depth=8, color_type=3):
    """Minimální PNG jen s IHDR — pro test validace hlavičky."""
    import struct
    import zlib

    ihdr = struct.pack(">IIBBBBB", width, height, bit_depth, color_type, 0, 0, 0)
    chunk = (
        struct.pack(">I", len(ihdr))
        + b"IHDR"
        + ihdr
        + struct.pack(">I", zlib.crc32(b"IHDR" + ihdr) & 0xFFFFFFFF)
    )
    return b"\x89PNG\r\n\x1a\n" + chunk


@pytest.mark.parametrize("w,h", [(100000, 100000), (0, 10), (10, 0), (2**31, 8)])
def test_rejects_absurd_png_dimensions(w, h):
    """Podvržený IHDR nesmí vést k alokaci obřího řádku."""
    with pytest.raises(ValueError):
        radar.decode_frame(_png_with_ihdr(w, h))


def test_rejects_unsupported_bit_depth():
    with pytest.raises(ValueError):
        radar.decode_frame(_png_with_ihdr(100, 100, bit_depth=16))


def test_rejects_non_png_data():
    with pytest.raises(ValueError):
        radar.decode_frame(b"not a PNG at all" * 10)


def test_tar_limits_are_sane():
    """Limity musí být nad reálnými daty (6 snímků po ~25 kB)."""
    assert radar.MAX_TAR_MEMBERS >= 8
    assert radar.MAX_TAR_MEMBER_BYTES >= 512 * 1024
    assert radar.MAX_IMAGE_DIM >= 1024


def test_stamps_are_five_minute_steps():
    from datetime import datetime, timezone

    stamps = radar._stamps(datetime(2026, 7, 27, 13, 47, tzinfo=timezone.utc), count=3)
    assert stamps == ["20260727.1345", "20260727.1340", "20260727.1335"]
