# -*- coding: utf-8 -*-
# Módulo de interfaz web
# Entrega la página HTML desde archivos estáticos en disco

from fastapi.responses import HTMLResponse
from pathlib import Path
import sys


def _get_frontend_dir() -> Path:
    # Obtiene la ruta base donde se encuentra el frontend (HTML, CSS, imágenes)
    # Soporta ejecución normal y empaquetada con PyInstaller (usando _MEIPASS)
    base = Path(__file__).resolve().parent
    try:
        # Si existe _MEIPASS, se usa como base para recursos empaquetados
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass) / "app" / "web"
    except Exception:
        # Si algo falla, se mantiene la ruta por defecto
        pass
    return base / "frontend"


def render_upload_page() -> HTMLResponse:
    # Lee el archivo index.html del frontend y lo devuelve como respuesta
    frontend_dir = _get_frontend_dir()
    index_path = frontend_dir / "index.html"
    try:
        html = index_path.read_text(encoding="utf-8")
    except Exception as e:
        # Si no se puede leer el HTML, se devuelve un mensaje simple de error
        # Comentario y mensaje en español orientados a diagnóstico en campo
        print(f"# Error cargando interfaz web: {e}")
        html = "<html><body><h1>Error</h1><p>No se pudo cargar la interfaz web.</p></body></html>"
    return HTMLResponse(content=html, status_code=200)
