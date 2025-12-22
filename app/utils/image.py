# -*- coding: utf-8 -*-
# Funciones de imagen para impresión térmica
# Conversión a monocromo y dithering

from PIL import Image, ImageOps

def to_thermal_mono_dither(img: Image.Image, target_width: int) -> Image.Image:
    # Ajustar ancho manteniendo proporción
    w, h = img.size
    if w != target_width:
        ratio = target_width / float(w)
        img = img.resize((target_width, int(h * ratio)), Image.LANCZOS)
    # Convertir a escala de grises y aplicar threshold con dithering
    img = ImageOps.grayscale(img)
    img = img.convert("1")
    return img
