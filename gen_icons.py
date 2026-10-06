#!/usr/bin/env python3
"""Genera los iconos PWA (icons/): dos monedas solapadas sobre fondo verde azulado.
Ejecuta: python3 gen_icons.py"""
from pathlib import Path

from PIL import Image, ImageDraw

FONDO = (15, 118, 110)
MONEDA_ATRAS = (204, 251, 241)
MONEDA_DELANTE = (247, 245, 242)


def icono(tam):
    img = Image.new("RGBA", (tam, tam), FONDO + (255,))
    d = ImageDraw.Draw(img)
    r, cy = tam * 0.22, tam * 0.5
    for cx, color in ((tam * 0.40, MONEDA_ATRAS), (tam * 0.60, MONEDA_DELANTE)):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color, outline=FONDO, width=max(2, tam // 40))
    return img


Path("icons").mkdir(exist_ok=True)
icono(192).convert("RGB").save("icons/icon-192.png")
icono(512).convert("RGB").save("icons/icon-512.png")
icono(512).save("icons/icon-maskable-512.png")
icono(180).convert("RGB").save("icons/apple-touch-icon.png")
print("iconos generados en icons/.")
