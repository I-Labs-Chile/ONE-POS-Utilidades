# -*- coding: utf-8 -*-
# Backend Windows: impresión ESC/POS mediante Print Spooler con RAW
# Decisiones técnicas y hallazgos (documentación para mantenimiento):
# - La impresora aparece como "USB001" en Windows; el driver POS no expone un dispositivo accesible.
# - No hay acceso directo a nodos como en Linux (/dev/usb/lp*); Windows requiere usar el spooler lógico.
# - ESC/POS funciona de forma fiable enviando trabajos RAW al spooler (StartDocPrinter con DataType="RAW").
# - El spooler consume los jobs incluso si el driver filtra/ignora comandos ESC/POS; por eso el corte debe considerarse opcional.
# - Este enfoque se validó imprimiendo texto desde Python usando win32print con StartDocPrinter/WritePrinter/EndDocPrinter.

from typing import Optional
from PIL import Image
import win32print

class WindowsSpooler:
    def __init__(self, printer_name: str):
        self.printer_name = printer_name
        self.hPrinter = None
        self._page_started = False
        self._doc_started = False

    def connect(self) -> bool:
        # Abre la impresora y comienza un documento RAW
        self.hPrinter = win32print.OpenPrinter(self.printer_name)
        win32print.StartDocPrinter(self.hPrinter, 1, ("ESC/POS Job", None, "RAW"))
        self._doc_started = True
        win32print.StartPagePrinter(self.hPrinter)
        self._page_started = True
        return True

    def send_raw(self, data: bytes) -> bool:
        if not (self.hPrinter and self._doc_started and self._page_started):
            raise RuntimeError("Spooler no conectado")
        win32print.WritePrinter(self.hPrinter, data)
        return True

    def disconnect(self):
        try:
            if self.hPrinter:
                if self._page_started:
                    win32print.EndPagePrinter(self.hPrinter)
                if self._doc_started:
                    win32print.EndDocPrinter(self.hPrinter)
                win32print.ClosePrinter(self.hPrinter)
        finally:
            self.hPrinter = None
            self._page_started = False
            self._doc_started = False


class WindowsEscposSender:
    # Compositor de comandos ESC/POS que envía bytes al spooler RAW
    # Mantiene los mismos bytes ESC/POS que Linux; el corte se intenta pero es opcional.
    def __init__(self, printer_name: str):
        self._spooler = WindowsSpooler(printer_name)
        self._spooler.connect()

    def _send(self, data: bytes):
        self._spooler.send_raw(data)

    def init(self):
        self._send(b"\x1B@")

    def cut(self):
        # El corte no es confiable en Windows (drivers pueden filtrar)
        try:
            self._send(b"\x1DVA0")
        except Exception:
            pass

    def feed(self, lines: int = 1):
        if lines > 0:
            self._send(b"\n" * lines)

    def text(self, content: str, encoding: str = "cp437"):
        if content:
            self._send(content.encode(encoding, errors="replace") + b"\n")

    def print_qr(self, data: str, size: int = 6):
        """
        Imprime código QR usando comandos ESC/POS (modelo 2).
        Tamaño: 1-16 (puntos por módulo)
        """
        try:
            # ESC/POS QR Code commands (modelo 2)
            qr_data = data.encode('utf-8')
            
            # Seleccionar modelo QR (modelo 2)
            self._send(b'\x1D\x28\x6B\x04\x00\x31\x41\x32\x00')
            
            # Establecer tamaño de módulo
            size = max(1, min(16, size))  # Limitar entre 1-16
            self._send(b'\x1D\x28\x6B\x03\x00\x31\x43' + bytes([size]))
            
            # Nivel de corrección de errores (L=48, M=49, Q=50, H=51)
            self._send(b'\x1D\x28\x6B\x03\x00\x31\x45\x30')  # Nivel L
            
            # Almacenar datos del QR
            data_len = len(qr_data) + 3
            pl = data_len & 0xFF
            ph = (data_len >> 8) & 0xFF
            self._send(b'\x1D\x28\x6B' + bytes([pl, ph]) + b'\x31\x50\x30' + qr_data)
            
            # Imprimir QR almacenado
            self._send(b'\x1D\x28\x6B\x03\x00\x31\x51\x30')
            
        except Exception as e:
            # Si falla la impresión del QR, simplemente ignorar
            print(f"# Advertencia: No se pudo imprimir código QR: {e}")
            pass

    def print_image(self, img: Image.Image):
        # Igual al raster ESC/POS usado en Linux (GS v 0)
        self.init()
        w, h = img.size
        bytes_per_row = (w + 7) // 8
        data = bytearray()
        for y in range(h):
            row = 0
            row_bytes = bytearray()
            for x in range(w):
                if img.getpixel((x, y)) == 0:
                    row |= 1 << (7 - (x % 8))
                if x % 8 == 7:
                    row_bytes.append(row)
                    row = 0
            if w % 8 != 0:
                row_bytes.append(row)
            data.extend(b"\x1Dv0")
            data.extend(bytes([0x00]))
            data.extend(bytes([bytes_per_row & 0xFF, (bytes_per_row >> 8) & 0xFF]))
            data.extend(bytes([1, 0]))
            data.extend(row_bytes)
        data.extend(b"\n\n")
        self._send(bytes(data))

    def close(self):
        self._spooler.disconnect()