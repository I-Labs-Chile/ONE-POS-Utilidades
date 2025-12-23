#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Punto de entrada del servidor
# Usa uvicorn para iniciar FastAPI

import os
import sys

try:
    # Cargar variables desde archivo .env si existe (útil para despliegues y PyInstaller)
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # Si python-dotenv no está disponible se ignora silenciosamente
    pass

if __name__ == "__main__":
    # Configurar variables por defecto
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", "8080"))
    
    # Banner informativo
    print("=" * 60)
    print("    SERVIDOR DE IMPRESIÓN ESC/POS - Q-CUBE")
    print("=" * 60)
    print(f"  Host: {host}")
    print(f"  Puerto: {port}")
    print(f"  Acceso local: http://localhost:{port}")
    print(f"  Presiona Ctrl+C para detener el servidor")
    print("=" * 60)
    print()
    
    # Import diferido para evitar costos al inspeccionar
    import uvicorn
    uvicorn.run("app.web.api:app", host=host, port=port, reload=False, workers=1)
