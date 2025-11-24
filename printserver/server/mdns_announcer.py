from typing import Optional, Dict, Any, Union
import threading
import asyncio
import logging
import socket
import time

# Importaciones con fallbacks de seguridad
try:
    from zeroconf import Zeroconf, ServiceInfo
    from zeroconf.asyncio import AsyncZeroconf
    HAS_ZEROCONF = True
except ImportError:
    HAS_ZEROCONF = False

# Importaciones de configuración con fallback
try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

logger = logging.getLogger(__name__)

class MDNSAnnouncer:
    
    def __init__(self, server_host: str = None, server_port: int = None):
        if not HAS_ZEROCONF:
            raise ImportError("Zeroconf library not available")
        
        self.server_host = server_host or self._get_local_ip()
        self.server_port = server_port or settings.SERVER_PORT
        
        self.zeroconf: Optional[AsyncZeroconf] = None
        self.services: Dict[str, ServiceInfo] = {}
        self.is_running = False
        
        logger.debug(f"mDNS announcer initialized for {self.server_host}:{self.server_port}")
    
    def _get_local_ip(self) -> str:
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception:
            # Fallback to localhost
            logger.warning("Could not determine local IP, using localhost")
            return "127.0.0.1"
    
    async def start(self):
        if not HAS_ZEROCONF:
            logger.error("Cannot start mDNS announcer: Zeroconf not available")
            return
        
        if self.is_running:
            logger.warning("mDNS announcer already running")
            return
        
        try:
            self.zeroconf = AsyncZeroconf()
            
            # Register all services
            await self._register_ipp_service()
            await self._register_printer_service()
            await self._register_pdl_service()
            await self._register_airprint_service()
            
            self.is_running = True
            logger.info(f"mDNS announcer started - services published for {settings.PRINTER_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to start mDNS announcer: {e}")
            await self.stop()
            raise
    
    async def stop(self):
        if not self.is_running:
            return
        
        try:
            # Unregister all services
            for service_name, service_info in self.services.items():
                try:
                    await self.zeroconf.async_unregister_service(service_info)
                    logger.debug(f"Unregistered service: {service_name}")
                except Exception as e:
                    logger.warning(f"Error unregistering service {service_name}: {e}")
            
            # Close zeroconf
            if self.zeroconf:
                await self.zeroconf.async_close()
            
            self.services.clear()
            self.zeroconf = None
            self.is_running = False
            
            logger.info("mDNS announcer stopped")
            
        except Exception as e:
            logger.error(f"Error stopping mDNS announcer: {e}")
    
    async def _register_ipp_service(self):
        service_name = f"{settings.MDNS_SERVICE_NAME}._ipp._tcp.local."
        
        # Get actual local IP
        local_ip = self.server_host
        if local_ip == '0.0.0.0':
            local_ip = self._get_local_ip()
        
        # Create TXT record for IPP service - optimizado para Android/Mopria
        txt_record = {
            'txtvers': '1',
            'qtotal': '1',
            'rp': 'ipp/printer',
            'ty': settings.PRINTER_MAKE_MODEL,
            'adminurl': f'http://{local_ip}:{self.server_port}/',
            'note': settings.PRINTER_INFO,
            'priority': '0',
            'product': f'({settings.PRINTER_MAKE_MODEL})',
            
            # Formatos soportados - CRÍTICO para Android
            'pdl': 'application/pdf,application/octet-stream,image/jpeg,image/png,image/pwg-raster',
            
            # Capabilities
            'Color': 'F',  # Monochrome
            'Duplex': 'F',  # No duplex
            'Bind': 'F',
            'Sort': 'F',
            'Collate': 'F',
            'PaperMax': 'om_roll_58_203.2x3048',
            
            # URF para AirPrint
            'URF': 'W8,SRGB24,CP1,RS300,DM1',
            
            # UUID único
            'UUID': settings.MDNS_TXT_RECORDS.get('UUID', '12345678-1234-1234-1234-123456789012'),
            
            # Seguridad
            'TLS': '1.2',
            'air': 'none',  # Sin autenticación
            
            # Información de media
            'kind': 'document',
            'PaperCustom': 'T',
            
            # Capacidades binarias
            'Binary': 'T',
            'Transparent': 'T',
            'TBCP': 'F',
            
            # IPP everywhere
            'rfo': 'ipp/print',
            'printer-type': '0x801046',  # Tipo de impresora IPP
            }
        
        service_info = ServiceInfo(
            "_ipp._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=self.server_port,
            properties=txt_record,
            server=f"{socket.gethostname()}.local.")
        
        await self.zeroconf.async_register_service(service_info)
        self.services["ipp"] = service_info
        
        logger.info(f"Registered IPP service: {service_name} at {local_ip}:{self.server_port}")
    
    async def _register_airprint_service(self):
        # AirPrint uses the same _ipp._tcp service but with specific TXT records
        service_name = f"{settings.MDNS_SERVICE_NAME} AirPrint._ipp._tcp.local."
        
        # Enhanced TXT record for AirPrint compatibility
        txt_record = {
            'txtvers': '1',
            'qtotal': '1',
            'rp': 'ipp/printer',
            'ty': settings.PRINTER_MAKE_MODEL,
            'adminurl': f'http://{self.server_host}:{self.server_port}/',
            'note': f"{settings.PRINTER_INFO} (AirPrint)",
            'priority': '0',
            'product': f'({settings.PRINTER_MAKE_MODEL})',
            'pdl': 'application/pdf,image/jpeg,image/png',  # AirPrint preferred formats
            'URF': 'W8,SRGB24,CP1,RS300,V1.4,MT1-8-11,OB10,PQ3-4-5,CN1',
            'Color': 'F',  # Monochrome
            'Duplex': 'F',  # No duplex
            'Bind': 'F',
            'Sort': 'F', 
            'Collate': 'F',
            'PaperMax': '<legal-A4',
            'UUID': settings.MDNS_TXT_RECORDS.get('UUID', '12345678-1234-1234-1234-123456789012'),
            'TLS': '1.2',
            'air': 'none',  # No authentication required
            'kind': 'document,envelope,photo',
            'PaperCustom': '1',
            'Binary': 'T',
            'Transparent': 'T',
            'TBCP': 'F',
            'Punch': 'F',
            'Staple': 'F',
            'Fax': 'F',
            'Scan': 'F'
        }
        
        service_info = ServiceInfo(
            "_ipp._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(self.server_host)],
            port=self.server_port,
            properties=txt_record,
            server=f"{settings.MDNS_SERVICE_NAME}.local."
        )
        
        await self.zeroconf.async_register_service(service_info)
        self.services["airprint"] = service_info
        
        logger.info(f"Registered AirPrint service: {service_name}")
    
    def get_service_info(self) -> Dict[str, Any]:
        if not self.is_running:
            return {'status': 'stopped', 'services': []}
        
        services_info = []
        for service_name, service_info in self.services.items():
            services_info.append({
                'name': service_name,
                'type': service_info.type,
                'server': service_info.server,
                'port': service_info.port,
                'addresses': [socket.inet_ntoa(addr) for addr in service_info.addresses],
                'txt_records': {k.decode(): v.decode() if isinstance(v, bytes) else v 
                              for k, v in service_info.properties.items()}
            })
        
        return {
            'status': 'running',
            'host': self.server_host,
            'port': self.server_port,
            'services': services_info
        }

class SynchronousMDNSAnnouncer:

    def __init__(self, server_host: str = None, server_port: int = None):
        if not HAS_ZEROCONF:
            raise ImportError("Zeroconf library not available")
        
        self.server_host = server_host or self._get_local_ip()
        self.server_port = server_port or settings.SERVER_PORT
        
        self.zeroconf: Optional[Zeroconf] = None
        self.services: Dict[str, ServiceInfo] = {}
        self.is_running = False
    
    def _get_local_ip(self) -> str:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception:
            logger.warning("Could not determine local IP, using localhost")
            return "127.0.0.1"
    
    def start(self):
        if self.is_running:
            return
        
        try:
            self.zeroconf = Zeroconf()
            
            # Register IPP service
            self._register_ipp_service()
            
            self.is_running = True
            logger.info(f"Synchronous mDNS announcer started for {settings.PRINTER_NAME}")
            
        except Exception as e:
            logger.error(f"Failed to start synchronous mDNS announcer: {e}")
            self.stop()
            raise
    
    def stop(self):
        if not self.is_running:
            return
        
        try:
            for service_name, service_info in self.services.items():
                try:
                    self.zeroconf.unregister_service(service_info)
                except Exception as e:
                    logger.warning(f"Error unregistering service {service_name}: {e}")
            
            if self.zeroconf:
                self.zeroconf.close()
            
            self.services.clear()
            self.zeroconf = None
            self.is_running = False
            
            logger.info("Synchronous mDNS announcer stopped")
            
        except Exception as e:
            logger.error(f"Error stopping synchronous mDNS announcer: {e}")
    
    def _register_ipp_service(self):
        service_name = f"{settings.MDNS_SERVICE_NAME}._ipp._tcp.local."
        
        txt_record = {
            'txtvers': '1',
            'qtotal': '1',
            'rp': 'ipp/printer',
            'ty': settings.PRINTER_MAKE_MODEL,
            'adminurl': f'http://{self.server_host}:{self.server_port}/',
            'note': settings.PRINTER_INFO,
            'priority': '0',
            'product': f'({settings.PRINTER_MAKE_MODEL})',
            'pdl': ','.join(settings.SUPPORTED_FORMATS),
            'URF': 'W8,SRGB24,CP1,RS300'
        }
        
        service_info = ServiceInfo(
            "_ipp._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(self.server_host)],
            port=self.server_port,
            properties=txt_record,
            server=f"{settings.MDNS_SERVICE_NAME}.local."
        )
        
        self.zeroconf.register_service(service_info)
        self.services["ipp"] = service_info
        
        logger.info(f"Registered IPP service: {service_name}")

# Factory function to create appropriate announcer
def create_mdns_announcer(async_mode: bool = True, **kwargs) -> Union[MDNSAnnouncer, SynchronousMDNSAnnouncer]:
    if not HAS_ZEROCONF:
        raise ImportError("Zeroconf library not available - install with: pip install zeroconf")
    
    if async_mode:
        return MDNSAnnouncer(**kwargs)
    else:
        return SynchronousMDNSAnnouncer(**kwargs)