# -*- coding: utf-8 -*-
# Composición de la tira de fotos para la cabina.
# Apila N fotos (crop 4:3) sobre fondo blanco y agrega logo + QR en la base.
# La composición se hace EN COLOR: la conversión monocromática ocurre una
# sola vez después, en el pipeline térmico común (onepos_common.image).

from typing import List

import qrcode
from PIL import Image, ImageOps


def _load_rgb(path: str) -> Image.Image:
    # Carga aplicando rotación EXIF (cámaras/phones) y garantizando RGB
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def _crop_4_3(img: Image.Image) -> Image.Image:
    # Recorte central a relación 4:3 (formato clásico de tira fotográfica)
    w, h = img.size
    ratio = 4 / 3
    if w / h > ratio:  # demasiado ancha -> recortar costados
        new_w = int(h * ratio)
        left = (w - new_w) // 2
        box = (left, 0, left + new_w, h)
    else:  # demasiado alta -> recortar arriba/abajo
        new_h = int(w / ratio)
        top = (h - new_h) // 2
        box = (0, top, w, top + new_h)
    return img.crop(box)


def _qr_image(data: str, box_px: int) -> Image.Image:
    # QR con zona de silencio; se genera grande y se reduce con NEAREST
    # para mantener los módulos nítidos al imprimir.
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return img.resize((box_px, box_px), Image.NEAREST)


def compose_strip(photo_paths: List[str], target_width: int, logo_path: str, qr_url: str) -> Image.Image:
    # Construye la tira completa. Devuelve imagen RGB lista para el pipeline.
    if not photo_paths:
        raise ValueError("Se requiere al menos una fotografía")

    margin = max(8, target_width // 32)          # borde exterior
    gap = max(6, target_width // 48)             # separación entre elementos
    photo_h = int(target_width * 3 / 4)          # altura del crop 4:3

    # Fotos escaladas
    photos = []
    for path in photo_paths:
        p = _crop_4_3(_load_rgb(path)).resize((target_width, photo_h), Image.LANCZOS)
        photos.append(p)

    # Logo a ~55% del ancho preservando aspecto
    logo = _load_rgb(logo_path)
    logo_w = int(target_width * 0.55)
    logo_h = max(1, int(logo.size[1] * logo_w / logo.size[0]))
    logo = logo.resize((logo_w, logo_h), Image.LANCZOS)

    # QR cuadrado (~33% del ancho)
    qr_box = int(target_width * 0.33)
    qr = _qr_image(qr_url, qr_box)

    # Fila inferior: logo + QR centrados horizontalmente con separación
    row_h = max(logo_h, qr_box)
    row_w = logo_w + gap + qr_box
    if row_w > target_width:
        # Fallback defensivo para anchos de papel muy chicos
        scale = target_width / row_w
        logo_w = int(logo_w * scale)
        logo = logo.resize((logo_w, max(1, int(logo_h * scale))), Image.LANCZOS)
        qr_box = int(qr_box * scale)
        qr = _qr_image(qr_url, qr_box)
        row_w = target_width
        row_h = max(logo.size[1], qr_box)

    total_h = (
        margin
        + len(photos) * photo_h
        + (len(photos) - 1) * gap   # separaciones entre fotos
        + gap                       # separación antes de la fila inferior
        + row_h
        + margin
    )

    strip = Image.new("RGB", (target_width, total_h), "white")

    y = margin
    for p in photos:
        strip.paste(p, (0, y))
        y += photo_h + gap

    # Fila inferior centrada verticalmente dentro de su banda
    x0 = (target_width - row_w) // 2
    strip.paste(logo, (x0, y + (row_h - logo.size[1]) // 2))
    strip.paste(qr, (x0 + logo_w + gap, y + (row_h - qr_box) // 2))

    return strip
