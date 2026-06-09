# Brand assets

Tyto PNG soubory patří do [home-assistant/brands](https://github.com/home-assistant/brands)
repa, aby je Home Assistant a HACS automaticky stahovali z `brands.home-assistant.io`.

## Jak submitnout

1. Fork https://github.com/home-assistant/brands
2. Do svého forku zkopíruj obsah `brands/chmu_meteogram/` do:

       custom_integrations/chmu_meteogram/
       ├── icon.png         (256×256)
       ├── icon@2x.png      (512×512)
       ├── logo.png         (440×96)
       └── logo@2x.png      (880×192)

3. Commit + push:

       git add custom_integrations/chmu_meteogram
       git commit -m "Add chmu_meteogram (custom integration)"
       git push

4. Open PR proti `home-assistant/brands` → `master`.
   Title: `Add chmu_meteogram (custom integration)`.

Po mergi se ikona zobrazí v HA UI i v HACS dlaždici (dnes je tam „icon not available").

## Regenerace

```powershell
python tools/make_icon.py
```

Skript je idempotentní; všechna 4 PNG vygeneruje znova.
