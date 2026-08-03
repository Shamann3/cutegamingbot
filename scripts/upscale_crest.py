"""Generate crisp 2x/3x crest assets from cute-crest.png.

Предпочтительный путь для нового логотипа:
  1) положи файл в public/assets/logo-drop/logo.png
  2) запусти: python scripts/prepare_logo.py

Этот скрипт — быстрый апскейл уже готового cute-crest.png.
"""
from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parents[1] / "public" / "assets"
SRC = ROOT / "cute-crest.png"


def main():
    if not SRC.exists():
        raise SystemExit(
            f"Нет {SRC}. Положи логотип в public/assets/logo-drop/logo.png "
            "и запусти python scripts/prepare_logo.py"
        )
    img = Image.open(SRC).convert("RGBA")
    w, h = img.size
    for scale, name in ((2, "cute-crest-2x.png"), (3, "cute-crest-3x.png")):
        out = img.resize((w * scale, h * scale), Image.Resampling.LANCZOS)
        out = out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        path = ROOT / name
        out.save(path, optimize=True)
        print("wrote", path.name, out.size)


if __name__ == "__main__":
    main()
