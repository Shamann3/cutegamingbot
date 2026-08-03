"""Generate winter-tinted forest backgrounds from summer forest assets."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parents[1] / "public" / "assets"

SOURCES = [
    "forest-bg.png",
    "forest-bg-2x.png",
    "forest-bg-3x.png",
    "forest-bg-4k.png",
    "forest-bg.webp",
    "forest-bg-2x.webp",
    "forest-bg-3x.webp",
    "forest-bg-4k.webp",
]


def winterize(img: Image.Image) -> Image.Image:
    rgba = img.convert("RGBA")
    arr = np.array(rgba, dtype=np.float32)
    r, g, b, a = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2], arr[:, :, 3]

    # Cool cast: pull greens toward blue-silver, keep structure
    nr = r * 0.62 + g * 0.12 + 48
    ng = g * 0.55 + b * 0.22 + 52
    nb = b * 0.78 + g * 0.12 + 78

    # Soft vignette brightness toward cooler midtones
    h, w = r.shape
    yy, xx = np.mgrid[0:h, 0:w]
    cy, cx = h * 0.45, w * 0.5
    dist = np.sqrt(((yy - cy) / h) ** 2 + ((xx - cx) / w) ** 2)
    shade = np.clip(1.05 - dist * 0.35, 0.72, 1.08)
    nr *= shade
    ng *= shade
    nb *= shade * 1.02

    out = np.stack(
        [
            np.clip(nr, 0, 255),
            np.clip(ng, 0, 255),
            np.clip(nb, 0, 255),
            a,
        ],
        axis=2,
    ).astype(np.uint8)

    result = Image.fromarray(out, "RGBA")
    result = ImageEnhance.Color(result).enhance(0.55)
    result = ImageEnhance.Contrast(result).enhance(1.08)
    result = ImageEnhance.Brightness(result).enhance(0.92)
    # Soft frost bloom
    frost = result.filter(ImageFilter.GaussianBlur(radius=1.1))
    return Image.blend(result, frost, 0.18)


def main():
    done = 0
    for name in SOURCES:
        src = ROOT / name
        if not src.exists():
            print("skip missing", name)
            continue
        dst_name = name.replace("forest-bg", "forest-bg-winter", 1)
        dst = ROOT / dst_name
        img = Image.open(src)
        winter = winterize(img)
        if dst.suffix.lower() == ".webp":
            winter.convert("RGB").save(dst, "WEBP", quality=82, method=4)
        else:
            winter.save(dst, optimize=True)
        print("wrote", dst.name, winter.size)
        done += 1
    print("done", done)


if __name__ == "__main__":
    main()
