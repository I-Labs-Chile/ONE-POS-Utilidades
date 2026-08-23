#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Entrypoint de la Cabina Fotográfica ONE-POS (utilidad independiente).
# Defaults propios ANTES de importar módulos: puerto y directorio de datos
# separados del servidor web para poder coexistir en la misma máquina.

import os
import sys

# Defaults de despliegue de la cabina (no pisan variables ya definidas)
os.environ.setdefault("SERVER_PORT", "8081")
os.environ.setdefault("QUEUE_DIR", "./data-cabina")

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

if __name__ == "__main__":
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", "8081"))

    print("=" * 60)
    print("    CABINA FOTOGRAFICA ONE-POS")
    print("=" * 60)
    print(f"  Host: {host}")
    print(f"  Puerto: {port}")
    print(f"  Datos: {os.environ.get('QUEUE_DIR')}")
    print(f"  QR destino: {os.environ.get('CABINA_QR_URL', 'https://www.instagram.com/ilabs.cl/')}")
    print("  Presiona Ctrl+C para detener la cabina")
    print("=" * 60)
    print()

    import uvicorn
    uvicorn.run("cabina.api:app", host=host, port=port, reload=False, workers=1)
