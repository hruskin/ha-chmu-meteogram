"""Zpracuje dodaný zdrojový obrázek na brand soubory integrace.

Vstup:  brand_src.png (v rootu repa, čtvercový)
Výstup: custom_components/chmu_meteogram/brand/{icon,icon@2x,logo,logo@2x}.png

Kroky:
- ořez na čtverec (center-crop, kdyby zdroj čtverec nebyl)
- jemné zaoblení rohů squircle maskou (app-icon vzhled; rohy průhledné,
  ale střed hran neprůhledný → trim projde)
- icon@2x 512, icon 256
- logo = ikona + text „ČHMÚ Meteogram"

Závislosti: pillow, numpy. Spuštění:
    python tools/process_icon.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "brand_src.png"
OUT_DIR = ROOT / "custom_components" / "chmu_meteogram" / "brand"


def _heal_artifact(im: Image.Image) -> Image.Image:
    """Přemaže drobný generátorový artefakt v pravém dolním rohu pozadím.

    V oblasti x≥0.885·w, y≥0.70·h nejsou žádné legitimní prvky (křivka jde
    vpravo nahoru, sloupce končí dřív), ověřeno analýzou. Vyplníme ji
    dominantní barvou pozadí.
    """
    a = np.array(im)
    h, w = a.shape[:2]
    bg = np.median(a[10:200, 10:200, :3].reshape(-1, 3), axis=0).astype(np.uint8)
    x0, y0 = int(w * 0.885), int(h * 0.70)
    a[y0:, x0:, :3] = bg
    a[y0:, x0:, 3] = 255
    return Image.fromarray(a)


def _recolor_bg(im: Image.Image, to_bg=(38, 108, 188)) -> Image.Image:
    """Posune tmavě modré pozadí na světlejší (dark_icon pro tmavý režim HA).

    Blenduje podle podobnosti pixelu s původním pozadím → mrak/křivka/sloupce
    zůstanou, hrany se prolnou bez halo.
    """
    a = np.array(im).astype(np.float32)
    h, w = a.shape[:2]
    bg = np.median(a[10:200, 10:200, :3].reshape(-1, 3), axis=0)
    to = np.array(to_bg, np.float32)
    dist = np.sqrt(((a[..., :3] - bg) ** 2).sum(axis=2))
    sim = np.clip(1.0 - dist / 90.0, 0.0, 1.0)[..., None]  # 1 = pozadí
    a[..., :3] += (to - bg) * sim
    a[..., :3] = np.clip(a[..., :3], 0, 255)
    return Image.fromarray(a.astype(np.uint8))


def _center_square(im: Image.Image) -> Image.Image:
    w, h = im.size
    if w == h:
        return im
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def _squircle_mask(size: int, n: float = 4.6) -> Image.Image:
    """Maska superelipsy — jemně zaoblené „app-icon" rohy."""
    lin = (np.arange(size, dtype=np.float32) + 0.5) / size * 2.0 - 1.0
    val = np.abs(lin)[None, :] ** n + np.abs(lin)[:, None] ** n
    return Image.fromarray(((val <= 1.0) * 255).astype(np.uint8))


def _rounded(im: Image.Image) -> Image.Image:
    """Ořízne obrázek squircle maskou (rohy průhledné)."""
    s = im.size[0]
    mask = _squircle_mask(s)
    out = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    out.paste(im, (0, 0), mask)
    return out


def load_icon(dark: bool = False) -> Image.Image:
    im = Image.open(SRC).convert("RGBA")
    im = _center_square(im)
    im = _heal_artifact(im)
    if dark:
        im = _recolor_bg(im)
    return _rounded(im)


def make_logo(icon_full: Image.Image, width: int, height: int) -> Image.Image:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    icon = icon_full.resize((height, height), Image.LANCZOS)
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
    if not SRC.exists():
        print(f"CHYBÍ zdroj: {SRC}")
        return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    icon_full = load_icon()  # čtverec v původním rozlišení, zaoblený
    icon_full.resize((512, 512), Image.LANCZOS).save(OUT_DIR / "icon@2x.png", optimize=True)
    icon_full.resize((256, 256), Image.LANCZOS).save(OUT_DIR / "icon.png", optimize=True)

    # varianta pro tmavý režim (světlejší pozadí)
    dark_full = load_icon(dark=True)
    dark_full.resize((512, 512), Image.LANCZOS).save(OUT_DIR / "dark_icon@2x.png", optimize=True)
    dark_full.resize((256, 256), Image.LANCZOS).save(OUT_DIR / "dark_icon.png", optimize=True)

    logo = make_logo(icon_full, 880, 192)
    logo.save(OUT_DIR / "logo@2x.png", optimize=True)
    logo.resize((440, 96), Image.LANCZOS).save(OUT_DIR / "logo.png", optimize=True)

    print(f"Vygenerováno do {OUT_DIR}")
    for f in sorted(OUT_DIR.glob("*.png")):
        print(f"  {f.name} ({f.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
