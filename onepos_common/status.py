# -*- coding: utf-8 -*-
# Monitor de disponibilidad de impresora compartido por las utilidades.
# Un hilo daemon verifica el estado cada pocos segundos y expone un dict
# thread-safe con el último resultado.

import time
import threading
import platform


def create_printer_status() -> dict:
    # Estado inicial compartido (mismo contrato para todas las utilidades).
    return {
        "available": False,
        "last_check": 0,
        "device_path": None,
        "printer_name": None,
        "error": None,
    }


def start_printer_monitor(status: dict, interval: int = 3) -> "PrinterMonitor":
    # Lanza el hilo de monitoreo y devuelve el monitor (con snapshot()).
    monitor = PrinterMonitor(status, interval)
    monitor.start()
    print("# Monitor de impresora iniciado")
    return monitor


class PrinterMonitor:
    def __init__(self, status: dict, interval: int):
        self._status = status
        self._interval = interval
        self._lock = threading.Lock()

    def snapshot(self) -> dict:
        # Copia consistente del estado para lecturas (endpoints HTTP).
        with self._lock:
            return dict(self._status)

    def start(self) -> threading.Thread:
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread

    def _check_windows(self):
        # Windows: resolver nombre y verificar apertura vía spooler
        try:
            from onepos_common.windows_spooler import resolve_printer_name
            printer_name = resolve_printer_name()
        except Exception as e:
            printer_name = None
            error_msg = f"No se pudo resolver la impresora de Windows: {e}"
            print(f"# {error_msg}")
        is_available = False
        error_msg = None

        if not printer_name:
            error_msg = "No hay ninguna impresora instalada en Windows"
        else:
            try:
                import win32print
                # Intentar abrir y cerrar la impresora
                h = win32print.OpenPrinter(printer_name)
                win32print.ClosePrinter(h)
                is_available = True
            except Exception as e:
                error_msg = f"No se puede acceder a '{printer_name}': {str(e)}"
                print(f"# {error_msg}")

        with self._lock:
            self._status["available"] = is_available
            self._status["device_path"] = None
            self._status["printer_name"] = printer_name if is_available else None
            self._status["error"] = error_msg
            self._status["last_check"] = int(time.time())

    def _check_linux(self):
        # Linux: detector USB existente
        from onepos_common.usb_detector import USBPrinterDetector
        detector = USBPrinterDetector()
        printers = detector.scan_for_printers()

        with self._lock:
            if printers:
                self._status["available"] = True
                self._status["device_path"] = printers[0].device_path
                self._status["printer_name"] = printers[0].friendly_name
                self._status["error"] = None
            else:
                self._status["available"] = False
                self._status["device_path"] = None
                self._status["printer_name"] = None
                self._status["error"] = "No se detectaron impresoras USB"
            self._status["last_check"] = int(time.time())

    def run(self):
        while True:
            try:
                if platform.system() == "Windows":
                    self._check_windows()
                else:
                    self._check_linux()
            except Exception as e:
                error_msg = f"Error en monitoreo de impresora: {str(e)}"
                print(f"# {error_msg}")
                with self._lock:
                    self._status["available"] = False
                    self._status["error"] = error_msg
                    self._status["last_check"] = int(time.time())
            time.sleep(self._interval)
