from pathlib import Path
import os

class PrintServerSettings:
    
    # Server configuration
    SERVER_HOST = os.getenv('PRINTSERVER_HOST', '0.0.0.0')
    SERVER_PORT = int(os.getenv('PRINTSERVER_PORT', 631))  # Puerto estándar IPP
    
    # Printer configuration
    PRINTER_NAME = os.getenv('PRINTER_NAME', 'Thermal-Printer')
    PRINTER_INFO = os.getenv('PRINTER_INFO', 'IPP Thermal Printer')
    PRINTER_LOCATION = os.getenv('PRINTER_LOCATION', 'Office')
    PRINTER_MAKE_MODEL = os.getenv('PRINTER_MAKE_MODEL', 'Generic Thermal ESC/POS Printer')
    
    # Thermal printer specific settings - OPTIMIZADO PARA 58MM
    PRINTER_WIDTH_MM = int(os.getenv('PRINTER_WIDTH_MM', 58))  # ✅ 58mm por defecto
    PRINTER_MAX_PIXELS = int(os.getenv('PRINTER_MAX_PIXELS', 384))  # ✅ 58mm @ 203 DPI
    PRINTER_DPI = int(os.getenv('PRINTER_DPI', 203))

    # USB configuration
    USB_VENDOR_ID = os.getenv('USB_VENDOR_ID', None)  # Auto-detect if None
    USB_PRODUCT_ID = os.getenv('USB_PRODUCT_ID', None)  # Auto-detect if None
    USB_TIMEOUT = int(os.getenv('USB_TIMEOUT', 5000))  # 5 seconds
    
    # IPP configuration
    IPP_VERSION = "2.1"
    IPP_CHARSET = "utf-8"
    IPP_NATURAL_LANGUAGE = "en"
    
    # mDNS configuration
    MDNS_SERVICE_NAME = PRINTER_NAME
    MDNS_DOMAIN = "local."
    
    # Supported formats
    SUPPORTED_FORMATS = [
        "application/pdf",
        "image/pwg-raster", 
        "image/jpeg",
        "image/png",
        "text/plain",
        "application/octet-stream"
    ]
    
    # Supported operations
    SUPPORTED_OPERATIONS = [
        "Print-Job",
        "Validate-Job", 
        "Get-Printer-Attributes",
        "Get-Jobs"
    ]
    
    # Printer attributes
    PRINTER_ATTRIBUTES = {
        'charset-supported': ['utf-8'],
        'compression-supported': ['none', 'deflate'],
        'document-format-supported': SUPPORTED_FORMATS,
        'printer-name': PRINTER_NAME,
        'printer-info': PRINTER_INFO,
        'printer-location': PRINTER_LOCATION,
        'printer-make-and-model': PRINTER_MAKE_MODEL,
        'printer-state': 'idle',  # idle, processing, stopped
        'operations-supported': SUPPORTED_OPERATIONS,
        'color-supported': False,
        'media-supported': ['roll'],
        'printer-kind': ['thermal'],
        'sides-supported': ['one-sided'],
        'print-quality-supported': [3, 4, 5],  # draft, normal, high
        'printer-resolution-supported': [(PRINTER_DPI, PRINTER_DPI, 'dpi')],
        'media-size-supported': [
            {
                'x-dimension': PRINTER_WIDTH_MM * 100,  # Convert to hundredths of mm
                'y-dimension': 32767  # Maximum for continuous roll
            }
        ]
    }
    
    # mDNS TXT record attributes for AirPrint/IPP
    MDNS_TXT_RECORDS = {
        'txtvers': '1',
        'qtotal': '1',
        'rp': f'ipp/printer',
        'ty': PRINTER_MAKE_MODEL,
        'adminurl': f'http://{SERVER_HOST}:{SERVER_PORT}/',
        'note': PRINTER_INFO,
        'priority': '0',
        'product': f'({PRINTER_MAKE_MODEL})',
        'pdl': 'application/pdf,image/pwg-raster,image/jpeg,image/png',
        'URF': 'W8,SRGB24,CP1,RS300',  # AirPrint URF capabilities
        'Color': 'F',  # Monochrome printer
        'Duplex': 'F',  # No duplex
        'Bind': 'F',
        'Sort': 'F',
        'Collate': 'F',
        'PaperMax': f'<legal-A4',
        'UUID': os.getenv('PRINTER_UUID', '12345678-1234-1234-1234-123456789012'),
        'TLS': '1.2',
        'air': 'username,password'
    }
    
    # Logging configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG')
    LOG_FILE = os.getenv('LOG_FILE', None)  # None for console only
    
    # Status update interval
    STATUS_UPDATE_INTERVAL = int(os.getenv('STATUS_UPDATE_INTERVAL', 60))  # Reducido a 60 segundos

    # Log Printing Configuration
    PRINT_LOGS_TO_PRINTER = os.getenv('PRINT_LOGS_TO_PRINTER', 'false').lower() in ['true', '1', 'yes']
    PRINT_LOG_LEVELS = os.getenv('PRINT_LOG_LEVELS', 'INFO,WARNING,ERROR').split(',')
    
    # Network Configuration
    ENABLE_MDNS = os.getenv('ENABLE_MDNS', 'true').lower() in ['true', '1', 'yes']
    AUTO_PORT_FALLBACK = os.getenv('AUTO_PORT_FALLBACK', 'true').lower() in ['true', '1', 'yes']

    # Build information
    VERSION = "1.0.0"
    BUILD_DATE = "2024-11-22"
    
    @classmethod
    def get_printer_uri(cls):
        import socket
        
        host = cls.SERVER_HOST
        if host == '0.0.0.0':
            # Get actual local IP
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
            errors.append("PRINTER_WIDTH_MM should be 58, 80, or 110 (common thermal sizes)")
        
        if cls.PRINTER_DPI not in [203, 300]:
            errors.append("PRINTER_DPI should be 203 or 300 (common thermal DPI)")
        
        if not cls.PRINTER_NAME or len(cls.PRINTER_NAME) == 0:
            errors.append("PRINTER_NAME cannot be empty")
        
        return errors

# Global settings instance
settings = PrintServerSettings()