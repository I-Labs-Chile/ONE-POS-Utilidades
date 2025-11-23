import asyncio
import logging
import platform
import time
from typing import Optional, List, Tuple, Dict, Any
import threading

try:
    import usb.core
    import usb.util
    HAS_PYUSB = True
except ImportError:
    HAS_PYUSB = False

# Try relative import first, fallback to absolute
try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

logger = logging.getLogger(__name__)

class PrinterConnectionError(Exception):
    pass

class PrinterNotFoundError(Exception):
    pass

class PrinterBackend:
    
    def __init__(self):
        self.device = None
        self.endpoint_out = None
        self.endpoint_in = None
        self.is_connected = False
        self.connection_lock = threading.Lock()
        self.last_error = None
        
        # Common thermal printer USB classes
        self.thermal_printer_classes = [
            (0x07, 0x01),  # Printer class, unidirectional
            (0x07, 0x02),  # Printer class, bidirectional  
            (0xFF, 0xFF),  # Vendor specific
        ]
        
        # Known thermal printer vendor/product IDs
        self.known_thermal_printers = [
            # (vendor_id, product_id, description)
            (0x04b8, 0x0202, "Epson TM series"),
            (0x04b8, 0x0e03, "Epson TM-T20"),
            (0x04b8, 0x0e15, "Epson TM-T82"),
            (0x0fe6, 0x811e, "Star TSP650"),
            (0x0fe6, 0x811f, "Star TSP700"),
            (0x0fe6, 0x8120, "Star TSP800"),
            (0x1504, 0x0006, "Citizen CT-S310"),
            (0x2d84, 0x0011, "Generic thermal printer"),
            (0x28e9, 0x0289, "Generic ESC/POS"),
        ]
    
    async def connect(self) -> bool:
        with self.connection_lock:
            if self.is_connected:
                return True
            
            try:
                self.device = await self._find_printer()
                if not self.device:
                    raise PrinterNotFoundError("No compatible thermal printer found")
                
                await self._setup_device()
                self.is_connected = True
                self.last_error = None
                
                logger.info(f"Connected to printer: {self._get_device_info()}")
                return True
                
            except Exception as e:
                self.last_error = str(e)
                logger.error(f"Failed to connect to printer: {e}")
                self.is_connected = False
                return False
    
    async def disconnect(self):
        with self.connection_lock:
            if self.device:
                try:
                    usb.util.dispose_resources(self.device)
                except:
                    pass  # Ignore disposal errors
                self.device = None
            
            self.endpoint_out = None
            self.endpoint_in = None
            self.is_connected = False
            
            logger.info("Disconnected from printer")
    
    async def send_raw(self, data: bytes) -> bool:
        if not self.is_connected:
            if not await self.connect():
                return False
        
        try:
            return await self._write_data(data)
        except Exception as e:
            logger.error(f"Failed to send data to printer: {e}")
            self.last_error = str(e)
            
            # Try to reconnect on communication error
            self.is_connected = False
            return False
    
    async def detect_printer(self) -> Optional[Dict[str, Any]]:
        try:
            device = await self._find_printer()
            if device:
                return {
                    'vendor_id': device.idVendor,
                    'product_id': device.idProduct,
                    'manufacturer': usb.util.get_string(device, device.iManufacturer) or "Unknown",
                    'product': usb.util.get_string(device, device.iProduct) or "Unknown",
                    'serial': usb.util.get_string(device, device.iSerialNumber) or "Unknown",
                    'bus': device.bus,
                    'address': device.address
                }
        except Exception as e:
            logger.debug(f"Error detecting printer: {e}")
        
        return None
    
    async def get_printer_status(self) -> Dict[str, Any]:
        status = {
            'connected': self.is_connected,
            'last_error': self.last_error,
            'device_info': None
        }
        
        if self.is_connected and self.device:
            status['device_info'] = self._get_device_info()
        
        return status
    
    async def _find_printer(self):
        if not HAS_PYUSB:
            raise PrinterConnectionError("PyUSB not available")
        
        # If specific vendor/product IDs are configured, try those first
        if settings.USB_VENDOR_ID and settings.USB_PRODUCT_ID:
            try:
                vendor_id = int(settings.USB_VENDOR_ID, 16) if isinstance(settings.USB_VENDOR_ID, str) else settings.USB_VENDOR_ID
                product_id = int(settings.USB_PRODUCT_ID, 16) if isinstance(settings.USB_PRODUCT_ID, str) else settings.USB_PRODUCT_ID
                
                device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
                if device:
                    logger.info(f"Found configured printer: {vendor_id:04x}:{product_id:04x}")
                    return device
            except Exception as e:
                logger.warning(f"Failed to find configured printer {settings.USB_VENDOR_ID}:{settings.USB_PRODUCT_ID}: {e}")
        
        # Search for known thermal printers
        for vendor_id, product_id, description in self.known_thermal_printers:
            device = usb.core.find(idVendor=vendor_id, idProduct=product_id)
            if device:
                logger.info(f"Found known thermal printer: {description} ({vendor_id:04x}:{product_id:04x})")
                return device
        
        # Search by USB class (printer)
        for class_code, subclass_code in self.thermal_printer_classes:
            device = usb.core.find(bDeviceClass=class_code, bDeviceSubClass=subclass_code)
            if device:
                logger.info(f"Found printer by USB class: {class_code:02x}:{subclass_code:02x}")
                return device
        
        # Last resort: look for any device with printer interface
        devices = usb.core.find(find_all=True)
        for device in devices:
            try:
                for cfg in device:
                    for intf in cfg:
                        if intf.bInterfaceClass == 7:  # Printer class
                            logger.info(f"Found printer interface: {device.idVendor:04x}:{device.idProduct:04x}")
                            return device
            except:
                continue
        
        return None
    
    async def _setup_device(self):
        if not self.device:
            raise PrinterConnectionError("No device to setup")
        
        try:
            # Detach kernel driver if necessary (Linux)
            if platform.system() == "Linux":
                try:
                    if self.device.is_kernel_driver_active(0):
                        self.device.detach_kernel_driver(0)
                        logger.debug("Detached kernel driver")
                except:
                    pass  # May not be necessary or supported
            
            # Set configuration
            try:
                self.device.set_configuration()
            except usb.core.USBError as e:
                if e.errno != 16:  # Device busy is OK
                    raise
            
            # Find bulk out endpoint
            cfg = self.device.get_active_configuration()
            intf = cfg[(0, 0)]
            
            self.endpoint_out = None
            self.endpoint_in = None
            
            for ep in intf:
                if usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_OUT:
                    if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                        self.endpoint_out = ep
                elif usb.util.endpoint_direction(ep.bEndpointAddress) == usb.util.ENDPOINT_IN:
                    if usb.util.endpoint_type(ep.bmAttributes) == usb.util.ENDPOINT_TYPE_BULK:
                        self.endpoint_in = ep
            
            if not self.endpoint_out:
                raise PrinterConnectionError("No bulk OUT endpoint found")
            
            logger.debug(f"Setup complete - OUT: {self.endpoint_out.bEndpointAddress:02x}")
            
        except Exception as e:
            raise PrinterConnectionError(f"Failed to setup device: {e}")
    
    async def _write_data(self, data: bytes) -> bool:
        if not self.endpoint_out:
            raise PrinterConnectionError("No output endpoint available")
        
        try:
            # Write data in chunks to avoid USB transfer size limits
            chunk_size = self.endpoint_out.wMaxPacketSize or 64
            total_written = 0
            
            for i in range(0, len(data), chunk_size):
                chunk = data[i:i + chunk_size]
                written = self.endpoint_out.write(chunk, settings.USB_TIMEOUT)
                total_written += written
            
            logger.debug(f"Wrote {total_written} bytes to printer")
            return total_written == len(data)
            
        except usb.core.USBTimeoutError:
            raise PrinterConnectionError("USB write timeout")
        except usb.core.USBError as e:
            raise PrinterConnectionError(f"USB write error: {e}")
    
    def _get_device_info(self) -> Dict[str, Any]:
        if not self.device:
            return {}
        
        try:
            return {
                'vendor_id': f"{self.device.idVendor:04x}",
                'product_id': f"{self.device.idProduct:04x}",
                'manufacturer': usb.util.get_string(self.device, self.device.iManufacturer) or "Unknown",
                'product': usb.util.get_string(self.device, self.device.iProduct) or "Unknown",
                'serial': usb.util.get_string(self.device, self.device.iSerialNumber) or "Unknown",
                'bus': self.device.bus,
                'address': self.device.address,
                'speed': self.device.speed
            }
        except:
            return {
                'vendor_id': f"{self.device.idVendor:04x}",
                'product_id': f"{self.device.idProduct:04x}",
                'manufacturer': "Unknown",
                'product': "Unknown",
                'serial': "Unknown",
                'bus': getattr(self.device, 'bus', 0),
                'address': getattr(self.device, 'address', 0)
            }

# Alternative backend for systems without PyUSB or direct device access
class FilePrinterBackend:
    
    def __init__(self, device_path: str = "/dev/usb/lp0"):
        self.device_path = device_path
        self.is_connected = False
        self.last_error = None
    
    async def connect(self) -> bool:
        try:
            # Test if we can open the device
            with open(self.device_path, 'wb') as f:
                pass  # Just test opening
            
            self.is_connected = True
            self.last_error = None
            logger.info(f"Connected to printer at {self.device_path}")
            return True
            
        except Exception as e:
            self.last_error = str(e)
            logger.error(f"Failed to connect to {self.device_path}: {e}")
            self.is_connected = False
            return False
    
    async def disconnect(self):
        self.is_connected = False
        logger.info(f"Disconnected from {self.device_path}")
    
    async def send_raw(self, data: bytes) -> bool:
        if not self.is_connected:
            if not await self.connect():
                return False
        
        try:
            with open(self.device_path, 'wb') as f:
                f.write(data)
                f.flush()
            
            logger.debug(f"Wrote {len(data)} bytes to {self.device_path}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to write to {self.device_path}: {e}")
            self.last_error = str(e)
            self.is_connected = False
            return False
    
    async def detect_printer(self) -> Optional[Dict[str, Any]]:
        try:
            import os
            import stat
            
            if os.path.exists(self.device_path):
                st = os.stat(self.device_path)
                return {
                    'device_path': self.device_path,
                    'device_type': 'character' if stat.S_ISCHR(st.st_mode) else 'block',
                    'permissions': oct(st.st_mode)[-3:],
                    'accessible': os.access(self.device_path, os.W_OK)
                }
        except Exception as e:
            logger.debug(f"Error detecting device file: {e}")
        
        return None
    
    async def get_printer_status(self) -> Dict[str, Any]:
        return {
            'connected': self.is_connected,
            'device_path': self.device_path,
            'last_error': self.last_error
        }

def create_printer_backend() -> PrinterBackend:
    if HAS_PYUSB:
        return PrinterBackend()
    else:
        logger.warning("PyUSB not available, using file backend")
        return FilePrinterBackend()