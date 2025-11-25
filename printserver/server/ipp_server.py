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
        
        # Parse attributes (simplified)
        offset = 8
        current_group = None
        attr_count = 0
        
        while offset < len(data):
            if offset + 1 >= len(data):
                logger.debug(f"End of data reached at offset {offset}")
                break
                
            tag = data[offset]
            offset += 1
            
            if tag == 0x01:  # operation-attributes-tag
                current_group = 'operation'
                logger.debug("Found operation-attributes-tag")
                continue
            elif tag == 0x02:  # job-attributes-tag
                current_group = 'job'
                logger.debug("Found job-attributes-tag")
                continue
            elif tag == 0x04:  # printer-attributes-tag
                current_group = 'printer'
                logger.debug("Found printer-attributes-tag")
                continue
            elif tag == 0x03:  # end-of-attributes-tag
                # Document data follows
                doc_size = len(data) - offset
                logger.debug(f"Found end-of-attributes-tag, document data: {doc_size} bytes")
                message.document_data = data[offset:]
                break
            
            # Parse attribute (simplified)
            if offset + 2 >= len(data):
                logger.debug(f"Not enough data for attribute at offset {offset}")
                break
                
            name_length = int.from_bytes(data[offset:offset+2], 'big')
            offset += 2
            
            if offset + name_length >= len(data):
                logger.debug(f"Insufficient data for attribute name at offset {offset}, need {name_length} bytes")
                break
                
            name = data[offset:offset+name_length].decode('utf-8', errors='ignore')
            offset += name_length
            
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
            
            if current_group == 'operation':
                message.operation_attributes[name] = attr_value
            elif current_group == 'job':
                message.job_attributes[name] = attr_value
            elif current_group == 'printer':
                message.printer_attributes[name] = attr_value
                
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
        
        # Server state
        self.is_running = False
        self.start_time = None
    
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
        
        # Initialize debugging session
        if DEBUG_ENABLED:
            log_android_debug(client_ip, f"New connection from {client_type}", {
                'client_addr': str(client_addr),
                'client_type': client_type
            })
        
        try:
            keep_alive = True
            # Loop para soportar múltiples requests en la misma conexión (CUPS)
            while keep_alive:
                timeout_duration = 3.0 if is_android else 10.0
                try:
                    request_line = await asyncio.wait_for(reader.readline(), timeout=timeout_duration)
                except asyncio.TimeoutError:
                    logger.debug(f"Connection timeout from {client_addr} after {timeout_duration}s, closing")
                    if DEBUG_ENABLED:
                        log_android_debug(client_ip, "Timeout waiting for request", {'client_type': client_type})
                    break

                # EOF / cierre
                if not request_line:
                    logger.debug(f"EOF from {client_addr}")
                    break

                # TCP probe vacío
                if len(request_line.strip()) == 0:
                    logger.info(f"🔍 Empty probe from {client_ip}")
                    wait_time = 0.5 if is_android else 2.0
                    await asyncio.sleep(wait_time)
                    # Intentar siguiente iteración
                    continue

                raw_request_line = request_line[:100]
                logger.debug(f"📄 Request line raw: {raw_request_line}")
                request_line_str = request_line.decode('utf-8', errors='ignore').strip()
                if not request_line_str:
                    await self._send_http_error(writer, 400, "Bad Request", keep_alive=False)
                    break

                parts = request_line_str.split()
                if len(parts) < 2:
                    await self._send_http_error(writer, 400, "Bad Request", keep_alive=False)
                    break

                method, path = parts[0], parts[1]
                version = parts[2] if len(parts) >= 3 else "HTTP/1.0"
                if version not in ["HTTP/1.0", "HTTP/1.1"]:
                    version = "HTTP/1.0"

                # Normalizar path CUPS /printers/<queue>
                if path.startswith('/printers/'):
                    path = '/ipp/printer'

                headers = {}
                content_length = 0
                transfer_encoding = None
                expect_continue = False
                connection_type = 'close'

                while True:
                    header_line = await reader.readline()
                    if not header_line or header_line == b'\r\n':
                        break
                    h = header_line.decode('utf-8', errors='ignore').strip()
                    if ':' in h:
                        k, v = h.split(':', 1)
                        k_l = k.strip().lower()
                        v_s = v.strip()
                        headers[k_l] = v_s
                        if k_l == 'content-length':
                            try:
                                content_length = int(v_s)
                            except ValueError:
                                content_length = 0
                        elif k_l == 'transfer-encoding':
                            transfer_encoding = v_s.lower()
                        elif k_l == 'expect' and '100-continue' in v_s.lower():
                            expect_continue = True
                        elif k_l == 'connection':
                            connection_type = v_s.lower()

                keep_alive = (connection_type == 'keep-alive' and version == 'HTTP/1.1')

                if expect_continue:
                    writer.write(b"HTTP/1.1 100 Continue\r\n\r\n")
                    await writer.drain()

                logger.info(f"📨 {method} {path} {version} from {client_ip} keep_alive={keep_alive}")

                # Routing
                if method == 'OPTIONS':
                    await self._handle_options_request(writer, path, keep_alive)
                elif method == 'HEAD':
                    await self._handle_head_request(writer, path, keep_alive)
                elif method == 'GET' and path == '/':
                    await self._handle_web_interface(writer)
                elif method == 'GET' and path == '/status':
                    await self._handle_status_request(writer)
                elif method == 'POST' and path in ['/ipp/print', '/ipp/printer', '/ipp', '/']:
                    await self._handle_ipp_request(reader, writer, headers, client_ip, content_length, transfer_encoding, keep_alive)
                else:
                    logger.warning(f"🚫 Unhandled request: {method} {path}")
                    await self._send_http_error(writer, 404, "Not Found", keep_alive)

                if not keep_alive:
                    break

        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
            import traceback
            logger.debug(f"Client handler error: {traceback.format_exc()}")
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
        client_addr = writer.get_extra_info('peername')
        if not client_ip:
            client_ip = client_addr[0] if client_addr else "unknown"
        
        try:
            user_agent = headers.get('user-agent', 'unknown')
            logger.info(f"📱 Client: {user_agent} from {client_ip}")
            
            # Determine how to read the body
            ipp_data = b''
            
            if transfer_encoding == 'chunked':
                # Read chunked data
                logger.debug(f"📦 Reading chunked data from {client_ip}")
                chunks = []
                total_size = 0
                
                while True:
                    # Read chunk size line
                    chunk_size_line = await reader.readline()
                    if not chunk_size_line:
                        break
                    
                    # Parse chunk size (hex)
                    try:
                        chunk_size = int(chunk_size_line.strip(), 16)
                    except ValueError:
                        logger.error(f"Invalid chunk size: {chunk_size_line}")
                        break
                    
                    if chunk_size == 0:
                        # Last chunk, read trailing headers if any
                        await reader.readline()  # Read final CRLF
                        break
                    
                    # Read chunk data
                    chunk_data = await reader.readexactly(chunk_size)
                    chunks.append(chunk_data)
                    total_size += chunk_size
                    
                    # Read trailing CRLF after chunk
                    await reader.readline()
                    
                    logger.debug(f"📦 Read chunk: {chunk_size} bytes (total: {total_size})")
                
                ipp_data = b''.join(chunks)
                actual_length = len(ipp_data)
                logger.info(f"✅ Chunked transfer complete: {actual_length} bytes")
                
            elif content_length > 0:
                # Read with Content-Length
                logger.debug(f"📄 Reading {content_length} bytes from {client_ip}")
                ipp_data = await reader.read(content_length)
                actual_length = len(ipp_data)
                logger.debug(f"Read {actual_length}/{content_length} bytes")
                
            else:
                # Try to read whatever is available (fallback)
                logger.warning(f"⚠️ No Content-Length or Transfer-Encoding, reading available data")
                # Set a reasonable timeout for reading
                try:
                    ipp_data = await asyncio.wait_for(reader.read(10 * 1024 * 1024), timeout=5.0)
                    actual_length = len(ipp_data)
                    logger.info(f"📄 Read {actual_length} bytes without explicit length")
                except asyncio.TimeoutError:
                    logger.error("❌ Timeout reading request data")
                    await self._send_http_error(writer, 408, "Request Timeout")
                    return
            
            # Validate we have data
            if not ipp_data or len(ipp_data) == 0:
                logger.warning(f"⚠️ No data received from {client_addr}")
                if DEBUG_ENABLED and self._is_android_client(client_ip):
                    log_android_debug(client_ip, "ERROR: No IPP data received", {
                        'headers': dict(headers),
                        'content_length': content_length,
                        'transfer_encoding': transfer_encoding
                    })
                await self._send_http_error(writer, 400, "No content")
                return
            
            actual_length = len(ipp_data)
            logger.info(f"✅ Received {actual_length} bytes of IPP data from {client_ip}")
            
            # Save request data for analysis
            if DEBUG_ENABLED and self._is_android_client(client_ip):
                save_request_data(client_ip, ipp_data, headers, "/ipp/printer")
                log_android_debug(client_ip, f"IPP data received: {actual_length} bytes", {
                    'expected': content_length if content_length > 0 else 'chunked',
                    'received': actual_length,
                    'data_preview': ipp_data[:100].hex() if len(ipp_data) > 0 else 'empty',
                    'transfer_encoding': transfer_encoding
                })
            
            # Validate IPP data has minimum header
            if actual_length < 8:
                logger.error(f"❌ IPP data too short from {client_addr}: {actual_length} bytes")
                await self._send_http_error(writer, 400, "Invalid IPP data")
                return
            
            # Parse IPP message
            logger.debug(f"Parsing IPP message from {client_addr}")
            message = parse_ipp_request(ipp_data)
            
            if DEBUG_ENABLED and self._is_android_client(client_ip):
                log_android_debug(client_ip, "IPP message parsed", {
                    'operation_id': f"0x{message.operation_id:04x}" if message.operation_id else "None",
                    'request_id': message.request_id,
                    'version': message.version_number,
                    'operation_attributes': len(message.operation_attributes),
                    'document_data_size': len(message.document_data) if message.document_data else 0
                })
            
            if message.operation_id is None:
                logger.error(f"❌ Failed to parse IPP operation from {client_addr}")
                if DEBUG_ENABLED and self._is_android_client(client_ip):
                    log_android_debug(client_ip, "ERROR: Failed to parse IPP operation")
                await self._send_http_error(writer, 400, "Invalid IPP message")
                return
            
            # Log operation details
            operation_name = self.SUPPORTED_OPERATIONS.get(message.operation_id, f'Unknown-0x{message.operation_id:04x}')
            logger.info(f"🔧 Processing: {operation_name} from {client_ip}")
            
            # Handle operation
            logger.debug(f"Processing IPP operation from {client_addr}")
            response_data = await self._process_ipp_operation(message, client_ip)
            
            if not response_data:
                logger.error(f"❌ No response data generated for {client_addr}")
                await self._send_http_error(writer, 500, "Failed to process operation")
                return
            
            # Send HTTP response - Optimizado para CUPS (fix concatenation)
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/ipp\r\n"
                f"Content-Length: {len(response_data)}\r\n"
                "Server: CUPS/2.4 IPP/2.1\r\n"
                "Content-Language: en\r\n"
                "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
                f"Connection: {'Keep-Alive' if keep_alive else 'close'}\r\n"
                + ("Keep-Alive: timeout=5, max=100\r\n" if keep_alive else "")
                + "Cache-Control: no-cache\r\n"
                + "\r\n"
            )
            
            logger.debug(f"Sending {len(response_data)} bytes response to {client_addr}")
            writer.write(response_headers.encode())
            writer.write(response_data)
            await writer.drain()
            logger.info(f"✅ Response sent successfully to {client_ip}: {len(response_data)} bytes")
            
        except Exception as e:
            logger.error(f"❌ Error processing IPP request from {client_addr}: {e}")
            import traceback
            logger.debug(f"IPP error traceback: {traceback.format_exc()}")
            try:
                await self._send_http_error(writer, 500, "IPP Processing Error")
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
                # CORRECCIÓN: Iterar sobre el diccionario correctamente
                for i, (attr_name, attr_value) in enumerate(message.operation_attributes.items()):
                    if i >= 5:  # Solo mostrar los primeros 5
                        break
                    logger.debug(f"  Attribute: {attr_name}={attr_value.value}")
            
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
                logger.debug("Routing to _handle_get_jobs")
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
                    response.write(bytes([2,0]))
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
                    return self._create_error_response(message.request_id, 0x0405)  # client-error-not-found
            else:
                logger.warning(f"❌ Unsupported IPP operation: 0x{message.operation_id:04x}")
                return self._create_error_response(message.request_id, 0x0501)  # server-error-operation-not-supported
                
        except Exception as e:
            logger.error(f"❌ Error in _process_ipp_operation: {e}")
            import traceback
            logger.debug(f"Operation processing error traceback: {traceback.format_exc()}")
            return self._create_error_response(getattr(message, 'request_id', 1), 0x0500)  # server-error-internal-error
    
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
                return self._create_error_response(message.request_id, 0x0400)  # client-error-bad-request
            
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
            return self._create_print_job_response(message.request_id, job_id)
            
        except Exception as e:
            logger.error(f"❌ Error in print job handler: {e}")
            import traceback
            logger.debug(f"Print job handler error: {traceback.format_exc()}")
            return self._create_error_response(message.request_id, 0x0500)  # server-error-internal-error
    
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
            # Move job to completed/failed list
            job['completion_time'] = datetime.now()
            if job['state'] == 'completed':
                self.completed_jobs.append(job)
                logger.info(f"✅ Job {job_id} completed and archived")
            else:
                self.failed_jobs.append(job)
                logger.warning(f"❌ Job {job_id} failed with state: {job['state']}")
            
            # Remove from active jobs
            self.active_jobs.pop(job_id, None)
    
    def _create_print_job_response(self, request_id: int, job_id: int) -> bytes:
        response = io.BytesIO()
        
        # IPP header
        response.write(bytes([2, 0]))  # Version 2.0
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
    
    async def _handle_get_printer_attributes(self, message: IPPMessage) -> bytes:
        response = io.BytesIO()
        
        # IPP header
        response.write(bytes([2, 0]))  # Version 2.0
        response.write((0x0000).to_bytes(2, 'big'))  # successful-ok
        response.write(message.request_id.to_bytes(4, 'big'))
        
        # Operation attributes group
        response.write(bytes([0x01]))
        
        # Required attributes
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # Printer attributes group
        response.write(bytes([0x04]))
        
        # Get actual network information
        network_info = self.port_manager.get_network_info()
        local_ip = network_info['local_ip']
        
        # printer-uri-supported - TODAS las variantes para máxima compatibilidad
        # CUPS prefiere URIs específicos y consistentes
        printer_uris = [
            f'ipp://{local_ip}:{self.port}/ipp/printer',  # Estándar IPP
            f'ipp://{local_ip}:{self.port}/ipp/print',    # Alternativo común
            f'ipp://{local_ip}:{self.port}/',              # Root path
            f'http://{local_ip}:{self.port}/ipp/printer', # HTTP fallback
            f'ipp://{local_ip}:{self.port}/ipp',          # Sin trailing slash
        ]
        
        for uri in printer_uris:
            self._write_attribute(response, 0x45, 'printer-uri-supported', uri)
        
        # uri-authentication-supported - para cada URI
        for _ in printer_uris:
            self._write_attribute(response, 0x44, 'uri-authentication-supported', 'none')
        
        # uri-security-supported - para cada URI
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
        
        # printer-state (3=idle, 4=processing, 5=stopped)
        # Check printer backend status properly
        if self.printer_backend and hasattr(self.printer_backend, 'is_ready'):
            if self.printer_backend.is_ready():
                state = 3  # idle - printer is ready
            else:
                state = 5  # stopped - printer not ready
        elif self.printer_backend and hasattr(self.printer_backend, 'is_connected'):
            state = 3 if self.printer_backend.is_connected else 5
        else:
            state = 5  # stopped - no backend available
        self._write_attribute(response, 0x23, 'printer-state', state.to_bytes(4, 'big'))
        
        # printer-state-reasons
        reasons = 'none'
        self._write_attribute(response, 0x44, 'printer-state-reasons', reasons)
        
        # printer-is-accepting-jobs - CRUCIAL para CUPS
        self._write_attribute(response, 0x22, 'printer-is-accepting-jobs', (1).to_bytes(1, 'big'))
        
        # queued-job-count - CUPS lo revisa
        self._write_attribute(response, 0x21, 'queued-job-count', len(self.active_jobs).to_bytes(4, 'big'))
        
        # operations-supported - En orden de preferencia para CUPS
        for op_id in self.SUPPORTED_OPERATIONS.keys():
            self._write_attribute(response, 0x23, 'operations-supported', op_id.to_bytes(4, 'big'))
        
        # document-format-supported - ORDEN IMPORTANTE: preferir formatos raw primero
        formats = [
            'application/octet-stream',  # Raw - PRIMERO para que Android lo prefiera
            'image/pwg-raster',          # PWG Raster - formato estándar IPP
            'application/vnd.cups-raster',  # CUPS raster
            'image/urf',                 # URF para AirPrint
            'application/pdf',
            'image/jpeg',
            'image/png',
            'text/plain',
        ]
        for fmt in formats:
            self._write_attribute(response, 0x49, 'document-format-supported', fmt)
        
        # document-format-default - RAW para procesamiento local
        self._write_attribute(response, 0x49, 'document-format-default', 'application/octet-stream')
        
        # document-format-preferred - PWG Raster es el estándar
        self._write_attribute(response, 0x49, 'document-format-preferred', 'image/pwg-raster')
        
        # charset-supported
        for charset in ['utf-8', 'us-ascii']:
            self._write_attribute(response, 0x47, 'charset-supported', charset)
        self._write_attribute(response, 0x47, 'charset-configured', 'utf-8')
        
        # natural-language-supported
        for lang in ['en-us', 'es-es', 'es']:
            self._write_attribute(response, 0x48, 'natural-language-supported', lang)
        self._write_attribute(response, 0x48, 'natural-language-configured', 'en-us')
        
        # Media supported - 58mm thermal roll
        media_names = [
            'oe_roll_58mm',              # Nombre genérico
            'om_roll_58_203.2x3048',     # Formato Mopria
            'roll_max_58_203.2x3048',
            'custom_58x3048mm',
            'continuous_58x3048mm',
        ]
        for media in media_names:
            self._write_attribute(response, 0x44, 'media-supported', media)
        
        self._write_attribute(response, 0x44, 'media-default', 'oe_roll_58mm')
        self._write_attribute(response, 0x44, 'media-ready', 'oe_roll_58mm')
        
        # media-col-supported (atributos de media collection)
        media_col_attrs = ['media-size', 'media-type', 'media-source']
        for attr in media_col_attrs:
            self._write_attribute(response, 0x44, 'media-col-supported', attr)
        
        # media-type-supported
        self._write_attribute(response, 0x44, 'media-type-supported', 'continuous')
        self._write_attribute(response, 0x44, 'media-source-supported', 'main')
        
        # Print quality
        for quality in [3, 4, 5]:  # draft, normal, high
            self._write_attribute(response, 0x23, 'print-quality-supported', quality.to_bytes(4, 'big'))
        self._write_attribute(response, 0x23, 'print-quality-default', (4).to_bytes(4, 'big'))
        
        # Color capabilities
        self._write_attribute(response, 0x22, 'color-supported', (0).to_bytes(1, 'big'))
        self._write_attribute(response, 0x44, 'print-color-mode-supported', 'monochrome')
        self._write_attribute(response, 0x44, 'print-color-mode-default', 'monochrome')
        
        # Resolution - 203 DPI (8 dots/mm)
        resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')
        self._write_attribute(response, 0x32, 'printer-resolution-supported', resolution)
        self._write_attribute(response, 0x32, 'printer-resolution-default', resolution)
        
        # PWG Raster capabilities
        self._write_attribute(response, 0x44, 'pwg-raster-document-type-supported', 'black_1')
        self._write_attribute(response, 0x44, 'pwg-raster-document-sheet-back', 'normal')
        self._write_attribute(response, 0x21, 'pwg-raster-document-resolution-supported', resolution)
        
        # Sides (impresión duplex)
        self._write_attribute(response, 0x44, 'sides-supported', 'one-sided')
        self._write_attribute(response, 0x44, 'sides-default', 'one-sided')
        
        # Orientation
        for orientation in [3, 4, 5, 6]:  # portrait, landscape, reverse-portrait, reverse-landscape
            self._write_attribute(response, 0x23, 'orientation-requested-supported', orientation.to_bytes(4, 'big'))
        self._write_attribute(response, 0x23, 'orientation-requested-default', (3).to_bytes(4, 'big'))
        
        # Compression
        for compression in ['none', 'gzip', 'deflate']:
            self._write_attribute(response, 0x44, 'compression-supported', compression)
        
        # IPP versions
        for version in ['1.1', '2.0', '2.1', '2.2']:
            self._write_attribute(response, 0x44, 'ipp-versions-supported', version)
        
        # ipp-features-supported
        for feature in ['ipp-everywhere', 'none']:
            self._write_attribute(response, 0x44, 'ipp-features-supported', feature)
        
        # Job management
        self._write_attribute(response, 0x21, 'job-priority-supported', (100).to_bytes(4, 'big'))
        self._write_attribute(response, 0x21, 'job-priority-default', (50).to_bytes(4, 'big'))
        self._write_attribute(response, 0x21, 'copies-supported', (1).to_bytes(4, 'big') + (99).to_bytes(4, 'big'))
        self._write_attribute(response, 0x21, 'copies-default', (1).to_bytes(4, 'big'))
        
        # PDL override
        self._write_attribute(response, 0x44, 'pdl-override-supported', 'not-attempted')
        
        # Finishings
        self._write_attribute(response, 0x23, 'finishings-supported', (3).to_bytes(4, 'big'))  # none
        self._write_attribute(response, 0x23, 'finishings-default', (3).to_bytes(4, 'big'))
        
        # Page ranges
        self._write_attribute(response, 0x22, 'page-ranges-supported', (1).to_bytes(1, 'big'))
        
        # Multiple document handling
        self._write_attribute(response, 0x44, 'multiple-document-handling-supported', 'separate-documents-uncollated-copies')
        
        # Printer more info
        more_info = f'http://{local_ip}:{self.port}/'
        self._write_attribute(response, 0x45, 'printer-more-info', more_info)
        
        # Device UUID
        uuid_value = settings.MDNS_TXT_RECORDS.get('UUID', '12345678-1234-1234-1234-123456789012')
        self._write_attribute(response, 0x45, 'printer-uuid', f'urn:uuid:{uuid_value}')
        
        # printer-device-id (formato IEEE 1284)
        device_id = f'MFG:{settings.PRINTER_MAKE_MODEL.split()[0]};MDL:{settings.PRINTER_NAME};CLS:PRINTER;DES:Thermal Receipt Printer;CMD:ESC/POS;'
        self._write_attribute(response, 0x41, 'printer-device-id', device_id)
        # device-uri (CUPS compatibility)
        device_uri = f"usb://{settings.PRINTER_MAKE_MODEL.replace(' ', '%20')}"
        self._write_attribute(response, 0x45, 'device-uri', device_uri)
        
        # Printer kind
        for kind in ['document', 'receipt']:
            self._write_attribute(response, 0x44, 'printer-kind', kind)
        
        # URI schemes
        for scheme in ['ipp', 'http']:
            self._write_attribute(response, 0x45, 'uri-scheme-supported', scheme)
        
        # which-jobs-supported
        for which in ['completed', 'not-completed', 'all']:
            self._write_attribute(response, 0x44, 'which-jobs-supported', which)
        
        # job-ids-supported - Rango de IDs de trabajos
        self._write_attribute(response, 0x22, 'job-ids-supported', (1).to_bytes(1, 'big'))
        
        # job-k-octets-supported - Tamaño máximo de trabajos (10MB)
        self._write_attribute(response, 0x21, 'job-k-octets-supported', (0).to_bytes(4, 'big') + (10240).to_bytes(4, 'big'))
        
        # printer-up-time (seconds since start)
        uptime = int(time.time() - self._start_time)
        self._write_attribute(response, 0x21, 'printer-up-time', uptime.to_bytes(4, 'big'))
        
        # printer-current-time
        now = datetime.now()
        current_time = (
            now.year.to_bytes(2, 'big') +
            now.month.to_bytes(1, 'big') +
            now.day.to_bytes(1, 'big') +
            now.hour.to_bytes(1, 'big') +
            now.minute.to_bytes(1, 'big') +
            now.second.to_bytes(1, 'big') +
            (0).to_bytes(1, 'big') +  # deciseconds
            b'+' +  # direction from UTC
            (0).to_bytes(1, 'big') +  # hours from UTC
            (0).to_bytes(1, 'big')    # minutes from UTC
        )
        self._write_attribute(response, 0x31, 'printer-current-time', current_time)
        
        # End of attributes
        response.write(bytes([0x03]))
        
        logger.debug(f"✅ Generated printer attributes response: {len(response.getvalue())} bytes")
        return response.getvalue()
    
    async def _handle_get_jobs(self, message: IPPMessage) -> bytes:
        response = io.BytesIO()
        
        # IPP header
        response.write(bytes([2, 0]))
        response.write((0x0000).to_bytes(2, 'big'))
        response.write(message.request_id.to_bytes(4, 'big'))
        
        # Operation attributes
        response.write(bytes([0x01]))
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
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
        
        # End of attributes
        response.write(bytes([0x03]))
        
        return response.getvalue()
    
    async def _handle_validate_job(self, message: IPPMessage) -> bytes:
        response = io.BytesIO()
        
        # IPP header
        response.write(bytes([2, 0]))
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
    
    def _create_error_response(self, request_id: int, status_code: int) -> bytes:
        response = io.BytesIO()
        
        # IPP header
        response.write(bytes([2, 0]))  # Version 2.0
        response.write(status_code.to_bytes(2, 'big'))
        response.write(request_id.to_bytes(4, 'big'))
        
        # Operation attributes
        response.write(bytes([0x01]))
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # End of attributes
        response.write(bytes([0x03]))
        
        return response.getvalue()
    
    async def _handle_web_interface(self, writer: asyncio.StreamWriter):
        html_content = self._generate_web_interface()
        
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/html; charset=utf-8\r\n"
            f"Content-Length: {len(html_content)}\r\n"
            "Server: ONE-POS-IPP/1.0\r\n"
            "\r\n"
        )
        
        writer.write(response.encode())
        writer.write(html_content.encode())
        await writer.drain()
    
    async def _handle_status_request(self, writer: asyncio.StreamWriter):
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
            'network': self.port_manager.get_network_info()
        }
        
        json_content = json.dumps(status, indent=2, default=str)
        
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            "Server: ONE-POS-IPP/1.0\r\n"
            "\r\n"
        )
        
        writer.write(response.encode())
        writer.write(json_content.encode())
        await writer.drain()
    
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
        """Handle OPTIONS request (CUPS usa esto para discovery)"""
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
            f"Connection: {'Keep-Alive' if keep_alive else 'close'}\r\n"
            + ("Keep-Alive: timeout=5, max=100\r\n" if keep_alive else "")
            + "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
            + "\r\n"
        )
        
        writer.write(response.encode())
        await writer.drain()
        logger.debug(f"✅ OPTIONS response sent for {path}")
    
    async def _handle_head_request(self, writer: asyncio.StreamWriter, path: str, keep_alive: bool = False):
        """Handle HEAD request (como GET pero sin body)"""
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
            f"Connection: {'Keep-Alive' if keep_alive else 'close'}\r\n"
            + ("Keep-Alive: timeout=5, max=100\r\n" if keep_alive else "")
            + "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
            + "\r\n"
        )
        
        writer.write(response.encode())
        await writer.drain()
        logger.debug(f"✅ HEAD response sent for {path}")
    
    async def _send_http_error(self, writer: asyncio.StreamWriter, status_code: int, message: str, keep_alive: bool = False):
        response = (
            f"HTTP/1.1 {status_code} {message}\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            "Server: CUPS/2.4 IPP/2.1\r\n"
            f"Connection: {'Keep-Alive' if keep_alive else 'close'}\r\n"
            + ("Keep-Alive: timeout=5, max=50\r\n" if keep_alive else "")
            + "Date: " + datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT') + "\r\n"
            + "\r\n"
            + f"{message}"
        )
        
        writer.write(response.encode())
        await writer.drain()
    
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