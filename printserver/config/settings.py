from pathlib import Path
import os

class PrintServerSettings:
    
    # Configuración del servidor
    SERVER_HOST = os.getenv('PRINTSERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('PRINTSERVER_PORT', 631))  # Puerto estándar IPP

    # Configuración de la impresora - Presentar como impresora genérica estándar
    PRINTER_NAME = os.getenv('PRINTER_NAME', 'ONE-POS-Printer')
    PRINTER_INFO = os.getenv('PRINTER_INFO', 'ONE POS Network Printer')
    PRINTER_LOCATION = os.getenv('PRINTER_LOCATION', 'Office')
    PRINTER_MAKE_MODEL = os.getenv('PRINTER_MAKE_MODEL', 'Generic IPP Network Printer')

    # Configuración física de la impresora - Configuración interna (no expuesta a clientes)
    PRINTER_WIDTH_MM = int(os.getenv('PRINTER_WIDTH_MM', 58))  # Ancho real: 58mm
    PRINTER_MAX_PIXELS = int(os.getenv('PRINTER_MAX_PIXELS', 384))  # 58mm @ 203 DPI
    PRINTER_DPI = int(os.getenv('PRINTER_DPI', 203))  # Resolución interna

    # Configuración USB
    USB_VENDOR_ID = os.getenv('USB_VENDOR_ID', None)  # Auto-detect if None
    USB_PRODUCT_ID = os.getenv('USB_PRODUCT_ID', None)  # Auto-detect if None
    USB_TIMEOUT = int(os.getenv('USB_TIMEOUT', 5000))  # 5 seconds

    # Configuración IPP
    IPP_VERSION = "2.1"
    IPP_CHARSET = "utf-8"
    IPP_NATURAL_LANGUAGE = "en"

    # Configuración mDNS
    MDNS_SERVICE_NAME = PRINTER_NAME
    MDNS_DOMAIN = "local."

    # El servidor convierte automáticamente a ESC/POS internamente
    SUPPORTED_FORMATS = [
        "application/pdf",          # Documentos PDF estándar
        "image/jpeg",               # Imágenes JPEG
        "image/png",                # Imágenes PNG
        "image/pwg-raster",         # PWG Raster (AirPrint/CUPS)
        "text/plain",               # Texto plano
        "application/vnd.escpos",   # ESC/POS directo (clientes avanzados, uso interno)
        "application/octet-stream"  # Binario genérico (auto-detect)
    ]
    
    # Soportar operaciones IPP comunes
    SUPPORTED_OPERATIONS = [
        "Print-Job",
        "Validate-Job", 
        "Get-Printer-Attributes",
        "Get-Jobs"
    ]
    
    # Printer attributes - Presentar como impresora genérica estándar (no térmica)
    PRINTER_ATTRIBUTES = {
        'charset-supported': ['utf-8'],
        'compression-supported': ['none', 'deflate'],
        'document-format-supported': SUPPORTED_FORMATS,
        'printer-name': PRINTER_NAME,
        'printer-info': PRINTER_INFO,
        'printer-location': PRINTER_LOCATION,
        'printer-make-and-model': PRINTER_MAKE_MODEL,
        'printer-state': 'idle',                                                                           # idle, processing, stopped
        'operations-supported': SUPPORTED_OPERATIONS,
        'color-supported': False,                                                                          # Monocromático (común en muchas impresoras)
        'media-supported': ['na_index-3x5_3x5in', 'custom_min_57.91x101.6mm', 'custom_max_57.91x3048mm'],  # Tamaños genéricos
        'printer-kind': ['document'],                                                                      # Impresora de documentos genérica
        'sides-supported': ['one-sided'],
        'print-quality-supported': [3, 4, 5],                                                              # draft, normal, high
        'printer-resolution-supported': [(203, 203, 'dpi'), (300, 300, 'dpi')],                            # Resoluciones comunes
        'media-size-supported': [
            {
                'x-dimension': PRINTER_WIDTH_MM * 100,  # Ancho en centésimas de mm
                'y-dimension': 32767  # Longitud máxima para papel continuo
            }
        ]
    }
    
    # Anunciar como impresora genérica, NO mencionar "thermal", No incluimos application/vnd.escpos en pdl para mantener apariencia genérica
    MDNS_TXT_RECORDS = {
        'txtvers': '1',
        'qtotal': '1',
        'rp': f'ipp/printer',
        'ty': PRINTER_MAKE_MODEL,                                        # "Generic IPP Network Printer"
        'adminurl': f'http://{SERVER_HOST}:{SERVER_PORT}/',
        'note': PRINTER_INFO,
        'priority': '0',
        'product': f'({PRINTER_MAKE_MODEL})',
        'pdl': 'application/pdf,image/pwg-raster,image/jpeg,image/png',  # Solo formatos públicos
        'URF': 'W8,SRGB24,CP1,RS300',                                    # AirPrint URF capabilities estándar
        'Color': 'F',                                                    # Monochrome printer (común)
        'Duplex': 'F',                                                   # No duplex (común)
        'Bind': 'F',
        'Sort': 'F',
        'Collate': 'F',
        'PaperMax': f'<legal-A4',
        'UUID': os.getenv('PRINTER_UUID', '12345678-1234-1234-1234-123456789012'),
        'TLS': '1.2',
        'air': 'username,password'
    }
    
    # Configuración de registro/logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
    LOG_FILE = os.getenv('LOG_FILE', None)  # Ninguno = salida a consola

    # Intervalo de actualización de estado
    STATUS_UPDATE_INTERVAL = int(os.getenv('STATUS_UPDATE_INTERVAL', 60))  # Reducido a 60 segundos

    # Configuración de registro de impresión
    PRINT_LOGS_TO_PRINTER = os.getenv('PRINT_LOGS_TO_PRINTER', 'false').lower() in ['true', '1', 'yes']
    PRINT_LOG_LEVELS = os.getenv('PRINT_LOG_LEVELS', 'INFO,WARNING,ERROR').split(',')
    
    # Configuración de red
    ENABLE_MDNS = os.getenv('ENABLE_MDNS', 'true').lower() in ['true', '1', 'yes']
    AUTO_PORT_FALLBACK = os.getenv('AUTO_PORT_FALLBACK', 'true').lower() in ['true', '1', 'yes']

    # Información de la versión
    VERSION = "1.1.0"
    BUILD_DATE = "2025-11-22"
    
    # Configuración USB para impresora
    USB_PRINTER_DEVICE = os.getenv('USB_PRINTER_DEVICE', None)  # None = auto-detect
    USB_AUTO_DETECT = os.getenv('USB_AUTO_DETECT', 'true').lower() == 'true'
    
    # Si se especifica un device, usarlo; sino auto-detectar
    @classmethod
    def get_printer_device(cls):
        if cls.USB_PRINTER_DEVICE:
            return cls.USB_PRINTER_DEVICE
        return None
    
    @classmethod
    def get_printer_uri(cls):
        import socket
        
        host = cls.SERVER_HOST
        if host == '0.0.0.0':
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(1)
                    s.connect(("8.8.8.8", 80))
                    host = s.getsockname()[0]
            except Exception:
                try:
                    host = socket.gethostbyname(socket.gethostname())
                except Exception:
                    host = 'localhost'
        
        return f"ipp://{host}:{cls.SERVER_PORT}/ipp/printer"
    
    @classmethod
    def get_web_interface_url(cls):
        import socket
        
        host = cls.SERVER_HOST
        if host == '0.0.0.0':
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.settimeout(1)
                    s.connect(("8.8.8.8", 80))
                    host = s.getsockname()[0]
            except Exception:
                try:
                    host = socket.gethostbyname(socket.gethostname())
                except Exception:
                    host = 'localhost'
        
        return f"http://{host}:{cls.SERVER_PORT}/"
    
    @classmethod
    def validate_config(cls):
        errors = []
        
        if cls.SERVER_PORT < 1 or cls.SERVER_PORT > 65535:
            errors.append("SERVER_PORT must be between 1 and 65535")
        
        if cls.PRINTER_WIDTH_MM not in [58, 80, 110]:
            errors.append("PRINTER_WIDTH_MM should be 58, 80, or 110 (common printer sizes)")
        
        if cls.PRINTER_DPI not in [203, 300]:
            errors.append("PRINTER_DPI should be 203 or 300 (common printer DPI)")
        
        if not cls.PRINTER_NAME or len(cls.PRINTER_NAME) == 0:
            errors.append("PRINTER_NAME cannot be empty")
        
        return errors

# Cargar configuración por defecto
settings = PrintServerSettings()