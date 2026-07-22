"""Vygeneruje brand ikonu integrace (moderní design).

Výstup do custom_components/chmu_meteogram/brand/:
    icon.png      (256x256)
    icon@2x.png   (512x512)
    logo.png      (440x96 — symbol + text)
    logo@2x.png   (880x192)

Design: squircle (jako app-icon) s diagonálním modrým gradientem, teplé slunce
s měkkým zářením, jemný mrak, výrazná oranžová teplotní křivka s vrženým stínem
a zaoblené sloupce srážek. Vše se kreslí 4× supersamplované a zmenší se
(LANCZOS) → hladké hrany.

Závislosti: pillow, numpy. Spuštění:
    python tools/make_icon.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

# HA 2026.3+ čte lokální brand obrázky z custom_components/<domain>/brand/.
OUT_DIR = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "chmu_meteogram"
    / "brand"
)

SS = 4  # supersampling

# ---- paleta (RGBA) ----
BG_TOP = (86, 170, 240, 255)      # světlá obloha (vlevo nahoře)
BG_BOTTOM = (26, 96, 178, 255)    # hlubší modrá (vpravo dole)
SUN_CORE = (255, 214, 92, 255)
SUN_EDGE = (255, 170, 60, 255)
SUN_GLOW = (255, 200, 90, 130)
CLOUD = (255, 255, 255, 255)
CLOUD_SHADOW = (12, 60, 120, 90)
CURVE = (255, 118, 74, 255)       # teplá korálová — pop na modré
CURVE_SHADOW = (10, 40, 90, 110)
BAR = (255, 255, 255, 150)        # poloprůhledné bílé sloupce


def _gradient(size: int, c1, c2) -> Image.Image:
    """Diagonální gradient (levý horní c1 → pravý dolní c2)."""
    ramp = np.linspace(0.0, 1.0, size, dtype=np.float32)
    t = (ramp[None, :] + ramp[:, None]) * 0.5
    arr = np.zeros((size, size, 4), np.uint8)
    for i in range(4):
        arr[..., i] = (c1[i] + (c2[i] - c1[i]) * t).astype(np.uint8)
    return Image.fromarray(arr)  # (H,W,4) → RGBA


def _squircle_mask(size: int, n: float = 4.5) -> Image.Image:
    """Maska superelipsy (squircle) — |x|^n + |y|^n <= 1."""
    lin = (np.arange(size, dtype=np.float32) + 0.5) / size * 2.0 - 1.0
    val = np.abs(lin)[None, :] ** n + np.abs(lin)[:, None] ** n
    return Image.fromarray(((val <= 1.0) * 255).astype(np.uint8))  # 2D → L


def _smooth_curve(points, samples: int = 90):
    """Catmull-Rom interpolace."""
    if len(points) < 4:
        return points
    out = []
    pts = [points[0], *points, points[-1]]
    for i in range(1, len(pts) - 2):
        p0, p1, p2, p3 = pts[i - 1], pts[i], pts[i + 1], pts[i + 2]
        for j in range(samples):
            t = j / samples
            t2, t3 = t * t, t * t * t
            x = 0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t
                       + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
                       + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3)
            y = 0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t
                       + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
                       + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3)
            out.append((x, y))
    out.append(points[-1])
    return out


def _draw_cloud(draw: ImageDraw.ImageDraw, cx, cy, scale, fill):
    for dx, dy, r in [(-1.5, 0.15, 1.35), (-0.4, -0.7, 1.7),
                      (0.85, -0.35, 1.55), (1.7, 0.2, 1.25), (0.2, 0.5, 1.7)]:
        x, y, rr = cx + dx * scale, cy + dy * scale, r * scale
        draw.ellipse((x - rr, y - rr, x + rr, y + rr), fill=fill)


def _layer(size: int) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def make_icon(out_size: int) -> Image.Image:
    """Moderní squircle ikona o straně out_size (kreslí se SS× větší)."""
    s = out_size * SS

    # --- podklad: gradient přes squircle masku ---
    base = _gradient(s, BG_TOP, BG_BOTTOM)
    mask = _squircle_mask(s)
    icon = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    icon.paste(base, (0, 0), mask)

    # jemné vnitřní zesvětlení nahoře (lesk)
    sheen, sd = _layer(s)
    sd.ellipse((-s * 0.3, -s * 0.55, s * 1.3, s * 0.45), fill=(255, 255, 255, 28))
    sheen = sheen.filter(ImageFilter.GaussianBlur(s * 0.02))
    icon.alpha_composite(Image.composite(sheen, Image.new("RGBA", (s, s), (0, 0, 0, 0)), mask))

    # --- slunce se zářením (vlevo nahoře) ---
    sx, sy, sr = s * 0.30, s * 0.30, s * 0.115
    glow, gd = _layer(s)
    gd.ellipse((sx - sr * 2.1, sy - sr * 2.1, sx + sr * 2.1, sy + sr * 2.1), fill=SUN_GLOW)
    glow = glow.filter(ImageFilter.GaussianBlur(s * 0.03))
    icon.alpha_composite(glow)
    # tělo slunce s jemným radiálním přechodem (dvě kola)
    sun, sund = _layer(s)
    sund.ellipse((sx - sr, sy - sr, sx + sr, sy + sr), fill=SUN_EDGE)
    sund.ellipse((sx - sr * 0.82, sy - sr * 0.82, sx + sr * 0.82, sy + sr * 0.82), fill=SUN_CORE)
    icon.alpha_composite(sun)

    # --- mrak (vpravo nahoře) s měkkým stínem ---
    cx, cy, cs = s * 0.66, s * 0.34, s * 0.072
    shadow, shd = _layer(s)
    _draw_cloud(shd, cx, cy + s * 0.02, cs, CLOUD_SHADOW)
    shadow = shadow.filter(ImageFilter.GaussianBlur(s * 0.02))
    icon.alpha_composite(shadow)
    cloud, cld = _layer(s)
    _draw_cloud(cld, cx, cy, cs, CLOUD)
    icon.alpha_composite(cloud)

    # --- teplotní křivka (hero) s vrženým stínem ---
    base_y = s * 0.585
    amp = s * 0.11
    ctrl = [
        (s * 0.13, base_y + amp * 0.65),
        (s * 0.30, base_y - amp * 0.35),
        (s * 0.45, base_y + amp * 0.25),
        (s * 0.60, base_y - amp * 0.95),
        (s * 0.76, base_y - amp * 0.15),
        (s * 0.89, base_y - amp * 0.7),
    ]
    curve = _smooth_curve(ctrl)
    lw = int(s * 0.032)

    shadow, shd = _layer(s)
    shd.line([(x, y + s * 0.012) for x, y in curve], fill=CURVE_SHADOW, width=lw, joint="curve")
    shadow = shadow.filter(ImageFilter.GaussianBlur(s * 0.012))
    icon.alpha_composite(shadow)

    line, ld = _layer(s)
    ld.line(curve, fill=CURVE, width=lw, joint="curve")
    # zaoblené konce
    for (x, y) in (curve[0], curve[-1]):
        ld.ellipse((x - lw / 2, y - lw / 2, x + lw / 2, y + lw / 2), fill=CURVE)
    icon.alpha_composite(line)

    # --- sloupce srážek (dole) ---
    bars, bd = _layer(s)
    heights = [0.35, 0.6, 0.9, 1.0, 0.72, 0.45, 0.28]
    bar_w = s * 0.05
    gap = s * 0.028
    top_min, bottom = s * 0.72, s * 0.86
    total = len(heights) * bar_w + (len(heights) - 1) * gap
    x0 = (s - total) / 2
    for i, h in enumerate(heights):
        x = x0 + i * (bar_w + gap)
        y = bottom - (bottom - top_min) * h
        bd.rounded_rectangle((x, y, x + bar_w, bottom), radius=bar_w * 0.5, fill=BAR)
    icon.alpha_composite(Image.composite(bars, Image.new("RGBA", (s, s), (0, 0, 0, 0)), mask))

    return icon.resize((out_size, out_size), Image.LANCZOS)


def make_logo(width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icon = make_icon(height)
    img.paste(icon, (0, 0), icon)

    draw = ImageDraw.Draw(img)
    text_x = int(height * 1.18)
    try:
        font_big = ImageFont.truetype("seguibl.ttf", int(height * 0.34))
        font_sm = ImageFont.truetype("seguisb.ttf", int(height * 0.185))
    except OSError:
        try:
            font_big = ImageFont.truetype("arialbd.ttf", int(height * 0.34))
            font_sm = ImageFont.truetype("arial.ttf", int(height * 0.185))
        except OSError:
            font_big = ImageFont.load_default()
            font_sm = ImageFont.load_default()

    draw.text((text_x, int(height * 0.17)), "ČHMÚ", fill=(20, 60, 120, 255), font=font_big)
    draw.text((text_x, int(height * 0.60)), "Meteogram", fill=(90, 130, 180, 255), font=font_sm)
    return img


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    icon = make_icon(512)
    icon.save(OUT_DIR / "icon@2x.png", optimize=True)
    icon.resize((256, 256), Image.LANCZOS).save(OUT_DIR / "icon.png", optimize=True)

    logo = make_logo(880, 192)
    logo.save(OUT_DIR / "logo@2x.png", optimize=True)
    logo.resize((440, 96), Image.LANCZOS).save(OUT_DIR / "logo.png", optimize=True)

    print(f"Vygenerováno do {OUT_DIR}")
    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"  {f.name} ({f.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
