# -*- coding: utf-8 -*-
# Funciones de imagen para impresión térmica
# Conversión a monocromo con normalización y dithering mejorado

from PIL import Image, ImageOps, ImageEnhance, ImageStat
import numpy as np

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
