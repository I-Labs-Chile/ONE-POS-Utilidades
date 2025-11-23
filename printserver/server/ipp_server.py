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
        logger.debug(f"New connection from {client_addr}")
        
        # Initialize debugging session if available
        debug_session_id = None
        if DEBUG_ENABLED:

            # Detect client type based on IP and patterns
            client_type = "android" if self._is_android_client(client_ip) else "pc"
            log_android_debug(client_ip, f"New connection from {client_type}", {
                'client_addr': str(client_addr),
                'client_type': client_type
            })
        
        try:
            # Read HTTP headers
            request_line = await reader.readline()
            if not request_line:
                return
            
            request_line = request_line.decode('utf-8').strip()
            logger.debug(f"Request line: {request_line}")
            
            # Parse HTTP method and path
            parts = request_line.split()
            if len(parts) < 3:
                await self._send_http_error(writer, 400, "Bad Request")
                return
            
            method, path, version = parts[0], parts[1], parts[2]
            
            # Read headers
            headers = {}
            while True:
                header_line = await reader.readline()
                if not header_line or header_line == b'\r\n':
                    break
                
                header_str = header_line.decode('utf-8').strip()
                if ':' in header_str:
                    name, value = header_str.split(':', 1)
                    headers[name.strip().lower()] = value.strip()
            
            # Log detailed request info for debugging
            if DEBUG_ENABLED and self._is_android_client(client_ip):
                log_android_debug(client_ip, f"Android request: {method} {path}", {
                    'method': method,
                    'path': path,
                    'headers': dict(headers),
                    'version': version
                })
            
            # Handle different endpoints
            logger.debug(f"Handling {method} request to {path}")
            
            if method == 'POST' and path in ['/ipp/print', '/ipp/printer', '/']:
                await self._handle_ipp_request(reader, writer, headers, client_ip)
            elif method == 'GET' and path == '/':
                await self._handle_web_interface(writer)
            elif method == 'GET' and path == '/status':
                await self._handle_status_request(writer)
            else:
                logger.warning(f"🚫 Unhandled request: {method} {path} from {client_addr}")
                await self._send_http_error(writer, 404, "Not Found")
                
        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
            try:
                await self._send_http_error(writer, 500, "Internal Server Error")
            except:
                pass
        finally:
            try:
                writer.close()
                await writer.wait_closed()
            except:
                pass
    
    async def _handle_ipp_request(self, reader: asyncio.StreamReader, 
                                  writer: asyncio.StreamWriter, headers: dict, client_ip: str = None):

        client_addr = writer.get_extra_info('peername')
        if not client_ip:
            client_ip = client_addr[0] if client_addr else "unknown"
            
        try:
            # Read content length
            content_length = int(headers.get('content-length', 0))
            logger.debug(f"IPP request from {client_addr} - Content-Length: {content_length}")
            
            # Log for Android debugging
            if DEBUG_ENABLED and self._is_android_client(client_ip):
                log_android_debug(client_ip, "IPP Request received", {
                    'content_length': content_length,
                    'headers': dict(headers)
                })
            
            if content_length == 0:
                logger.warning(f"No content from {client_addr}")
                if DEBUG_ENABLED and self._is_android_client(client_ip):
                    log_android_debug(client_ip, "ERROR: Empty IPP request")
                await self._send_http_error(writer, 400, "No content")
                return
            
            # Read IPP data
            ipp_data = await reader.read(content_length)
            logger.debug(f"Read {len(ipp_data)} bytes from {client_addr}")
            
            # Save request data for analysis
            if DEBUG_ENABLED and self._is_android_client(client_ip):
                save_request_data(client_ip, ipp_data, headers, "/ipp/printer")
                log_android_debug(client_ip, f"IPP data received: {len(ipp_data)} bytes")
            
            if len(ipp_data) != content_length:
                logger.error(f"Incomplete data from {client_addr}: expected {content_length}, got {len(ipp_data)}")
                if DEBUG_ENABLED and self._is_android_client(client_ip):
                    log_android_debug(client_ip, "ERROR: Incomplete IPP data", {
                        'expected': content_length,
                        'received': len(ipp_data)
                    })
                await self._send_http_error(writer, 400, "Incomplete data")
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
                logger.error(f"Failed to parse IPP operation from {client_addr}")
                if DEBUG_ENABLED and self._is_android_client(client_ip):
                    log_android_debug(client_ip, "ERROR: Failed to parse IPP operation")
                await self._send_http_error(writer, 400, "Invalid IPP message")
                return
            
            # Handle operation
            logger.debug(f"Processing IPP operation from {client_addr}")
            response_data = await self._process_ipp_operation(message, client_ip)
            
            if not response_data:
                logger.error(f"No response data generated for {client_addr}")
                await self._send_http_error(writer, 500, "Failed to process operation")
                return
            
            # Send HTTP response
            response_headers = (
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/ipp\r\n"
                f"Content-Length: {len(response_data)}\r\n"
                "Server: ONE-POS-IPP/1.0\r\n"
                "\r\n"
            )
            
            logger.debug(f"Sending {len(response_data)} bytes response to {client_addr}")
            writer.write(response_headers.encode())
            writer.write(response_data)
            await writer.drain()
            logger.debug(f"✅ IPP response sent successfully to {client_addr}")
            
        except Exception as e:
            logger.error(f"❌ Error processing IPP request from {client_addr}: {e}")
            import traceback
            logger.debug(f"IPP error traceback: {traceback.format_exc()}")
            try:
                await self._send_http_error(writer, 500, "IPP Processing Error")
            except:
                pass
    
    async def _process_ipp_operation(self, message: IPPMessage, client_ip: str = None) -> bytes:

        try:
            operation_name = self.SUPPORTED_OPERATIONS.get(message.operation_id, 'Unknown')
            logger.info(f"📱 Processing IPP operation: {operation_name} (0x{message.operation_id:04x})")
            
            # Enhanced debugging for Android compatibility
            logger.debug(f"Request ID: {message.request_id}, Version: {message.version_number}")
            if message.operation_attributes:
                logger.debug(f"Operation attributes: {len(message.operation_attributes)} items")
                for attr in message.operation_attributes[:5]:  # Log first 5 attributes
                    logger.debug(f"  Attribute: {attr.name}={attr.value}")
            if message.document_data:
                logger.info(f"📄 Document data received: {len(message.document_data)} bytes")
            
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
            logger.info("🖨️  Handling Print-Job from Android device")
            
            # Validate document data
            if not message.document_data:
                logger.error("❌ No document data received")
                return self._create_error_response(message.request_id, 0x0400)  # client-error-bad-request
            
            # Get document format
            document_format = 'application/octet-stream'
            if 'document-format' in message.operation_attributes:
                document_format = message.operation_attributes['document-format'].value
                
            logger.info(f"📄 Print job - Format: {document_format}, Size: {len(message.document_data)} bytes")
            
            # Create job
            job_id = self._create_job(message)
            
            # Process job asynchronously
            asyncio.create_task(self._process_print_job(job_id, message.document_data, document_format))
            
            # Return success response
            return self._create_print_job_response(message.request_id, job_id)
            
        except Exception as e:
            logger.error(f"Error in print job: {e}")
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
    
    async def _process_print_job(self, job_id: int, document_data: bytes, document_format: str):

        job = self.active_jobs.get(job_id)
        if not job:
            logger.error(f"❌ Job {job_id} not found")
            return

        try:
            job['state'] = 'processing'
            logger.info(f"🔄 Processing print job {job_id} - Format: {document_format}, Size: {len(document_data)} bytes")
            
            # Validate document data
            if not document_data or len(document_data) == 0:
                logger.error(f"❌ Job {job_id}: No document data received (empty content)")
                job['state'] = 'aborted'
                job['state_reasons'] = ['document-format-error']
                return
            
            # Log first few bytes for debugging
            preview = document_data[:100] if len(document_data) >= 100 else document_data
            logger.debug(f"Document preview (first {len(preview)} bytes): {preview}")
            
            # Check if this looks like a valid document
            if document_format == 'application/pdf':
                if not document_data.startswith(b'%PDF'):
                    logger.warning(f"⚠️ Job {job_id}: Document claims to be PDF but doesn't start with PDF header")
            elif document_format.startswith('image/'):

                # Check common image headers
                image_headers = {
                    b'\xFF\xD8\xFF': 'JPEG',
                    b'\x89PNG\r\n\x1A\n': 'PNG',
                    b'GIF87a': 'GIF',
                    b'GIF89a': 'GIF'
                }
                header_found = False
                for header, img_type in image_headers.items():
                    if document_data.startswith(header):
                        logger.debug(f"✅ Detected valid {img_type} image")
                        header_found = True
                        break
                if not header_found:
                    logger.warning(f"⚠️ Job {job_id}: Document claims to be {document_format} but header not recognized")
            
            # Convert document if converter is available
            escpos_data = None
            if self.converter:
                logger.debug(f"🔧 Converting document from {document_format} to ESC/POS")
                try:
                    escpos_data = await self.converter.convert_to_escpos(document_data, document_format)
                    if escpos_data and len(escpos_data) > 0:
                        logger.info(f"✅ Conversion successful: {len(escpos_data)} bytes of ESC/POS data")
                    else:
                        logger.error(f"❌ Conversion failed: No ESC/POS data generated")
                        job['state'] = 'aborted'
                        job['state_reasons'] = ['document-format-error']
                        return
                except Exception as conv_error:
                    logger.error(f"❌ Conversion error for job {job_id}: {conv_error}")
                    job['state'] = 'aborted'
                    job['state_reasons'] = ['document-format-error']
                    return
            else:

                # Assume raw ESC/POS data
                logger.debug("📄 No converter available, treating as raw ESC/POS data")
                escpos_data = document_data
            
            # Final check on ESC/POS data
            if not escpos_data or len(escpos_data) == 0:
                logger.error(f"❌ Job {job_id}: No printable data after processing")
                job['state'] = 'aborted'
                job['state_reasons'] = ['document-format-error']
                return
            
            # Send to printer
            if self.printer_backend and self.printer_backend.is_connected:
                logger.debug(f"🖨️ Sending {len(escpos_data)} bytes to printer")
                success = await self.printer_backend.send_raw(escpos_data)
                if success:
                    job['state'] = 'completed'
                    job['state_reasons'] = ['job-completed-successfully']
                    logger.info(f"✅ Job {job_id} completed successfully - printed {len(escpos_data)} bytes")
                else:
                    job['state'] = 'aborted'
                    job['state_reasons'] = ['printer-stopped']
                    logger.error(f"❌ Job {job_id} failed to print - printer backend error")
            else:
                # Offline mode - mark as completed anyway for testing
                job['state'] = 'completed'
                job['state_reasons'] = ['job-completed-with-warnings']
                logger.warning(f"⚠️ Job {job_id} processed in offline mode - {len(escpos_data)} bytes would be printed")
            
        except Exception as e:
            job['state'] = 'aborted'
            job['state_reasons'] = ['processing-stopped']
            logger.error(f"❌ Job {job_id} failed with exception: {e}")
            import traceback
            logger.debug(f"Job processing error traceback: {traceback.format_exc()}")
        finally:

            # Move job to completed list
            job['completion_time'] = datetime.now()
            if job['state'] == 'completed':
                self.completed_jobs.append(job)
                logger.info(f"📋 Job {job_id} moved to completed jobs")
            else:
                self.failed_jobs.append(job)
                logger.warning(f"📋 Job {job_id} moved to failed jobs with state: {job['state']}")
            
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
        logger.debug("🔍 Building comprehensive printer attributes response")
        
        response = io.BytesIO()
        
        # IPP header
        response.write(bytes([2, 0]))  # Version 2.0
        response.write((0x0000).to_bytes(2, 'big'))  # successful-ok
        response.write(message.request_id.to_bytes(4, 'big'))
        
        # Operation attributes
        response.write(bytes([0x01]))  # operation-attributes-tag
        self._write_attribute(response, 0x47, 'attributes-charset', 'utf-8')
        self._write_attribute(response, 0x48, 'attributes-natural-language', 'en-us')
        
        # Printer attributes
        response.write(bytes([0x04]))  # printer-attributes-tag
        
        # Basic printer identification
        printer_uri = f"ipp://{self.port_manager.get_network_info()['local_ip']}:{self.port}/ipp/printer"
        self._write_attribute(response, 0x45, 'printer-uri-supported', printer_uri)
        self._write_attribute(response, 0x42, 'printer-name', settings.PRINTER_NAME)
        self._write_attribute(response, 0x41, 'printer-info', 'ONE-POS Thermal Printer (58mm)')
        self._write_attribute(response, 0x41, 'printer-make-and-model', 'Generic 58mm Thermal Printer')
        self._write_attribute(response, 0x45, 'printer-device-id', 'MFG:Generic;CMD:ESC/POS;MDL:58mm Thermal;')
        
        # Printer state and capabilities
        state = 3 if self.printer_backend and self.printer_backend.is_connected else 4  # idle or stopped
        self._write_attribute(response, 0x23, 'printer-state', state.to_bytes(4, 'big'))
        
        # printer-state-reasons
        reasons = 'none' if state == 3 else 'offline'
        self._write_attribute(response, 0x44, 'printer-state-reasons', reasons)
        
        # printer-is-accepting-jobs
        accepting = 1 if state == 3 else 0  # true if idle, false if stopped
        self._write_attribute(response, 0x22, 'printer-is-accepting-jobs', accepting.to_bytes(1, 'big'))
        
        # operations-supported
        for op_id in self.SUPPORTED_OPERATIONS.keys():
            self._write_attribute(response, 0x23, 'operations-supported', op_id.to_bytes(4, 'big'))
        
        # document-format-supported
        formats = [
            'application/pdf',
            'image/jpeg', 
            'image/png',
            'image/pwg-raster',
            'text/plain',
            'application/octet-stream'
        ]
        for fmt in formats:
            self._write_attribute(response, 0x49, 'document-format-supported', fmt)
        
        # document-format-default
        self._write_attribute(response, 0x49, 'document-format-default', 'application/pdf')
        
        # Media and print quality attributes
        self._write_attribute(response, 0x44, 'media-supported', 'roll_max_58_203.2x3048')
        self._write_attribute(response, 0x44, 'media-default', 'roll_max_58_203.2x3048')
        self._write_attribute(response, 0x44, 'media-ready', 'roll_max_58_203.2x3048')
        
        # Print quality
        self._write_attribute(response, 0x23, 'print-quality-supported', (3).to_bytes(4, 'big'))  # draft
        self._write_attribute(response, 0x23, 'print-quality-supported', (4).to_bytes(4, 'big'))  # normal  
        self._write_attribute(response, 0x23, 'print-quality-supported', (5).to_bytes(4, 'big'))  # high
        self._write_attribute(response, 0x23, 'print-quality-default', (4).to_bytes(4, 'big'))  # normal
        
        # Color capabilities
        self._write_attribute(response, 0x22, 'color-supported', (0).to_bytes(1, 'big'))  # false (monochrome)
        
        # Resolution
        # 203 DPI in both directions
        resolution = (203).to_bytes(4, 'big') + (203).to_bytes(4, 'big') + (3).to_bytes(1, 'big')  # 3 = dpi
        self._write_attribute(response, 0x32, 'printer-resolution-supported', resolution)
        self._write_attribute(response, 0x32, 'printer-resolution-default', resolution)
        
        # Charset and language support
        self._write_attribute(response, 0x47, 'charset-supported', 'utf-8')
        self._write_attribute(response, 0x47, 'charset-configured', 'utf-8')
        self._write_attribute(response, 0x48, 'natural-language-configured', 'en-us')
        self._write_attribute(response, 0x48, 'generated-natural-language-supported', 'en-us')
        
        # URI schemes
        self._write_attribute(response, 0x45, 'uri-schemes-supported', 'ipp')
        self._write_attribute(response, 0x45, 'uri-schemes-supported', 'http')
        
        # Job management
        self._write_attribute(response, 0x21, 'job-priority-supported', (1).to_bytes(4, 'big'))
        self._write_attribute(response, 0x21, 'job-priority-default', (50).to_bytes(4, 'big'))
        self._write_attribute(response, 0x21, 'job-hold-until-supported', (1).to_bytes(4, 'big'))
        self._write_attribute(response, 0x44, 'job-hold-until-default', 'no-hold')
        
        # PDL override
        self._write_attribute(response, 0x44, 'pdl-override-supported', 'not-attempted')
        
        # Compression
        self._write_attribute(response, 0x44, 'compression-supported', 'none')
        
        # IPP versions
        self._write_attribute(response, 0x44, 'ipp-versions-supported', '1.1')
        self._write_attribute(response, 0x44, 'ipp-versions-supported', '2.0')
        
        # Printer up time (seconds since start)
        import time
        uptime = int(time.time() - getattr(self, '_start_time', time.time()))
        self._write_attribute(response, 0x21, 'printer-up-time', uptime.to_bytes(4, 'big'))
        
        # Printer current time
        current_time = int(time.time())
        self._write_attribute(response, 0x21, 'printer-current-time', current_time.to_bytes(4, 'big'))
        
        # Multiple document jobs
        self._write_attribute(response, 0x22, 'multiple-document-jobs-supported', (0).to_bytes(1, 'big'))  # false
        
        logger.debug("✅ Printer attributes response built successfully")
        
        # End of attributes
        response.write(bytes([0x03]))
        
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
    
    async def _send_http_error(self, writer: asyncio.StreamWriter, status_code: int, message: str):
        response = (
            f"HTTP/1.1 {status_code} {message}\r\n"
            "Content-Type: text/plain\r\n"
            f"Content-Length: {len(message)}\r\n"
            "Server: ONE-POS-IPP/1.0\r\n"
            "\r\n"
            f"{message}"
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