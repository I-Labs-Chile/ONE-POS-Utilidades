# -*- coding: utf-8 -*-
# Pruebas de procesamiento de imagen

from PIL import Image
from app.utils.image import to_thermal_mono_dither

def test_image_processing():
    img = Image.new("RGB", (800, 600), color=(128, 128, 128))
    out = to_thermal_mono_dither(img, target_width=384)
    assert out.mode == "1"
    assert out.size[0] == 384

