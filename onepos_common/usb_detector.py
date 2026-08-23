from typing import List, Dict, Optional
from pathlib import Path
import subprocess
import logging
import glob
import os
import re

logger = logging.getLogger(__name__)

# Clase que representa información encontrada sobre una impresora USB.
class USBPrinterInfo:

    # Inicializa la estructura con datos básicos de la impresora.
    def __init__(self, device_path: str, vendor_id: str = None, product_id: str = None,
                 manufacturer: str = None, product: str = None, serial: str = None):
        self.device_path = device_path
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.manufacturer = manufacturer
        self.product = product
        self.serial = serial

    # Representación breve para logging/debug.
    def __repr__(self):
        return (f"USBPrinterInfo(device={self.device_path}, "
                f"vendor={self.manufacturer}, product={self.product})")

    # Nombre legible de la impresora a mostrar en interfaces.
    @property
    def friendly_name(self):
        if self.manufacturer and self.product:
            return f"{self.manufacturer} {self.product}"
        elif self.product:
            return self.product
        else:
            return self.device_path

# Clase para detectar impresoras USB conectadas al sistema.
class USBPrinterDetector:

    # Rutas comunes de dispositivos de impresora en Linux
    DEVICE_PATTERNS = [
        '/dev/usb/lp*',      # Dispositivos LP USB estándar
        '/dev/lp*',          # Dispositivos LP paralelos/USB legacy
        '/dev/usblp*',       # Algunos sistemas usan este nombre
    ]
    
    # IDs de vendor conocidos de fabricantes de impresoras térmicas
    KNOWN_THERMAL_VENDORS = {
        '0483': 'STMicroelectronics',  # Muchas térmicas genéricas
        '0519': 'Star Micronics',      # Impresoras Star Micronics
        '04b8': 'Seiko Epson',         # Impresoras Epson
        '067b': 'Prolific',            # Chips USB-Serie usados en térmicas
        '1a86': 'QinHeng Electronics', # CH340/CH341 (común en térmicas chinas)
        '1504': 'Bixolon',             # Bixolon
        '0dd4': 'Custom Engineering',  # Impresoras Custom Engineering
        '0fe6': 'ICS Advent',          # Impresoras ICS Advent
        '2730': 'Citizen',             # Impresoras Citizen
        '154f': 'SNBC',                # Usado en muchas POS
        '28e9': 'GproPrinter',         # Impresoras genéricas
    }
    
    def __init__(self):

        # Lista interna de impresoras detectadas
        self.detected_printers: List[USBPrinterInfo] = []
        logger.info("USBPrinterDetector inicializado")
    
    def scan_for_printers(self) -> List[USBPrinterInfo]:

        # Escanea el sistema en busca de impresoras USB.
        logger.info("Escaneando impresoras USB...")
        self.detected_printers = []

        # 1) Buscar nodos de dispositivo típicos (/dev/usb/lp*, /dev/lp*)
        device_printers = self._scan_device_nodes()

        # 2) Enriquecer con salida de lsusb (si está disponible)
        usb_info = self._get_lsusb_info()

        # 3) Revisar sysfs para obtener metadatos adicionales
        sysfs_printers = self._scan_sysfs()

        # Combinar resultados, evitando duplicados
        all_devices = set()

        for printer in device_printers:
            all_devices.add(printer.device_path)
            self.detected_printers.append(printer)

        self._enrich_with_usb_info(usb_info)

        for printer in sysfs_printers:
            if printer.device_path not in all_devices:
                self.detected_printers.append(printer)

        logger.info(f"Se encontraron {len(self.detected_printers)} impresora(s)")
        for printer in self.detected_printers:
            logger.info(f"   {printer.friendly_name} -> {printer.device_path}")

        return self.detected_printers
    
    def _scan_device_nodes(self) -> List[USBPrinterInfo]:

        # Busca nodos de dispositivo en disco que coincidan con patrones conocidos.
        printers = []

        for pattern in self.DEVICE_PATTERNS:
            devices = glob.glob(pattern)
            for device in devices:
                if os.path.exists(device):
                    # Añadir solo si es escribible
                    if os.access(device, os.W_OK):
                        logger.debug(f"Dispositivo escribible encontrado: {device}")
                        printers.append(USBPrinterInfo(device_path=device))
                    else:
                        logger.warning(f"Dispositivo {device} encontrado sin permiso de escritura")

        return printers
    
    def _get_lsusb_info(self) -> List[Dict]:

        # Ejecuta 'lsusb -v' para obtener información detallada de dispositivos USB.
        try:
            result = subprocess.run(['lsusb', '-v'],
                                    capture_output=True,
                                    text=True,
                                    timeout=5)

            if result.returncode != 0:
                logger.warning("El comando lsusb falló")
                return []

            return self._parse_lsusb_output(result.stdout)

        except FileNotFoundError:
            logger.warning("lsusb no encontrado, instale el paquete usbutils")
            return []
        except subprocess.TimeoutExpired:
            logger.warning("Tiempo de espera de lsusb agotado")
            return []
        except Exception as e:
            logger.error(f"Error ejecutando lsusb: {e}")
            return []
    
    def _parse_lsusb_output(self, output: str) -> List[Dict]:

        # Parsea la salida de lsusb -v y extrae los dispositivos que parecen impresoras.
        devices = []
        current_device = {}

        for line in output.split('\n'):

            # Inicio de un nuevo dispositivo en la salida de lsusb
            if line.startswith('Bus '):
                if current_device:
                    devices.append(current_device)
                current_device = {}

                # Extraer Bus, Device e IDs
                match = re.search(r'Bus (\d+) Device (\d+): ID ([0-9a-f]+):([0-9a-f]+)', line)
                if match:
                    current_device['bus'] = match.group(1)
                    current_device['device'] = match.group(2)
                    current_device['vendor_id'] = match.group(3)
                    current_device['product_id'] = match.group(4)

            # Extraer manufacturer/product/serial y marcadores de clase impresora
            elif 'idVendor' in line:
                match = re.search(r'idVendor\s+0x([0-9a-f]+)\s+(.+)', line)
                if match:
                    current_device['manufacturer'] = match.group(2).strip()

            elif 'idProduct' in line:
                match = re.search(r'idProduct\s+0x([0-9a-f]+)\s+(.+)', line)
                if match:
                    current_device['product'] = match.group(2).strip()

            elif 'iSerial' in line:
                match = re.search(r'iSerial\s+\d+\s+(.+)', line)
                if match:
                    current_device['serial'] = match.group(1).strip()

            elif 'bInterfaceClass' in line and '7 Printer' in line:
                current_device['is_printer'] = True

        # Añadir último dispositivo parseado
        if current_device:
            devices.append(current_device)

        # Filtrar solo aquellos que sean impresoras o vendors conocidos de térmicas
        printers = [d for d in devices if d.get('is_printer', False) or
                    d.get('vendor_id', '').lower() in [v.lower() for v in self.KNOWN_THERMAL_VENDORS.keys()]]

        logger.debug(f"lsusb encontró {len(printers)} dispositivo(s) de impresora")
        return printers
    
    # Revisa sysfs (/sys/class/usb) para obtener información de dispositivos conectados.
    def _scan_sysfs(self) -> List[USBPrinterInfo]:
        
        printers = []

        usb_devices = glob.glob('/sys/class/usb/lp*')

        for device_path in usb_devices:
            try:

                # Leer metadatos del dispositivo desde sysfs
                device_link = os.readlink(os.path.join(device_path, 'device'))

                usb_path = os.path.join(device_path, 'device')

                vendor_id = self._read_sysfs_file(usb_path, 'idVendor')
                product_id = self._read_sysfs_file(usb_path, 'idProduct')
                manufacturer = self._read_sysfs_file(usb_path, 'manufacturer')
                product = self._read_sysfs_file(usb_path, 'product')
                serial = self._read_sysfs_file(usb_path, 'serial')

                device_name = os.path.basename(device_path)
                dev_path = f"/dev/usb/{device_name}"

                if not os.path.exists(dev_path):
                    dev_path = f"/dev/{device_name}"

                if os.path.exists(dev_path):
                    printer = USBPrinterInfo(
                        device_path=dev_path,
                        vendor_id=vendor_id,
                        product_id=product_id,
                        manufacturer=manufacturer,
                        product=product,
                        serial=serial
                    )
                    printers.append(printer)
                    logger.debug(f"sysfs: encontrado {printer}")

            except Exception as e:
                logger.debug(f"Error leyendo dispositivo sysfs {device_path}: {e}")

        return printers
    
    # Lee un archivo en sysfs y devuelve su contenido en string, si existe.
    def _read_sysfs_file(self, base_path: str, filename: str) -> Optional[str]:
        
        try:
            file_path = os.path.join(base_path, filename)
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    return f.read().strip()
        except:
            pass
        return None
    
    # Enriquecer la lista de impresoras detectadas con la información obtenida por lsusb.
    def _enrich_with_usb_info(self, usb_devices: List[Dict]):
        
        for printer in self.detected_printers:
            device_num = self._extract_device_number(printer.device_path)

            for usb_dev in usb_devices:
                if not printer.vendor_id and usb_dev.get('vendor_id'):
                    printer.vendor_id = usb_dev['vendor_id']
                if not printer.product_id and usb_dev.get('product_id'):
                    printer.product_id = usb_dev['product_id']
                if not printer.manufacturer and usb_dev.get('manufacturer'):
                    printer.manufacturer = usb_dev['manufacturer']
                if not printer.product and usb_dev.get('product'):
                    printer.product = usb_dev['product']
                if not printer.serial and usb_dev.get('serial'):
                    printer.serial = usb_dev['serial']
    
    # Extrae el número final del nombre del dispositivo (ej: lp0 -> 0)
    def _extract_device_number(self, device_path: str) -> Optional[int]:
        
        match = re.search(r'(\d+)$', device_path)
        if match:
            return int(match.group(1))
        return None
    
    # Devuelve la primera impresora detectada (o None si no hay ninguna).
    def get_primary_printer(self) -> Optional[USBPrinterInfo]:
        
        if not self.detected_printers:
            self.scan_for_printers()

        return self.detected_printers[0] if self.detected_printers else None

    # Busca una impresora detectada por su vendor_id.
    def get_printer_by_vendor(self, vendor_id: str) -> Optional[USBPrinterInfo]:
        
        for printer in self.detected_printers:
            if printer.vendor_id and printer.vendor_id.lower() == vendor_id.lower():
                return printer
        return None
    
    # Determina si el vendor ID corresponde a un fabricante típico de impresoras térmicas.
    def is_thermal_printer(self, printer: USBPrinterInfo) -> bool:
        
        if not printer.vendor_id:
            return False

        return printer.vendor_id.lower() in [v.lower() for v in self.KNOWN_THERMAL_VENDORS.keys()]
    
    # Intenta abrir el nodo de dispositivo en modo escritura para verificar permisos.
    def test_printer_connection(self, device_path: str) -> bool:
        
        try:
            with open(device_path, 'wb') as f:
                pass
            logger.debug(f"El dispositivo {device_path} es escribible")
            return True
        except PermissionError:
            logger.warning(f"Sin permiso de escritura para {device_path}")
            return False
        except FileNotFoundError:
            logger.warning(f"Dispositivo {device_path} no encontrado")
            return False
        except Exception as e:
            logger.error(f"Error probando {device_path}: {e}")
            return False
