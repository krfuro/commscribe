#!/usr/bin/env python3
"""Tegner appikonet.

electron-builder lager .icns og .ico selv ut fra en 1024x1024 PNG, saa dette
skriptet trenger bare aa produsere den ene fila. Resultatet er sjekket inn, saa
et vanlig bygg ikke er avhengig av Pillow - kjor dette bare naar ikonet endres.

    python3 packaging/make_icon.py
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parent.parent / "desktop" / "build" / "icon.png"
SIZE = 1024
SS = 4                      # tegn firedobbelt og krymp - gir myke kanter

BG_TOP = (17, 32, 51)
BG_BOTTOM = (8, 14, 22)
ACCENT = (69, 200, 240)
ACCENT_DIM = (29, 143, 184)
GREEN = (61, 220, 145)


def rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1],
                                           radius=radius, fill=255)
    return mask


def gradient(size: int, top: tuple, bottom: tuple) -> Image.Image:
    img = Image.new("RGB", (1, size))
    px = img.load()
    for y in range(size):
        t = y / (size - 1)
        px[0, y] = tuple(round(a + (b - a) * t) for a, b in zip(top, bottom))
    return img.resize((size, size), Image.BILINEAR)


def draw_icon() -> Image.Image:
    n = SIZE * SS
    canvas = gradient(n, BG_TOP, BG_BOTTOM).convert("RGBA")
    d = ImageDraw.Draw(canvas)

    # Bolgeformen er motivet. Buene ligger som en hette over den, og alt er
    # senket litt under midten slik at helheten ser sentrert ut.
    cx, cy = n / 2, n * 0.545

    for i, radius in enumerate((0.255, 0.335, 0.415)):
        r = n * radius
        width = int(n * 0.030)
        fade = 1.0 - i * 0.30
        color = tuple(round(c * fade + 22 * (1 - fade)) for c in ACCENT_DIM)
        d.arc([cx - r, cy - r, cx + r, cy + r],
              start=200, end=340, fill=color + (255,), width=width)

    bars = 11
    span = n * 0.46
    bar_w = span / (bars * 2 - 1)
    heights = [0.18, 0.34, 0.56, 0.80, 0.48, 1.0, 0.62, 0.88, 0.42, 0.28, 0.16]
    for i, h in enumerate(heights):
        x = cx - span / 2 + i * bar_w * 2
        half = n * 0.185 * h
        # Midtsoylene er lysest, saa blikket lander i sentrum.
        t = 1 - abs(i - (bars - 1) / 2) / ((bars - 1) / 2)
        color = tuple(round(a + (b - a) * (t * 0.85))
                      for a, b in zip(ACCENT_DIM, ACCENT))
        d.rounded_rectangle([x, cy - half, x + bar_w, cy + half],
                            radius=bar_w / 2, fill=color + (255,))

    # Sendediode: appen lytter.
    r = n * 0.036
    lx, ly = n * 0.775, n * 0.775
    d.ellipse([lx - r * 2.4, ly - r * 2.4, lx + r * 2.4, ly + r * 2.4],
              fill=(GREEN[0] // 7, GREEN[1] // 7, GREEN[2] // 7, 255))
    d.ellipse([lx - r, ly - r, lx + r, ly + r], fill=GREEN + (255,))

    canvas.putalpha(rounded_mask(n, int(n * 0.225)))
    return canvas.resize((SIZE, SIZE), Image.LANCZOS)


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    icon = draw_icon()
    icon.save(OUT)
    # NSIS vil ha en ekte .ico for installer- og avinstalleringsvinduene.
    ico = OUT.with_suffix(".ico")
    icon.save(ico, sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f"skrev {OUT} og {ico}")


if __name__ == "__main__":
    main()
