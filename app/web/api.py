# -*- coding: utf-8 -*-
# Servidor HTTP FastAPI
# Endpoints para subir PDF, consultar cola y salud

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import os
import uuid
import time

from app.core.queue import PrintQueue, PrintJob, JobState
from app.core.worker import PrintWorker
from app.utils.network import get_primary_ip

app = FastAPI()

# Inicializar cola y worker globales
queue = PrintQueue()
worker = PrintWorker(queue)

class Health(BaseModel):
    ok: bool
    cola_pendientes: int
    ultimos_impresos: int
    ip_local: str
    impresora: dict

@app.on_event("startup")
async def on_startup():
    # Arrancar worker de impresión
    worker.start()

@app.on_event("shutdown")
async def on_shutdown():
    # Detener worker limpiamente
    worker.stop()

@app.post("/imprimir")
async def imprimir_pdf(request: Request, archivo: UploadFile = File(...)):
    # Validar tipo de archivo
    if not archivo.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos PDF")
    # Guardar temporalmente
    trabajos_dir = queue.get_jobs_dir()
    os.makedirs(trabajos_dir, exist_ok=True)
    job_id = str(uuid.uuid4())
    tmp_path = os.path.join(trabajos_dir, f"{job_id}.pdf")
    contenido = await archivo.read()
    with open(tmp_path, "wb") as f:
        f.write(contenido)
    # Crear trabajo y agregar a la cola
    cliente_ip = request.client.host if request and request.client else "desconocido"
    job = PrintJob(
        id=job_id,
        client_ip=cliente_ip,
        original_filename=archivo.filename,
        received_at=int(time.time()),
        state=JobState.PENDING,
        pdf_path=tmp_path,
        error_message="",
    )
    queue.enqueue(job)
    return JSONResponse({"id": job_id, "estado": job.state})

@app.get("/cola")
async def obtener_cola():
    # Devolver estado de la cola y últimos impresos
    return JSONResponse(queue.status())

@app.get("/estado")
async def estado():
    # Devuelve IP local y configuración de impresora
    ip = get_primary_ip()
    cfg = {
        "interfaz": worker.printer_interface,
        "usb_vendor": worker.usb_vendor,
        "usb_product": worker.usb_product,
        "paper_width_px": worker.paper_width_px,
    }
    return JSONResponse({
        "ip": ip,
        "impresora": cfg,
        "cola": queue.status(),
    })

@app.get("/salud")
async def salud():
    # Endpoint de salud simple
    pendientes = queue.count_pending()
    impresos = queue.count_last_printed()
    return JSONResponse(Health(ok=True, cola_pendientes=pendientes, ultimos_impresos=impresos, ip_local=get_primary_ip(), impresora={
        "interfaz": worker.printer_interface,
        "usb_vendor": worker.usb_vendor,
        "usb_product": worker.usb_product,
        "paper_width_px": worker.paper_width_px,
    }).dict())
