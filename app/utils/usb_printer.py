from typing import Optional
import logging
import time
import os

from app.utils.usb_detector import USBPrinterDetector, USBPrinterInfo

logger = logging.getLogger(__name__)

class USBPrinterBackend:

    # Backend para operar una impresora USB mediante nodo de dispositivo.
    def __init__(self, device_path: Optional[str] = None):

        # Ruta al nodo de dispositivo (ej: /dev/usb/lp0). Si es None, se detectará.
        self.device_path = device_path
        self.device_handle = None
        self.is_connected = False
        self.detector = USBPrinterDetector()
        self.current_printer: Optional[USBPrinterInfo] = None

        logger.info("USBPrinterBackend inicializado")

        # Auto-detect si no se especificó device
        if not self.device_path:
            logger.info("No se especificó ruta de dispositivo, se auto-detectará al conectar")
    
    def connect(self) -> bool:

        # Intento de conexión a la impresora. Realiza auto-detección si es necesario.
        try:
            if not self.device_path:
                logger.info("Auto-detectando impresora...")
                printers = self.detector.scan_for_printers()

                if not printers:
                    logger.error("No se detectaron impresoras")
                    logger.info("Verifique:")
                    logger.info("   1. La impresora está conectada por USB")
                    logger.info("   2. La impresora está encendida")
                    logger.info("   3. El usuario tiene permisos (agregar a grupos lp/lpadmin)")
                    return False

                # Usar la primera impresora detectada
                self.current_printer = printers[0]
                self.device_path = self.current_printer.device_path

                logger.info(f"Auto-detectada: {self.current_printer.friendly_name}")
                logger.info(f"   Dispositivo: {self.device_path}")

                if self.current_printer.vendor_id:
                    logger.info(f"   ID de proveedor: {self.current_printer.vendor_id}")
                if self.current_printer.product_id:
                    logger.info(f"   ID de producto: {self.current_printer.product_id}")

                if self.detector.is_thermal_printer(self.current_printer):
                    logger.info("   Impresora térmica detectada")

            # Verificar que el dispositivo existe
            if not os.path.exists(self.device_path):
                logger.error(f"Dispositivo no encontrado: {self.device_path}")
                return False

            # Verificar permisos de escritura
            if not self.detector.test_printer_connection(self.device_path):
                logger.error(f"No se puede escribir en {self.device_path}")
                logger.info("Intente: sudo usermod -a -G lp $USER")
                logger.info("Luego cierre sesión y vuelva a ingresar")
                return False

            # Abrir dispositivo en modo binario sin buffering
            logger.info(f"Conectando a {self.device_path}...")
            self.device_handle = open(self.device_path, 'wb', buffering=0)
            self.is_connected = True

            # Enviar comando de inicialización ESC @
            self._send_init_command()

            logger.info(f"Conectado a la impresora: {self.device_path}")
            return True

        except PermissionError:
            logger.error(f"Permiso denegado: {self.device_path}")
            logger.info("Ejecutar: sudo chmod 666 {self.device_path}")
            logger.info("O agregar usuario al grupo lp: sudo usermod -a -G lp $USER")
            return False
        except Exception as e:
            logger.error(f"Falló la conexión: {e}")
            return False
    
    # Envía el comando de inicialización ESC @ a la impresora.
    def _send_init_command(self):

        try:
            init_cmd = b'\x1b@'
            self.device_handle.write(init_cmd)
            self.device_handle.flush()
            time.sleep(0.1)
            logger.debug("Comando de inicialización enviado")
        except Exception as e:
            logger.warning(f"Error al enviar comando de inicialización: {e}")
    
    # Cierra el handle del dispositivo y marca como desconectado.
    def disconnect(self):

        if self.device_handle:
            try:
                self.device_handle.close()
                logger.info(f"Desconectado de {self.device_path}")
            except:
                pass
            finally:
                self.device_handle = None
                self.is_connected = False
    
    # Envía datos binarios crudos a la impresora; intenta conectar si no está conectado.
    def send_raw(self, data: bytes) -> bool:

        if not self.is_connected:
            logger.warning("Impresora no conectada, intentando auto-conectar...")
            if not self.connect():
                logger.error("Fallo en auto-conexión")
                return False

        try:
            logger.debug(f"Enviando {len(data)} bytes a la impresora...")
            self.device_handle.write(data)
            self.device_handle.flush()
            logger.info(f"{len(data)} bytes enviados correctamente")
            return True

        except Exception as e:
            logger.error(f"Error al enviar datos: {e}")
            self.is_connected = False
            return False

    # Indica si el backend está conectado y listo para enviar datos.
    def is_ready(self) -> bool:
        return self.is_connected
    
    # Devuelve un diccionario con el estado actual de la impresora/backend.
    def get_status(self) -> dict:
        status = {
            'connected': self.is_connected,
            'device_path': self.device_path,
            'ready': self.is_ready()
        }

        if self.current_printer:
            status.update({
                'manufacturer': self.current_printer.manufacturer,
                'product': self.current_printer.product,
                'vendor_id': self.current_printer.vendor_id,
                'product_id': self.current_printer.product_id,
                'serial': self.current_printer.serial,
                'is_thermal': self.detector.is_thermal_printer(self.current_printer)
            })
        return status
    
    # Reescanea el sistema y devuelve una lista con metadatos básicos de cada impresora.
    def rescan_printers(self) -> list:
        printers = self.detector.scan_for_printers()
        return [
            {
                'device': p.device_path,
                'name': p.friendly_name,
                'vendor_id': p.vendor_id,
                'product_id': p.product_id,
                'is_thermal': self.detector.is_thermal_printer(p)
            }
            for p in printers
        ]
