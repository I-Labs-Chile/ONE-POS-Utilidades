import asyncio
import logging
from typing import Dict, Any, Optional
from aiohttp import web, hdrs
from aiohttp.web_request import Request
from aiohttp.web_response import Response
import time
import uuid

from .ipp_parser import IPPParser, IPPMessage, IPPOperation, IPPStatusCode, IPPTag

# Try relative import first, fallback to absolute
try:
    from ..config.settings import settings
except ImportError:
    from config.settings import settings

logger = logging.getLogger(__name__)

class IPPServer:
    
    def __init__(self, printer_backend=None, converter=None):
        self.app = web.Application()
        self.printer_backend = printer_backend
        self.converter = converter
        self.server_runner = None
        self.server_site = None
        self.job_counter = 0
        self.active_jobs: Dict[int, Dict[str, Any]] = {}
        
        # Setup routes
        self._setup_routes()
        
        # Printer state
        self.printer_state = "idle"  # idle, processing, stopped
        self.printer_state_reasons = ["none"]
        
    def _setup_routes(self):
        # Main IPP endpoint
        self.app.router.add_post('/ipp/printer', self._handle_ipp_request)
        self.app.router.add_post('/ipp/print', self._handle_ipp_request)
        
        # Web interface endpoints  
        self.app.router.add_get('/', self._handle_root)
        self.app.router.add_get('/printer', self._handle_printer_info)
        
        # Add CORS support for web browsers
        self.app.middlewares.append(self._cors_handler)
    
    async def _cors_handler(self, request: Request, handler):
        response = await handler(request)
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    
    async def start(self, host: str = None, port: int = None):
        host = host or settings.SERVER_HOST
        port = port or settings.SERVER_PORT
        
        try:
            self.server_runner = web.AppRunner(self.app)
            await self.server_runner.setup()
            
            self.server_site = web.TCPSite(self.server_runner, host, port)
            await self.server_site.start()
            
            logger.info(f"IPP Server started on http://{host}:{port}")
            logger.info(f"Printer URI: ipp://{host}:{port}/ipp/printer")
            
        except Exception as e:
            logger.error(f"Failed to start IPP server: {e}")
            raise
    
    async def stop(self):
        if self.server_site:
            await self.server_site.stop()
            self.server_site = None
        
        if self.server_runner:
            await self.server_runner.cleanup()
            self.server_runner = None
        
        logger.info("IPP Server stopped")
    
    async def _handle_root(self, request: Request) -> Response:
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{settings.PRINTER_NAME} - IPP Print Server</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .info {{ background: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .status {{ color: green; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>{settings.PRINTER_NAME}</h1>
            <div class="info">
                <h2>Printer Information</h2>
                <p><strong>Model:</strong> {settings.PRINTER_MAKE_MODEL}</p>
                <p><strong>Location:</strong> {settings.PRINTER_LOCATION}</p>
                <p><strong>Status:</strong> <span class="status">{self.printer_state.upper()}</span></p>
                <p><strong>IPP URI:</strong> ipp://{request.host}/ipp/printer</p>
                <p><strong>Supported Formats:</strong> {', '.join(settings.SUPPORTED_FORMATS)}</p>
                <h3>Connection Instructions</h3>
                <ul>
                    <li><strong>Windows:</strong> Add printer using "The printer that I want isn't listed" → "Add a printer using TCP/IP address"</li>
                    <li><strong>macOS:</strong> System Preferences → Printers & Scanners → Add Printer (should auto-detect via AirPrint)</li>
                    <li><strong>Linux CUPS:</strong> lpadmin -p {settings.PRINTER_NAME} -E -v ipp://{request.host}/ipp/printer -m everywhere</li>
                    <li><strong>Chrome/Android:</strong> Should auto-detect via mDNS</li>
                </ul>
            </div>
        </body>
        </html>
        """
        return Response(text=html_content, content_type='text/html')
    
    async def _handle_printer_info(self, request: Request) -> Response:
        info = {
            'printer_name': settings.PRINTER_NAME,
            'printer_info': settings.PRINTER_INFO,
            'printer_location': settings.PRINTER_LOCATION,
            'printer_make_model': settings.PRINTER_MAKE_MODEL,
            'printer_state': self.printer_state,
            'printer_uri': f"ipp://{request.host}/ipp/printer",
            'supported_formats': settings.SUPPORTED_FORMATS,
            'active_jobs': len(self.active_jobs)
        }
        return web.json_response(info)
    
    async def _handle_ipp_request(self, request: Request) -> Response:
        try:
            # Read request body
            request_data = await request.read()
            
            # Validate Content-Type
            content_type = request.headers.get(hdrs.CONTENT_TYPE, '')
            if not content_type.startswith('application/ipp'):
                logger.warning(f"Invalid content type: {content_type}")
                return Response(status=400, text="Invalid Content-Type for IPP")
            
            # Parse IPP message
            try:
                ipp_request = IPPParser.parse_request(request_data)
            except Exception as e:
                logger.error(f"Failed to parse IPP request: {e}")
                return Response(status=400, text="Invalid IPP request")
            
            # Handle IPP operation
            response_data = await self._handle_ipp_operation(ipp_request)
            
            return Response(
                body=response_data,
                content_type='application/ipp',
                headers={
                    'Server': f'IPP-PrintServer/{settings.VERSION}',
                    'Date': time.strftime('%a, %d %b %Y %H:%M:%S GMT', time.gmtime())
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling IPP request: {e}")
            # Return generic IPP error
            error_response = IPPParser.build_response(
                0, 0, IPPStatusCode.SERVER_ERROR_INTERNAL_ERROR, {}
            )
            return Response(
                body=error_response,
                content_type='application/ipp',
                status=500
            )
    
    async def _handle_ipp_operation(self, request: IPPMessage) -> bytes:
        operation_id = request.operation_id
        
        logger.info(f"Handling IPP operation: {operation_id} (request_id: {request.request_id})")
        
        try:
            if operation_id == IPPOperation.GET_PRINTER_ATTRIBUTES:
                return await self._handle_get_printer_attributes(request)
            elif operation_id == IPPOperation.PRINT_JOB:
                return await self._handle_print_job(request)
            elif operation_id == IPPOperation.VALIDATE_JOB:
                return await self._handle_validate_job(request)
            elif operation_id == IPPOperation.GET_JOBS:
                return await self._handle_get_jobs(request)
            elif operation_id == IPPOperation.CANCEL_JOB:
                return await self._handle_cancel_job(request)
            else:
                logger.warning(f"Unsupported operation: {operation_id}")
                return IPPParser.build_response(
                    operation_id, 
                    request.request_id,
                    IPPStatusCode.SERVER_ERROR_OPERATION_NOT_SUPPORTED,
                    {}
                )
                
        except Exception as e:
            logger.error(f"Error in IPP operation handler: {e}")
            return IPPParser.build_response(
                operation_id,
                request.request_id, 
                IPPStatusCode.SERVER_ERROR_INTERNAL_ERROR,
                {}
            )
    
    async def _handle_get_printer_attributes(self, request: IPPMessage) -> bytes:
        # Get requested attributes or return all if not specified
        requested_attrs = None
        if 'requested-attributes' in request.operation_attributes:
            requested_attrs = request.operation_attributes['requested-attributes'].value
            if isinstance(requested_attrs, str):
                requested_attrs = [requested_attrs]
        
        # Build printer attributes
        printer_attrs = dict(settings.PRINTER_ATTRIBUTES)
        
        # Add dynamic attributes
        printer_attrs.update({
            'printer-state': 3 if self.printer_state == 'idle' else 4,  # idle=3, processing=4
            'printer-state-reasons': self.printer_state_reasons,
            'printer-up-time': int(time.time()),
            'queued-job-count': len(self.active_jobs),
            'printer-uuid': f"urn:uuid:{settings.MDNS_TXT_RECORDS['UUID']}",
            'device-uri': settings.get_printer_uri(),
            'printer-uri-supported': [settings.get_printer_uri()],
            'uri-security-supported': ['none'],
            'uri-authentication-supported': ['none']
        })
        
        # Filter attributes if requested
        if requested_attrs:
            filtered_attrs = {}
            for attr_name in requested_attrs:
                if attr_name in printer_attrs:
                    filtered_attrs[attr_name] = printer_attrs[attr_name]
            printer_attrs = filtered_attrs
        
        logger.debug(f"Returning {len(printer_attrs)} printer attributes")
        
        return IPPParser.build_response(
            IPPOperation.GET_PRINTER_ATTRIBUTES,
            request.request_id,
            IPPStatusCode.SUCCESSFUL_OK,
            printer_attrs
        )
    
    async def _handle_print_job(self, request: IPPMessage) -> bytes:
        # Validate document data
        if not request.document_data:
            return IPPParser.build_response(
                IPPOperation.PRINT_JOB,
                request.request_id,
                IPPStatusCode.CLIENT_ERROR_BAD_REQUEST,
                {'status-message': 'No document data provided'}
            )
        
        # Get document format
        document_format = 'application/octet-stream'
        if 'document-format' in request.operation_attributes:
            document_format = request.operation_attributes['document-format'].value
        
        # Validate supported format
        if document_format not in settings.SUPPORTED_FORMATS:
            return IPPParser.build_response(
                IPPOperation.PRINT_JOB,
                request.request_id,
                IPPStatusCode.CLIENT_ERROR_DOCUMENT_FORMAT_NOT_SUPPORTED,
                {
                    'status-message': f'Document format {document_format} not supported',
                    'document-format-supported': settings.SUPPORTED_FORMATS
                }
            )
        
        # Create job
        job_id = self._create_job(request)
        
        # Process print job asynchronously
        asyncio.create_task(self._process_print_job(job_id, request.document_data, document_format))
        
        # Return successful response
        job_attrs = {
            'job-id': job_id,
            'job-state': 3,  # pending
            'job-state-reasons': ['job-queued'],
            'job-uri': f"{settings.get_printer_uri()}/jobs/{job_id}",
            'time-at-creation': int(time.time())
        }
        
        return IPPParser.build_response(
            IPPOperation.PRINT_JOB,
            request.request_id,
            IPPStatusCode.SUCCESSFUL_OK,
            job_attrs
        )
    
    async def _handle_validate_job(self, request: IPPMessage) -> bytes:
        # Get document format
        document_format = 'application/octet-stream'
        if 'document-format' in request.operation_attributes:
            document_format = request.operation_attributes['document-format'].value
        
        # Validate format
        if document_format not in settings.SUPPORTED_FORMATS:
            return IPPParser.build_response(
                IPPOperation.VALIDATE_JOB,
                request.request_id,
                IPPStatusCode.CLIENT_ERROR_DOCUMENT_FORMAT_NOT_SUPPORTED,
                {
                    'status-message': f'Document format {document_format} not supported',
                    'document-format-supported': settings.SUPPORTED_FORMATS
                }
            )
        
        # Check printer state
        if self.printer_state == 'stopped':
            return IPPParser.build_response(
                IPPOperation.VALIDATE_JOB,
                request.request_id,
                IPPStatusCode.SERVER_ERROR_NOT_ACCEPTING_JOBS,
                {'status-message': 'Printer is stopped'}
            )
        
        return IPPParser.build_response(
            IPPOperation.VALIDATE_JOB,
            request.request_id,
            IPPStatusCode.SUCCESSFUL_OK,
            {}
        )
    
    async def _handle_get_jobs(self, request: IPPMessage) -> bytes:
        # Return information about active jobs
        jobs_attrs = {}
        for job_id, job_info in self.active_jobs.items():
            job_attrs = {
                'job-id': job_id,
                'job-state': job_info.get('state', 3),
                'job-state-reasons': job_info.get('state_reasons', ['job-queued']),
                'job-uri': f"{settings.get_printer_uri()}/jobs/{job_id}",
                'time-at-creation': job_info.get('created_at', int(time.time()))
            }
            jobs_attrs.update(job_attrs)
        
        return IPPParser.build_response(
            IPPOperation.GET_JOBS,
            request.request_id,
            IPPStatusCode.SUCCESSFUL_OK,
            jobs_attrs
        )
    
    async def _handle_cancel_job(self, request: IPPMessage) -> bytes:
        # Get job ID from request
        job_id = None
        if 'job-id' in request.operation_attributes:
            job_id = request.operation_attributes['job-id'].value
        
        if job_id is None or job_id not in self.active_jobs:
            return IPPParser.build_response(
                IPPOperation.CANCEL_JOB,
                request.request_id,
                IPPStatusCode.CLIENT_ERROR_NOT_FOUND,
                {'status-message': 'Job not found'}
            )
        
        # Cancel the job
        self.active_jobs[job_id]['state'] = 7  # canceled
        self.active_jobs[job_id]['state_reasons'] = ['job-canceled-by-user']
        
        return IPPParser.build_response(
            IPPOperation.CANCEL_JOB,
            request.request_id,
            IPPStatusCode.SUCCESSFUL_OK,
            {}
        )
    
    def _create_job(self, request: IPPMessage) -> int:
        self.job_counter += 1
        job_id = self.job_counter
        
        # Extract job attributes
        job_name = "Unknown Document"
        if 'job-name' in request.operation_attributes:
            job_name = request.operation_attributes['job-name'].value
        
        user_name = "anonymous"
        if 'requesting-user-name' in request.operation_attributes:
            user_name = request.operation_attributes['requesting-user-name'].value
        
        # Store job information
        self.active_jobs[job_id] = {
            'id': job_id,
            'name': job_name,
            'user': user_name,
            'state': 3,  # pending
            'state_reasons': ['job-queued'],
            'created_at': int(time.time()),
            'uuid': str(uuid.uuid4())
        }
        
        logger.info(f"Created job {job_id}: {job_name} by {user_name}")
        return job_id
    
    async def _process_print_job(self, job_id: int, document_data: bytes, document_format: str):
        try:
            if job_id not in self.active_jobs:
                return
            
            job = self.active_jobs[job_id]
            
            # Update job state
            job['state'] = 5  # processing
            job['state_reasons'] = ['job-printing']
            self.printer_state = "processing"
            
            logger.info(f"Processing job {job_id} ({document_format})")
            
            # Convert document to ESC/POS commands
            if self.converter:
                escpos_data = await self.converter.convert_to_escpos(document_data, document_format)
            else:
                # Fallback: assume raw ESC/POS data
                escpos_data = document_data
            
            # Send to printer
            if self.printer_backend:
                await self.printer_backend.send_raw(escpos_data)
            else:
                logger.warning("No printer backend available, job not printed")
            
            # Update job state to completed
            job['state'] = 9  # completed
            job['state_reasons'] = ['job-completed-successfully']
            job['completed_at'] = int(time.time())
            
            logger.info(f"Job {job_id} completed successfully")
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            if job_id in self.active_jobs:
                self.active_jobs[job_id]['state'] = 8  # aborted  
                self.active_jobs[job_id]['state_reasons'] = ['job-aborted-by-system']
        
        finally:
            # Reset printer state
            self.printer_state = "idle"
            
            # Clean up completed/failed jobs after some time
            await asyncio.sleep(300)  # Keep for 5 minutes
            if job_id in self.active_jobs:
                del self.active_jobs[job_id]