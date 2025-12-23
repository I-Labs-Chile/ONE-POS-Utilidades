# -*- coding: utf-8 -*-
# Servidor HTTP FastAPI
# Endpoints para subir PDF, consultar cola y salud

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import os
import uuid
import time
import threading

from app.core.queue import PrintQueue, PrintJob, JobState
from app.core.worker import PrintWorker
from app.core.test_print import run_printer_selftest
from app.utils.network import get_primary_ip
from app.utils.usb_detector import USBPrinterDetector
from app.web.frontend import render_upload_page
from pathlib import Path

app = FastAPI()

# Montar archivos estáticos del frontend (CSS, JS, imágenes)
_frontend_dir = Path(__file__).resolve().parent / "frontend"
_frontend_static = _frontend_dir / "src"

# Montar primero el directorio src para archivos CSS y JS
if _frontend_static.exists():
    app.mount("/static", StaticFiles(directory=str(_frontend_static)), name="static")

# Inicializar cola y worker globales
queue = PrintQueue()
worker = PrintWorker(queue)

# Estado global de la impresora
printer_status = {
    "available": False,
    "last_check": 0,
    "device_path": None,
    "printer_name": None
}
printer_status_lock = threading.Lock()

def check_printer_availability():

    global printer_status
    detector = USBPrinterDetector()
    
    while True:
        try:
            printers = detector.scan_for_printers()
            with printer_status_lock:
                if printers:
                    printer_status["available"] = True
                    printer_status["device_path"] = printers[0].device_path
                    printer_status["printer_name"] = printers[0].friendly_name
                else:
                    printer_status["available"] = False
                    printer_status["device_path"] = None
                    printer_status["printer_name"] = None
                printer_status["last_check"] = int(time.time())
        except Exception as e:
            with printer_status_lock:
                printer_status["available"] = False
                printer_status["last_check"] = int(time.time())
        
        time.sleep(3)  # Verificar cada 3 segundos

class Health(BaseModel):
    ok: bool
    cola_pendientes: int
    ultimos_impresos: int
    ip_local: str
    impresora: dict
    impresora_disponible: bool
    impresora_nombre: Optional[str] = None


class PrinterSelfTestResult(BaseModel):
    ok: bool
    url: str
    detalle: str


@app.get("/", response_class=HTMLResponse)
async def raiz():
    # Endpoint raíz que entrega la interfaz web para subir documentos
    # Se delega la generación de HTML al módulo app.web.frontend
    return render_upload_page()


@app.post("/test-impresora", response_model=PrinterSelfTestResult)
async def test_impresora():
    # Endpoint para ejecutar una prueba de conexión con la impresora
    # Envía un mensaje de bienvenida y un código QR con la URL del servidor
    resultado = run_printer_selftest(worker)
    return PrinterSelfTestResult(**resultado)

@app.on_event("startup")
async def on_startup():
    # Arrancar worker de impresión
    worker.start()
    # Iniciar hilo de monitoreo de impresora
    monitor_thread = threading.Thread(target=check_printer_availability, daemon=True)
    monitor_thread.start()

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
        kind="pdf",
    )
    queue.enqueue(job)
    return JSONResponse({"id": job_id, "estado": job.state})


@app.post("/imprimir-imagen")
async def imprimir_imagen(request: Request, archivo: UploadFile = File(...)):
    # Validar tipo de archivo de imagen por extensión
    nombre = archivo.filename.lower()
    extensiones_permitidas = (".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp")
    if not nombre.endswith(extensiones_permitidas):
        raise HTTPException(status_code=400, detail="Solo se aceptan imágenes (jpg, png, bmp, gif, webp)")
    # Guardar temporalmente la imagen en la carpeta de trabajos
    trabajos_dir = queue.get_jobs_dir()
    os.makedirs(trabajos_dir, exist_ok=True)
    job_id = str(uuid.uuid4())
    # Mantener la extensión original para facilitar diagnóstico en disco
    _, ext = os.path.splitext(nombre)
    if not ext:
        ext = ".png"
    tmp_path = os.path.join(trabajos_dir, f"{job_id}{ext}")
    contenido = await archivo.read()
    with open(tmp_path, "wb") as f:
        f.write(contenido)
    # Crear trabajo y agregar a la cola como imagen
    cliente_ip = request.client.host if request and request.client else "desconocido"
    job = PrintJob(
        id=job_id,
        client_ip=cliente_ip,
        original_filename=archivo.filename,
        received_at=int(time.time()),
        state=JobState.PENDING,
        pdf_path=tmp_path,
        error_message="",
        kind="image",
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
    # Endpoint de salud que incluye verificación de disponibilidad de impresora
    pendientes = queue.count_pending()
    impresos = queue.count_last_printed()
    
    with printer_status_lock:
        impresora_disponible = printer_status["available"]
        impresora_nombre = printer_status["printer_name"]
    
    return JSONResponse(Health(
        ok=impresora_disponible, 
        cola_pendientes=pendientes, 
        ultimos_impresos=impresos, 
        ip_local=get_primary_ip(), 
        impresora={
            "interfaz": worker.printer_interface,
            "usb_vendor": worker.usb_vendor,
            "usb_product": worker.usb_product,
            "paper_width_px": worker.paper_width_px,
        },
        impresora_disponible=impresora_disponible,
        impresora_nombre=impresora_nombre
    ).dict())
