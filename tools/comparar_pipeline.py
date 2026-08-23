#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Herramienta de investigación del pipeline fotográfico térmico.
#
# Genera retratos sintéticos (o usa fotos reales pasadas como argumentos),
# los pasa por el pipeline legacy y por variantes del pipeline nuevo
# (orden exposición/gamma, valor de gamma, luma 601/709) y produce:
#   - hojas comparativas PNG (tiles al ancho real del papel, 384 px)
#   - tabla de métricas objetivas (% tinta, bordes, entropía)
#
# Uso:
#   .venv/bin/python tools/comparar_pipeline.py                # sintéticos
#   .venv/bin/python tools/comparar_pipeline.py foto1.jpg ...  # fotos reales

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from PIL import Image, ImageDraw

from onepos_common.image import (
    to_thermal_mono_dither,
    to_thermal_photo_dither,
)

PAPEL_W = 384
MARGEN = 12
ETIQUETA_H = 22

# Columnas del comparativo: (nombre, kwargs para to_thermal_photo_dither)
VARIANTES = [
    ("legacy", "legacy"),
    ("ef g1.25", dict(order="exposure_first", gamma=1.25)),
    ("ef g1.4 *", dict(order="exposure_first", gamma=1.4)),
    ("ef g1.6", dict(order="exposure_first", gamma=1.6)),
    ("gf g1.4", dict(order="gamma_first", gamma=1.4)),
    ("ef g1.4 l709", dict(order="exposure_first", gamma=1.4, luma="709")),
]


def retrato_sintetico(w=800, h=600, seed=42):
    # Piel con sombreado radial + barba/pelo oscuros texturizados + fondo claro:
    # reproduce el caso problemático (sombras ricas que el contraste fijo aplana).
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    bg = 228 - (xx / w) * 28
    img = np.stack([bg, bg, bg], axis=-1)

    cx, cy = w / 2, h * 0.45
    rx, ry = w * 0.22, h * 0.34
    d = (((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)
    cara = d < 1.0
    piel = np.array([226, 176, 152], dtype=np.float32)
    sombra = (1.0 - 0.30 * np.clip(d, 0, 1))[..., None]
    img[cara] = np.clip(piel * sombra[cara], 0, 255)

    textura = rng.normal(0, 16, size=(h, w)).astype(np.float32)[..., None]
    barba = cara & (yy > cy + ry * 0.12) & (d < 0.88)
    img[barba] = np.clip(np.float32([74, 56, 47]) + textura, 0, 255)[barba]
    pelo = cara & (yy < cy - ry * 0.35)
    img[pelo] = np.clip(np.float32([50, 39, 33]) + textura, 0, 255)[pelo]

    for sx in (-1, 1):
        ex, ey = cx + sx * rx * 0.42, cy - ry * 0.18
        ojo = ((xx - ex) / (rx * 0.13)) ** 2 + ((yy - ey) / (ry * 0.07)) ** 2 < 1
        img[ojo] = np.float32([36, 31, 29])
        ceja = ((xx - ex) / (rx * 0.21)) ** 2 + ((yy - ey + ry * 0.15) / (ry * 0.05)) ** 2 < 1
        img[ceja] = np.float32([56, 43, 37])
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def exposiciones(img_rgb):
    # Misma escena en tres exposiciones para probar la continuidad del ajuste.
    arr = np.asarray(img_rgb, dtype=np.float32)
    return [
        ("normal", arr.copy()),
        ("oscura x0.55", arr * 0.55),
        ("clara x1.45", np.clip(arr * 1.45, 0, 255)),
    ]


def aplicar_variante(rgb_arr, nombre, spec):
    img = Image.fromarray(np.clip(rgb_arr, 0, 255).astype(np.uint8), "RGB")
    if spec == "legacy":
        return to_thermal_mono_dither(img, target_width=PAPEL_W)
    return to_thermal_photo_dither(img, target_width=PAPEL_W, **spec)


def _metricas_arr(l):
    # Métricas sobre un array de grises 0-255: % tinta (<128), densidad de
    # bordes (gradiente horizontal medio) y entropía del histograma.
    tinta = float((l < 128).mean())
    bordes = float(np.abs(np.diff(l, axis=1)).mean())
    hist = np.bincount(np.clip(l, 0, 255).astype(np.uint8).ravel(), minlength=256).astype(np.float64)
    p = hist / hist.sum()
    p = p[p > 0]
    entropia = float(-(p * np.log2(p)).sum())
    return tinta, bordes, entropia


def metricas(img_1bpp):
    return _metricas_arr(np.asarray(img_1bpp.convert("L"), dtype=np.float32))


def hoja(nombre_caso, rgb_arr, out_path):
    casos = [("gris crudo", None)] + VARIANTES
    tiles, alto_max, filas_metricas = [], 0, []

    for nombre, spec in casos:
        if spec is None:
            gris = Image.fromarray(np.clip(rgb_arr, 0, 255).astype(np.uint8), "RGB").convert("L")
            tile = gris.resize((PAPEL_W, int(gris.height * PAPEL_W / gris.width)), Image.LANCZOS)
            m = _metricas_arr(np.asarray(tile, dtype=np.float32))
        else:
            res = aplicar_variante(rgb_arr, nombre, spec)
            tile = res
            m = metricas(res)
        tiles.append((nombre, tile, m))
        alto_max = max(alto_max, tile.height)

    W = MARGEN + len(casos) * (PAPEL_W + MARGEN)
    H = ETIQUETA_H + alto_max + MARGEN + 30
    hoja_img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(hoja_img)

    x = MARGEN
    draw.text((MARGEN, 4), f"{nombre_caso}  (ancho papel {PAPEL_W}px)", fill="black")
    y0 = ETIQUETA_H
    for nombre, tile, (tinta, bordes, entropia) in tiles:
        draw.text((x, y0 - ETIQUETA_H + 4), nombre[:18], fill="black")
        hoja_img.paste(tile.convert("RGB"), (x, y0))
        draw.text((x, y0 + alto_max + 4),
                  f"tinta {tinta*100:4.1f}% b{bordes:4.1f}", fill="black")
        filas_metricas.append(f"  {nombre:<18} tinta={tinta*100:5.1f}%  bordes={bordes:5.2f}  entropia={entropia:5.2f}")
        x += PAPEL_W + MARGEN

    hoja_img.save(out_path)
    return out_path, filas_metricas


def main():
    ap = argparse.ArgumentParser(description="Comparativa de pipelines térmicos")
    ap.add_argument("inputs", nargs="*", help="fotos reales (si se omiten, usa sintéticos)")
    ap.add_argument("--out", default="/tmp/opencode/comparativa")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    if args.inputs:
        casos = [(os.path.splitext(os.path.basename(p))[0],
                  np.asarray(Image.open(p).convert("RGB"), dtype=np.float32))
                 for p in args.inputs]
    else:
        base = retrato_sintetico()
        casos = exposiciones(base)

    for nombre_caso, rgb_arr in casos:
        path, filas = hoja(nombre_caso, rgb_arr, os.path.join(args.out, f"{nombre_caso}.png"))
        print(f"\n== {nombre_caso} -> {path}")
        print("\n".join(filas))

    print("\nListo. Abre los PNG y compara textura de barba/pelo y ruido en fondo.")


if __name__ == "__main__":
    main()
