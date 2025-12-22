#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Punto de entrada del servidor
# Usa uvicorn para iniciar FastAPI

import os
import sys

if __name__ == "__main__":
    # Configurar variables por defecto
    host = os.environ.get("SERVER_HOST", "0.0.0.0")
    port = int(os.environ.get("SERVER_PORT", "8080"))
    # Import diferido para evitar costos al inspeccionar
    import uvicorn
    uvicorn.run("app.web.api:app", host=host, port=port, reload=False, workers=1)
