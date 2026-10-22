"""Regenerate Xwav raster icons from the canonical SVG (Pillow + CairoSVG)."""

from io import BytesIO
from pathlib import Path

import cairosvg
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "web/platform-assets/logos/xwav-icon.svg"


def main() -> None:
    image = Image.open(
        BytesIO(cairosvg.svg2png(url=str(SOURCE), output_width=1024, output_height=1024))
    ).convert("RGBA")
    for relative, size in [
        ("web/electron/icons/icon.png", 1024),
        ("web/public/apple-touch-icon.png", 180),
        ("web/public/icon-192.png", 192),
        ("web/public/icon-512.png", 512),
        ("web/src/assets/xwav-icon.png", 512),
        ("docs/images/xwav-logo.png", 1024),
    ]:
        image.resize((size, size), Image.Resampling.LANCZOS).save(ROOT / relative)
    image.save(
        ROOT / "web/electron/icons/icon.ico",
        sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
    )
    image.save(ROOT / "web/electron/icons/icon.icns", format="ICNS")
    print("Generated Xwav PNG, ICO and ICNS assets from", SOURCE.relative_to(ROOT))


if __name__ == "__main__":
    main()
