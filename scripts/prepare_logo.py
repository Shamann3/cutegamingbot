"""
Подготовка логотипа фермы из public/assets/logo-drop/.

Положи файл logo.png (или logo.jpg / logo.webp) в logo-drop/, затем:

    python scripts/prepare_logo.py

Результат:
  public/assets/cute-crest.png
  public/assets/cute-crest-2x.png
  public/assets/cute-crest-3x.png
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

ROOT = Path(__file__).resolve().parents[1]
DROP = ROOT / "public" / "assets" / "logo-drop"
OUT = ROOT / "public" / "assets"

CANDIDATES = (
    "logo.png",
    "logo.jpg",
    "logo.jpeg",
    "logo.webp",
    "crest.png",
    "cute-crest.png",
)

# Базовый размер «1x» в UI (ретина собирается как 2x/3x)
BASE_MAX = 256


def find_source() -> Path:
    for name in CANDIDATES:
        path = DROP / name
        if path.exists():
            return path
    # fallback: уже лежащий crest
    legacy = OUT / "cute-crest.png"
    if legacy.exists():
        return legacy
    raise SystemExit(
        f"Не найден логотип. Положи файл в {DROP} как logo.png "
        f"(или logo.jpg / logo.webp) и запусти снова."
    )


def trim_transparent(img: Image.Image, pad: int = 8) -> Image.Image:
    rgba = img.convert("RGBA")
    bbox = rgba.getbbox()
    if not bbox:
        return rgba
    trimmed = rgba.crop(bbox)
    if pad <= 0:
        return trimmed
    return ImageOps.expand(trimmed, border=pad, fill=(0, 0, 0, 0))


def fit_square(img: Image.Image, size: int) -> Image.Image:
    rgba = img.convert("RGBA")
    rgba.thumbnail((size, size), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    x = (size - rgba.width) // 2
    y = (size - rgba.height) // 2
    canvas.paste(rgba, (x, y), rgba)
    return canvas


def sharpen(img: Image.Image) -> Image.Image:
    return img.filter(ImageFilter.UnsharpMask(radius=1.1, percent=115, threshold=2))


def main() -> None:
    DROP.mkdir(parents=True, exist_ok=True)
    src = find_source()
    print("source:", src)

    base = trim_transparent(Image.open(src))
    one = sharpen(fit_square(base, BASE_MAX))
    two = sharpen(fit_square(base, BASE_MAX * 2))
    three = sharpen(fit_square(base, BASE_MAX * 3))

    paths = {
        OUT / "cute-crest.png": one,
        OUT / "cute-crest-2x.png": two,
        OUT / "cute-crest-3x.png": three,
    }
    for path, img in paths.items():
        img.save(path, optimize=True)
        print("wrote", path.name, img.size)

    print("OK. Перезапусти Mini App в Telegram, чтобы увидеть новый логотип.")


if __name__ == "__main__":
    main()
