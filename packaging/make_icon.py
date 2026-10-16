"""Draw the app icon (same design as assets/icon.svg) into assets/icon.png and assets/icon.ico.

Pure numpy + zlib, so no image tools are needed:  .venv/bin/python packaging/make_icon.py"""
import struct
import zlib
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "assets"


def draw(size, ss=4):
    n = size * ss
    y, x = (np.mgrid[0:n, 0:n] + 0.5) / n * 128            # coordinates in the SVG's 128x128 space
    img = np.zeros((n, n, 4))

    def paint(mask, color):
        img[mask] = (*[c / 255 for c in color], 1.0)

    k = 28                                                   # rounded square, radius 28
    cx, cy = np.clip(x, k, 128 - k), np.clip(y, k, 128 - k)
    paint((x - cx) ** 2 + (y - cy) ** 2 <= k * k, (0x4f, 0x46, 0xe5))
    d = np.hypot(x - 64, y - 64)
    paint(abs(d - 34) <= 4.5, (255, 255, 255))               # ring
    paint(d <= 14, (255, 255, 255))                          # centre dot
    d2 = np.hypot(x - 98, y - 30)
    paint(d2 <= 13, (0x4f, 0x46, 0xe5))                      # red dot with a border
    paint(d2 <= 9, (0xe5, 0x48, 0x4d))
    img = img.reshape(size, ss, size, ss, 4).mean(axis=(1, 3))   # smooth the edges
    return (img * 255 + 0.5).astype(np.uint8)


def png_bytes(rgba):
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[r].tobytes() for r in range(h))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    (OUT / "icon.png").write_bytes(png_bytes(draw(256)))
    sizes = [16, 32, 48, 64, 128, 256]                       # Windows .ico: PNG-compressed images
    images = [png_bytes(draw(s)) for s in sizes]
    head = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries = b""
    for s, data in zip(sizes, images):
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset)
        offset += len(data)
    (OUT / "icon.ico").write_bytes(head + entries + b"".join(images))
    print("wrote", OUT / "icon.png", "and", OUT / "icon.ico")
