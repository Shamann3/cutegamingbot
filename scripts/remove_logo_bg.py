from PIL import Image
import numpy as np
import sys

path = sys.argv[1] if len(sys.argv) > 1 else r"public/assets/cute-crest.png"

img = Image.open(path).convert("RGBA")
arr = np.array(img, dtype=np.float32)
rgb = arr[:, :, :3]

brightness = rgb.mean(axis=2)
color_range = rgb.max(axis=2) - rgb.min(axis=2)

bg = (brightness >= 228) & (color_range <= 28)
soft = (brightness >= 205) & (brightness < 228) & (color_range <= 22)

alpha = np.full(arr.shape[:2], 255.0, dtype=np.float32)
alpha[bg] = 0.0
alpha[soft] = np.clip((228 - brightness[soft]) / 23.0 * 255.0, 0, 255)

arr[:, :, 3] = alpha
Image.fromarray(arr.astype(np.uint8)).save(path, optimize=True)
print(f"saved transparent PNG: {path}")
