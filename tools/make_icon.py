"""Vygeneruje ikonu integrace pro Home Assistant brands repository.

Výstup:
    brands/chmu_meteogram/icon.png       (256x256)
    brands/chmu_meteogram/icon@2x.png    (512x512)
    brands/chmu_meteogram/logo.png       (440x96 — text + symbol)
    brands/chmu_meteogram/logo@2x.png    (880x192)

Spuštění:
    python tools/make_icon.py

Design: zaoblený modrý čtverec, uvnitř stylizovaný meteogram — křivka teploty
(oranžová), pod ní sloupce srážek (světle modrá), nahoře malé slunce/mrak.
"""
from __future__ import annotations

from math import cos, pi, sin
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# HA 2026.3+ čte lokální brand obrázky z custom_components/<domain>/brand/.
# Brands repo (home-assistant/brands) už custom integrace nepřijímá.
OUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "chmu_meteogram"
    / "brand"
)

# Paleta — neutrální, čitelná, ladí s ČHMÚ ale není to jejich logo
NAVY = (16, 50, 100, 255)        # rámeček / pozadí
SKY = (220, 235, 250, 255)       # vnitřek
SUN = (255, 195, 70, 255)        # slunce
CLOUD = (255, 255, 255, 240)
TEMP = (220, 80, 60, 255)        # teplotní křivka
TEMP_GLOW = (220, 80, 60, 60)
RAIN = (60, 140, 220, 220)       # sloupce srážek


def _smooth_curve(points: list[tuple[float, float]], samples: int = 80) -> list[tuple[float, float]]:
    """Catmull-Rom interpolace, ať teplotní křivka vypadá organicky."""
    if len(points) < 4:
        return points
    out: list[tuple[float, float]] = []
    pts = [points[0], *points, points[-1]]  # zrcadlení krajů
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * (
                (2 * p1[0])
                + (-p0[0] + p2[0]) * t
                + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
            )
            y = 0.5 * (
                (2 * p1[1])
                + (-p0[1] + p2[1]) * t
                + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
            )
            out.append((x, y))
    out.append(points[-1])
    return out


def _draw_cloud(draw: ImageDraw.ImageDraw, cx: float, cy: float, scale: float) -> None:
    blobs = [
        (cx - 1.4 * scale, cy + 0.1 * scale, 1.4 * scale),
        (cx - 0.4 * scale, cy - 0.6 * scale, 1.6 * scale),
        (cx + 0.8 * scale, cy - 0.3 * scale, 1.5 * scale),
        (cx + 1.6 * scale, cy + 0.3 * scale, 1.2 * scale),
    ]
    for x, y, r in blobs:
        draw.ellipse((x - r, y - r, x + r, y + r), fill=CLOUD)


def make_icon(size: int) -> Image.Image:
    """Vygeneruje čtvercovou ikonu o straně `size`."""
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # rámeček (zaoblený čtverec) + vnitřek
    # POZOR: home-assistant/brands vyžaduje „trimmed" obrázek (bez plně
    # průhledných okrajových řad). Kreslíme proto od hrany k hraně (pad=0);
    # zaoblené rohy vytvoří průhledné rohy, ale střed každé hrany je
    # neprůhledný, takže getbbox() = celý čtverec a trim projde. Vypadá to
    # jako app-icon.
    radius = s * 0.20
    draw.rounded_rectangle(
        (0, 0, s - 1, s - 1),
        radius=radius,
        fill=SKY,
        outline=NAVY,
        width=max(2, int(s * 0.025)),
    )

    # slunce vlevo nahoře
    sr = s * 0.09
    sx, sy = s * 0.28, s * 0.28
    # paprsky
    for i in range(8):
        a = i * pi / 4
        x1 = sx + cos(a) * sr * 1.4
        y1 = sy + sin(a) * sr * 1.4
        x2 = sx + cos(a) * sr * 1.85
        y2 = sy + sin(a) * sr * 1.85
        draw.line([(x1, y1), (x2, y2)], fill=SUN, width=max(2, int(s * 0.018)))
    draw.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=SUN)

    # mrak vpravo nahoře
    _draw_cloud(draw, s * 0.66, s * 0.32, s * 0.07)

    # křivka teploty (oranžová) — středová část ikony
    base_y = s * 0.58
    amp = s * 0.10
    ctrl = [
        (s * 0.18, base_y + amp * 0.6),
        (s * 0.32, base_y - amp * 0.4),
        (s * 0.47, base_y + amp * 0.2),
        (s * 0.62, base_y - amp * 0.9),
        (s * 0.78, base_y - amp * 0.2),
        (s * 0.86, base_y - amp * 0.6),
    ]
    curve = _smooth_curve(ctrl)
    # jemný glow pod křivkou
    glow_layer = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)
    glow_draw.line(curve, fill=TEMP_GLOW, width=max(8, int(s * 0.05)))
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(radius=s * 0.012))
    img.alpha_composite(glow_layer)
    draw = ImageDraw.Draw(img)
    draw.line(curve, fill=TEMP, width=max(3, int(s * 0.025)))

    # sloupce srážek u spodního okraje
    bar_top = s * 0.80
    bar_bottom = s * 0.88
    bar_w = s * 0.045
    gap = s * 0.022
    heights = [0.30, 0.55, 0.85, 1.00, 0.75, 0.45, 0.25]  # relativní
    total_w = len(heights) * bar_w + (len(heights) - 1) * gap
    start_x = (s - total_w) / 2
    for i, h in enumerate(heights):
        x0 = start_x + i * (bar_w + gap)
        y0 = bar_bottom - (bar_bottom - bar_top) * h
        draw.rounded_rectangle(
            (x0, y0, x0 + bar_w, bar_bottom),
            radius=bar_w * 0.35,
            fill=RAIN,
        )

    return img


def make_logo(width: int, height: int) -> Image.Image:
    """Logo: ikona vlevo + textový label."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icon = make_icon(height).resize((height, height), Image.LANCZOS)
    img.paste(icon, (0, 0), icon)

    draw = ImageDraw.Draw(img)
    text_x = int(height * 1.15)
    try:
        font_big = ImageFont.truetype("seguibl.ttf", int(height * 0.32))
        font_sm = ImageFont.truetype("seguisb.ttf", int(height * 0.18))
    except (OSError, IOError):
        try:
            font_big = ImageFont.truetype("arialbd.ttf", int(height * 0.32))
            font_sm = ImageFont.truetype("arial.ttf", int(height * 0.18))
        except (OSError, IOError):
            font_big = ImageFont.load_default()
            font_sm = ImageFont.load_default()

    draw.text((text_x, int(height * 0.18)), "ČHMÚ", fill=NAVY, font=font_big)
    draw.text(
        (text_x, int(height * 0.58)),
        "Meteogram",
        fill=(70, 110, 160, 255),
        font=font_sm,
    )
    return img


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # ikony — návrh při 512 px, downscale pro 256
    icon_big = make_icon(512)
    icon_big.save(OUT_DIR / "icon@2x.png", optimize=True)
    icon_big.resize((256, 256), Image.LANCZOS).save(OUT_DIR / "icon.png", optimize=True)

    # loga — 440x96, 880x192
    logo_big = make_logo(880, 192)
    logo_big.save(OUT_DIR / "logo@2x.png", optimize=True)
    logo_big.resize((440, 96), Image.LANCZOS).save(OUT_DIR / "logo.png", optimize=True)

    print(f"Vygenerováno do {OUT_DIR}")
    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"  {f.name} ({f.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
