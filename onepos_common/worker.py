# -*- coding: utf-8 -*-
# Worker de impresión secuencial
# Rasteriza PDF, convierte a monocromo y envía ESC/POS

import os
import glob
import re
import threading
import subprocess
from typing import Optional
from PIL import Image

from onepos_common.queue import PrintQueue, PrintJob, JobState
from onepos_common.printer_manager import create_sender

from onepos_common.image import to_thermal_mono_dither, to_thermal_photo_dither

class PrintWorker:
    def __init__(self, queue: PrintQueue, selftest_fn=None):
        self.queue = queue
        # Callback opcional de prueba de impresión al arrancar (inyectado por
        # cada utilidad; evita que common dependa de código de las apps).
        self.selftest_fn = selftest_fn
        self.queue = queue
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # Configuración de impresora
        self.printer_interface = os.environ.get("PRINTER_IF", "usb").lower()
        self.printer_host = os.environ.get("PRINTER_HOST", "127.0.0.1")
        self.printer_port = int(os.environ.get("PRINTER_PORT", "9100"))
        self.usb_vendor = int(os.environ.get("USB_VENDOR", "0"))
        self.usb_product = int(os.environ.get("USB_PRODUCT", "0"))
        # Ancho en píxeles pensado para 58mm por defecto (384 puntos)
        self.paper_width_px = int(os.environ.get("PAPER_WIDTH_PX", "384"))
        # DPI de rasterización del PDF; 203 es estándar en muchas térmicas de 58mm
        self.raster_dpi = int(os.environ.get("RASTER_DPI", os.environ.get("PAPER_DPI", "203")))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("# Worker de impresión iniciado")
        # Ejecutar prueba de impresión automática al iniciar
        self._print_welcome()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("# Worker de impresión detenido")

    def _print_welcome(self):
        # Imprime mensaje de bienvenida y QR al iniciar el servidor
        if self.selftest_fn is None:
            print("# Sin prueba de impresion configurada al arrancar")
            return
        try:
            threading.Thread(target=self.selftest_fn, daemon=True).start()
        except Exception as e:
            print(f"# No se pudo ejecutar impresión de bienvenida: {e}")

    def _create_sender(self):
        try:
            return create_sender(
                interface=self.printer_interface,
                host=self.printer_host,
                port=self.printer_port,
                usb_vendor=self.usb_vendor,
                usb_product=self.usb_product,
            )
        except Exception as e:
            print(f"# No se pudo inicializar el backend de impresora: {e}")
            return None

    def _run(self):
        while not self._stop.is_set():
            job = self.queue.dequeue()
            if not job:
                self._stop.wait(0.5)
                continue
            sender = self._create_sender()
            try:
                self.queue.mark_processing(job)
                print(f"# Procesando trabajo {job.id} tipo={getattr(job, 'kind', 'pdf')} archivo={job.original_filename}")
                if sender is None:
                    raise RuntimeError("Impresora no disponible")
                images = []
                temp_generated = []
                # Seleccionar flujo según tipo de trabajo
                kind = getattr(job, "kind", "pdf")
                if kind == "pdf":
                    images = self._pdf_to_images(job.pdf_path)
                    temp_generated = list(images)
                elif kind == "image":
                    images = [job.pdf_path]
                else:
                    raise RuntimeError(f"Tipo de trabajo desconocido: {kind}")
                for img_path in images:
                    img = Image.open(img_path)
                    if getattr(job, "preset", "") == "foto":
                        # Cabina: pipeline fotográfico (niveles->exposición->gamma)
                        img = to_thermal_photo_dither(img, target_width=self.paper_width_px)
                    else:
                        img = to_thermal_mono_dither(img, target_width=self.paper_width_px)
                    sender.print_image(img)
                # Avanzar algunas líneas para evitar que el corte quede muy cerca del contenido
                try:
                    sender.feed(4)
                except Exception:
                    pass
                sender.cut()
                self.queue.mark_printed(job)
                print(f"# Trabajo {job.id} impreso")
            except Exception as e:
                self.queue.mark_error(job, str(e))
                print(f"# Error imprimiendo trabajo {job.id}: {e}")
            finally:
                # Limpieza de archivos temporales y cierre de conexión
                try:
                    if sender:
                        sender.close()
                except Exception:
                    pass
                try:
                    # Solo se eliminan los archivos generados temporalmente al rasterizar PDFs
                    for p in locals().get('temp_generated', []):
                        if p:
                            os.remove(p)
                except Exception:
                    pass

    def _pdf_to_images(self, pdf_path: str):
        # Utiliza pdftoppm para rasterizar
        # Cada página se genera como PNG temporal
        out_prefix = os.path.join(self.queue.get_jobs_dir(), os.path.basename(pdf_path) + "_page")
        cmd = [
            "pdftoppm",
            "-png",
            "-r",
            str(self.raster_dpi),
            pdf_path,
            out_prefix,
        ]
        print(f"# Ejecutando rasterización: {' '.join(cmd)}")
        try:
            subprocess.run(cmd, check=True)
        except FileNotFoundError:
            raise RuntimeError(
                "No se encontró 'pdftoppm' (poppler-utils). En Linux instale: "
                "sudo apt-get install poppler-utils. La versión para Windows debe "
                "incluir poppler junto al ejecutable."
            )
        # Recoger archivos generados con orden natural de páginas.
        # pdftoppm rellena con ceros el número cuando hay 10+ páginas
        # (ej: prefix-01.png), por eso se usa glob y no una secuencia fija.
        base = os.path.basename(pdf_path) + "_page"
        dirp = self.queue.get_jobs_dir()
        pattern = os.path.join(dirp, f"{base}-*.png")
        def _page_number(path: str) -> int:
            match = re.search(r"-(\d+)\.png$", path)
            return int(match.group(1)) if match else 0
        files = sorted(glob.glob(pattern), key=_page_number)
        if not files:
            raise RuntimeError("No se generaron imágenes del PDF")
        return files
