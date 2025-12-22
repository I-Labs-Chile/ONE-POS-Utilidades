# -*- coding: utf-8 -*-
# Configuración de pruebas: agregar ruta del proyecto al sys.path

import sys
import os

ROOT = os.path.dirname(os.path.abspath(os.path.join(__file__, '..')))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
