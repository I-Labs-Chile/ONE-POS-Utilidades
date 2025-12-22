# -*- coding: utf-8 -*-
# Worker de impresión secuencial
# Rasteriza PDF, convierte a monocromo y envía ESC/POS

import os
import threading
import subprocess
from typing import Optional
from PIL import Image

from app.core.queue import PrintQueue, PrintJob, JobState
from app.utils.escpos import EscposSender
from app.utils.image import to_thermal_mono_dither

class PrintWorker:
    def __init__(self, queue: PrintQueue):
        self.queue = queue
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        # Configuración de impresora
        self.printer_interface = "usb"  # Solo USB
        self.printer_host = os.environ.get("PRINTER_HOST", "127.0.0.1")
        self.printer_port = int(os.environ.get("PRINTER_PORT", "9100"))
        self.usb_vendor = int(os.environ.get("USB_VENDOR", "0"))
        self.usb_product = int(os.environ.get("USB_PRODUCT", "0"))
        self.paper_width_px = int(os.environ.get("PAPER_WIDTH_PX", "384"))

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        print("# Worker de impresión iniciado")

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("# Worker de impresión detenido")

    def _create_sender(self) -> Optional[EscposSender]:
        # Crear sender USB bajo demanda
        try:
            return EscposSender(
                interface=self.printer_interface,
                host=self.printer_host,
                port=self.printer_port,
                usb_vendor=self.usb_vendor,
                usb_product=self.usb_product,
            )
        except Exception as e:
            print(f"# No se pudo inicializar la impresora USB: {e}")
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
                print(f"# Procesando trabajo {job.id} archivo={job.original_filename}")
                if sender is None:
                    raise RuntimeError("Impresora no disponible")
                images = self._pdf_to_images(job.pdf_path)
                for img_path in images:
                    img = Image.open(img_path)
                    img = to_thermal_mono_dither(img, target_width=self.paper_width_px)
                    sender.print_image(img)
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
                    for p in locals().get('images', []):
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
            "200",
            pdf_path,
            out_prefix,
        ]
        print(f"# Ejecutando rasterización: {' '.join(cmd)}")
        subprocess.run(cmd, check=True)
        # Recoger archivos generados
        base = os.path.basename(pdf_path) + "_page"
        dirp = self.queue.get_jobs_dir()
        files = []
        for i in range(1, 1000):
            candidate = os.path.join(dirp, f"{base}-{i}.png")
            if os.path.exists(candidate):
                files.append(candidate)
            else:
                if i == 1:
                    raise RuntimeError("No se generaron imágenes del PDF")
                break
        return files
