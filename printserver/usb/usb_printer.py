from .usb_detector import USBPrinterDetector, USBPrinterInfo
from typing import Optional
import logging
import time
import os

logger = logging.getLogger(__name__)

class USBPrinterBackend:
    
    def __init__(self, device_path: Optional[str] = None):

        self.device_path = device_path
        self.device_handle = None
        self.is_connected = False
        self.detector = USBPrinterDetector()
        self.current_printer: Optional[USBPrinterInfo] = None
        
        logger.info("USBPrinterBackend initialized")
        
        # Auto-detect si no se especificó device
        if not self.device_path:
            logger.info("No device path specified, will auto-detect on connect")
    
    def connect(self) -> bool:

        try:
            # Si no tenemos device path, detectar automáticamente
            if not self.device_path:
                logger.info("🔍 Auto-detecting printer...")
                printers = self.detector.scan_for_printers()
                
                if not printers:
                    logger.error("❌ No printers detected")
                    logger.info("💡 Make sure:")
                    logger.info("   1. Printer is connected via USB")
                    logger.info("   2. Printer is powered on")
                    logger.info("   3. User has permissions (add to lp/lpadmin group)")
                    return False
                
                # Usar la primera impresora detectada
                self.current_printer = printers[0]
                self.device_path = self.current_printer.device_path
                
                logger.info(f"✅ Auto-detected: {self.current_printer.friendly_name}")
                logger.info(f"   Device: {self.device_path}")
                
                if self.current_printer.vendor_id:
                    logger.info(f"   Vendor ID: {self.current_printer.vendor_id}")
                if self.current_printer.product_id:
                    logger.info(f"   Product ID: {self.current_printer.product_id}")
                
                # Verificar si es térmica conocida
                if self.detector.is_thermal_printer(self.current_printer):
                    logger.info("   🔥 Thermal printer detected")
            
            # Verificar que el dispositivo existe
            if not os.path.exists(self.device_path):
                logger.error(f"❌ Device not found: {self.device_path}")
                return False
            
            # Verificar permisos
            if not self.detector.test_printer_connection(self.device_path):
                logger.error(f"❌ Cannot write to {self.device_path}")
                logger.info("💡 Try: sudo usermod -a -G lp $USER")
                logger.info("   Then logout and login again")
                return False
            
            # Abrir dispositivo
            logger.info(f"🔌 Connecting to {self.device_path}...")
            self.device_handle = open(self.device_path, 'wb', buffering=0)
            self.is_connected = True
            
            # Enviar comando de inicialización
            self._send_init_command()
            
            logger.info(f"✅ Connected to printer: {self.device_path}")
            return True
            
        except PermissionError:
            logger.error(f"❌ Permission denied: {self.device_path}")
            logger.info("💡 Run: sudo chmod 666 {self.device_path}")
            logger.info("   Or add user to lp group: sudo usermod -a -G lp $USER")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect: {e}")
            import traceback
            logger.debug(f"Connection error: {traceback.format_exc()}")
            return False
    
    def _send_init_command(self):

        try:
            # ESC @ - Initialize printer
            init_cmd = b'\x1b@'
            self.device_handle.write(init_cmd)
            self.device_handle.flush()
            time.sleep(0.1)
            logger.debug("Sent initialization command")
        except Exception as e:
            logger.warning(f"Failed to send init command: {e}")
    
    def disconnect(self):

        if self.device_handle:
            try:
                self.device_handle.close()
                logger.info(f"Disconnected from {self.device_path}")
            except:
                pass
            finally:
                self.device_handle = None
                self.is_connected = False
    
    def send_raw(self, data: bytes) -> bool:

        if not self.is_connected:
            logger.warning("Printer not connected, attempting auto-connect...")
            if not self.connect():
                logger.error("Failed to auto-connect")
                return False
        
        try:
            logger.debug(f"Sending {len(data)} bytes to printer...")
            self.device_handle.write(data)
            self.device_handle.flush()
            logger.info(f"✅ Sent {len(data)} bytes successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to send data: {e}")
            self.is_connected = False
            return False
    
    def is_ready(self) -> bool:

        return self.is_connected
    
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