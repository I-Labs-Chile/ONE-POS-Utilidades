# -*- coding: utf-8 -*-
# Funciones de imagen para impresión térmica
# Conversión a monocromo con normalización y dithering mejorado

import os
from PIL import Image, ImageOps, ImageEnhance, ImageStat
import numpy as np


def _env_float(name: str, default: float) -> float:
    # Lee un float del entorno con fallback seguro (permite ajustar el
    # preset foto en despliegues empaquetados sin recompilar).
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# Defaults del pipeline fotográfico (cabina); documentados en cabina/.env.example
PHOTO_GAMMA = _env_float("THERMAL_GAMMA", 1.4)
PHOTO_BRIGHTNESS_TARGET = _env_float("THERMAL_BRIGHTNESS_TARGET", 128.0)

def _normalize_brightness(img: Image.Image) -> Image.Image:

    # Obtener estadísticas de la imagen
    stat = ImageStat.Stat(img)
    mean_brightness = stat.mean[0]  # Brillo promedio (0-255)
    
    # Si la imagen es muy oscura (promedio < 100), aumentar brillo
    if mean_brightness < 100:
        factor = 1.0 + (100 - mean_brightness) / 200.0  # Aumentar hasta 1.5x
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(factor)
    
    # Si la imagen es muy clara (promedio > 180), oscurecer ligeramente
    elif mean_brightness > 180:
        factor = 0.85
        enhancer = ImageEnhance.Brightness(img)
        img = enhancer.enhance(factor)
    
    # Ajustar contraste automáticamente
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(1.3)  # Aumentar contraste un 30%
    
    return img

def _auto_levels(img: Image.Image) -> Image.Image:

    # Convertir a numpy para procesamiento más rápido
    img_array = np.array(img, dtype=np.float32)
    
    # Calcular percentiles para evitar valores extremos (outliers)
    min_val = np.percentile(img_array, 2)
    max_val = np.percentile(img_array, 98)
    
    # Evitar división por cero
    if max_val - min_val < 1:
        return img
    
    # Expandir el rango al completo [0, 255]
    img_array = (img_array - min_val) * (255.0 / (max_val - min_val))
    img_array = np.clip(img_array, 0, 255).astype(np.uint8)
    
    return Image.fromarray(img_array, mode='L')

def _floyd_steinberg_dithering(img: Image.Image) -> Image.Image:

    img_array = np.array(img, dtype=np.float32)
    height, width = img_array.shape
    
    for y in range(height):
        for x in range(width):
            old_pixel = img_array[y, x]
            new_pixel = 255 if old_pixel > 127 else 0
            img_array[y, x] = new_pixel
            error = old_pixel - new_pixel
            
            # Distribuir el error a los píxeles vecinos
            if x + 1 < width:
                img_array[y, x + 1] += error * 7/16
            if y + 1 < height:
                if x > 0:
                    img_array[y + 1, x - 1] += error * 3/16
                img_array[y + 1, x] += error * 5/16
                if x + 1 < width:
                    img_array[y + 1, x + 1] += error * 1/16
    
    img_array = np.clip(img_array, 0, 255).astype(np.uint8)
    return Image.fromarray(img_array, mode='L')

def to_thermal_mono_dither(img: Image.Image, target_width: int, enhance: bool = True) -> Image.Image:

    # Ajustar ancho manteniendo proporción
    w, h = img.size
    if w != target_width:
        ratio = target_width / float(w)
        new_height = int(h * ratio)
        img = img.resize((target_width, new_height), Image.LANCZOS)
    
    # Convertir a escala de grises
    img = ImageOps.grayscale(img)
    
    if enhance:
        # Normalizar brillo y contraste
        img = _normalize_brightness(img)
        
        # Ajustar niveles automáticamente
        img = _auto_levels(img)
        
        # Aplicar dithering Floyd-Steinberg de alta calidad
        img = _floyd_steinberg_dithering(img)
    
    # Convertir a monocromo final
    img = img.convert("1")

    return img


# ---------------------------------------------------------------------------
# Pipeline fotográfico (preset "foto", usado por la cabina)
#
# Diferencias con el pipeline legacy:
#   - Auto-niveles ANTES de cualquier ajuste de tono (no destruye histograma)
#   - Exposición continua (target de media con clamp) en vez del escalón
#     binario <100/>180 y sin contraste fijo +30%
#   - Gamma > 1 justo antes del dithering: abre sombras (textura de barba/
#     pelo) y compensa el dot gain del papel térmico
# ---------------------------------------------------------------------------

def _luma_grayscale(img: Image.Image, weights: str = "601") -> Image.Image:
    # Convierte RGB a grises. "601" usa la luminancia estándar de PIL;
    # "709" pesa más el canal verde (suele dar más detalle en piel).
    if weights == "709":
        arr = np.asarray(img.convert("RGB"), dtype=np.float32)
        luma = arr[..., 0] * 0.2126 + arr[..., 1] * 0.7152 + arr[..., 2] * 0.0722
        return Image.fromarray(np.clip(luma, 0, 255).astype(np.uint8), mode="L")
    return ImageOps.grayscale(img)


def _normalize_exposure(img: Image.Image, target: float = 128.0,
                        clamp=(0.80, 1.35)) -> Image.Image:
    # Ajuste continuo de exposición: factor = target/media con clamp.
    # Sin umbrales binarios ni saltos bruscos entre fotos vecinas.
    stat = ImageStat.Stat(img)
    mean_brightness = stat.mean[0]
    if mean_brightness <= 0:
        return img
    factor = target / mean_brightness
    factor = max(clamp[0], min(clamp[1], factor))
    if abs(factor - 1.0) < 0.01:
        return img
    return ImageEnhance.Brightness(img).enhance(factor)


def _gamma_lift(img: Image.Image, gamma: float = 1.4) -> Image.Image:
    # Curva gamma p' = 255*(p/255)^(1/gamma) via LUT.
    # gamma > 1 aclara sombras/medios sin tocar blancos; <= 1 no-op.
    if gamma is None or gamma <= 1.001 or gamma > 3.0:
        return img
    lut = [int(round(255.0 * ((i / 255.0) ** (1.0 / gamma)))) for i in range(256)]
    return img.point(lut)


def to_thermal_photo_dither(img: Image.Image, target_width: int, *,
                            gamma: float = None,
                            brightness_target: float = None,
                            clamp=(0.80, 1.35),
                            luma: str = "601",
                            order: str = "exposure_first") -> Image.Image:
    # Cadena recomendada para fotografías:
    #   resize -> gris -> auto-niveles p2-p98 -> [exposicion <-> gamma] -> F-S -> 1bpp
    #
    # order="exposure_first" (default): niveles -> exposicion -> gamma.
    #   La gamma queda pegada al dithering y su apertura de sombras sobrevive.
    # order="gamma_first": niveles -> gamma -> exposicion (variante de estudio;
    #   la normalizacion a target recorta parte del levantamiento de sombras).
    if gamma is None:
        gamma = PHOTO_GAMMA
    if brightness_target is None:
        brightness_target = PHOTO_BRIGHTNESS_TARGET

    # Ajustar ancho manteniendo proporción (igual que el pipeline legacy)
    w, h = img.size
    if w != target_width:
        ratio = target_width / float(w)
        new_height = int(h * ratio)
        img = img.resize((target_width, new_height), Image.LANCZOS)

    img = _luma_grayscale(img, weights=luma)
    img = _auto_levels(img)

    if order == "gamma_first":
        img = _gamma_lift(img, gamma)
        img = _normalize_exposure(img, target=brightness_target, clamp=clamp)
    else:
        img = _normalize_exposure(img, target=brightness_target, clamp=clamp)
        img = _gamma_lift(img, gamma)

    img = _floyd_steinberg_dithering(img)
    return img.convert("1")
