import asyncio
import logging
import platform
import threading
import time
from typing import Optional, Dict, Any, List, Tuple
from abc import ABC, abstractmethod

try:
    import usb.core
    import usb.util
    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False

logger = logging.getLogger(__name__)

class USBError(Exception):
    pass

class USBDeviceNotFoundError(USBError):
    pass

class USBCommunicationError(USBError):
    pass

class USBHandler(ABC):
    
    @abstractmethod
    async def open_device(self, vendor_id: Optional[int] = None, product_id: Optional[int] = None) -> bool:
        pass
    
    @abstractmethod
    async def write(self, data: bytes) -> int:
        pass
    
    @abstractmethod
    async def read(self, size: int, timeout: int = 1000) -> bytes:
        pass
    
    @abstractmethod
    async def close(self):
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        pass
    
    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        pass

class LibUSBHandler(USBHandler):
    
    def __init__(self, timeout: int = 5000):

        if not HAS_PYUSB:
            raise ImportError("PyUSB no disponible")
        
        self.device = None
        self.endpoint_out = None
        self.endpoint_in = None
        self.timeout = timeout
        self.is_open = False
        self.device_lock = threading.Lock()
        
        # Configuraciones conocidas de impresoras térmicas
        self.thermal_printer_configs = [
            # (vendor_id, product_id, interface, out_endpoint, in_endpoint)
            (0x04b8, 0x0202, 0, 0x01, 0x82),  # Epson TM series
            (0x04b8, 0x0e03, 0, 0x01, 0x82),  # Epson TM-T20
            (0x04b8, 0x0e15, 0, 0x01, 0x82),  # Epson TM-T82
            (0x0fe6, 0x811e, 0, 0x02, 0x81),  # Star TSP650
            (0x1504, 0x0006, 0, 0x02, 0x81),  # Citizen CT-S310
            (0x2d84, 0x0011, 0, 0x01, 0x82),  # Generic thermal printer
        ]
    
    async def open_device(self, vendor_id: Optional[int] = None, product_id: Optional[int] = None) -> bool:
        with self.device_lock:
            if self.is_open:
                return True
            
            try:
                # Encontrar dispositivo
                if vendor_id and product_id:
                    self.device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
                else:
                    self.device = self._find_thermal_printer()
                
                if self.device is None:
                    raise USBDeviceNotFoundError("No se encontró ninguna impresora térmica compatible")
                
                # Configurar dispositivo
                await self._configure_device()
                
                self.is_open = True
                logger.info(f"Dispositivo USB abierto: {self._format_device_id()}")
                return True
                
            except Exception as e:
                logger.error(f"Error al abrir el dispositivo USB: {e}")
                self.device = None
                self.is_open = False
                return False
    
    async def write(self, data: bytes) -> int:
        if not self.is_open or not self.endpoint_out:
            raise USBCommunicationError("Dispositivo no abierto o sin endpoint de salida")
        
        try:
            # Dividir datos en fragmentos si es necesario
            max_packet_size = self.endpoint_out.wMaxPacketSize or 64
            total_written = 0
            
            for i in range(0, len(data), max_packet_size):
                chunk = data[i:i + max_packet_size]
                written = self.endpoint_out.write(chunk, self.timeout)
                total_written += written
                
                # Pequeña demora entre fragmentos para no abrumar al dispositivo
                if i + max_packet_size < len(data):
                    await asyncio.sleep(0.001)
            
            logger.debug(f"Se escribieron {total_written} bytes en el dispositivo USB")
            return total_written
            
        except usb.core.USBTimeoutError:
            raise USBCommunicationError("Tiempo de espera de escritura USB agotado")
        except usb.core.USBError as e:
            raise USBCommunicationError(f"Error de escritura USB: {e}")
    
    async def read(self, size: int, timeout: int = 1000) -> bytes:
        if not self.is_open or not self.endpoint_in:
            raise USBCommunicationError("Dispositivo no abierto o sin endpoint de entrada")
        
        try:
            data = self.endpoint_in.read(size, timeout or self.timeout)
            return bytes(data)
            
        except usb.core.USBTimeoutError:
            # El tiempo de espera es esperado para dispositivos que no tienen datos
            return b""
        except usb.core.USBError as e:
            raise USBCommunicationError(f"Error de lectura USB: {e}")
    
    async def close(self):
        with self.device_lock:
            if self.device:
                try:
                    usb.util.dispose_resources(self.device)
                except:
                    pass  # Ignorar errores de eliminación
                
                self.device = None
                self.endpoint_out = None
                self.endpoint_in = None
            
            self.is_open = False
            logger.debug("Dispositivo USB cerrado")
    
    def is_connected(self) -> bool:
        return self.is_open and self.device is not None
    
    def get_device_info(self) -> Dict[str, Any]:
        if not self.device:
            return {}
        
        try:
            return {
                'vendor_id': f"{self.device.idVendor:04x}",
                'product_id': f"{self.device.idProduct:04x}",
                'manufacturer': usb.util.get_string(self.device, self.device.iManufacturer) or "Desconocido",
                'product': usb.util.get_string(self.device, self.device.iProduct) or "Desconocido",
                'serial_number': usb.util.get_string(self.device, self.device.iSerialNumber) or "Desconocido",
                'bus': self.device.bus,
                'address': self.device.address,
                'speed': getattr(self.device, 'speed', 'Desconocido'),
                'handler': 'LibUSB'
            }
        except Exception as e:
            logger.warning(f"Error al obtener información del dispositivo: {e}")
            return {
                'vendor_id': f"{self.device.idVendor:04x}",
                'product_id': f"{self.device.idProduct:04x}",
                'manufacturer': "Desconocido",
                'product': "Desconocido",
                'error': str(e),
                'handler': 'LibUSB'
            }
    
    def _find_thermal_printer(self):
        # Intentar primero con configuraciones conocidas
        for vendor_id, product_id, _, _, _ in self.thermal_printer_configs:
            device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
            if device:
                logger.info(f"Impresora conocida encontrada: {vendor_id:04x}:{product_id:04x}")
                return device
        
        # Intentar por clase USB (impresora)
        device = usb.core.find(bDeviceClass=7)  # Clase de impresora
        if device:
            logger.info(f"Impresora encontrada por clase: {device.idVendor:04x}:{device.idProduct:04x}")
            return device
        
        # Buscar en todos los dispositivos interfaces de impresora
        devices = usb.core.find(find_all=True)
        for device in devices:
            try:
                for cfg in device:
                    for intf in cfg:
                        if intf.bInterfaceClass == 7:  # Clase de impresora
                            logger.info(f"Interfaz de impresora encontrada: {device.idVendor:04x}:{device.idProduct:04x}")
                            return device
            except usb.core.USBError:
                continue
        
        return None
    
    async def _configure_device(self):
        if not self.device:
            raise USBCommunicationError("No hay dispositivo para configurar")
        
        try:
            # Desvincular controlador del kernel si es necesario (Linux)
            if platform.system() == "Linux":
                try:
                    if self.device.is_kernel_driver_active(0):
                        self.device.detach_kernel_driver(0)
                        logger.debug("Controlador del kernel desvinculado")
                except usb.core.USBError:
                    pass  # Puede que no sea necesario
            
            # Establecer configuración
            try:
                self.device.set_configuration()
            except usb.core.USBError as e:
                if e.errno != 16:  # Dispositivo ocupado es a menudo OK
                    raise USBCommunicationError(f"Error al establecer la configuración: {e}")
            
            # Encontrar endpoints
            cfg = self.device.get_active_configuration()
            intf = cfg[(0, 0)]
            
            self.endpoint_out = None
            self.endpoint_in = None
            
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                        self.endpoint_out = ep
                        logger.debug(f"Endpoint BULK OUT encontrado: {ep.bEndpointAddress:02x}")
                elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                        self.endpoint_in = ep
                        logger.debug(f"Endpoint BULK IN encontrado: {ep.bEndpointAddress:02x}")
            
            if not self.endpoint_out:
                raise USBCommunicationError("No se encontró ningún endpoint BULK OUT")
            
            # El endpoint de entrada es opcional para muchas impresoras térmicas
            if not self.endpoint_in:
                logger.warning("No se encontró ningún endpoint BULK IN - el dispositivo puede ser solo de salida")
                
        except Exception as e:
            if isinstance(e, USBCommunicationError):
                raise
            raise USBCommunicationError(f"La configuración del dispositivo falló: {e}")
    
    def _format_device_id(self) -> str:
        if not self.device:
            return "Desconocido"
        return f"{self.device.idVendor:04x}:{self.device.idProduct:04x}"

class FileUSBHandler(USBHandler):
    
    def __init__(self, device_path: str = "/dev/usb/lp0"):
        self.device_path = device_path
        self.is_open = False
        self.device_info = {}
    
    async def open_device(self, vendor_id: Optional[int] = None, product_id: Optional[int] = None) -> bool:
        try:
            # Probar si podemos escribir en el archivo de dispositivo
            with open(self.device_path, 'wb') as f:
                pass  # Solo probar apertura
            
            # Obtener información del archivo
            import os
            import stat
            
            if os.path.exists(self.device_path):
                st = os.stat(self.device_path)
                self.device_info = {
                    'device_path': self.device_path,
                    'device_type': 'character' if stat.S_ISCHR(st.st_mode) else 'block',
                    'permissions': oct(st.st_mode)[-3:],
                    'writable': os.access(self.device_path, os.W_OK),
                    'handler': 'File'
                }
            logger.info(f"Archivo de dispositivo abierto: {self.device_path}")
            self.is_open = True
            return True
            
        except Exception as e:
            logger.error(f"Error al abrir el archivo de dispositivo {self.device_path}: {e}")
            self.is_open = False
            return False
    
    async def write(self, data: bytes) -> int:
        if not self.is_open:
            raise USBCommunicationError("Archivo de dispositivo no abierto")
        
        try:
            with open(self.device_path, 'wb') as f:
                written = f.write(data)
                f.flush()
            
            logger.debug(f"Se escribieron {written} bytes en {self.device_path}")
            return written
            
        except Exception as e:
            raise USBCommunicationError(f"Error al escribir en {self.device_path}: {e}")
    
    async def read(self, size: int, timeout: int = 1000) -> bytes:
        return b""  # La mayoría de los archivos de dispositivo de impresoras no soportan lectura
    
    async def close(self):
        self.is_open = False
        logger.debug(f"Archivo de dispositivo cerrado: {self.device_path}")
    
    def is_connected(self) -> bool:
        return self.is_open
    
    def get_device_info(self) -> Dict[str, Any]:
        return self.device_info.copy()

def create_usb_handler(prefer_file: bool = False, **kwargs) -> USBHandler:

    # Verificar plataforma y disponibilidad
    system = platform.system()
    
    if prefer_file or not HAS_PYUSB:
        # Usar controlador basado en archivo
        device_path = kwargs.get('device_path', '/dev/usb/lp0')
        if system == "Linux":
            # Probar rutas comunes de dispositivos impresora en Linux
            for path in ['/dev/usb/lp0', '/dev/usb/lp1', '/dev/lp0', '/dev/lp1']:
                import os
                if os.path.exists(path):
                    device_path = path
                    break
        
        return FileUSBHandler(device_path)
    
    else:
        # Usar controlador libusb
        timeout = kwargs.get('timeout', 5000)
        return LibUSBHandler(timeout)

# Funciones utilitarias para el descubrimiento de dispositivos USB
async def list_usb_printers() -> List[Dict[str, Any]]:
    printers = []
    
    if HAS_PYUSB:
        try:
            # Encontrar todos los dispositivos de clase impresora
            devices = usb.core.find(find_all=True, bDeviceClass=7)  # Clase de impresora
            
            for device in devices:
                try:
                    printer_info = {
                        'vendor_id': f"{device.idVendor:04x}",
                        'product_id': f"{device.idProduct:04x}",
                        'manufacturer': usb.util.get_string(device, device.iManufacturer) or "Desconocido",
                        'product': usb.util.get_string(device, device.iProduct) or "Desconocido",
                        'bus': device.bus,
                        'address': device.address,
                        'method': 'usb_class'
                    }
                    printers.append(printer_info)
                except usb.core.USBError:
                    continue
                    
        except Exception as e:
            logger.warning(f"Error al listar dispositivos USB: {e}")
    
    # También verificar archivos de dispositivo en Linux
    if platform.system() == "Linux":
        import os
        for path in ['/dev/usb/lp0', '/dev/usb/lp1', '/dev/lp0', '/dev/lp1']:
            if os.path.exists(path):
                printers.append({
                    'device_path': path,
                    'method': 'device_file',
                    'accessible': os.access(path, os.W_OK)
                })
    
    return printers

if __name__ == "__main__":
    # Probar controlador USB
    async def test_usb_handler():
        """Probar la funcionalidad del controlador USB"""
        print("Probando controlador USB...")
        
        # Listar impresoras disponibles
        printers = await list_usb_printers()
        print(f"Se encontraron {len(printers)} impresoras:")
        for printer in printers:
            print(f"  {printer}")
        
        # Probar creación de controlador
        try:
            handler = create_usb_handler()
            print(f"Controlador creado: {type(handler).__name__}")
            
            # Intentar abrir dispositivo
            if await handler.open_device():
                info = handler.get_device_info()
                print(f"Información del dispositivo: {info}")
                await handler.close()
            else:
                print("Error al abrir el dispositivo")
                
        except Exception as e:
            print(f"Error al probar el controlador: {e}")
    
    # Ejecutar prueba
    asyncio.run(test_usb_handler())