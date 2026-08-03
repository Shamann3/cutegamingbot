"""Generate spring/autumn tinted forest backgrounds from summer assets."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1] / "public" / "assets"

SOURCES = [
    "forest-bg.png",
    "forest-bg-2x.png",
    "forest-bg-3x.png",
    "forest-bg.webp",
    "forest-bg-2x.webp",
    "forest-bg-3x.webp",
]


def tint(img: Image.Image, mode: str) -> Image.Image:
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    if mode == "spring":
        # Fresh greens + soft pink bloom
        nr = r * 0.78 + 35
        ng = g * 0.95 + 28
        nb = b * 0.72 + 22
        color, contrast, bright = 1.15, 1.04, 1.05
    else:
        # Autumn: warm amber / copper
        nr = r * 0.95 + 40
        ng = g * 0.72 + 18
        nb = b * 0.45 + 8
        color, contrast, bright = 1.05, 1.1, 0.96

    out = np.stack(
        [np.clip(nr, 0, 255), np.clip(ng, 0, 255), np.clip(nb, 0, 255), a],
        axis=2,
    ).astype(np.uint8)
    result = Image.fromarray(out, "RGBA")
    result = ImageEnhance.Color(result).enhance(color)
    result = ImageEnhance.Contrast(result).enhance(contrast)
    result = ImageEnhance.Brightness(result).enhance(bright)
    soft = result.filter(ImageFilter.GaussianBlur(radius=0.8))
    return Image.blend(result, soft, 0.12)


def main():
    for mode in ("spring", "autumn"):
        for name in SOURCES:
            src = ROOT / name
            if not src.exists():
                print("skip", name)
                continue
            dst = ROOT / name.replace("forest-bg", f"forest-bg-{mode}", 1)
            img = Image.open(src)
            out = tint(img, mode)
            if dst.suffix.lower() == ".webp":
                out.convert("RGB").save(dst, "WEBP", quality=82, method=4)
            else:
                out.save(dst, optimize=True)
            print("wrote", dst.name)


if __name__ == "__main__":
    main()
