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


def _data(now_dbz=None, forecast=(), threshold=12):
    def mk(d):
        return radar.Sample(d, radar.rain_rate(d) if d else None, 1.0 if d else 0.0)

    return radar.RadarData(
        observed_at=None,
        now=mk(now_dbz),
        forecast=[(m, mk(d)) for m, d in forecast],
        threshold_dbz=threshold,
    )


def test_raining_respects_threshold():
    assert _data(now_dbz=20).raining
    assert not _data(now_dbz=8).raining      # pod prahem = virga/šum
    assert not _data(now_dbz=None).raining


def test_starts_in_picks_first_over_threshold():
    d = _data(now_dbz=None, forecast=[(10, 4), (20, 8), (30, 30), (40, 40)])
    assert d.starts_in == 30
    assert d.rain_expected


def test_starts_in_zero_when_raining():
    assert _data(now_dbz=30, forecast=[(10, 30)]).starts_in == 0


def test_no_rain_expected_when_all_weak():
    d = _data(now_dbz=None, forecast=[(10, 4), (20, 8)])
    assert d.starts_in is None
    assert not d.rain_expected


def test_stamps_are_five_minute_steps():
    from datetime import datetime, timezone

    stamps = radar._stamps(datetime(2026, 7, 27, 13, 47, tzinfo=timezone.utc), count=3)
    assert stamps == ["20260727.1345", "20260727.1340", "20260727.1335"]
