# -*- coding: utf-8 -
 # Envío de comandos ESC/POS por TCP o USB con detección y robustez

import socket
from typing import Optional
from PIL import Image
from app.utils.usb_printer import USBPrinterBackend

# Intentar importar PyUSB
try:
    import usb.core
    import usb.util
    HAS_PYUSB = True
except Exception:
    HAS_PYUSB = False

class USBCommunicationError(Exception):
    pass

class _UsbFileBackend:
    # Backend que escribe directamente a un archivo de dispositivo
    def __init__(self, device_path: str = "/dev/usb/lp0"):
        self.device_path = device_path
        self.handle = None
        self.connected = False

    def auto_detect_path(self) -> str:
        # Probar rutas comunes en Linux
        for path in ["/dev/usb/lp0", "/dev/usb/lp1", "/dev/lp0", "/dev/lp1"]:
            try:
                import os
                if os.path.exists(path) and os.access(path, os.W_OK):
                    return path
            except Exception:
                pass
        return self.device_path

    def open(self) -> bool:
        import os
        # Detectar automáticamente si no existe la ruta
        if not self.device_path or not os.path.exists(self.device_path):
            self.device_path = self.auto_detect_path()
        if not os.path.exists(self.device_path):
            return False
        try:
            self.handle = open(self.device_path, 'wb', buffering=0)
            self.connected = True
            return True
        except Exception:
            self.connected = False
            self.handle = None
            return False

    def write(self, data: bytes) -> int:
        if not self.connected or not self.handle:
            raise USBCommunicationError("Archivo de dispositivo no abierto")
        written = self.handle.write(data)
        self.handle.flush()
        return written

    def close(self):
        try:
            if self.handle:
                self.handle.close()
        finally:
            self.handle = None
            self.connected = False

class _UsbLibBackend:
    # Backend que usa PyUSB/libusb con escritura por paquetes BULK
    def __init__(self, timeout: int = 5000, vendor_id: Optional[int] = None, product_id: Optional[int] = None):
        if not HAS_PYUSB:
            raise ImportError("PyUSB no disponible")
        self.timeout = timeout
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.dev = None
        self.ep_out = None
        self.ep_in = None
        # Lista de impresoras térmicas comunes
        self.known = [
            (0x04b8, 0x0202), # Epson TM series
            (0x04b8, 0x0e03), # Epson TM-T20
            (0x04b8, 0x0e15), # Epson TM-T82
            (0x0fe6, 0x811e), # Star TSP650
            (0x1504, 0x0006), # Citizen CT-S310
            (0x2d84, 0x0011), # Genérica
        ]

    def _find_device(self):
        # Buscar por vendor/product o por lista conocida o por clase impresora
        if self.vendor_id and self.product_id:
            self.dev = usb.core.find(idVendor=self.vendor_id, idProduct=self.product_id)
            if self.dev:
                return
        for v, p in self.known:
            d = usb.core.find(idVendor=v, idProduct=p)
            if d:
                self.dev = d
                return
        # Por clase de dispositivo impresora (7)
        try:
            self.dev = usb.core.find(bDeviceClass=7)
        except Exception:
            self.dev = None

    def open(self) -> bool:
        self._find_device()
        if not self.dev:
            return False
        try:
            import platform
            if platform.system() == "Linux":
                try:
                    if self.dev.is_kernel_driver_active(0):
                        self.dev.detach_kernel_driver(0)
                except Exception:
                    pass
            try:
                self.dev.set_configuration()
            except usb.core.USBError as e:
                # Errno 16 (ocupado) es aceptable
                try:
                    if e.errno != 16:
                        raise
                except Exception:
                    raise
            cfg = self.dev.get_active_configuration()
            intf = cfg[(0,0)]
            self.ep_out = None
            self.ep_in = None
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT and usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                    self.ep_out = ep
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN and usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                    self.ep_in = ep
            if not self.ep_out:
                return False
            return True
        except Exception:
            self.dev = None
            self.ep_out = None
            self.ep_in = None
            return False

    def write(self, data: bytes) -> int:
        if not self.dev or not self.ep_out:
            raise USBCommunicationError("Dispositivo USB no abierto")
        total = 0
        max_packet = self.ep_out.wMaxPacketSize or 64
        for i in range(0, len(data), max_packet):
            chunk = data[i:i+max_packet]
            written = self.ep_out.write(chunk, self.timeout)
            total += written
        return total

    def close(self):
        try:
            if self.dev:
                usb.util.dispose_resources(self.dev)
        finally:
            self.dev = None
            self.ep_out = None
            self.ep_in = None

class EscposSender:
    def __init__(self, interface: str = "tcp", host: str = "127.0.0.1", port: int = 9100, usb_vendor: int = 0, usb_product: int = 0):
        self.interface = interface
        self.host = host
        self.port = port
        self.usb_vendor = usb_vendor
        self.usb_product = usb_product
        self.sock: Optional[socket.socket] = None
        self._usb_backend_file: Optional[_UsbFileBackend] = None
        self._usb_backend_lib: Optional[_UsbLibBackend] = None
        self._usb_backend_printer: Optional[USBPrinterBackend] = None
        self._init_device()

    def _init_device(self):
        if self.interface == "tcp":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            try:
                self.sock.connect((self.host, self.port))
                print("# Conectado a impresora TCP")
            except Exception as e:
                raise RuntimeError(f"No se pudo conectar a la impresora TCP: {e}")
        elif self.interface == "usb":
            # Intentar primero backend especializado de impresoras USB basado en detección previa
            try:
                self._usb_backend_printer = USBPrinterBackend()
                if not self._usb_backend_printer.connect():
                    self._usb_backend_printer = None
                    raise RuntimeError("No se pudo conectar a la impresora USB mediante auto detección")
                print("# Conectado a impresora USB mediante auto detección de dispositivo")
            except Exception as e:
                # Si falla, se mantiene compatibilidad con PyUSB o archivo de dispositivo clásico
                print(f"# Fallback a backends USB clásicos por error: {e}")
                if HAS_PYUSB:
                    self._usb_backend_lib = _UsbLibBackend(timeout=5000, vendor_id=self.usb_vendor or None, product_id=self.usb_product or None)
                    if not self._usb_backend_lib.open():
                        self._usb_backend_lib = None
                        self._usb_backend_file = _UsbFileBackend()
                        if not self._usb_backend_file.open():
                            raise RuntimeError("No se pudo abrir la impresora USB ni por libusb ni por archivo de dispositivo")
                        print("# Conectado a impresora USB por archivo de dispositivo")
                    else:
                        print("# Conectado a impresora USB por libusb")
                else:
                    self._usb_backend_file = _UsbFileBackend()
                    if not self._usb_backend_file.open():
                        raise RuntimeError("No se pudo abrir la impresora USB por archivo de dispositivo")
                    print("# Conectado a impresora USB por archivo de dispositivo")
        else:
            raise RuntimeError("Interfaz de impresora desconocida")

    def _send(self, data: bytes):
        if self.interface == "tcp":
            self.sock.sendall(data)
        else:
            if self._usb_backend_printer:
                ok = self._usb_backend_printer.send_raw(data)
                if not ok:
                    raise USBCommunicationError("No se pudieron enviar datos a la impresora USB")
            elif self._usb_backend_lib:
                self._usb_backend_lib.write(data)
            elif self._usb_backend_file:
                self._usb_backend_file.write(data)
            else:
                raise USBCommunicationError("USB backend no inicializado")

    def init(self):
        self._send(b"\x1B@")

    def cut(self):
        # Corte parcial por defecto
        self._send(b"\x1DVA0")

    def feed(self, lines: int = 1):
        # Avance de papel una cantidad de líneas
        if lines <= 0:
            return
        self._send(b"\n" * lines)

    def text(self, content: str, encoding: str = "utf-8"):
        # Imprime una línea de texto simple
        if not content:
            return
        self.init()
        self._send(content.encode(encoding, errors="replace") + b"\n")

    def print_qr(self, data: str, size: int = 4, ec_level: int = 48):
        # Imprime un código QR usando comandos ESC/POS compatibles con Epson
        # data: texto/URL a codificar
        # size: tamaño de módulo (1-16)
        # ec_level: nivel de corrección (48=L,49=M,50=Q,51=H)
        if not data:
            return
        self.init()
        payload = data.encode("utf-8", errors="replace")
        if size < 1:
            size = 1
        if size > 16:
            size = 16
        if ec_level not in (48, 49, 50, 51):
            ec_level = 48
        # Tamaño de módulo
        self._send(b"\x1D(k" + bytes([3, 0, 49, 67, size]))
        # Nivel de corrección de errores
        self._send(b"\x1D(k" + bytes([3, 0, 49, 69, ec_level]))
        # Almacenar datos del QR
        length = len(payload) + 3
        pL = length & 0xFF
        pH = (length >> 8) & 0xFF
        self._send(b"\x1D(k" + bytes([pL, pH, 49, 80, 48]) + payload)
        # Imprimir QR
        self._send(b"\x1D(k" + bytes([3, 0, 49, 81, 48]))
        self.feed(2)

    def print_image(self, img: Image.Image):
        # Convertir imagen 1bpp en formato ESC/POS raster
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
            # Comando raster line (GS v 0)
            data.extend(b"\x1Dv0")
            data.extend(bytes([0x00]))
            data.extend(bytes([bytes_per_row & 0xFF, (bytes_per_row >> 8) & 0xFF]))
            data.extend(bytes([1, 0]))
            data.extend(row_bytes)
        data.extend(b"\n\n")
        self._send(bytes(data))

    def close(self):
        try:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.sock.close()
            if self._usb_backend_printer:
                self._usb_backend_printer.disconnect()
            if self._usb_backend_lib:
                self._usb_backend_lib.close()
            if self._usb_backend_file:
                self._usb_backend_file.close()
        finally:
            self.sock = None
            self._usb_backend_printer = None
            self._usb_backend_lib = None
            self._usb_backend_file = None
