# Xwav app icons

`icon.svg`, `icon.png`, `icon.ico`, and `icon.icns` contain the Xwav flowing wave mark. The master SVG is `../../platform-assets/logos/xwav-icon.svg`.

From the repository root, run `python3 scripts/generate_xwav_assets.py` with Pillow and CairoSVG installed to regenerate raster files.

Apple Icon Composer source lives in `../../platform-assets/AppIcon.icon`. The upstream compiled `Assets.car` was removed because it contains the old brand. Electron uses the generated Xwav ICNS on macOS; iOS compiles the shared Icon Composer source with Xcode. See `../../../docs/BRANDING.md` for palette and compatibility notes.
