import asyncio
import io
import logging
import socket
from datetime import datetime
import json
import time
from pathlib import Path

# Simple internal debugging without external dependencies
DEBUG_ENABLED = True
DEBUG_DIR = Path(__file__).parent.parent / "debug_logs"
from typing import Dict, Any, Optional, List, Tuple
import json

# Try relative import first, fallback to absolute
try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

from .port_manager import PortManager

logger = logging.getLogger(__name__)

def log_android_debug(client_ip: str, message: str, data: dict = None):

    if not DEBUG_ENABLED:
        return
        
    DEBUG_DIR.mkdir(exist_ok=True)
    
    log_entry = {
        'timestamp': time.time(),
        'client_ip': client_ip,
        'message': message,
        'data': data or {}
    }
    
    debug_file = DEBUG_DIR / f"android_debug_{client_ip.replace('.', '_')}.log"
    with open(debug_file, 'a', encoding='utf-8') as f:
        f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {message}\n")
        if data:
            f.write(f"  Data: {json.dumps(data, indent=2, default=str)}\n")
        f.write("-" * 50 + "\n")

def save_request_data(client_ip: str, request_data: bytes, headers: dict, path: str):

    if not DEBUG_ENABLED:
        return
        
    DEBUG_DIR.mkdir(exist_ok=True)
    
    # Save raw data
    timestamp = int(time.time())
    raw_file = DEBUG_DIR / f"request_{client_ip.replace('.', '_')}_{timestamp}.bin"
    with open(raw_file, 'wb') as f:
        f.write(request_data)
    
    # Save metadata
    meta_file = DEBUG_DIR / f"request_{client_ip.replace('.', '_')}_{timestamp}.json"
    metadata = {
        'timestamp': timestamp,
        'client_ip': client_ip,
        'path': path,
        'headers': dict(headers),
        'data_size': len(request_data),
        'raw_file': str(raw_file.name)
    }
    with open(meta_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, default=str)

class IPPMessage:
    
    def __init__(self):
        self.version_number = (2, 0)
        self.operation_id = None
        self.request_id = None
        self.operation_attributes = {}
        self.job_attributes = {}
        self.printer_attributes = {}
        self.document_data = None

def parse_ipp_request(data: bytes) -> IPPMessage:

    message = IPPMessage()
    
    if len(data) < 8:
        logger.error(f"IPP data too short: {len(data)} bytes (minimum 8 required)")
        return message
    
    try:
        # Parse IPP header (8 bytes)
        message.version_number = (data[0], data[1])
        message.operation_id = int.from_bytes(data[2:4], 'big')
        message.request_id = int.from_bytes(data[4:8], 'big')
        
        logger.debug(f"Parsed IPP header - Version: {message.version_number}, "
                    f"Operation: 0x{message.operation_id:04x}, Request ID: {message.request_id}")
        
        # Parse attributes (RFC 8011 compliant)
        offset = 8
        current_group = None
        attr_count = 0
        last_attribute_name = None  # Para manejar valores múltiples según RFC 8011
        
        def _store_attribute(target: dict, name: str, attr_value: 'AttributeValue'):
            """Store attribute supporting multi-valued attributes (RFC 8011 5.1.4)."""
            existing = target.get(name)
            if existing is None:
                target[name] = attr_value
            else:
                # Convert to list and append
                if isinstance(existing, list):
                    existing.append(attr_value)
                else:
                    target[name] = [existing, attr_value]

        while offset < len(data):
            if offset + 1 >= len(data):
                logger.debug(f"End of data reached at offset {offset}")
                break
                
            tag = data[offset]
            offset += 1
            
            if tag == 0x01:  # operation-attributes-tag
                current_group = 'operation'
                last_attribute_name = None  # Reset en nuevo grupo
                logger.debug("Found operation-attributes-tag")
                continue
            elif tag == 0x02:  # job-attributes-tag
                current_group = 'job'
                last_attribute_name = None  # Reset en nuevo grupo
                logger.debug("Found job-attributes-tag")
                continue
            elif tag == 0x04:  # printer-attributes-tag
                current_group = 'printer'
                last_attribute_name = None  # Reset en nuevo grupo
                logger.debug("Found printer-attributes-tag")
                continue
            elif tag == 0x03:  # end-of-attributes-tag
                # Document data follows
                doc_size = len(data) - offset
                logger.debug(f"Found end-of-attributes-tag, document data: {doc_size} bytes")
                message.document_data = data[offset:]
                break
            
            # Parse attribute (RFC 8011 compliant)
            if offset + 2 >= len(data):
                logger.debug(f"Not enough data for attribute at offset {offset}")
                break
                
            name_length = int.from_bytes(data[offset:offset+2], 'big')
            offset += 2
            
            # RFC 8011: Si name_length == 0, usar el último attribute-name válido
            if name_length == 0:
                if last_attribute_name is None:
                    logger.warning(f"name_length == 0 but no previous attribute name available")
                    # Intentar continuar saltando este atributo mal formado
                    if offset + 2 <= len(data):
                        value_length = int.from_bytes(data[offset:offset+2], 'big')
                        offset += 2 + value_length
                    continue
                name = last_attribute_name
                logger.debug(f"Using previous attribute name: {name}")
            else:
                if offset + name_length >= len(data):
                    logger.debug(f"Insufficient data for attribute name at offset {offset}, need {name_length} bytes")
                    break
                    
                name = data[offset:offset+name_length].decode('utf-8', errors='ignore')
                offset += name_length
                last_attribute_name = name  # Guardar para posibles valores múltiples
            
            if offset + 2 >= len(data):
                logger.debug(f"No space for value length after attribute '{name}'")
                break
                
            value_length = int.from_bytes(data[offset:offset+2], 'big')
            offset += 2
            
            if offset + value_length > len(data):
                logger.debug(f"Insufficient data for attribute '{name}' value, need {value_length} bytes")
                break
                
            value_data = data[offset:offset+value_length]
            offset += value_length
            
            # Store attribute
            attr_value = AttributeValue(tag, value_data)
            attr_count += 1
            
            # Para atributos con valores múltiples, podríamos convertirlos en listas
            # Por ahora, simplemente sobrescribimos (último valor gana)
            if current_group == 'operation':
                _store_attribute(message.operation_attributes, name, attr_value)
            elif current_group == 'job':
                _store_attribute(message.job_attributes, name, attr_value)
            elif current_group == 'printer':
                _store_attribute(message.printer_attributes, name, attr_value)
                
            if attr_count <= 10:  # Log first 10 attributes for debugging
                logger.debug(f"Parsed attribute: {name} = {attr_value.value} (tag: 0x{tag:02x})")
        
        logger.debug(f"✅ Parsing complete: {attr_count} attributes, "
                    f"operation_id=0x{message.operation_id:04x}")
        
    except Exception as e:
        logger.error(f"❌ Error parsing IPP request: {e}")
        import traceback
        logger.debug(f"Parser error traceback: {traceback.format_exc()}")
    
    return message

class AttributeValue:
    
    def __init__(self, tag: int, data: bytes):
        self.tag = tag
        self.data = data
        
    @property
    def value(self):
        if self.tag in [0x21, 0x23]:  # integer, enum
            if len(self.data) == 4:
                return int.from_bytes(self.data, 'big')
        elif self.tag in [0x41, 0x42, 0x43, 0x44, 0x45]:  # text/name values
            return self.data.decode('utf-8', errors='ignore')
        elif self.tag == 0x22:  # boolean
            return len(self.data) > 0 and self.data[0] != 0
        return self.data

class IPPServer:

    SUPPORTED_OPERATIONS = {
        0x0002: 'Print-Job',
        0x0004: 'Validate-Job',
        0x000b: 'Get-Printer-Attributes',
        0x000a: 'Get-Jobs',
        0x0008: 'Cancel-Job'
    }
    
    def __init__(self, printer_backend=None, converter=None):
 
        import time
        self.printer_backend = printer_backend
        self.converter = converter
        self.server = None
        self.host = None
        self.port = None
        self.requested_port = None
        self.port_manager = PortManager()
        self._start_time = time.time()  # For printer-up-time attribute
        
        # Job management
        self.active_jobs = {}
        self.completed_jobs = []
        self.failed_jobs = []
        self.job_counter = 1
        self.job_retention_seconds = 300  # Mantener jobs completados por 5 minutos
        
        # Server state
        self.is_running = False
        self.start_time = None

        # Solo AGREGAR estas líneas al final del __init__ existente:
        self.connection_stats = {
            'total_connections': 0,
            'probe_connections': 0,
            'valid_connections': 0,
            'cups_connections': 0,
            'android_connections': 0
}
    
    def _is_cups_probe_connection(self, client_ip: str, had_data: bool, request_count: int) -> bool:
        """
        Detecta si una conexión es un CUPS probe que debe ignorarse en logs.
        
        CUPS hace múltiples conexiones simultáneas para discovery:
        - Algunas nunca envían datos (pure probes)
        - Otras envían OPTIONS/HEAD y cierran inmediatamente
        
        Args:
            client_ip: IP del cliente
            had_data: Si la conexión recibió algún dato
            request_count: Número de requests procesadas
            
        Returns:
            True si es una conexión probe que debe ignorarse
        """
        # Localhost sin datos = probe
        if client_ip == '127.0.0.1' and not had_data:
            return True
        
        # Localhost con solo 1 request corto = probe
        if client_ip == '127.0.0.1' and request_count == 1:
            return True
        
        # Red local con timeout inmediato = probe
        if client_ip.startswith('10.') and not had_data:
            return True
        
        return False
    
    def _get_adaptive_timeout(self, request_count: int, is_android: bool) -> float:
        """
        Calcula timeout adaptativo basado en tipo de cliente y número de request.
        
        CUPS hace probes rápidos, Android necesita más tiempo para renderizar.
        
        Args:
            request_count: Número de request actual
            is_android: Si el cliente es Android
            
        Returns:
            Timeout en segundos
        """
        if request_count == 1:
            # Primera request: timeout corto para detectar probes
            return 2.0
        
        # Requests subsecuentes: más tiempo según cliente
        return 5.0 if is_android else 10.0
    
    def _should_log_connection(self, client_ip: str, method: str = None, 
                              request_count: int = 0, had_data: bool = False) -> bool:
        """
        Determina si una conexión/request debe loguearse para evitar spam.
        
        Args:
            client_ip: IP del cliente
            method: Método HTTP (GET, POST, etc.)
            request_count: Número de request
            had_data: Si hubo datos en la conexión
            
        Returns:
            True si debe loguearse
        """
        # Siempre loguear POST (requests reales)
        if method == 'POST':
            return True
        
        # Siempre loguear primera request con datos
        if request_count == 1 and had_data:
            return True
        
        # Loguear GET importantes
        if method == 'GET' and request_count <= 2:
            return True
        
        # No loguear probes de CUPS
        if self._is_cups_probe_connection(client_ip, had_data, request_count):
            return False
        
        # No loguear OPTIONS/HEAD repetitivos de localhost
        if client_ip == '127.0.0.1' and method in ['OPTIONS', 'HEAD'] and request_count > 1:
            return False
        
        return True
    
    def _get_max_requests_per_connection(self, client_type: str) -> int:
        """
        Determina el máximo de requests permitidas por conexión según tipo de cliente.
        
        CUPS raramente usa más de 5-10 requests.
        Android puede hacer muchas más.
        
        Args:
            client_type: 'cups/linux' o 'android'
            
        Returns:
            Número máximo de requests
        """
        if client_type == "cups/linux":
            return 10
        elif client_type == "android":
            return 100
        else:
            return 50  # Default conservador

    def _is_android_client(self, client_ip: str) -> bool:
        """Check if client is in Android/mobile IP patterns for enhanced debugging"""
        android_ip_patterns = [
            "192.168.1.121",
            "192.168.1.122",
            "192.168.1.123",
        ]
        
        # Could also check user agent if available, but for now use IP
        return client_ip in android_ip_patterns

    async def start(self, host: str = '0.0.0.0', port: int = 631):

        self.host = host
        self.requested_port = port
        
        # Intentar obtener el puerto solicitado
        available_port = await self._get_available_port(port)
        if not available_port:
            raise RuntimeError(f"No available ports found starting from {port}")
        
        self.port = available_port
        
        try:
            # Crear servidor con opciones de socket optimizadas
            self.server = await asyncio.start_server(
                self.handle_client,
                host, 
                available_port,
                reuse_address=True,
                reuse_port=True if hasattr(socket, 'SO_REUSEPORT') else False,
                backlog=100  # Aumentar backlog para más conexiones concurrentes
            )
            
            self.is_running = True
            self.start_time = datetime.now()
            
            logger.info(f"✅ IPP server started on {host}:{available_port}")
            
            # Mostrar información de conexión
            network_info = self.port_manager.get_network_info()
            if network_info['local_ip'] != 'localhost':
                logger.info(f"📡 External access: ipp://{network_info['local_ip']}:{available_port}/ipp/printer")
            
            if available_port != port:
                logger.warning(f"⚠️  Port {port} was not available, using {available_port}")
                
        except Exception as e:
            logger.error(f"Failed to start IPP server: {e}")
            raise
    
    async def _get_available_port(self, preferred_port: int) -> Optional[int]:

        # 1. Verificar si el puerto preferido está disponible
        if self.port_manager.is_port_available(preferred_port):
            logger.info(f"✅ Port {preferred_port} is available")
            return preferred_port
        
        # 2. Verificar qué proceso usa el puerto
        processes = self.port_manager.get_process_using_port(preferred_port)
        if processes:
            logger.warning(f"🚫 Port {preferred_port} is occupied by:")
            for proc in processes:
                logger.warning(f"   - {proc.get('name', 'Unknown')} (PID: {proc.get('pid', 'Unknown')})")
            
            # 3. Si es CUPS, intentar detenerlo (solo en puerto 631)
            if preferred_port == 631:
                cups_detected = any('cups' in proc.get('name', '').lower() for proc in processes)
                if cups_detected:
                    logger.info("🔄 Attempting to stop CUPS service...")
                    if self.port_manager.stop_service_on_port(preferred_port):
                        # Esperar un momento y verificar de nuevo
                        await asyncio.sleep(2)
                        if self.port_manager.is_port_available(preferred_port):
                            logger.info(f"✅ Successfully freed port {preferred_port}")
                            return preferred_port
                        else:
                            logger.warning("❌ Failed to free port after stopping CUPS")
        
        # 4. Buscar puerto alternativo
        logger.info("🔍 Searching for alternative port...")
        alternative_port = self.port_manager.find_available_port(
            preferred_port=None,
            start_range=8631 if preferred_port == 631 else preferred_port + 1,
            end_range=8700
        )
        
        if alternative_port:
            logger.info(f"✅ Found alternative port: {alternative_port}")
            return alternative_port
        
        # 5. Como último recurso, intentar puertos estándar
        logger.warning("⚠️  No ports in normal range, trying standard ports...")
        for test_port in [8631, 9100, 9101, 8632, 8633]:
            if test_port != preferred_port and self.port_manager.is_port_available(test_port):
                logger.info(f"✅ Found fallback port: {test_port}")
                return test_port
        
        logger.error("❌ No available ports found")
        return None
    
    async def handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        client_addr = writer.get_extra_info('peername')
        client_ip = client_addr[0] if client_addr else "unknown"
        
        # Get socket info for better diagnostics
        try:
            socket_info = writer.get_extra_info('socket')
            logger.debug(f"New connection from {client_addr} (socket: {socket_info})")
        except:
            logger.debug(f"New connection from {client_addr}")
        
        # Detect client type (Android, Linux CUPS, etc)
        is_android = self._is_android_client(client_ip)
        client_type = "android" if is_android else "cups/linux"
        
        # ===== FIX 1: Timeout adaptativo más agresivo =====
        # CUPS hace muchas conexiones probe que cierran inmediatamente
        # Reducir timeout inicial para detectar estas conexiones rápido
        initial_timeout = 2.0  # 2 segundos en lugar de 30
        request_timeout = 5.0 if is_android else 10.0  # Timeout para requests subsecuentes
        
        # Initialize debugging session
        if DEBUG_ENABLED:
            log_android_debug(client_ip, f"New connection from {client_type}", {
                'client_addr': str(client_addr),
                'client_type': client_type
            })
        
        try:
            # Loop para soportar múltiples requests en la misma conexión (CUPS)
            request_count = 0
            connection_had_data = False  # Track if we ever received real data
            
            while True:
                request_count += 1
                
                # ===== FIX 2: Timeout diferenciado para primera request =====
                # Primera request: timeout corto para detectar probes
                # Requests subsecuentes: timeout normal
                if request_count == 1:
                    timeout_duration = initial_timeout
                else:
                    timeout_duration = request_timeout
                
                # Solo logear primera request para evitar spam
                if request_count == 1 or connection_had_data:
                    logger.debug(f"[{client_ip}] Waiting for request #{request_count} (timeout: {timeout_duration}s)")
                
                try:
                    request_line = await asyncio.wait_for(
                        reader.readline(), 
                        timeout=timeout_duration
                    )
                except asyncio.TimeoutError:
                    # ===== FIX 3: Manejo silencioso de probe connections =====
                    # CUPS hace muchas conexiones probe que nunca envían datos
                    # Solo logear si la conexión tuvo actividad previa
                    if connection_had_data:
                        logger.debug(f"[{client_ip}] Connection timeout after {timeout_duration}s without request line.")
                    # No logear nada para probes vacíos (reduce spam)
                    break
                
                # EOF / cierre del cliente
                if not request_line:
                    # ===== FIX 4: Logging condicional de EOF =====
                    # Solo loguear EOF si hubo requests válidas anteriormente
                    if connection_had_data:
                        logger.debug(f"[{client_ip}] EOF received from client (connection closed)")
                    break
                
                # Marcar que esta conexión tuvo datos
                connection_had_data = True
                
                # TCP probe vacío (mantener conexión)
                if len(request_line.strip()) == 0:
                    logger.debug(f"[{client_ip}] Empty probe received, continuing...")
                    await asyncio.sleep(0.5)
                    continue
                
                # Log request line (solo si hay datos reales)
                raw_request_line = request_line[:100]
                logger.debug(f"[{client_ip}] Request line: {raw_request_line}")
                
                # === DETECCIÓN DE RAW DATA (PDF/ESC/POS directo sin HTTP wrapper) ===
                # Algunos clientes Android/iOS envían el documento directamente
                if request_line.startswith(b'%PDF') or request_line.startswith(b'\x1b'):
                    logger.info(f"📄 [Android/iOS] Raw document detected from {client_ip}")
                    logger.info(f"📄 Document type: {'PDF' if request_line.startswith(b'%PDF') else 'ESC/POS'}")
                    
                    # Leer todo el documento
                    document_data = request_line
                    while True:
                        try:
                            chunk = await asyncio.wait_for(reader.read(8192), timeout=5.0)
                            if not chunk:
                                break
                            document_data += chunk
                        except asyncio.TimeoutError:
                            break
                    
                    logger.info(f"📄 Received raw document: {len(document_data)} bytes")
                    
                    # Procesar el documento directamente
                    try:
                        if request_line.startswith(b'%PDF'):
                            # Es un PDF, convertir a ESC/POS
                            from .converter import DocumentConverter
                            converter = DocumentConverter()
                            escpos_data = await converter.convert_to_escpos(document_data, 'application/pdf')
                            logger.info(f"✅ PDF converted to ESC/POS: {len(escpos_data)} bytes")
                        else:
                            # Ya es ESC/POS, usar directamente
                            escpos_data = document_data
                            logger.info(f"✅ ESC/POS data received: {len(escpos_data)} bytes")
                        
                        # Enviar a la impresora
                        if self.printer_backend and hasattr(self.printer_backend, 'is_connected'):
                            if self.printer_backend.is_connected:
                                success = await self.printer_backend.send_raw(escpos_data)
                                if success:
                                    logger.info(f"✅ Printed successfully: {len(escpos_data)} bytes sent to printer")
                                else:
                                    logger.error("❌ Failed to print document")
                                
                                # Enviar respuesta simple (algunos clientes no esperan respuesta)
                                try:
                                    writer.write(b"HTTP/1.1 200 OK\r\n")
                                    writer.write(b"Content-Type: text/plain\r\n")
                                    writer.write(b"Content-Length: 2\r\n")
                                    writer.write(b"\r\n")
                                    writer.write(b"OK")
                                    await writer.drain()
                                except:
                                    pass  # Cliente puede haber cerrado conexión
                            else:
                                logger.error("❌ Printer not connected")
                        
                    except Exception as e:
                        logger.error(f"❌ Error processing raw document: {e}")
                        import traceback
                        logger.debug(traceback.format_exc())
                    
                    # Cerrar conexión y salir del loop
                    break
                
                # Parse request line (HTTP normal)
                request_line_str = request_line.decode('utf-8', errors='ignore').strip()
                if not request_line_str:
                    logger.warning(f"[{client_ip}] Empty request line, sending 400")
                    await self._send_http_error(writer, 400, "Bad Request", keep_alive=False)
                    break
                
                parts = request_line_str.split()
                if len(parts) < 2:
                    logger.warning(f"[{client_ip}] Invalid request line format, sending 400")
                    await self._send_http_error(writer, 400, "Bad Request", keep_alive=False)
                    break
                
                method = parts[0]
                path = parts[1]
                version = parts[2] if len(parts) >= 3 else "HTTP/1.0"
                
                # Validar versión HTTP
                if version not in ["HTTP/1.0", "HTTP/1.1"]:
                    logger.warning(f"[{client_ip}] Unsupported HTTP version: {version}")
                    version = "HTTP/1.1"
                
                # Normalizar path CUPS /printers/<queue> -> /ipp/printer
                if path.startswith('/printers/'):
                    original_path = path
                    path = '/ipp/printer'
                    logger.debug(f"[{client_ip}] CUPS path normalized: {original_path} -> {path}")
                
                # Parse headers
                headers = {}
                content_length = 0
                transfer_encoding = None
                expect_continue = False
                connection_type = None
                
                while True:
                    header_line = await reader.readline()
                    if not header_line or header_line == b'\r\n':
                        break
                    
                    h = header_line.decode('utf-8', errors='ignore').strip()
                    if ':' in h:
                        k, v = h.split(':', 1)
                        k_lower = k.strip().lower()
                        v_stripped = v.strip()
                        headers[k_lower] = v_stripped
                        
                        # Parse specific headers
                        if k_lower == 'content-length':
                            try:
                                content_length = int(v_stripped)
                            except ValueError:
                                content_length = 0
                        elif k_lower == 'transfer-encoding':
                            transfer_encoding = v_stripped.lower()
                        elif k_lower == 'expect' and '100-continue' in v_stripped.lower():
                            expect_continue = True
                        elif k_lower == 'connection':
                            connection_type = v_stripped.lower()
                
                # ===== FIX 5: Keep-Alive más conservador para CUPS =====
                # CUPS a veces envía Connection: close pero espera keep-alive
                # Ser más permisivo con HTTP/1.1
                if version == "HTTP/1.1":
                    # HTTP/1.1: Keep-Alive por defecto UNLESS explícitamente close
                    keep_alive = (connection_type != 'close')
                    # Pero si es CUPS local, siempre cerrar después de OPTIONS/HEAD
                    if client_ip == '127.0.0.1' and method in ['OPTIONS', 'HEAD']:
                        keep_alive = False
                else:  # HTTP/1.0
                    keep_alive = (connection_type == 'keep-alive')
                
                logger.debug(f"[{client_ip}] Keep-Alive: {keep_alive} (Connection: {connection_type}, Version: {version})")
                
                # Handle Expect: 100-continue
                if expect_continue:
                    logger.debug(f"[{client_ip}] Sending 100 Continue")
                    writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
                    await writer.drain()
                
                # Log request (solo requests con datos reales)
                logger.info(f"📨 [{client_ip}] {method} {path} {version} (request #{request_count})")
                
                # Logging condicional de headers (solo primeras 5)
                if request_count <= 3 or content_length > 0:
                    logger.debug(f"[{client_ip}] Headers: {dict(list(headers.items())[:5])}...")
                
                # === ROUTING DE REQUESTS ===
                
                if method == 'OPTIONS':
                    await self._handle_options_request(writer, path, keep_alive)
                    
                elif method == 'HEAD':
                    await self._handle_head_request(writer, path, keep_alive)
                    
                elif method == 'GET' and path == '/':
                    await self._handle_web_interface(writer, keep_alive)
                    
                elif method == 'GET' and path == '/status':
                    await self._handle_status_request(writer, keep_alive)
                
                elif method == 'GET' and path in ['/icon-small.png', '/icon-large.png']:
                    await self._handle_icon_request(writer, keep_alive, path)
                    
                elif method == 'POST' and path in ['/ipp/print', '/ipp/printer', '/ipp', '/']:
                    await self._handle_ipp_request(
                        reader, writer, headers, client_ip, 
                        content_length, transfer_encoding, keep_alive
                    )
                    
                else:
                    logger.warning(f"[{client_ip}] Unhandled request: {method} {path}")
                    await self._send_http_error(writer, 404, "Not Found", keep_alive)
                
                # Si el cliente pidió cerrar conexión, salir del loop
                if not keep_alive:
                    logger.debug(f"[{client_ip}] Client requested connection close, exiting loop")
                    break
                
                # ===== FIX 6: Límite de requests más conservador para CUPS =====
                # CUPS raramente usa más de 5-10 requests por conexión
                max_requests = 10 if client_type == "cups/linux" else 100
                if request_count >= max_requests:
                    logger.info(f"[{client_ip}] Max requests per connection reached ({max_requests}), closing")
                    break
            
            # ===== FIX 7: Logging resumido de cierre de conexión =====
            # Solo loguear si hubo requests válidas
            if connection_had_data and request_count > 1:
                logger.debug(f"[{client_ip}] Connection closed after {request_count} requests")
            
        except ConnectionResetError as e:
            # Cliente cerró abruptamente; esto es normal para CUPS probes
            if connection_had_data:
                logger.debug(f"[{client_ip}] Connection reset by peer: {e}")
            # No logear nada para probes que nunca enviaron datos
            
        except Exception as e:
            # Solo logear excepciones de conexiones que tuvieron datos
            if connection_had_data:
                logger.error(f"[{client_ip}] Error handling client: {e}")
                import traceback
                logger.debug(f"Client handler error traceback:\n{traceback.format_exc()}")
            
            try:
                await self._send_http_error(writer, 500, "Internal Server Error", keep_alive=False)
            except:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass

    async def _handle_ipp_request(self, reader: asyncio.StreamReader, 
                            writer: asyncio.StreamWriter, headers: dict, 
                            client_ip: str = None, content_length: int = 0,
                            transfer_encoding: str = None, keep_alive: bool = False):
        """
        REEMPLAZAR el método _handle_ipp_request con esta versión optimizada
        """
        client_addr = writer.get_extra_info('peername')
        if not client_ip:
            client_ip = client_addr[0] if client_addr else "unknown"
        
        try:
            user_agent = headers.get('user-agent', 'unknown')
            
            # Logging condicional: solo para debug detallado
            is_cups = 'CUPS' in user_agent
            should_log_detail = not is_cups or content_length > 0
            
            if should_log_detail:
                logger.info(f"📱 Client: {user_agent} from {client_ip}")
            
            # CUPS handshake logging (solo si no es Android)
            if not self._is_android_client(client_ip) and should_log_detail:
                self._log_cups_handshake(client_ip, "IPP Request Received", headers)
            
            # Read body data
            ipp_data = b''
            
            if transfer_encoding == 'chunked':
                # Chunked transfer
                chunks = []
                total_size = 0
                
                while True:
                    chunk_size_line = await reader.readline()
                    if not chunk_size_line:
                        break
                    
                    try:
                        chunk_size = int(chunk_size_line.strip(), 16)
                    except ValueError:
                        logger.error(f"[{client_ip}] Invalid chunk size")
                        break
                    
                    if chunk_size == 0:
                        await reader.readline()  # Read final CRLF
                        break
                    
                    chunk_data = await reader.readexactly(chunk_size)
                    chunks.append(chunk_data)
                    total_size += chunk_size
                    await reader.readline()  # Read trailing CRLF
                
                ipp_data = b''.join(chunks)
                if should_log_detail:
                    logger.info(f"✅ Chunked transfer: {len(ipp_data)} bytes")
                    
            elif content_length > 0:
                # Fixed Content-Length
                try:
                    ipp_data = await asyncio.wait_for(
                        reader.read(content_length),
                        timeout=30.0  # Timeout para lecturas grandes
                    )
                except asyncio.TimeoutError:
                    logger.error(f"[{client_ip}] Timeout reading {content_length} bytes")
                    await self._send_http_error(writer, 408, "Request Timeout", keep_alive=False)
                    return
            else:
                # No explicit length - try to read with timeout
                try:
                    ipp_data = await asyncio.wait_for(
                        reader.read(10 * 1024 * 1024),  # Max 10MB
                        timeout=5.0
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"[{client_ip}] No data received (timeout)")
                    await self._send_http_error(writer, 400, "No content", keep_alive=False)
                    return
            
            # Validate data
            if not ipp_data or len(ipp_data) == 0:
                logger.warning(f"[{client_ip}] No IPP data received")
                await self._send_http_error(writer, 400, "No content", keep_alive=False)
                return
            
            actual_length = len(ipp_data)
            
            # Logging condicional del tamaño
            if should_log_detail:
                logger.info(f"✅ Received {actual_length} bytes from {client_ip}")
            
            # Save for debugging (solo Android o errores)
            if DEBUG_ENABLED and (self._is_android_client(client_ip) or actual_length < 100):
                save_request_data(client_ip, ipp_data, headers, "/ipp/printer")
            
            # Validate minimum IPP header
            if actual_length < 8:
                logger.error(f"[{client_ip}] IPP data too short: {actual_length} bytes")
                await self._send_http_error(writer, 400, "Invalid IPP data", keep_alive=False)
                return
            
            # Parse IPP message
            message = parse_ipp_request(ipp_data)
            
            if message.operation_id is None:
                logger.error(f"[{client_ip}] Failed to parse IPP operation")
                await self._send_http_error(writer, 400, "Invalid IPP message", keep_alive=False)
                return
            
            # Log operation
            operation_name = self.SUPPORTED_OPERATIONS.get(
                message.operation_id, 
                f'Unknown-0x{message.operation_id:04x}'
            )
            
            # Solo loguear operaciones importantes
            if message.operation_id != 0x000b or should_log_detail:  # 0x000b = Get-Printer-Attributes
                logger.info(f"🔧 {operation_name} from {client_ip}")
            
            # Process operation
            response_data = await self._process_ipp_operation(message, client_ip)
            
            if not response_data:
                logger.error(f"[{client_ip}] No response generated")
                await self._send_http_error(writer, 500, "Processing failed", keep_alive=False)
                return
            
            # Send response
            ipp_version = f"{message.version_number[0]}.{message.version_number[1]}"
            
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/ipp\r\n"
                f"Content-Length: {len(response_data)}\r\n"
                f"Server: IPP/{ipp_version}\r\n"
                "Content-Language: en\r\n"
                "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
                f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
            )
            
            if keep_alive:
                response_headers += "Keep-Alive: timeout=30, max=100\r\n"
            
            response_headers += "\r\n"
            
            try:
                writer.write(response_headers.encode())
                writer.write(response_data)
                await writer.drain()
                
                # Logging condicional de éxito
                if should_log_detail or len(response_data) > 5000:
                    logger.info(f"✅ Response sent to {client_ip}: {len(response_data)} bytes")
                
            except (ConnectionResetError, BrokenPipeError) as e:
                logger.debug(f"[{client_ip}] Connection closed during send: {e}")
                return
            
        except Exception as e:
            logger.error(f"[{client_ip}] IPP request error: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            try:
                await self._send_http_error(writer, 500, "IPP Error", keep_alive=False)
            except:
                pass
    
    async def _process_ipp_operation(self, message: IPPMessage, client_ip: str = None) -> bytes:
        """Process IPP operation"""
        try:
            operation_name = self.SUPPORTED_OPERATIONS.get(message.operation_id, 'Unknown')
            logger.info(f"📱 Processing IPP operation: {operation_name} (0x{message.operation_id:04x})")
            
            # Enhanced debugging for Android compatibility
            logger.debug(f"Request ID: {message.request_id}, Version: {message.version_number}")
            if message.operation_attributes:
                logger.debug(f"Operation attributes: {len(message.operation_attributes)} items")
                shown = 0
                for attr_name, attr_value in message.operation_attributes.items():
                    if shown >= 8:  # mostrar algunos más ahora que soportamos multi-valor
                        break
                    if isinstance(attr_value, list):
                        values = [v.value for v in attr_value]
                        logger.debug(f"  Attribute: {attr_name}={values}")
                    else:
                        logger.debug(f"  Attribute: {attr_name}={attr_value.value}")
                    shown += 1
            
            if message.job_attributes:
                logger.debug(f"Job attributes: {len(message.job_attributes)} items")
                for i, (attr_name, attr_value) in enumerate(message.job_attributes.items()):
                    if i >= 5:
                        break
                    logger.debug(f"  Job Attr: {attr_name}={attr_value.value}")
            
            if message.document_data:
                logger.info(f"📄 Document data received: {len(message.document_data)} bytes")
                # Log preview of document data
                preview = message.document_data[:50] if len(message.document_data) >= 50 else message.document_data
                logger.debug(f"Document preview (hex): {preview.hex()}")
            
            # Process operation
            if message.operation_id == 0x0002:  # Print-Job
                logger.debug("Routing to _handle_print_job")
                return await self._handle_print_job(message)
            elif message.operation_id == 0x000b:  # Get-Printer-Attributes
                logger.debug("Routing to _handle_get_printer_attributes")
                return await self._handle_get_printer_attributes(message)
            elif message.operation_id == 0x000a:  # Get-Jobs
                logger.info(f"🔧 Get-Jobs from {client_ip}")
                return await self._handle_get_jobs(message)
            elif message.operation_id == 0x0004:  # Validate-Job
                logger.debug("Routing to _handle_validate_job")
                return await self._handle_validate_job(message)
            elif message.operation_id == 0x0008:  # Cancel-Job
                logger.debug("Routing to Cancel-Job handler")
                # Intentar obtener job-id
                job_id = None
                if 'job-id' in message.operation_attributes:
                    try:
                        job_id_attr = message.operation_attributes['job-id']
                        job_id = job_id_attr.value if isinstance(job_id_attr.value, int) else int(job_id_attr.value)
                    except Exception:
                        job_id = None
                # Cancelar si existe
                if job_id and job_id in self.active_jobs:
                    job = self.active_jobs[job_id]
                    job['state'] = 'aborted'
                    job['state_reasons'] = ['job-canceled-by-user']
                    self.failed_jobs.append(job)
                    self.active_jobs.pop(job_id, None)
                    logger.info(f"🛑 Job {job_id} canceled")
                    # Respuesta mínima IPP
                    response = io.BytesIO()
                    response.write(bytes(message.version_number))  # Usar versión del cliente
                    response.write((0x0000).to_bytes(2,'big'))  # successful-ok
                    response.write(message.request_id.to_bytes(4,'big'))
                    response.write(bytes([0x01]))  # operation-attributes
                    self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
                    self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
                    response.write(bytes([0x02]))  # job-attributes
                    self._write_attribute(response, 0x21, 'job-id', job_id.to_bytes(4,'big'))
                    self._write_attribute(response, 0x23, 'job-state', (8).to_bytes(4,'big'))  # canceled/aborted
                    self._write_attribute(response, 0x44, 'job-state-reasons', 'job-canceled-by-user')
                    response.write(bytes([0x03]))
                    return response.getvalue()
                else:
                    logger.warning("Cancel-Job requested for unknown job-id")
                    return self._create_error_response(message.request_id, 0x0405, message.version_number)  # client-error-not-found
            else:
                logger.warning(f"❌ Unsupported IPP operation: 0x{message.operation_id:04x}")
                return self._create_error_response(message.request_id, 0x0501, message.version_number)  # server-error-operation-not-supported
                
        except Exception as e:
            logger.error(f"❌ Error in _process_ipp_operation: {e}")
            import traceback
            logger.debug(f"Operation processing error traceback: {traceback.format_exc()}")
            version = getattr(message, 'version_number', (2, 0))
            return self._create_error_response(getattr(message, 'request_id', 1), 0x0500, version)  # server-error-internal-error
    
    async def _handle_print_job(self, message: IPPMessage) -> bytes:

        try:
            logger.info("🖨️  Handling Print-Job request")
            
            # Log all operation attributes for debugging
            logger.debug("Operation attributes:")
            for attr_name, attr_value in message.operation_attributes.items():
                logger.debug(f"  {attr_name}: {attr_value.value}")
            
            # Log job attributes
            if message.job_attributes:
                logger.debug("Job attributes:")
                for attr_name, attr_value in message.job_attributes.items():
                    logger.debug(f"  {attr_name}: {attr_value.value}")
            
            # Validate document data
            if not message.document_data or len(message.document_data) == 0:
                logger.error("❌ No document data received")
                return self._create_error_response(message.request_id, 0x0400, message.version_number)  # client-error-bad-request
            
            # Get document format from operation attributes
            document_format = 'application/octet-stream'
            if 'document-format' in message.operation_attributes:
                format_attr = message.operation_attributes['document-format']
                if isinstance(format_attr.value, bytes):
                    document_format = format_attr.value.decode('utf-8', errors='ignore')
                else:
                    document_format = str(format_attr.value)
            
            logger.info(f"📄 Print job details:")
            logger.info(f"  - Format: {document_format}")
            logger.info(f"  - Size: {len(message.document_data)} bytes")
            logger.info(f"  - First bytes (hex): {message.document_data[:50].hex()}")
            
            # Check if data looks like ESC/POS commands
            if message.document_data.startswith(b'\x1b') or b'\x1d' in message.document_data[:100]:
                logger.info("  ✅ Document appears to contain ESC/POS commands")
            
            # Get job name if available
            job_name = "Unnamed Job"
            if 'job-name' in message.operation_attributes:
                job_name_attr = message.operation_attributes['job-name']
                if isinstance(job_name_attr.value, str):
                    job_name = job_name_attr.value
                elif isinstance(job_name_attr.value, bytes):
                    job_name = job_name_attr.value.decode('utf-8', errors='ignore')
            
            logger.info(f"  - Job name: {job_name}")
            
            # Create job
            job_id = self._create_job(message)
            logger.info(f"✅ Created job {job_id} for '{job_name}'")
            
            # Process job asynchronously
            asyncio.create_task(self._process_print_job(job_id, message.document_data, document_format, job_name))
            
            # Return success response
            return self._create_print_job_response(message.request_id, job_id, message.version_number)
            
        except Exception as e:
            logger.error(f"❌ Error in print job handler: {e}")
            import traceback
            logger.debug(f"Print job handler error: {traceback.format_exc()}")
            return self._create_error_response(message.request_id, 0x0500, message.version_number)  # server-error-internal-error
    
    def _create_job(self, message: IPPMessage) -> int:

        job_id = self.job_counter
        self.job_counter += 1
        
        job = {
            'id': job_id,
            'state': 'pending',
            'creation_time': datetime.now(),
            'attributes': dict(message.job_attributes),
            'operation_attributes': dict(message.operation_attributes)
        }
        
        self.active_jobs[job_id] = job
        logger.info(f"Created job {job_id}")
        
        return job_id
    
    async def _schedule_job_removal(self, job_id: int):
        """
        Remueve un job de active_jobs después del período de retención.
        Esto permite que CUPS pueda consultar el estado del job antes de que desaparezca.
        """
        try:
            await asyncio.sleep(self.job_retention_seconds)
            
            if job_id in self.active_jobs:
                job = self.active_jobs.pop(job_id)
                logger.info(f"🗑️  Job {job_id} removed from active queue (state: {job['state']})")
                
        except asyncio.CancelledError:
            logger.debug(f"Job {job_id} removal task cancelled")
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
    
    async def _process_print_job(self, job_id: int, document_data: bytes, document_format: str, job_name: str = "Unnamed"):
        job = self.active_jobs.get(job_id)
        if not job:
            logger.error(f"❌ Job {job_id} not found")
            return

        try:
            job['state'] = 'processing'
            logger.info(f"🔄 Processing job {job_id} '{job_name}'")
            logger.info(f"   Format: {document_format}")
            logger.info(f"   Size: {len(document_data)} bytes")
            
            # Validate document data
            if not document_data or len(document_data) == 0:
                logger.error(f"❌ Job {job_id}: No document data (empty content)")
                job['state'] = 'aborted'
                job['state_reasons'] = ['document-format-error']
                return
            
            # Log document characteristics
            logger.debug(f"Document first 100 bytes (hex): {document_data[:100].hex()}")
            logger.debug(f"Document first 100 bytes (ascii): {document_data[:100]}")
            
            # Detect actual format if claimed as octet-stream
            actual_format = document_format
            if document_format == 'application/octet-stream':
                # Try to detect actual format
                if document_data.startswith(b'%PDF'):
                    actual_format = 'application/pdf'
                    logger.info(f"  🔍 Detected PDF document (header: %PDF)")
                elif document_data.startswith(b'\xFF\xD8\xFF'):
                    actual_format = 'image/jpeg'
                    logger.info(f"  🔍 Detected JPEG image")
                elif document_data.startswith(b'\x89PNG'):
                    actual_format = 'image/png'
                    logger.info(f"  🔍 Detected PNG image")
                elif b'\x1b' in document_data[:10] or b'\x1d' in document_data[:10]:
                    actual_format = 'application/vnd.escpos'
                    logger.info(f"  🔍 Detected ESC/POS commands (already in printer format)")
                else:
                    logger.warning(f"  ⚠️ Could not detect format, treating as raw data")
            
            # Process based on actual format
            escpos_data = None
            
            if actual_format == 'application/vnd.escpos' or (
                actual_format == 'application/octet-stream' and 
                (b'\x1b' in document_data[:100] or b'\x1d' in document_data[:100])
            ):
                # Already ESC/POS commands, use directly
                logger.info(f"  ✅ Document is already in ESC/POS format, using directly")
                escpos_data = document_data
                
            elif self.converter:
                # Need conversion
                logger.info(f"  🔧 Converting from {actual_format} to ESC/POS")
                try:
                    escpos_data = await self.converter.convert_to_escpos(document_data, actual_format)
                    if escpos_data and len(escpos_data) > 0:
                        logger.info(f"  ✅ Conversion successful: {len(escpos_data)} bytes of ESC/POS")
                        logger.debug(f"  ESC/POS preview (hex): {escpos_data[:50].hex()}")
                    else:
                        logger.error(f"  ❌ Conversion failed: No ESC/POS data generated")
                        job['state'] = 'aborted'
                        job['state_reasons'] = ['document-format-error']
                        return
                except Exception as conv_error:
                    logger.error(f"  ❌ Conversion error: {conv_error}")
                    import traceback
                    logger.debug(f"Conversion error traceback: {traceback.format_exc()}")
                    job['state'] = 'aborted'
                    job['state_reasons'] = ['document-format-error']
                    return
            else:
                # No converter and not ESC/POS - try to use raw data anyway
                logger.warning(f"  ⚠️ No converter available for {actual_format}, using raw data")
                escpos_data = document_data
            
            # Final validation
            if not escpos_data or len(escpos_data) == 0:
                logger.error(f"❌ Job {job_id}: No printable data after processing")
                job['state'] = 'aborted'
                job['state_reasons'] = ['document-format-error']
                return
            
            # Send to printer
            if self.printer_backend and self.printer_backend.is_connected:
                logger.info(f"  🖨️ Sending {len(escpos_data)} bytes to printer...")
                try:
                    success = await self.printer_backend.send_raw(escpos_data)
                    if success:
                        job['state'] = 'completed'
                        job['state_reasons'] = ['job-completed-successfully']
                        logger.info(f"  ✅ Job {job_id} printed successfully - {len(escpos_data)} bytes sent")
                    else:
                        job['state'] = 'aborted'
                        job['state_reasons'] = ['printer-stopped']
                        logger.error(f"  ❌ Job {job_id} failed - printer backend returned error")
                except Exception as print_error:
                    job['state'] = 'aborted'
                    job['state_reasons'] = ['printer-stopped']
                    logger.error(f"  ❌ Job {job_id} print error: {print_error}")
            else:
                # Offline/test mode
                job['state'] = 'completed'
                job['state_reasons'] = ['job-completed-with-warnings']
                logger.warning(f"  ⚠️ Job {job_id} processed in OFFLINE mode")
                logger.info(f"  📝 Would have printed {len(escpos_data)} bytes")
                
                # Save to file for debugging
                if DEBUG_ENABLED:
                    debug_file = DEBUG_DIR / f"job_{job_id}_{int(time.time())}.escpos"
                    with open(debug_file, 'wb') as f:
                        f.write(escpos_data)
                    logger.info(f"  💾 Saved ESC/POS data to: {debug_file}")
            
        except Exception as e:
            job['state'] = 'aborted'
            job['state_reasons'] = ['processing-stopped']
            logger.error(f"❌ Job {job_id} failed with exception: {e}")
            import traceback
            logger.debug(f"Job processing error traceback: {traceback.format_exc()}")
        finally:
            # Mark completion time but KEEP in active_jobs for CUPS to query
            job['completion_time'] = datetime.now()
            
            if job['state'] == 'completed':
                self.completed_jobs.append(job)
                logger.info(f"✅ Job {job_id} completed - kept in queue for CUPS")
            else:
                self.failed_jobs.append(job)
                logger.warning(f"❌ Job {job_id} failed with state: {job['state']}")
            
            # Schedule job removal after retention period
            asyncio.create_task(self._schedule_job_removal(job_id))
    
    def _create_print_job_response(self, request_id: int, job_id: int, version: tuple = (2, 0)) -> bytes:
        response = io.BytesIO()
        
        # IPP header - usar versión especificada o por defecto 2.0
        response.write(bytes(version))  # Versión compatible con cliente
        response.write((0x0000).to_bytes(2, 'big'))  # successful-ok
        response.write(request_id.to_bytes(4, 'big'))  # Request ID
        
        # Operation attributes
        response.write(bytes([0x01]))  # operation-attributes-tag
        
        # attributes-charset
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        
        # attributes-natural-language
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # Job attributes
        response.write(bytes([0x02]))  # job-attributes-tag
        
        # job-id
        self._write_attribute(response, 0x21, 'job-id', job_id.to_bytes(4, 'big'))
        
        # job-uri
        job_uri = f"ipp://{self.host}:{self.port}/ipp/jobs/{job_id}"
        self._write_attribute(response, 0x45, 'job-uri', job_uri)
        
        # job-state
        self._write_attribute(response, 0x23, 'job-state', (3).to_bytes(4, 'big'))  # pending
        
        # End of attributes
        response.write(bytes([0x03]))
        
        return response.getvalue()

    def _get_requested_attributes(self, message: IPPMessage) -> list:
        """
        Versión mejorada que maneja correctamente atributos vacíos y multi-valor.
        
        PROBLEMA ORIGINAL: No manejaba correctamente cuando requested-attributes
        está vacío o tiene valores None/vacíos.
        """
        if 'requested-attributes' not in message.operation_attributes:
            return []  # Vacío => enviar todo

        attr_obj = message.operation_attributes['requested-attributes']
        values = []

        # Manejar tanto listas como valores individuales
        if isinstance(attr_obj, list):
            for a in attr_obj:
                val = a.value
                if val is None:
                    continue  # Saltar None
                if isinstance(val, bytes):
                    decoded = val.decode('utf-8', errors='ignore').strip()
                    if decoded:  # Solo agregar si no está vacío
                        values.append(decoded)
                elif isinstance(val, str):
                    stripped = val.strip()
                    if stripped:
                        values.append(stripped)
        else:
            val = attr_obj.value
            if val is not None:
                if isinstance(val, bytes):
                    decoded = val.decode('utf-8', errors='ignore').strip()
                    if decoded:
                        values.append(decoded)
                elif isinstance(val, str):
                    stripped = val.strip()
                    if stripped:
                        values.append(stripped)

        # Eliminar duplicados preservando orden
        cleaned = []
        seen = set()
        for v in values:
            if v and v not in seen:
                cleaned.append(v)
                seen.add(v)
        
        return cleaned
    
    def _get_marker_attributes(self) -> dict:
        """
        Retorna atributos de marcadores (tinta/papel) para CUPS.
        
        Para impresoras sin indicadores de nivel, enviamos valores genéricos
        que indican "no aplicable" o "desconocido".
        """
        return {
            # marker-colors: Lista de colores (vacío para monocromático)
            'marker-colors': ['#000000'],  # Negro para impresoras monocromáticas
            
            # marker-names: Nombres genéricos de los marcadores
            'marker-names': ['Black Ink'],
            
            # marker-types: Tipo de marcador genérico
            'marker-types': ['continuous-supply'],
            
            # marker-levels: Nivel actual (-3 = unknown, estándar para impresoras sin sensor)
            'marker-levels': [-3],  # -3 = unknown (valor estándar IPP)
            
            # marker-high-levels: Nivel alto (umbral)
            'marker-high-levels': [100],
            
            # marker-low-levels: Nivel bajo (umbral)
            'marker-low-levels': [10],
            
            # marker-message: Mensaje del estado del marcador
            'marker-message': [''],
        }
    
    def _get_printer_state_info(self) -> Dict[str, Any]:
        """
        Calcula el estado actual de la impresora de forma consistente.
        
        Returns:
            dict con keys: state, state_reasons, state_message, is_accepting_jobs
        """
        # Determinar estado base (3=idle, 4=processing, 5=stopped)
        if self.printer_backend and hasattr(self.printer_backend, 'is_ready'):
            is_ready = self.printer_backend.is_ready()
            logger.debug(f"Printer backend is_ready(): {is_ready}")
        elif self.printer_backend and hasattr(self.printer_backend, 'is_connected'):
            is_ready = self.printer_backend.is_connected
            logger.debug(f"Printer backend is_connected: {is_ready}")
        else:
            is_ready = False
            logger.debug("No printer backend available")
        
        # Si hay jobs activos en estado processing, la impresora está ocupada
        has_processing_jobs = any(
            job.get('state') == 'processing' 
            for job in self.active_jobs.values()
        )
        
        # Calcular estado
        if not is_ready:
            state = 5  # stopped
            state_reasons = 'media-needed'  # O 'offline' o 'paused'
            state_message = 'Printer not connected or not ready'
            is_accepting_jobs = False
        elif has_processing_jobs:
            state = 4  # processing
            state_reasons = 'none'
            state_message = 'Processing job'
            is_accepting_jobs = True
        else:
            state = 3  # idle
            state_reasons = 'none'
            state_message = 'Ready to print'
            is_accepting_jobs = True
        
        state_names = {3: 'idle', 4: 'processing', 5: 'stopped'}
        logger.debug(f"📊 Printer state: {state_names.get(state, 'unknown')} ({state}), "
                    f"accepting jobs: {is_accepting_jobs}, reasons: {state_reasons}")
        
        return {
            'state': state,
            'state_reasons': state_reasons,
            'state_message': state_message,
            'is_accepting_jobs': is_accepting_jobs
        }
    
    def get_connection_statistics(self) -> Dict[str, Any]:
        """
        AGREGAR este método nuevo para debugging
        
        Retorna estadísticas de conexiones para diagnosticar problemas.
        """
        return {
            'total_connections': self.connection_stats['total_connections'],
            'valid_connections': self.connection_stats['valid_connections'],
            'probe_connections': self.connection_stats['probe_connections'],
            'cups_connections': self.connection_stats['cups_connections'],
            'android_connections': self.connection_stats['android_connections'],
            'probe_percentage': round(
                (self.connection_stats['probe_connections'] / 
                max(1, self.connection_stats['total_connections'])) * 100, 
                2
            ),
            'active_jobs': len(self.active_jobs),
            'completed_jobs': len(self.completed_jobs),
            'failed_jobs': len(self.failed_jobs)
        }
    
    async def _handle_get_printer_attributes(self, message: IPPMessage) -> bytes:
        response = io.BytesIO()
        
        # IPP header - usar la misma versión que el cliente
        response.write(bytes(message.version_number))
        response.write((0x0000).to_bytes(2, 'big'))  # successful-ok
        response.write(message.request_id.to_bytes(4, 'big'))
        
        # Operation attributes group
        response.write(bytes([0x01]))
        
        # Required attributes
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # Determinar qué atributos fueron solicitados
        requested_attrs = self._get_requested_attributes(message)
        
        # Si requested_attrs está vacío o contiene 'all', enviar todos
        send_all = not requested_attrs or 'all' in requested_attrs
        
        if requested_attrs and not send_all:
            logger.info(f"📋 CUPS requested {len(requested_attrs)} specific attributes")
        else:
            logger.info("📋 Sending ALL attributes")
        
        # Printer attributes group
        response.write(bytes([0x04]))
        
        # Get actual network information
        network_info = self.port_manager.get_network_info()
        local_ip = network_info['local_ip']
        if local_ip == '0.0.0.0':
            local_ip = '127.0.0.1'
        
        # Definir URIs disponibles
        printer_uris = [
            f'ipp://{local_ip}:{self.port}/ipp/printer',
            f'ipp://{local_ip}:{self.port}/ipp/print',
            f'ipp://{local_ip}:{self.port}/',
            f'http://{local_ip}:{self.port}/ipp/printer',
            f'ipp://{local_ip}:{self.port}/ipp',
        ]
        
        # Obtener atributos de marcadores
        marker_attrs = self._get_marker_attributes()
        
        # Si se solicitan atributos específicos, solo enviarlos
        if not send_all:
            # Procesar cada atributo solicitado
            for attr_name in requested_attrs:
                if attr_name == 'printer-uri-supported':
                    for uri in printer_uris:
                        self._write_attribute(response, 0x45, 'printer-uri-supported', uri)
                
                elif attr_name == 'uri-authentication-supported':
                    for _ in printer_uris:
                        self._write_attribute(response, 0x44, 'uri-authentication-supported', 'none')
                
                elif attr_name == 'uri-security-supported':
                    for _ in printer_uris:
                        self._write_attribute(response, 0x44, 'uri-security-supported', 'none')
                
                elif attr_name == 'printer-name':
                    self._write_attribute(response, 0x42, 'printer-name', settings.PRINTER_NAME)
                
                elif attr_name == 'printer-location':
                    self._write_attribute(response, 0x41, 'printer-location', settings.PRINTER_LOCATION)
                
                elif attr_name == 'printer-info':
                    self._write_attribute(response, 0x41, 'printer-info', settings.PRINTER_INFO)
                
                elif attr_name == 'printer-make-and-model':
                    self._write_attribute(response, 0x41, 'printer-make-and-model', settings.PRINTER_MAKE_MODEL)
                
                elif attr_name == 'printer-state':
                    state_info = self._get_printer_state_info()
                    self._write_attribute(response, 0x23, 'printer-state', state_info['state'].to_bytes(4, 'big'))
                
                elif attr_name == 'printer-state-reasons':
                    state_info = self._get_printer_state_info()
                    self._write_attribute(response, 0x44, 'printer-state-reasons', state_info['state_reasons'])
                
                elif attr_name == 'printer-state-message':
                    state_info = self._get_printer_state_info()
                    self._write_attribute(response, 0x41, 'printer-state-message', state_info['state_message'])
                
                elif attr_name == 'printer-is-accepting-jobs':
                    state_info = self._get_printer_state_info()
                    accepting = 1 if state_info['is_accepting_jobs'] else 0
                    self._write_attribute(response, 0x22, 'printer-is-accepting-jobs', accepting.to_bytes(1, 'big'))
                
                elif attr_name == 'queued-job-count':
                    self._write_attribute(response, 0x21, 'queued-job-count', len(self.active_jobs).to_bytes(4, 'big'))
                
                elif attr_name == 'operations-supported':
                    for op_id in self.SUPPORTED_OPERATIONS.keys():
                        self._write_attribute(response, 0x23, 'operations-supported', op_id.to_bytes(4, 'big'))

                elif attr_name == 'compression-supported':
                    for comp in ['none', 'gzip', 'deflate']:
                        self._write_attribute(response, 0x44, 'compression-supported', comp)

                elif attr_name == 'copies-supported':
                    # rangeOfInteger: min,max (dos enteros consecutivos)
                    self._write_attribute(response, 0x21, 'copies-supported', (1).to_bytes(4, 'big') + (99).to_bytes(4, 'big'))

                elif attr_name == 'print-color-mode-supported':
                    self._write_attribute(response, 0x44, 'print-color-mode-supported', 'monochrome')

                elif attr_name == 'media-col-supported':
                    for attr in ['media-size', 'media-type', 'media-source']:
                        self._write_attribute(response, 0x44, 'media-col-supported', attr)

                elif attr_name == 'multiple-document-handling-supported':
                    self._write_attribute(response, 0x44, 'multiple-document-handling-supported', 'separate-documents-uncollated-copies')

                elif attr_name == 'printer-alert':
                    self._write_attribute(response, 0x44, 'printer-alert', 'none')

                elif attr_name == 'printer-alert-description':
                    self._write_attribute(response, 0x41, 'printer-alert-description', 'none')

                elif attr_name == 'printer-mandatory-job-attributes':
                    self._write_attribute(response, 0x44, 'printer-mandatory-job-attributes', 'none')

                elif attr_name == 'cups-version':
                    self._write_attribute(response, 0x41, 'cups-version', '2.4')
                
                elif attr_name == 'document-format-supported':
                    formats = ['application/octet-stream', 'image/pwg-raster', 'application/vnd.cups-raster',
                            'image/urf', 'application/pdf', 'image/jpeg', 'image/png', 'text/plain']
                    for fmt in formats:
                        self._write_attribute(response, 0x49, 'document-format-supported', fmt)
                
                elif attr_name == 'document-format-default':
                    self._write_attribute(response, 0x49, 'document-format-default', 'application/octet-stream')
                
                elif attr_name == 'charset-supported':
                    for charset in ['utf-8', 'us-ascii']:
                        self._write_attribute(response, 0x47, 'charset-supported', charset)
                
                elif attr_name == 'charset-configured':
                    self._write_attribute(response, 0x47, 'charset-configured', 'utf-8')
                
                elif attr_name == 'natural-language-supported':
                    for lang in ['en-us', 'es-es', 'es']:
                        self._write_attribute(response, 0x48, 'natural-language-supported', lang)
                
                elif attr_name == 'media-supported':
                    media_names = ['oe_roll_58mm', 'om_roll_58_203.2x3048', 'roll_max_58_203.2x3048',
                                'custom_58x3048mm', 'continuous_58x3048mm']
                    for media in media_names:
                        self._write_attribute(response, 0x44, 'media-supported', media)
                
                elif attr_name == 'media-default':
                    self._write_attribute(response, 0x44, 'media-default', 'oe_roll_58mm')
                
                elif attr_name == 'sides-supported':
                    self._write_attribute(response, 0x44, 'sides-supported', 'one-sided')
                
                elif attr_name == 'sides-default':
                    self._write_attribute(response, 0x44, 'sides-default', 'one-sided')
                
                elif attr_name == 'ipp-versions-supported':
                    for version in ['1.1', '2.0', '2.1', '2.2']:
                        self._write_attribute(response, 0x44, 'ipp-versions-supported', version)
                
                elif attr_name == 'printer-type':
                    printer_type = 0x0008 | 0x2000 | 0x10000 | 0x20000 | 0x400000
                    self._write_attribute(response, 0x23, 'printer-type', printer_type.to_bytes(4, 'big'))
                
                elif attr_name == 'printer-type-mask':
                    self._write_attribute(response, 0x23, 'printer-type-mask', (0xFFFFFFFF).to_bytes(4, 'big'))
                
                elif attr_name == 'printer-up-time':
                    uptime = int(time.time() - self._start_time)
                    self._write_attribute(response, 0x21, 'printer-up-time', uptime.to_bytes(4, 'big'))
                
                elif attr_name == 'color-supported':
                    self._write_attribute(response, 0x22, 'color-supported', (0).to_bytes(1, 'big'))
                
                elif attr_name == 'copies-supported':
                    self._write_attribute(response, 0x21, 'copies-supported', (1).to_bytes(4, 'big') + (99).to_bytes(4, 'big'))
                
                elif attr_name == 'printer-uuid':
                    uuid_value = settings.MDNS_TXT_RECORDS.get('UUID', '12345678-1234-1234-1234-123456789012')
                    self._write_attribute(response, 0x45, 'printer-uuid', f'urn:uuid:{uuid_value}')
                
                elif attr_name == 'printer-device-id':
                    device_id = f'MFG:{settings.PRINTER_MAKE_MODEL.split()[0]};MDL:{settings.PRINTER_NAME};CLS:PRINTER;DES:Thermal Receipt Printer;CMD:ESC/POS;'
                    self._write_attribute(response, 0x41, 'printer-device-id', device_id)
                
                elif attr_name == 'printer-current-time':
                    now = datetime.now()
                    current_time = (
                        now.year.to_bytes(2, 'big') +
                        now.month.to_bytes(1, 'big') +
                        now.day.to_bytes(1, 'big') +
                        now.hour.to_bytes(1, 'big') +
                        now.minute.to_bytes(1, 'big') +
                        now.second.to_bytes(1, 'big') +
                        (0).to_bytes(1, 'big') +
                        b'+' +
                        (0).to_bytes(1, 'big') +
                        (0).to_bytes(1, 'big')
                    )
                    self._write_attribute(response, 0x31, 'printer-current-time', current_time)
                
                elif attr_name == 'output-bin-supported':
                    self._write_attribute(response, 0x44, 'output-bin-supported', 'face-down')
                
                elif attr_name == 'output-bin-default':
                    self._write_attribute(response, 0x44, 'output-bin-default', 'face-down')
                
                elif attr_name == 'printer-icons':
                    # Enviar URIs de íconos simples (aunque sean placeholders)
                    icon_base = f"http://{local_ip}:{self.port}"
                    self._write_attribute(response, 0x45, 'printer-icons', f"{icon_base}/icon-small.png")
                    self._write_attribute(response, 0x45, 'printer-icons', f"{icon_base}/icon-large.png")
                
                # ===== NUEVOS ATRIBUTOS PARA CUPS COMPATIBILITY =====
                elif attr_name == 'member-uris':
                    # Para impresoras simples, no hay miembros
                    pass
                
                elif attr_name == 'job-sheets-supported':
                    self._write_attribute(response, 0x44, 'job-sheets-supported', 'none')
                
                elif attr_name == 'job-sheets-default':
                    self._write_attribute(response, 0x44, 'job-sheets-default', 'none')
                
                elif attr_name == 'auth-info-required':
                    self._write_attribute(response, 0x44, 'auth-info-required', 'none')
                
                elif attr_name == 'number-up-default':
                    self._write_attribute(response, 0x21, 'number-up-default', (1).to_bytes(4, 'big'))
                
                elif attr_name == 'number-up-supported':
                    self._write_attribute(response, 0x21, 'number-up-supported', (1).to_bytes(4, 'big') + (1).to_bytes(4, 'big'))
                
                elif attr_name == 'media-col-default':
                    # Media collection por defecto
                    media_default = 'media-size=58xvariable;media-type=continuous;media-source=main'
                    self._write_attribute(response, 0x44, 'media-col-default', media_default)
                
                elif attr_name == 'media-size-supported':
                    # Soporte para tamaño de medio (58mm ancho, largo variable)
                    self._write_attribute(response, 0x44, 'media-size-supported', '58xvariable')
                
                elif attr_name == 'media-left-margin-supported':
                    self._write_attribute(response, 0x21, 'media-left-margin-supported', (0).to_bytes(4, 'big'))
                
                elif attr_name == 'media-right-margin-supported':
                    self._write_attribute(response, 0x21, 'media-right-margin-supported', (0).to_bytes(4, 'big'))
                
                elif attr_name == 'media-bottom-margin-supported':
                    self._write_attribute(response, 0x21, 'media-bottom-margin-supported', (0).to_bytes(4, 'big'))
                
                elif attr_name == 'media-top-margin-supported':
                    self._write_attribute(response, 0x21, 'media-top-margin-supported', (0).to_bytes(4, 'big'))
                
                # ===== ATRIBUTOS DE MARCADORES (CRÍTICO PARA CUPS) =====
                elif attr_name == 'marker-colors':
                    for color in marker_attrs['marker-colors']:
                        self._write_attribute(response, 0x44, 'marker-colors', color)
                
                elif attr_name == 'marker-names':
                    for name in marker_attrs['marker-names']:
                        self._write_attribute(response, 0x42, 'marker-names', name)
                
                elif attr_name == 'marker-types':
                    for mtype in marker_attrs['marker-types']:
                        self._write_attribute(response, 0x44, 'marker-types', mtype)
                
                elif attr_name == 'marker-levels':
                    for level in marker_attrs['marker-levels']:
                        self._write_attribute(response, 0x21, 'marker-levels', level.to_bytes(4, 'big', signed=True))
                
                elif attr_name == 'marker-high-levels':
                    for level in marker_attrs['marker-high-levels']:
                        self._write_attribute(response, 0x21, 'marker-high-levels', level.to_bytes(4, 'big'))
                
                elif attr_name == 'marker-low-levels':
                    for level in marker_attrs['marker-low-levels']:
                        self._write_attribute(response, 0x21, 'marker-low-levels', level.to_bytes(4, 'big'))
                
                elif attr_name == 'marker-message':
                    for msg in marker_attrs['marker-message']:
                        self._write_attribute(response, 0x41, 'marker-message', msg)
                
                elif attr_name == 'job-password-encryption-supported':
                    self._write_attribute(response, 0x44, 'job-password-encryption-supported', 'none')
                
                elif attr_name == 'job-presets-supported':
                    # CUPS/macOS puede solicitar presets de trabajos predefinidos
                    # Para impresoras térmicas simples, no hay presets
                    # Enviar colección vacía o simplemente no enviar nada (pass)
                    pass
                
                elif attr_name == 'media-col-database':
                    # CUPS 2.4+ solicita este atributo para conocer todos los tamaños disponibles
                    # Responder con una colección de media-col para cada tamaño de papel
                    # Para impresoras térmicas de 58mm, enviamos una entrada básica
                    
                    # Comenzar colección (1setOf)
                    response.write(bytes([0x34]))  # begCollection tag
                    response.write((0).to_bytes(2, 'big'))  # name-length = 0 (valor adicional)
                    response.write((0).to_bytes(2, 'big'))  # value-length = 0
                    
                    # media-size (memberAttrName)
                    response.write(bytes([0x4a]))  # memberAttrName tag
                    name_bytes = b'media-size'
                    response.write(len(name_bytes).to_bytes(2, 'big'))
                    response.write(name_bytes)
                    response.write((0).to_bytes(2, 'big'))  # value-length = 0
                    
                    # Comenzar sub-colección para media-size
                    response.write(bytes([0x34]))  # begCollection tag
                    response.write((0).to_bytes(2, 'big'))  # name-length = 0
                    response.write((0).to_bytes(2, 'big'))  # value-length = 0
                    
                    # x-dimension (58mm = 5800 micrometros / 100 = 580 en 0.01mm)
                    response.write(bytes([0x4a]))  # memberAttrName tag
                    name_bytes = b'x-dimension'
                    response.write(len(name_bytes).to_bytes(2, 'big'))
                    response.write(name_bytes)
                    response.write((0).to_bytes(2, 'big'))
                    
                    response.write(bytes([0x21]))  # integer tag
                    response.write((0).to_bytes(2, 'big'))  # name-length = 0
                    response.write((4).to_bytes(2, 'big'))  # value-length = 4
                    response.write((5800).to_bytes(4, 'big'))  # 58mm en micrometros
                    
                    # y-dimension (sin límite para papel continuo, usar valor largo)
                    response.write(bytes([0x4a]))  # memberAttrName tag
                    name_bytes = b'y-dimension'
                    response.write(len(name_bytes).to_bytes(2, 'big'))
                    response.write(name_bytes)
                    response.write((0).to_bytes(2, 'big'))
                    
                    response.write(bytes([0x21]))  # integer tag
                    response.write((0).to_bytes(2, 'big'))
                    response.write((4).to_bytes(2, 'big'))
                    response.write((30000).to_bytes(4, 'big'))  # 300mm máximo
                    
                    # Cerrar sub-colección media-size
                    response.write(bytes([0x37]))  # endCollection tag
                    response.write((0).to_bytes(2, 'big'))
                    response.write((0).to_bytes(2, 'big'))
                    
                    # media-type
                    response.write(bytes([0x4a]))  # memberAttrName tag
                    name_bytes = b'media-type'
                    response.write(len(name_bytes).to_bytes(2, 'big'))
                    response.write(name_bytes)
                    response.write((0).to_bytes(2, 'big'))
                    
                    response.write(bytes([0x44]))  # keyword tag
                    response.write((0).to_bytes(2, 'big'))
                    value_bytes = b'continuous'
                    response.write(len(value_bytes).to_bytes(2, 'big'))
                    response.write(value_bytes)
                    
                    # media-source
                    response.write(bytes([0x4a]))  # memberAttrName tag
                    name_bytes = b'media-source'
                    response.write(len(name_bytes).to_bytes(2, 'big'))
                    response.write(name_bytes)
                    response.write((0).to_bytes(2, 'big'))
                    
                    response.write(bytes([0x44]))  # keyword tag
                    response.write((0).to_bytes(2, 'big'))
                    value_bytes = b'auto'
                    response.write(len(value_bytes).to_bytes(2, 'big'))
                    response.write(value_bytes)
                    
                    # Cerrar colección principal
                    response.write(bytes([0x37]))  # endCollection tag
                    response.write((0).to_bytes(2, 'big'))
                    response.write((0).to_bytes(2, 'big'))
                    
                    logger.debug("✅ Sent media-col-database with printer paper specifications")
                
                elif attr_name == 'document-format-preferred':
                    # Formato preferido: PDF (estándar y universal)
                    self._write_attribute(response, 0x49, 'document-format-preferred', 'application/pdf')
                    logger.debug("✅ Sent document-format-preferred: application/pdf")
                
                elif attr_name == 'device-uri':
                    # URI del dispositivo físico (para impresoras de red es el mismo que printer-uri)
                    device_uri = f'ipp://{local_ip}:{self.port}/ipp/printer'
                    self._write_attribute(response, 0x45, 'device-uri', device_uri)
                    logger.debug(f"✅ Sent device-uri: {device_uri}")
                
                elif attr_name == 'printer-dns-sd-name':
                    # Nombre DNS-SD/mDNS (Bonjour/Zeroconf)
                    dns_sd_name = f"{settings.PRINTER_NAME}._ipp._tcp.local."
                    self._write_attribute(response, 0x41, 'printer-dns-sd-name', dns_sd_name)
                    logger.debug(f"✅ Sent printer-dns-sd-name: {dns_sd_name}")
                
                elif attr_name == 'printer-more-info':
                    # URL con más información sobre la impresora (interfaz web)
                    more_info_url = f'http://{local_ip}:{self.port}/'
                    self._write_attribute(response, 0x45, 'printer-more-info', more_info_url)
                    logger.debug(f"✅ Sent printer-more-info: {more_info_url}")
                
                # ===== ATRIBUTOS AVANZADOS WINDOWS/CUPS =====
                
                elif attr_name == 'copies-default':
                    # Número de copias por defecto
                    self._write_attribute(response, 0x21, 'copies-default', (1).to_bytes(4, 'big'))
                
                elif attr_name == 'orientation-requested-supported':
                    # Orientaciones soportadas: 3=portrait, 4=landscape
                    for orientation in [3, 4]:
                        self._write_attribute(response, 0x23, 'orientation-requested-supported', orientation.to_bytes(4, 'big'))
                
                elif attr_name == 'job-impressions-supported':
                    # Rango de impresiones soportadas por trabajo (rangeOfInteger)
                    self._write_attribute(response, 0x33, 'job-impressions-supported', (1).to_bytes(4, 'big') + (9999).to_bytes(4, 'big'))
                
                elif attr_name == 'job-pages-per-set-supported':
                    # Rango de páginas por set (rangeOfInteger)
                    self._write_attribute(response, 0x33, 'job-pages-per-set-supported', (1).to_bytes(4, 'big') + (9999).to_bytes(4, 'big'))
                
                elif attr_name == 'media-type-supported':
                    # Tipos de papel soportados
                    for media_type in ['stationery', 'continuous', 'labels']:
                        self._write_attribute(response, 0x44, 'media-type-supported', media_type)
                
                elif attr_name == 'media-col-ready':
                    # Media collection lista para usar (papel cargado actualmente)
                    # Similar a media-col-default pero indica papel físicamente presente
                    # Enviar colección básica
                    response.write(bytes([0x34]))  # begCollection tag
                    response.write((0).to_bytes(2, 'big'))
                    response.write((0).to_bytes(2, 'big'))
                    
                    # media-size
                    response.write(bytes([0x4a]))  # memberAttrName
                    name_bytes = b'media-size'
                    response.write(len(name_bytes).to_bytes(2, 'big'))
                    response.write(name_bytes)
                    response.write((0).to_bytes(2, 'big'))
                    
                    # Sub-colección media-size
                    response.write(bytes([0x34]))  # begCollection
                    response.write((0).to_bytes(2, 'big'))
                    response.write((0).to_bytes(2, 'big'))
                    
                    # x-dimension (58mm)
                    response.write(bytes([0x4a]))  # memberAttrName
                    response.write((11).to_bytes(2, 'big'))
                    response.write(b'x-dimension')
                    response.write((0).to_bytes(2, 'big'))
                    response.write(bytes([0x21]))  # integer
                    response.write((0).to_bytes(2, 'big'))
                    response.write((4).to_bytes(2, 'big'))
                    response.write((5800).to_bytes(4, 'big'))
                    
                    # y-dimension (continuo)
                    response.write(bytes([0x4a]))  # memberAttrName
                    response.write((11).to_bytes(2, 'big'))
                    response.write(b'y-dimension')
                    response.write((0).to_bytes(2, 'big'))
                    response.write(bytes([0x21]))  # integer
                    response.write((0).to_bytes(2, 'big'))
                    response.write((4).to_bytes(2, 'big'))
                    response.write((30000).to_bytes(4, 'big'))
                    
                    # Cerrar sub-colección
                    response.write(bytes([0x37]))  # endCollection
                    response.write((0).to_bytes(2, 'big'))
                    response.write((0).to_bytes(2, 'big'))
                    
                    # Cerrar colección principal
                    response.write(bytes([0x37]))  # endCollection
                    response.write((0).to_bytes(2, 'big'))
                    response.write((0).to_bytes(2, 'big'))
                
                elif attr_name == 'printer-resolution-default':
                    # Resolución por defecto: 203 DPI (thermal printer standard)
                    # Formato: x-resolution, y-resolution, units (3=dots per inch)
                    resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
                    self._write_attribute(response, 0x32, 'printer-resolution-default', resolution)
                
                elif attr_name == 'printer-resolution-supported':
                    # Resolución soportada
                    resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
                    self._write_attribute(response, 0x32, 'printer-resolution-supported', resolution)
                
                elif attr_name == 'print-quality-default':
                    # Calidad de impresión por defecto: 4=normal
                    self._write_attribute(response, 0x23, 'print-quality-default', (4).to_bytes(4, 'big'))
                
                elif attr_name == 'print-quality-supported':
                    # Calidades soportadas: 3=draft, 4=normal, 5=high
                    for quality in [3, 4, 5]:
                        self._write_attribute(response, 0x23, 'print-quality-supported', quality.to_bytes(4, 'big'))
                
                elif attr_name == 'pwg-raster-document-resolution-supported':
                    # Resoluciones PWG Raster soportadas
                    resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
                    self._write_attribute(response, 0x32, 'pwg-raster-document-resolution-supported', resolution)
                
                elif attr_name == 'pwg-raster-document-type-supported':
                    # Tipos de documento PWG Raster: black_1 (1-bit black), sgray_8 (8-bit grayscale)
                    for doc_type in ['black_1', 'sgray_8']:
                        self._write_attribute(response, 0x44, 'pwg-raster-document-type-supported', doc_type)
                
                elif attr_name == 'finishings-default':
                    # Acabados por defecto: 3=none
                    self._write_attribute(response, 0x23, 'finishings-default', (3).to_bytes(4, 'big'))
                
                elif attr_name == 'finishings-supported':
                    # Acabados soportados: 3=none
                    self._write_attribute(response, 0x23, 'finishings-supported', (3).to_bytes(4, 'big'))
                
                elif attr_name == 'job-password-supported':
                    # Longitud máxima de contraseña para trabajos: 0=no soportado
                    self._write_attribute(response, 0x21, 'job-password-supported', (0).to_bytes(4, 'big'))
                
                elif attr_name == 'media-source-default':
                    # Fuente de papel por defecto
                    self._write_attribute(response, 0x44, 'media-source-default', 'auto')
                
                elif attr_name == 'media-source-supported':
                    # Fuentes de papel soportadas
                    for source in ['auto', 'main', 'manual']:
                        self._write_attribute(response, 0x44, 'media-source-supported', source)
                
                elif attr_name == 'multiple-document-handling-default':
                    # Manejo de múltiples documentos por defecto
                    self._write_attribute(response, 0x44, 'multiple-document-handling-default', 'separate-documents-uncollated-copies')
                
                elif attr_name == 'client-info-supported':
                    # Información del cliente soportada (IPP Everywhere)
                    for info in ['client-name', 'client-version']:
                        self._write_attribute(response, 0x44, 'client-info-supported', info)
                
                elif attr_name == 'document-format-details-supported':
                    # Detalles de formato de documento soportados
                    for detail in ['document-format', 'document-format-version']:
                        self._write_attribute(response, 0x44, 'document-format-details-supported', detail)
                
                elif attr_name == 'mopria-certified':
                    # Certificación Mopria (para impresión móvil)
                    # Versión 1.3 es común, pero puedes ajustar según necesites
                    self._write_attribute(response, 0x41, 'mopria-certified', '1.3')
                
                elif attr_name == 'mopria_certified':
                    # Variante con guión bajo (algunos clientes lo solicitan así)
                    self._write_attribute(response, 0x41, 'mopria_certified', '1.3')
                
                elif attr_name == 'printer-firmware-name':
                    # Nombre del firmware
                    self._write_attribute(response, 0x41, 'printer-firmware-name', 'ONE-POS-Firmware')
                
                elif attr_name == 'printer-firmware-string-version':
                    # Versión del firmware en formato string
                    self._write_attribute(response, 0x41, 'printer-firmware-string-version', '1.0.0')
                
                elif attr_name == 'printer-strings-languages-supported':
                    # Idiomas soportados para strings de la impresora
                    for lang in ['en', 'es', 'en-us', 'es-es']:
                        self._write_attribute(response, 0x48, 'printer-strings-languages-supported', lang)
                
                # ===== ATRIBUTOS ADICIONALES WINDOWS/CUPS AVANZADOS =====
                
                elif attr_name == 'number-up-supported':
                    # N-up soportado (páginas por hoja) - solo 1 para impresora térmica
                    self._write_attribute(response, 0x21, 'number-up-supported', (1).to_bytes(4, 'big'))
                
                elif attr_name == 'output-bin-default':
                    # Bandeja de salida por defecto
                    self._write_attribute(response, 0x44, 'output-bin-default', 'face-up')
                
                elif attr_name == 'output-bin-supported':
                    # Bandejas de salida soportadas
                    self._write_attribute(response, 0x44, 'output-bin-supported', 'face-up')
                
                elif attr_name == 'orientation-requested-default':
                    # Orientación por defecto: 3=portrait
                    self._write_attribute(response, 0x23, 'orientation-requested-default', (3).to_bytes(4, 'big'))
                
                elif attr_name == 'sides-default':
                    # Impresión por defecto: one-sided (térmica no tiene duplex)
                    self._write_attribute(response, 0x44, 'sides-default', 'one-sided')
                
                elif attr_name == 'sides-supported':
                    # Lados soportados
                    self._write_attribute(response, 0x44, 'sides-supported', 'one-sided')
                
                elif attr_name == 'print-color-mode-default':
                    # Modo de color por defecto: monochrome (térmica es B&W)
                    self._write_attribute(response, 0x44, 'print-color-mode-default', 'monochrome')
                
                elif attr_name == 'print-color-mode-supported':
                    # Modos de color soportados
                    self._write_attribute(response, 0x44, 'print-color-mode-supported', 'monochrome')
                
                elif attr_name == 'pages-per-minute':
                    # Páginas por minuto (estimado para térmica: ~10 ppm)
                    self._write_attribute(response, 0x21, 'pages-per-minute', (10).to_bytes(4, 'big'))
                
                elif attr_name == 'pages-per-minute-color':
                    # PPM color: 0 (no soporta color)
                    self._write_attribute(response, 0x21, 'pages-per-minute-color', (0).to_bytes(4, 'big'))
                
                elif attr_name == 'printer-output-tray':
                    # Información de bandeja de salida
                    # Format: "process-option=value;process-option=value"
                    self._write_attribute(response, 0x41, 'printer-output-tray', 'type=unRemovableBin;maxcapacity=-1;remaining=-1;status=0;name=top')
                
                # ===== ATRIBUTOS PCLm (HP PCL mobile) =====
                
                elif attr_name == 'pclm-raster-back-side':
                    # Lado trasero para PCLm (not applicable for thermal)
                    self._write_attribute(response, 0x44, 'pclm-raster-back-side', 'normal')
                
                elif attr_name == 'pclm-source-resolution-supported':
                    # Resoluciones PCLm soportadas
                    # Format: resolution (xres, yres, units)
                    resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
                    self._write_attribute(response, 0x32, 'pclm-source-resolution-supported', resolution)
                
                # ===== ATRIBUTOS PDF =====
                
                elif attr_name == 'pdf-fit-to-page-default':
                    # Ajustar PDF a página por defecto: false
                    self._write_attribute(response, 0x22, 'pdf-fit-to-page-default', (0).to_bytes(1, 'big'))
                
                elif attr_name == 'pdf-fit-to-page-supported':
                    # Ajustar PDF a página soportado: true y false
                    self._write_attribute(response, 0x22, 'pdf-fit-to-page-supported', (1).to_bytes(1, 'big'))
                    self._write_attribute(response, 0x22, 'pdf-fit-to-page-supported', (0).to_bytes(1, 'big'))
                
                # ===== ATRIBUTOS PRESENTACIÓN Y ESCALADO =====
                
                elif attr_name == 'presentation-direction-number-up-default':
                    # Dirección de presentación para N-up: toright-tobottom
                    self._write_attribute(response, 0x44, 'presentation-direction-number-up-default', 'toright-tobottom')
                
                elif attr_name == 'presentation-direction-number-up-supported':
                    # Direcciones soportadas
                    for direction in ['toright-tobottom', 'tobottom-toright']:
                        self._write_attribute(response, 0x44, 'presentation-direction-number-up-supported', direction)
                
                elif attr_name == 'print-scaling-default':
                    # Escalado por defecto: auto
                    self._write_attribute(response, 0x44, 'print-scaling-default', 'auto')
                
                elif attr_name == 'print-scaling-supported':
                    # Escalados soportados
                    for scaling in ['auto', 'fill', 'fit', 'none']:
                        self._write_attribute(response, 0x44, 'print-scaling-supported', scaling)
                
                # ===== ATRIBUTOS PWG RASTER AVANZADOS =====
                
                elif attr_name == 'pwg-raster-document-sheet-back':
                    # Configuración de hoja trasera PWG (not applicable - one-sided)
                    self._write_attribute(response, 0x44, 'pwg-raster-document-sheet-back', 'normal')
                
                # ===== ATRIBUTOS CRÍTICOS PARA WINDOWS PRINT-JOB =====
                
                elif attr_name == 'pdl-override-supported':
                    # CRÍTICO: Indica si el servidor puede sobreescribir PDL (Page Description Language)
                    # Windows necesita esto para saber si puede enviar el formato preferido
                    self._write_attribute(response, 0x44, 'pdl-override-supported', 'attempted')
                
                elif attr_name == 'ipp-features-supported':
                    # Características IPP soportadas (IPP Everywhere)
                    for feature in ['ipp-everywhere', 'airprint-1.4', 'document-object']:
                        self._write_attribute(response, 0x44, 'ipp-features-supported', feature)
                
                elif attr_name == 'job-creation-attributes-supported':
                    # Atributos soportados al crear trabajos
                    for attr in ['copies', 'media', 'sides', 'print-quality', 'print-color-mode', 
                                'orientation-requested', 'printer-resolution']:
                        self._write_attribute(response, 0x44, 'job-creation-attributes-supported', attr)
                
                elif attr_name == 'printer-settable-attributes-supported':
                    # Atributos que el cliente puede modificar
                    for attr in ['printer-location', 'printer-info']:
                        self._write_attribute(response, 0x44, 'printer-settable-attributes-supported', attr)
                
                elif attr_name == 'document-charset-default':
                    # Charset por defecto para documentos
                    self._write_attribute(response, 0x47, 'document-charset-default', 'utf-8')
                
                elif attr_name == 'document-charset-supported':
                    # Charsets soportados
                    for charset in ['utf-8', 'us-ascii', 'iso-8859-1']:
                        self._write_attribute(response, 0x47, 'document-charset-supported', charset)
                
                elif attr_name == 'document-natural-language-default':
                    # Idioma natural por defecto
                    self._write_attribute(response, 0x48, 'document-natural-language-default', 'es')
                
                elif attr_name == 'document-natural-language-supported':
                    # Idiomas naturales soportados
                    for lang in ['en', 'es', 'en-us', 'es-cl']:
                        self._write_attribute(response, 0x48, 'document-natural-language-supported', lang)
                
                elif attr_name == 'generated-natural-language-supported':
                    # Idiomas para mensajes generados
                    for lang in ['en', 'es']:
                        self._write_attribute(response, 0x48, 'generated-natural-language-supported', lang)
                
                elif attr_name == 'which-jobs-supported':
                    # Qué trabajos se pueden consultar
                    for which in ['completed', 'not-completed', 'all']:
                        self._write_attribute(response, 0x44, 'which-jobs-supported', which)
                
                elif attr_name == 'job-ids-supported':
                    # Indica si soporta job-ids
                    self._write_attribute(response, 0x22, 'job-ids-supported', (1).to_bytes(1, 'big'))
                
                elif attr_name == 'job-k-octets-supported':
                    # Tamaño máximo de trabajo en kilobytes
                    # 0 = sin límite, pero especificamos 100MB = 102400 KB
                    self._write_attribute(response, 0x33, 'job-k-octets-supported', 
                                        (0).to_bytes(4, 'big') + (102400).to_bytes(4, 'big'))
                
                elif attr_name == 'job-priority-default':
                    # Prioridad por defecto (50 = normal)
                    self._write_attribute(response, 0x21, 'job-priority-default', (50).to_bytes(4, 'big'))
                
                elif attr_name == 'job-priority-supported':
                    # Prioridad soportada (1-100)
                    self._write_attribute(response, 0x21, 'job-priority-supported', (100).to_bytes(4, 'big'))
                
                elif attr_name == 'job-hold-until-default':
                    # Retención de trabajo por defecto
                    self._write_attribute(response, 0x44, 'job-hold-until-default', 'no-hold')
                
                elif attr_name == 'job-hold-until-supported':
                    # Opciones de retención
                    for hold in ['no-hold', 'indefinite']:
                        self._write_attribute(response, 0x44, 'job-hold-until-supported', hold)
                
                elif attr_name == 'charset-configured':
                    # Charset configurado (ya implementado arriba, pero por si acaso)
                    self._write_attribute(response, 0x47, 'charset-configured', 'utf-8')
                
                # ========== ATRIBUTOS ADICIONALES ANDROID ==========
                elif attr_name == 'epcl-version-supported':
                    # EPCL (Embedded Printing Command Language) - Samsung/HP printers
                    # No soportamos EPCL específicamente, enviar vacío o versión genérica
                    self._write_attribute(response, 0x44, 'epcl-version-supported', '1.0')
                
                elif attr_name == 'pclm-strip-height-preferred':
                    # PCLm strip height preferido en líneas (típico: 16-256)
                    # Para impresoras térmicas pequeñas, usar strips más pequeños
                    self._write_attribute(response, 0x21, 'pclm-strip-height-preferred', (16).to_bytes(4, 'big'))
                
                elif attr_name == 'pclm-compression-method-preferred':
                    # Método de compresión PCLm preferido
                    # Opciones: 'flate' (deflate/zip), 'rle' (run-length), 'jpeg'
                    self._write_attribute(response, 0x44, 'pclm-compression-method-preferred', 'flate')
                
                elif attr_name == 'media-ready':
                    # Papel actualmente cargado y listo para imprimir
                    # Para impresoras de rollo continuo, indicar el tamaño configurado
                    self._write_attribute(response, 0x44, 'media-ready', 'oe_roll_58mm')
                
                else:
                    logger.debug(f"⚠️ Requested attribute '{attr_name}' not implemented")
            
            # End of attributes
            response.write(bytes([0x03]))
            response_bytes = response.getvalue()
            logger.info(f"✅ Get-Printer-Attributes response: {len(response_bytes)} bytes, "
                       f"{len(requested_attrs)} attributes")
            
            return response_bytes
        
        # ========== MODO COMPLETO: Enviar TODOS los atributos ==========
        logger.debug("Sending complete attribute set (unfiltered)")
        
        try:
            # printer-uri-supported - TODAS las variantes
            for uri in printer_uris:
                self._write_attribute(response, 0x45, 'printer-uri-supported', uri)
            
            # uri-authentication-supported
            for _ in printer_uris:
                self._write_attribute(response, 0x44, 'uri-authentication-supported', 'none')
            
            # uri-security-supported
            for _ in printer_uris:
                self._write_attribute(response, 0x44, 'uri-security-supported', 'none')
            
            # printer-name
            self._write_attribute(response, 0x42, 'printer-name', settings.PRINTER_NAME)
            
            # printer-location
            self._write_attribute(response, 0x41, 'printer-location', settings.PRINTER_LOCATION)
            
            # printer-info
            self._write_attribute(response, 0x41, 'printer-info', settings.PRINTER_INFO)
            
            # printer-make-and-model
            self._write_attribute(response, 0x41, 'printer-make-and-model', settings.PRINTER_MAKE_MODEL)
            
            # Obtener estado consistente
            state_info = self._get_printer_state_info()
            
            # printer-state (3=idle, 4=processing, 5=stopped)
            self._write_attribute(response, 0x23, 'printer-state', state_info['state'].to_bytes(4, 'big'))
            
            # printer-state-reasons
            self._write_attribute(response, 0x44, 'printer-state-reasons', state_info['state_reasons'])
            
            # printer-state-message
            self._write_attribute(response, 0x41, 'printer-state-message', state_info['state_message'])
            
            # printer-is-accepting-jobs
            accepting = 1 if state_info['is_accepting_jobs'] else 0
            self._write_attribute(response, 0x22, 'printer-is-accepting-jobs', accepting.to_bytes(1, 'big'))
            
            # queued-job-count
            self._write_attribute(response, 0x21, 'queued-job-count', len(self.active_jobs).to_bytes(4, 'big'))
            
            # operations-supported
            for op_id in self.SUPPORTED_OPERATIONS.keys():
                self._write_attribute(response, 0x23, 'operations-supported', op_id.to_bytes(4, 'big'))
            
            # document-format-supported
            formats = ['application/octet-stream', 'image/pwg-raster', 'application/vnd.cups-raster',
                    'image/urf', 'application/pdf', 'image/jpeg', 'image/png', 'text/plain']
            for fmt in formats:
                self._write_attribute(response, 0x49, 'document-format-supported', fmt)
            
            # document-format-default
            self._write_attribute(response, 0x49, 'document-format-default', 'application/octet-stream')
            
            # document-format-preferred (formato preferido: PDF es el más universal)
            self._write_attribute(response, 0x49, 'document-format-preferred', 'application/pdf')
            
            # device-uri (URI del dispositivo físico)
            device_uri = f'ipp://{local_ip}:{self.port}/ipp/printer'
            self._write_attribute(response, 0x45, 'device-uri', device_uri)
            
            # printer-dns-sd-name (nombre mDNS/Bonjour)
            dns_sd_name = f"{settings.PRINTER_NAME}._ipp._tcp.local."
            self._write_attribute(response, 0x41, 'printer-dns-sd-name', dns_sd_name)
            
            # printer-more-info (URL de interfaz web)
            more_info_url = f'http://{local_ip}:{self.port}/'
            self._write_attribute(response, 0x45, 'printer-more-info', more_info_url)
            
            # ========== ATRIBUTOS DE MARCADORES (CRÍTICO PARA CUPS) ==========
            # marker-colors
            for color in marker_attrs['marker-colors']:
                self._write_attribute(response, 0x44, 'marker-colors', color)
            
            # marker-names
            for name in marker_attrs['marker-names']:
                self._write_attribute(response, 0x42, 'marker-names', name)
            
            # marker-types
            for mtype in marker_attrs['marker-types']:
                self._write_attribute(response, 0x44, 'marker-types', mtype)
            
            # marker-levels
            for level in marker_attrs['marker-levels']:
                self._write_attribute(response, 0x21, 'marker-levels', level.to_bytes(4, 'big', signed=True))
            
            # marker-high-levels
            for level in marker_attrs['marker-high-levels']:
                self._write_attribute(response, 0x21, 'marker-high-levels', level.to_bytes(4, 'big'))
            
            # marker-low-levels
            for level in marker_attrs['marker-low-levels']:
                self._write_attribute(response, 0x21, 'marker-low-levels', level.to_bytes(4, 'big'))
            
            # marker-message
            for msg in marker_attrs['marker-message']:
                self._write_attribute(response, 0x41, 'marker-message', msg)
            
            # ========== ATRIBUTOS ADICIONALES CUPS ==========
            # compression-supported
            for comp in ['none', 'gzip', 'deflate']:
                self._write_attribute(response, 0x44, 'compression-supported', comp)
            
            # copies-supported (rangeOfInteger)
            self._write_attribute(response, 0x33, 'copies-supported', 
                                (1).to_bytes(4, 'big') + (99).to_bytes(4, 'big'))
            
            # print-color-mode-supported
            self._write_attribute(response, 0x44, 'print-color-mode-supported', 'monochrome')
            
            # media-col-supported
            for attr in ['media-size', 'media-type', 'media-source']:
                self._write_attribute(response, 0x44, 'media-col-supported', attr)
            
            # multiple-document-handling-supported
            self._write_attribute(response, 0x44, 'multiple-document-handling-supported', 
                                'separate-documents-uncollated-copies')
            
            # cups-version
            self._write_attribute(response, 0x41, 'cups-version', '2.4')
            
            # job-password-encryption-supported
            self._write_attribute(response, 0x44, 'job-password-encryption-supported', 'none')
            
            # job-presets-supported (CUPS/macOS extension)
            # Para impresoras simples sin presets, no enviar nada
            # self._write_attribute(response, 0x44, 'job-presets-supported', 'none')
            
            # printer-alert
            self._write_attribute(response, 0x44, 'printer-alert', 'none')
            
            # printer-alert-description
            self._write_attribute(response, 0x41, 'printer-alert-description', 'none')
            
            # printer-mandatory-job-attributes
            self._write_attribute(response, 0x44, 'printer-mandatory-job-attributes', 'none')
            
            # ipp-versions-supported
            for version in ['1.1', '2.0', '2.1']:
                self._write_attribute(response, 0x44, 'ipp-versions-supported', version)
            
            # charset-supported
            for charset in ['utf-8', 'us-ascii']:
                self._write_attribute(response, 0x47, 'charset-supported', charset)
            
            # natural-language-supported
            for lang in ['en-us', 'es-es']:
                self._write_attribute(response, 0x48, 'natural-language-supported', lang)
            
            # media-supported
            for media in ['oe_roll_58mm', 'roll_max_58_203.2x3048']:
                self._write_attribute(response, 0x44, 'media-supported', media)
            
            # media-default
            self._write_attribute(response, 0x44, 'media-default', 'oe_roll_58mm')
            
            # media-col-database (CUPS 2.4+)
            # Colección que describe completamente los tamaños de papel disponibles
            response.write(bytes([0x34]))  # begCollection tag
            response.write((0).to_bytes(2, 'big'))
            response.write((0).to_bytes(2, 'big'))
            
            # media-size
            response.write(bytes([0x4a]))  # memberAttrName
            name_bytes = b'media-size'
            response.write(len(name_bytes).to_bytes(2, 'big'))
            response.write(name_bytes)
            response.write((0).to_bytes(2, 'big'))
            
            # Sub-colección media-size
            response.write(bytes([0x34]))  # begCollection
            response.write((0).to_bytes(2, 'big'))
            response.write((0).to_bytes(2, 'big'))
            
            # x-dimension
            response.write(bytes([0x4a]))
            name_bytes = b'x-dimension'
            response.write(len(name_bytes).to_bytes(2, 'big'))
            response.write(name_bytes)
            response.write((0).to_bytes(2, 'big'))
            response.write(bytes([0x21]))
            response.write((0).to_bytes(2, 'big'))
            response.write((4).to_bytes(2, 'big'))
            response.write((5800).to_bytes(4, 'big'))
            
            # y-dimension
            response.write(bytes([0x4a]))
            name_bytes = b'y-dimension'
            response.write(len(name_bytes).to_bytes(2, 'big'))
            response.write(name_bytes)
            response.write((0).to_bytes(2, 'big'))
            response.write(bytes([0x21]))
            response.write((0).to_bytes(2, 'big'))
            response.write((4).to_bytes(2, 'big'))
            response.write((30000).to_bytes(4, 'big'))
            
            # Cerrar media-size
            response.write(bytes([0x37]))  # endCollection
            response.write((0).to_bytes(2, 'big'))
            response.write((0).to_bytes(2, 'big'))
            
            # media-type
            response.write(bytes([0x4a]))
            name_bytes = b'media-type'
            response.write(len(name_bytes).to_bytes(2, 'big'))
            response.write(name_bytes)
            response.write((0).to_bytes(2, 'big'))
            response.write(bytes([0x44]))
            response.write((0).to_bytes(2, 'big'))
            value_bytes = b'continuous'
            response.write(len(value_bytes).to_bytes(2, 'big'))
            response.write(value_bytes)
            
            # media-source
            response.write(bytes([0x4a]))
            name_bytes = b'media-source'
            response.write(len(name_bytes).to_bytes(2, 'big'))
            response.write(name_bytes)
            response.write((0).to_bytes(2, 'big'))
            response.write(bytes([0x44]))
            response.write((0).to_bytes(2, 'big'))
            value_bytes = b'auto'
            response.write(len(value_bytes).to_bytes(2, 'big'))
            response.write(value_bytes)
            
            # Cerrar colección principal
            response.write(bytes([0x37]))  # endCollection
            response.write((0).to_bytes(2, 'big'))
            response.write((0).to_bytes(2, 'big'))
            
            # ========== ATRIBUTOS AVANZADOS (MODO COMPLETO) ==========
            
            # copies-default
            self._write_attribute(response, 0x21, 'copies-default', (1).to_bytes(4, 'big'))
            
            # orientation-requested-supported
            for orientation in [3, 4]:  # 3=portrait, 4=landscape
                self._write_attribute(response, 0x23, 'orientation-requested-supported', orientation.to_bytes(4, 'big'))
            
            # job-impressions-supported
            self._write_attribute(response, 0x33, 'job-impressions-supported', 
                                (1).to_bytes(4, 'big') + (9999).to_bytes(4, 'big'))
            
            # job-pages-per-set-supported
            self._write_attribute(response, 0x33, 'job-pages-per-set-supported', 
                                (1).to_bytes(4, 'big') + (9999).to_bytes(4, 'big'))
            
            # media-type-supported
            for media_type in ['stationery', 'continuous', 'labels']:
                self._write_attribute(response, 0x44, 'media-type-supported', media_type)
            
            # printer-resolution-default
            resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
            self._write_attribute(response, 0x32, 'printer-resolution-default', resolution)
            
            # printer-resolution-supported
            resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
            self._write_attribute(response, 0x32, 'printer-resolution-supported', resolution)
            
            # print-quality-default
            self._write_attribute(response, 0x23, 'print-quality-default', (4).to_bytes(4, 'big'))
            
            # print-quality-supported
            for quality in [3, 4, 5]:
                self._write_attribute(response, 0x23, 'print-quality-supported', quality.to_bytes(4, 'big'))
            
            # pwg-raster-document-resolution-supported
            resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
            self._write_attribute(response, 0x32, 'pwg-raster-document-resolution-supported', resolution)
            
            # pwg-raster-document-type-supported
            for doc_type in ['black_1', 'sgray_8']:
                self._write_attribute(response, 0x44, 'pwg-raster-document-type-supported', doc_type)
            
            # finishings-default
            self._write_attribute(response, 0x23, 'finishings-default', (3).to_bytes(4, 'big'))
            
            # finishings-supported
            self._write_attribute(response, 0x23, 'finishings-supported', (3).to_bytes(4, 'big'))
            
            # job-password-supported
            self._write_attribute(response, 0x21, 'job-password-supported', (0).to_bytes(4, 'big'))
            
            # media-source-default
            self._write_attribute(response, 0x44, 'media-source-default', 'auto')
            
            # media-source-supported
            for source in ['auto', 'main', 'manual']:
                self._write_attribute(response, 0x44, 'media-source-supported', source)
            
            # multiple-document-handling-default
            self._write_attribute(response, 0x44, 'multiple-document-handling-default', 
                                'separate-documents-uncollated-copies')
            
            # client-info-supported
            for info in ['client-name', 'client-version']:
                self._write_attribute(response, 0x44, 'client-info-supported', info)
            
            # document-format-details-supported
            for detail in ['document-format', 'document-format-version']:
                self._write_attribute(response, 0x44, 'document-format-details-supported', detail)
            
            # mopria-certified
            self._write_attribute(response, 0x41, 'mopria-certified', '1.3')
            
            # printer-firmware-name
            self._write_attribute(response, 0x41, 'printer-firmware-name', 'ONE-POS-Firmware')
            
            # printer-firmware-string-version
            self._write_attribute(response, 0x41, 'printer-firmware-string-version', '1.0.0')
            
            # printer-strings-languages-supported
            for lang in ['en', 'es', 'en-us', 'es-es']:
                self._write_attribute(response, 0x48, 'printer-strings-languages-supported', lang)
            
            # media-size-supported
            self._write_attribute(response, 0x44, 'media-size-supported', '58xvariable')
            
            # media-left-margin-supported
            self._write_attribute(response, 0x21, 'media-left-margin-supported', (0).to_bytes(4, 'big'))
            
            # media-right-margin-supported
            self._write_attribute(response, 0x21, 'media-right-margin-supported', (0).to_bytes(4, 'big'))
            
            # media-bottom-margin-supported
            self._write_attribute(response, 0x21, 'media-bottom-margin-supported', (0).to_bytes(4, 'big'))
            
            # media-top-margin-supported
            self._write_attribute(response, 0x21, 'media-top-margin-supported', (0).to_bytes(4, 'big'))
            
            # media-col-default
            self._write_attribute(response, 0x44, 'media-col-default', 'media-size=58xvariable;media-type=continuous;media-source=main')
            
            # number-up-default
            self._write_attribute(response, 0x21, 'number-up-default', (1).to_bytes(4, 'big'))
            
            # number-up-supported
            self._write_attribute(response, 0x33, 'number-up-supported', 
                                (1).to_bytes(4, 'big') + (1).to_bytes(4, 'big'))
            
            # ========== ATRIBUTOS ADICIONALES AVANZADOS ==========
            
            # output-bin-default
            self._write_attribute(response, 0x44, 'output-bin-default', 'face-up')
            
            # output-bin-supported
            self._write_attribute(response, 0x44, 'output-bin-supported', 'face-up')
            
            # orientation-requested-default
            self._write_attribute(response, 0x23, 'orientation-requested-default', (3).to_bytes(4, 'big'))
            
            # sides-default
            self._write_attribute(response, 0x44, 'sides-default', 'one-sided')
            
            # sides-supported
            self._write_attribute(response, 0x44, 'sides-supported', 'one-sided')
            
            # print-color-mode-default
            self._write_attribute(response, 0x44, 'print-color-mode-default', 'monochrome')
            
            # pages-per-minute
            self._write_attribute(response, 0x21, 'pages-per-minute', (10).to_bytes(4, 'big'))
            
            # pages-per-minute-color
            self._write_attribute(response, 0x21, 'pages-per-minute-color', (0).to_bytes(4, 'big'))
            
            # printer-output-tray
            self._write_attribute(response, 0x41, 'printer-output-tray', 
                                'type=unRemovableBin;maxcapacity=-1;remaining=-1;status=0;name=top')
            
            # pclm-raster-back-side
            self._write_attribute(response, 0x44, 'pclm-raster-back-side', 'normal')
            
            # pclm-source-resolution-supported
            resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
            self._write_attribute(response, 0x32, 'pclm-source-resolution-supported', resolution)
            
            # pdf-fit-to-page-default
            self._write_attribute(response, 0x22, 'pdf-fit-to-page-default', (0).to_bytes(1, 'big'))
            
            # pdf-fit-to-page-supported
            self._write_attribute(response, 0x22, 'pdf-fit-to-page-supported', (1).to_bytes(1, 'big'))
            self._write_attribute(response, 0x22, 'pdf-fit-to-page-supported', (0).to_bytes(1, 'big'))
            
            # presentation-direction-number-up-default
            self._write_attribute(response, 0x44, 'presentation-direction-number-up-default', 'toright-tobottom')
            
            # presentation-direction-number-up-supported
            for direction in ['toright-tobottom', 'tobottom-toright']:
                self._write_attribute(response, 0x44, 'presentation-direction-number-up-supported', direction)
            
            # print-scaling-default
            self._write_attribute(response, 0x44, 'print-scaling-default', 'auto')
            
            # print-scaling-supported
            for scaling in ['auto', 'fill', 'fit', 'none']:
                self._write_attribute(response, 0x44, 'print-scaling-supported', scaling)
            
            # pwg-raster-document-sheet-back
            self._write_attribute(response, 0x44, 'pwg-raster-document-sheet-back', 'normal')
            
            # ========== ATRIBUTOS CRÍTICOS PARA WINDOWS ==========
            
            # pdl-override-supported (CRÍTICO para Windows)
            self._write_attribute(response, 0x44, 'pdl-override-supported', 'attempted')
            
            # ipp-features-supported
            for feature in ['ipp-everywhere', 'airprint-1.4']:
                self._write_attribute(response, 0x44, 'ipp-features-supported', feature)
            
            # job-creation-attributes-supported
            for attr in ['copies', 'media', 'sides', 'print-quality', 'print-color-mode']:
                self._write_attribute(response, 0x44, 'job-creation-attributes-supported', attr)
            
            # which-jobs-supported
            for which in ['completed', 'not-completed', 'all']:
                self._write_attribute(response, 0x44, 'which-jobs-supported', which)
            
            # job-ids-supported
            self._write_attribute(response, 0x22, 'job-ids-supported', (1).to_bytes(1, 'big'))
            
            # job-k-octets-supported (0-100MB)
            self._write_attribute(response, 0x33, 'job-k-octets-supported', 
                                (0).to_bytes(4, 'big') + (102400).to_bytes(4, 'big'))
            
            # job-priority-default y supported
            self._write_attribute(response, 0x21, 'job-priority-default', (50).to_bytes(4, 'big'))
            self._write_attribute(response, 0x21, 'job-priority-supported', (100).to_bytes(4, 'big'))
            
            # job-hold-until
            self._write_attribute(response, 0x44, 'job-hold-until-default', 'no-hold')
            for hold in ['no-hold', 'indefinite']:
                self._write_attribute(response, 0x44, 'job-hold-until-supported', hold)
            
            # document charsets
            self._write_attribute(response, 0x47, 'document-charset-default', 'utf-8')
            for charset in ['utf-8', 'us-ascii', 'iso-8859-1']:
                self._write_attribute(response, 0x47, 'document-charset-supported', charset)
            
            # document languages
            self._write_attribute(response, 0x48, 'document-natural-language-default', 'es')
            for lang in ['en', 'es', 'en-us', 'es-cl']:
                self._write_attribute(response, 0x48, 'document-natural-language-supported', lang)
            
            # generated languages
            for lang in ['en', 'es']:
                self._write_attribute(response, 0x48, 'generated-natural-language-supported', lang)
            
            # ========== ATRIBUTOS ADICIONALES ANDROID ==========
            # epcl-version-supported (Embedded Printing Command Language)
            self._write_attribute(response, 0x44, 'epcl-version-supported', '1.0')
            
            # pclm-strip-height-preferred (PCLm strip height en líneas)
            self._write_attribute(response, 0x21, 'pclm-strip-height-preferred', (16).to_bytes(4, 'big'))
            
            # pclm-compression-method-preferred (método de compresión PCLm)
            self._write_attribute(response, 0x44, 'pclm-compression-method-preferred', 'flate')
            
            # media-ready (papel actualmente cargado)
            self._write_attribute(response, 0x44, 'media-ready', 'oe_roll_58mm')
            
            # End of attributes
            response.write(bytes([0x03]))
            
            response_bytes = response.getvalue()
            logger.info(f"✅ Get-Printer-Attributes response: {len(response_bytes)} bytes, ALL attributes")
            return response_bytes
            
        except Exception as e:
            logger.error(f"❌ Error generating complete attributes response: {e}")
            # Fallback: enviar respuesta de error
            return self._create_error_response(message.request_id, 0x0500, message.version_number)
        
    async def _handle_get_jobs(self, message: IPPMessage) -> bytes:
        response = io.BytesIO()
        
        # IPP header - usar versión del cliente
        response.write(bytes(message.version_number))
        response.write((0x0000).to_bytes(2, 'big'))
        response.write(message.request_id.to_bytes(4, 'big'))
        
        # Operation attributes
        response.write(bytes([0x01]))
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # Log Get-Jobs request
        logger.info(f"📋 Get-Jobs request - {len(self.active_jobs)} active jobs")
        
        # Job attributes for each active job
        for job in self.active_jobs.values():
            response.write(bytes([0x02]))  # job-attributes-tag
            
            # job-id
            self._write_attribute(response, 0x21, 'job-id', job['id'].to_bytes(4, 'big'))
            
            # job-uri
            job_uri = f"ipp://{self.host}:{self.port}/ipp/jobs/{job['id']}"
            self._write_attribute(response, 0x45, 'job-uri', job_uri)
            
            # job-state
            state_map = {'pending': 3, 'processing': 5, 'completed': 9, 'aborted': 8}
            state = state_map.get(job['state'], 3)
            self._write_attribute(response, 0x23, 'job-state', state.to_bytes(4, 'big'))
            
            # job-state-reasons
            reasons = job.get('state_reasons', ['none'])
            for reason in reasons:
                self._write_attribute(response, 0x44, 'job-state-reasons', reason)
            
            # job-name (if available)
            job_name = "Unknown"
            if 'operation_attributes' in job and 'job-name' in job['operation_attributes']:
                job_name_attr = job['operation_attributes']['job-name']
                if hasattr(job_name_attr, 'value'):
                    job_name = str(job_name_attr.value)
            self._write_attribute(response, 0x42, 'job-name', job_name)
            
            # time-at-creation
            if 'creation_time' in job:
                creation_ts = int(job['creation_time'].timestamp())
                self._write_attribute(response, 0x21, 'time-at-creation', creation_ts.to_bytes(4, 'big'))
            
            # time-at-completed (if completed)
            if 'completion_time' in job:
                completion_ts = int(job['completion_time'].timestamp())
                self._write_attribute(response, 0x21, 'time-at-completed', completion_ts.to_bytes(4, 'big'))
            
            logger.debug(f"  Job {job['id']}: state={job['state']} ({state}), name={job_name}")
        
        # End of attributes
        response.write(bytes([0x03]))
        
        logger.info(f"✅ Get-Jobs response: {len(self.active_jobs)} jobs returned")
        
        return response.getvalue()
    
    async def _handle_validate_job(self, message: IPPMessage) -> bytes:
        response = io.BytesIO()
        
        # IPP header - usar versión del cliente
        response.write(bytes(message.version_number))
        response.write((0x0000).to_bytes(2, 'big'))  # successful-ok
        response.write(message.request_id.to_bytes(4, 'big'))
        
        # Operation attributes
        response.write(bytes([0x01]))
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # End of attributes
        response.write(bytes([0x03]))
        
        return response.getvalue()
    
    def _write_attribute(self, stream: io.BytesIO, tag: int, name: str, value):
        # Tag
        stream.write(bytes([tag]))
        
        # Name length and name
        name_bytes = name.encode('utf-8')
        stream.write(len(name_bytes).to_bytes(2, 'big'))
        stream.write(name_bytes)
        
        # Value
        if isinstance(value, str):
            value_bytes = value.encode('utf-8')
        elif isinstance(value, bytes):
            value_bytes = value
        else:
            value_bytes = str(value).encode('utf-8')
        
        stream.write(len(value_bytes).to_bytes(2, 'big'))
        stream.write(value_bytes)
    
    def _create_error_response(self, request_id: int, status_code: int, version: tuple = (2, 0)) -> bytes:
        response = io.BytesIO()
        
        # IPP header - usar versión especificada
        response.write(bytes(version))  # Versión compatible con cliente
        response.write(status_code.to_bytes(2, 'big'))
        response.write(request_id.to_bytes(4, 'big'))
        
        # Operation attributes
        response.write(bytes([0x01]))
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # End of attributes
        response.write(bytes([0x03]))
        
        return response.getvalue()
    
    async def _handle_web_interface(self, writer: asyncio.StreamWriter, keep_alive: bool = False):
        html_content = self._generate_web_interface()
        
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(html_content)}\r\n"
            "Server: ONE-POS-IPP/1.0\r\n"
            f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
        )
        
        if keep_alive:
            response += "Keep-Alive: timeout=30, max=100\r\n"
        
        response += "\r\n"
        
        writer.write(response.encode())
        writer.write(html_content.encode())
        await writer.drain()
    
    async def _handle_status_request(self, writer: asyncio.StreamWriter, keep_alive: bool = False):
        """
        REEMPLAZAR el método _handle_status_request con esta versión mejorada
        """
        status = {
            'server': {
                'name': settings.PRINTER_NAME,
                'version': settings.VERSION,
                'uptime': str(datetime.now() - self.start_time) if self.start_time else '0',
                'is_running': self.is_running
            },
            'printer': {
                'connected': self.printer_backend.is_connected if self.printer_backend else False,
                'width_mm': settings.PRINTER_WIDTH_MM,
                'dpi': settings.PRINTER_DPI
            },
            'jobs': {
                'active': len(self.active_jobs),
                'completed': len(self.completed_jobs),
                'failed': len(self.failed_jobs)
            },
            'network': self.port_manager.get_network_info(),
            'connections': self.get_connection_statistics()  # NUEVO
        }
        
        json_content = json.dumps(status, indent=2, default=str)
        
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            "Server: ONE-POS-IPP/1.0\r\n"
            f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
        )
        
        if keep_alive:
            response += "Keep-Alive: timeout=30, max=100\r\n"
        
        response += "\r\n"
        
        writer.write(response.encode())
        writer.write(json_content.encode())
        await writer.drain()

    async def _handle_icon_request(self, writer: asyncio.StreamWriter, keep_alive: bool, path: str):
        """Devuelve un PNG mínimo para atributos printer-icons solicitados por CUPS/AirPrint."""
        # PNG 1x1 transparente (chunk válido) generado previamente
        # Hex: 89504E470D0A1A0A 0000000D49484452 00000001 00000001 0806000000 1F15C489
        #      0000000A49444154 789C6360000002000154 0B0DBD 0000000049454E44AE426082
        png_hex = (
            "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
            "0000000a49444154789c63600000020001540b0dbd0000000049454e44ae426082"
        )
        data = bytes.fromhex(png_hex)
        headers = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: image/png\r\n"
            f"Content-Length: {len(data)}\r\n"
            "Cache-Control: max-age=3600\r\n"
            f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
        )
        if keep_alive:
            headers += "Keep-Alive: timeout=30, max=100\r\n"
        headers += "\r\n"
        writer.write(headers.encode())
        writer.write(data)
        await writer.drain()
        logger.debug(f"✅ Icon {path} servido ({len(data)} bytes)")
    
    def _generate_web_interface(self) -> str:
        network_info = self.port_manager.get_network_info()
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{settings.PRINTER_NAME} - IPP Print Server</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
                .container {{ max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                h1 {{ color: #333; border-bottom: 2px solid #007cba; padding-bottom: 10px; }}
                .status {{ padding: 15px; margin: 20px 0; border-radius: 4px; }}
                .online {{ background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
                .offline {{ background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
                .info-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
                .info-card {{ padding: 15px; background: #f8f9fa; border-left: 4px solid #007cba; }}
                .info-card h3 {{ margin: 0 0 10px 0; color: #007cba; }}
                .config-box {{ background: #e9ecef; padding: 15px; margin: 20px 0; border-radius: 4px; font-family: monospace; }}
                .jobs {{ margin: 20px 0; }}
                button {{ background: #007cba; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; }}
                button:hover {{ background: #005a8b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>📨 {settings.PRINTER_NAME}</h1>
                <p>ONE-POS Universal IPP Print Server v{settings.VERSION}</p>
                
                <div class="status {'online' if self.printer_backend and self.printer_backend.is_connected else 'offline'}">
                    <strong>Status:</strong> {'🟢 Online - Ready to print' if self.printer_backend and self.printer_backend.is_connected else '🔴 Offline - No printer connected'}
                </div>
                
                <div class="info-grid">
                    <div class="info-card">
                        <h3>🖨️ Printer Info</h3>
                        <p><strong>Width:</strong> {settings.PRINTER_WIDTH_MM}mm</p>
                        <p><strong>Resolution:</strong> {settings.PRINTER_DPI} DPI</p>
                        <p><strong>Max Width:</strong> {settings.PRINTER_MAX_PIXELS}px</p>
                    </div>
                    
                    <div class="info-card">
                        <h3>🌐 Network Info</h3>
                        <p><strong>Host:</strong> {network_info['local_ip']}</p>
                        <p><strong>Port:</strong> {self.port}</p>
                        <p><strong>Platform:</strong> {network_info['platform'].title()}</p>
                    </div>
                </div>
                
                <div class="jobs">
                    <h3>📋 Job Statistics</h3>
                    <p>Active jobs: <strong>{len(self.active_jobs)}</strong></p>
                    <p>Completed jobs: <strong>{len(self.completed_jobs)}</strong></p>
                    <p>Failed jobs: <strong>{len(self.failed_jobs)}</strong></p>
                </div>
                
                <h3>📱 Client Configuration</h3>
                <div class="config-box">
        Host/Server: {network_info['local_ip']}<br>
        Port: {self.port}<br>
        Protocol: IPP<br>
        URI: ipp://{network_info['local_ip']}:{self.port}/ipp/printer<br>
        Queue/Path: /ipp/printer
                </div>
                
                <p><button onclick="location.reload()">🔄 Refresh</button> 
                <button onclick="window.open('/status', '_blank')">📊 JSON Status</button></p>
                
                <hr style="margin: 30px 0;">
                <p style="text-align: center; color: #666; font-size: 12px;">
                    Uptime: {str(datetime.now() - self.start_time) if self.start_time else 'Unknown'}<br>
                    ONE-POS Utilities | Thermal Printer IPP Server
                </p>
            </div>
        </body>
        </html>
                """
    async def _handle_options_request(self, writer: asyncio.StreamWriter, path: str, keep_alive: bool = False):
        logger.info(f"🔍 Handling OPTIONS request for {path}")
        
        # Métodos permitidos según el path
        if path in ['/ipp/printer', '/ipp/print', '/', '/ipp']:
            allowed_methods = 'GET, HEAD, POST, OPTIONS'
        else:
            allowed_methods = 'GET, HEAD, OPTIONS'
        
        response = (
            "HTTP/1.1 200 OK\r\n"
            f"Allow: {allowed_methods}\r\n"
            "Accept: application/ipp\r\n"
            "Content-Type: application/ipp\r\n"
            "Content-Length: 0\r\n"
            "Server: CUPS/2.4 IPP/2.1\r\n"
            f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
        )
        
        # Agregar Keep-Alive header si está activo
        if keep_alive:
            response += "Keep-Alive: timeout=30, max=100\r\n"
        
        response += "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
        response += "\r\n"
        
        writer.write(response.encode())
        await writer.drain()
        logger.debug(f"✅ OPTIONS response sent for {path} (Keep-Alive: {keep_alive})")
    
    async def _handle_head_request(self, writer: asyncio.StreamWriter, path: str, keep_alive: bool = False):
        logger.info(f"📋 Handling HEAD request for {path}")
        
        if path in ['/ipp/printer', '/ipp/print', '/', '/ipp']:
            content_type = 'application/ipp'
        else:
            content_type = 'text/html'
        
        response = (
            "HTTP/1.1 200 OK\r\n"
            f"Content-Type: {content_type}\r\n"
            "Server: CUPS/2.4 IPP/2.1\r\n"
            "Accept-Ranges: none\r\n"
            f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
        )
        
        if keep_alive:
            response += "Keep-Alive: timeout=30, max=100\r\n"
        
        response += "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
        response += "\r\n"
        
        writer.write(response.encode())
        await writer.drain()
        logger.debug(f"✅ HEAD response sent for {path} (Keep-Alive: {keep_alive})")

    async def _send_http_error(self, writer: asyncio.StreamWriter, status_code: int, message: str, keep_alive: bool = False):
        response = (
            f"HTTP/1.1 {status_code} {message}\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            "Server: CUPS/2.4 IPP/2.1\r\n"
            f"Connection: {'keep-alive' if keep_alive else 'close'}\r\n"
        )
        
        if keep_alive:
            response += "Keep-Alive: timeout=30, max=50\r\n"
        
        response += "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
        response += "\r\n"
        response += f"{message}"
        
        writer.write(response.encode())
        await writer.drain()
    

    def _log_cups_handshake(self, client_ip: str, operation: str, headers: dict, message: IPPMessage = None):
        """
        REEMPLAZAR el método _log_cups_handshake con esta versión más silenciosa
        """
        # Solo loguear en modo DEBUG muy detallado
        if not logger.isEnabledFor(logging.DEBUG):
            return
        
        # Solo loguear CUPS handshakes si hay contenido IPP real
        if message and message.operation_id:
            logger.debug("=" * 60)
            logger.debug(f"CUPS HANDSHAKE - {operation}")
            logger.debug("=" * 60)
            logger.debug(f"Client: {client_ip}")
            logger.debug(f"Operation: 0x{message.operation_id:04x}")
            logger.debug(f"Attributes: {len(message.operation_attributes)}")
            logger.debug("=" * 60)
    
    def get_connection_info(self) -> Dict[str, Any]:
        network_info = self.port_manager.get_network_info()
        
        return {
            'local_ip': network_info['local_ip'],
            'hostname': network_info['hostname'],
            'port': self.port,
            'ipp_uri': f"ipp://{network_info['local_ip']}:{self.port}/ipp/printer",
            'web_uri': f"http://{network_info['local_ip']}:{self.port}/",
            'platform': network_info['platform'],
            'port_changed': self.port != self.requested_port if self.requested_port else False
        }
    
    async def stop(self):
        self.is_running = False
        
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            logger.info("IPP Server stopped")