"""Remove opaque dark square background from cute-crest.png."""
from pathlib import Path

import numpy as np
from PIL import Image

path = Path(__file__).resolve().parents[1] / "public" / "assets" / "cute-crest.png"
img = Image.open(path).convert("RGBA")
arr = np.array(img, dtype=np.float32)
r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]

h, w = r.shape
edge = np.concatenate(
    [
        arr[0, :, :3].reshape(-1, 3),
        arr[-1, :, :3].reshape(-1, 3),
        arr[:, 0, :3].reshape(-1, 3),
        arr[:, -1, :3].reshape(-1, 3),
    ],
    axis=0,
)
bg = np.median(edge, axis=0)
print("bg", bg)

brightness = (r + g + b) / 3
sat = np.maximum(np.maximum(r, g), b) - np.minimum(np.minimum(r, g), b)
dist = np.sqrt((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2)

is_gold = (r > 90) & (g > 60) & (r >= g * 0.85) & (brightness > 70) & (sat > 25)
is_green = (g > 55) & (g > r * 1.05) & (g > b * 1.1) & (sat > 18)
is_bright = brightness > 85

is_bg = ((dist < 28) | ((brightness < 48) & (sat < 30) & (dist < 55))) & ~(
    is_gold | is_green | is_bright
)
soft = ((dist < 42) | ((brightness < 62) & (sat < 36))) & ~(is_gold | is_green) & ~is_bg

alpha = np.full((h, w), 255.0, dtype=np.float32)
alpha[is_bg] = 0.0
soft_t = np.clip((dist[soft] - 18) / 28.0, 0, 1)
alpha[soft] = np.minimum(alpha[soft], soft_t * 255)
arr[:, :, 3] = alpha

ys, xs = np.where(alpha > 8)
if len(xs):
    pad = 8
    x0, x1 = max(0, xs.min() - pad), min(w, xs.max() + pad + 1)
    y0, y1 = max(0, ys.min() - pad), min(h, ys.max() + pad + 1)
    arr = arr[y0:y1, x0:x1]

out = Image.fromarray(arr.astype(np.uint8), "RGBA")
out.save(path, optimize=True)
print("saved", path, out.size, "transparent", int((np.array(out)[:, :, 3] == 0).sum()))
