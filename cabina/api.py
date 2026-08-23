# -*- coding: utf-8 -*-
# API FastAPI de la Cabina Fotográfica ONE-POS.
# Utilidad autónoma: no comparte proceso ni endpoints con el servidor web.
# Endpoints:
#   GET  /         → interfaz kiosco
#   GET  /salud    → estado de impresora y cola
#   POST /captura  → recibe 3 fotos, compone tira y encola impresión

import os
import uuid
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from onepos_common.queue import PrintJob, PrintQueue, JobState
from onepos_common.status import create_printer_status, start_printer_monitor
from onepos_common.worker import PrintWorker

from cabina.compose import compose_strip

app = FastAPI(title="Cabina Fotográfica ONE-POS")

# Archivos estáticos del kiosco (JS/CSS/logo)
_frontend_dir = Path(__file__).resolve().parent / "frontend"
_frontend_static = _frontend_dir / "src"
if _frontend_static.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_static)), name="static")

# Cola y worker propios (datos separados vía QUEUE_DIR que define run_cabina.py)
queue = PrintQueue()
worker = PrintWorker(queue)   # sin selftest de bienvenida en la cabina

# Estado de impresora mantenido por el monitor común
printer_status = create_printer_status()
_printer_monitor = None

# Extensiones aceptadas para cada toma
_EXT_OK = (".jpg", ".jpeg", ".png", ".webp")


def _get_index_html() -> str:
    # Sirve el HTML del kiosco; compatible con empaquetado PyInstaller (_MEIPASS)
    base = _frontend_dir
    try:
        import sys
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass) / "cabina" / "frontend"
    except Exception:
        pass
    try:
        return (base / "index.html").read_text(encoding="utf-8")
    except Exception as e:
        print(f"# Error cargando interfaz de cabina: {e}")
        return "<html><body><h1>Error</h1><p>No se pudo cargar la interfaz de cabina.</p></body></html>"


@app.get("/", response_class=HTMLResponse)
async def raiz():
    # Interfaz kiosco de la cabina
    return _get_index_html()


@app.get("/salud")
async def salud():
    # Mismo contrato que el servidor web: el frontend de cabina lo consume igual
    snapshot = _printer_monitor.snapshot() if _printer_monitor else dict(printer_status)
    return JSONResponse({
        "ok": snapshot["available"],
        "cola_pendientes": queue.count_pending(),
        "impresora_disponible": snapshot["available"],
        "impresora_nombre": snapshot["printer_name"],
        "error": snapshot.get("error"),
    })


@app.post("/captura")
async def captura(
    request: Request,
    foto1: UploadFile = File(...),
    foto2: UploadFile = File(...),
    foto3: UploadFile = File(...),
):
    # Recibe las 3 tomas, compone la tira con logo + QR y encola la impresión.
    global _printer_monitor
    snapshot = _printer_monitor.snapshot() if _printer_monitor else dict(printer_status)
    if not snapshot["available"]:
        raise HTTPException(status_code=503, detail="Impresora no disponible")

    fotos = (foto1, foto2, foto3)
    trabajos_dir = queue.get_jobs_dir()
    os.makedirs(trabajos_dir, exist_ok=True)

    # Guardar tomas temporales con validación básica de tipo
    tmp_paths = []
    for i, foto in enumerate(fotos, start=1):
        nombre = (foto.filename or "").lower()
        if nombre and not nombre.endswith(_EXT_OK):
            raise HTTPException(status_code=400, detail=f"foto{i}: formato no permitido")
        contenido = await foto.read()
        if not contenido:
            raise HTTPException(status_code=400, detail=f"foto{i}: archivo vacío")
        ext = os.path.splitext(nombre)[1] or ".jpg"
        path = os.path.join(trabajos_dir, f"{uuid.uuid4()}_f{i}{ext}")
        with open(path, "wb") as f:
            f.write(contenido)
        tmp_paths.append(path)

    # Componer la tira EN COLOR; el pipeline térmico hará el mono una sola vez
    target_width = int(os.environ.get("PAPER_WIDTH_PX", "384"))
    qr_url = os.environ.get("CABINA_QR_URL", "https://www.instagram.com/ilabs.cl/")
    logo_path = str(_frontend_static / "empresa.png")
    try:
        strip = compose_strip(tmp_paths, target_width=target_width, logo_path=logo_path, qr_url=qr_url)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"No se pudo componer la tira: {e}")

    job_id = str(uuid.uuid4())
    strip_path = os.path.join(trabajos_dir, f"{job_id}.png")
    strip.save(strip_path)

    # Limpieza de las tomas crudas (solo queda la tira compuesta para imprimir)
    for p in tmp_paths:
        try:
            os.remove(p)
        except OSError:
            pass

    cliente_ip = request.client.host if request and request.client else "desconocido"
    job = PrintJob(
        id=job_id,
        client_ip=cliente_ip,
        original_filename="tira-cabina.png",
        received_at=int(time.time()),
        state=JobState.PENDING,
        pdf_path=strip_path,
        error_message="",
        kind="image",
        preset="foto",   # pipeline fotográfico (niveles->exposición->gamma)
    )
    queue.enqueue(job)
    print(f"# Tira de cabina encolada: {job_id} ({len(fotos)} fotos)")
    return JSONResponse({"id": job_id, "estado": job.state})


@app.on_event("startup")
async def on_startup():
    global _printer_monitor
    worker.start()
    _printer_monitor = start_printer_monitor(printer_status)


@app.on_event("shutdown")
async def on_shutdown():
    worker.stop()
