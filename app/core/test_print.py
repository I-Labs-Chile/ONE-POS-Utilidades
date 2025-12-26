# -*- coding: utf-8 -*-
# Lógica de prueba de impresora
# Envía un ticket de bienvenida y un código QR con la URL local

import os
import time
from typing import Dict

from app.core.worker import PrintWorker
from app.printer.manager import create_sender
from app.utils.network import get_primary_ip


def _build_selftest_url() -> str:
    # Construye la URL pública del servidor usando la IP local y el puerto
    ip = get_primary_ip()
    try:
        port = int(os.environ.get("SERVER_PORT", "8080"))
    except Exception:
        port = 8080
    return f"http://{ip}:{port}/"


def run_printer_selftest(worker: PrintWorker) -> Dict[str, object]:
    # Ejecuta una impresión de prueba para validar conexión con la impresora
    # Devuelve un diccionario con el resultado para exponerlo por la API
    resultado: Dict[str, object] = {
        "ok": False,
        "url": "",
        "detalle": "",
    }
    url = _build_selftest_url()
    resultado["url"] = url
    try:
        print("# Iniciando prueba de impresora")
        # CAMBIO: Usar create_sender en lugar de instanciar EscposSender directamente
        # Esto respeta el switch de plataforma Windows/Linux
        sender = create_sender(
            interface=worker.printer_interface,
            host=worker.printer_host,
            port=worker.printer_port,
            usb_vendor=worker.usb_vendor,
            usb_product=worker.usb_product,
        )
        if sender is None:
            raise RuntimeError("No se pudo crear el backend de impresora")
            
        print("# Impresora conectada correctamente para prueba de conexión")
        sender.init()
        sender.text("")
        sender.text("================================")
        sender.text("  ONE-POS UTILIDADES")
        sender.text("  Servidor de Impresion ESC/POS")
        sender.text("================================")
        sender.feed(1)
        sender.text("[OK] Impresora conectada")
        sender.text("[OK] Servidor iniciado")
        sender.text("")
        sender.text(time.strftime("Fecha: %Y-%m-%d %H:%M:%S"))
        sender.feed(2)
        sender.text("Escanea el codigo QR para")
        sender.text("acceder a la interfaz web:")
        sender.feed(2)
        # NOTA: print_qr puede no estar implementado en WindowsEscposSender
        # Verificar si existe el método antes de llamarlo
        if hasattr(sender, 'print_qr'):
            sender.print_qr(url, size=12)
        else:
            sender.text(f"URL: {url}")
        sender.feed(2)
        sender.text(f"URL: {url}")
        sender.feed(3)
        sender.cut()
        sender.close()
        resultado["ok"] = True
        resultado["detalle"] = "Prueba de impresión completada"
        print("# Prueba de impresión completada exitosamente")
        
    except Exception as e:
        print(f"# Error en prueba de impresora: {e}")
        resultado["detalle"] = str(e)
        
    return resultado
