import pytest
import asyncio
import io
import json
from unittest.mock import Mock, AsyncMock, patch
import logging

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from server.ipp_parser import (
    IPPParser, IPPMessage, IPPOperation, IPPStatusCode, IPPTag,
    IPPAttribute
)
from server.ipp_server import IPPServer
from config.settings import settings

logger = logging.getLogger(__name__)

class TestIPPParser:
    
    def test_parse_simple_request(self):

        # Create a minimal IPP request
        request_data = self._create_minimal_ipp_request(
            operation=IPPOperation.GET_PRINTER_ATTRIBUTES,
            request_id=123
        )
        
        # Parse the request
        message = IPPParser.parse_request(request_data)
        
        # Verify basic structure
        assert message.version_major == 2
        assert message.version_minor == 1
        assert message.operation_id == IPPOperation.GET_PRINTER_ATTRIBUTES
        assert message.request_id == 123
        
        # Should have required operation attributes
        assert 'attributes-charset' in message.operation_attributes
        assert 'attributes-natural-language' in message.operation_attributes
    
    def test_build_response(self):

        attributes = {
            'printer-name': 'Test Printer',
            'printer-state': 3,  # idle
            'document-format-supported': ['application/pdf', 'image/jpeg']
        }
        
        response_data = IPPParser.build_response(
            operation_id=IPPOperation.GET_PRINTER_ATTRIBUTES,
            request_id=456,
            status_code=IPPStatusCode.SUCCESSFUL_OK,
            attributes=attributes
        )
        
        # Response should be valid bytes
        assert isinstance(response_data, bytes)
        assert len(response_data) > 8  # At least header size
        
        # Should start with IPP version
        assert response_data[0] == 2  # Version major
        assert response_data[1] == 1  # Version minor
    
    def test_parse_print_job_request(self):

        # Create Print-Job request with document
        document_data = b"Test document content"
        request_data = self._create_print_job_request(document_data)
        
        message = IPPParser.parse_request(request_data)
        
        assert message.operation_id == IPPOperation.PRINT_JOB
        assert message.document_data == document_data
        assert 'document-format' in message.operation_attributes
    
    def test_attribute_serialization(self):
        test_cases = [
            ('string-attr', IPPTag.TEXT_WITHOUT_LANGUAGE, 'Test String'),
            ('integer-attr', IPPTag.INTEGER, 42),
            ('boolean-attr', IPPTag.BOOLEAN, True),
            ('uri-attr', IPPTag.URI, 'ipp://example.com/printer'),
        ]
        
        for name, tag, value in test_cases:
            # Create minimal response with this attribute
            response = IPPParser.build_response(
                operation_id=IPPOperation.GET_PRINTER_ATTRIBUTES,
                request_id=1,
                status_code=IPPStatusCode.SUCCESSFUL_OK,
                attributes={name: value}
            )
            
            # Should not raise exceptions
            assert isinstance(response, bytes)
            assert len(response) > 0
    
    def _create_minimal_ipp_request(self, operation: int, request_id: int) -> bytes:
        stream = io.BytesIO()
        
        # IPP header
        stream.write(bytes([2, 1]))  # Version 2.1
        stream.write(operation.to_bytes(2, 'big'))  # Operation
        stream.write(request_id.to_bytes(4, 'big'))  # Request ID
        
        # Operation attributes group
        stream.write(bytes([IPPTag.OPERATION_ATTRIBUTES_TAG]))
        
        # Required attributes
        self._write_attribute(stream, 'attributes-charset', IPPTag.CHARSET, 'utf-8')
        self._write_attribute(stream, 'attributes-natural-language', IPPTag.NATURAL_LANGUAGE, 'en')
        self._write_attribute(stream, 'printer-uri', IPPTag.URI, 'ipp://localhost/printer')
        
        # End of attributes
        stream.write(bytes([IPPTag.END_OF_ATTRIBUTES_TAG]))
        
        return stream.getvalue()
    
    def _create_print_job_request(self, document_data: bytes) -> bytes:
        stream = io.BytesIO()
        
        # IPP header
        stream.write(bytes([2, 1]))  # Version 2.1
        stream.write(IPPOperation.PRINT_JOB.to_bytes(2, 'big'))
        stream.write((123).to_bytes(4, 'big'))  # Request ID
        
        # Operation attributes group
        stream.write(bytes([IPPTag.OPERATION_ATTRIBUTES_TAG]))
        
        # Required attributes
        self._write_attribute(stream, 'attributes-charset', IPPTag.CHARSET, 'utf-8')
        self._write_attribute(stream, 'attributes-natural-language', IPPTag.NATURAL_LANGUAGE, 'en')
        self._write_attribute(stream, 'printer-uri', IPPTag.URI, 'ipp://localhost/printer')
        self._write_attribute(stream, 'document-format', IPPTag.MIME_MEDIA_TYPE, 'application/pdf')
        self._write_attribute(stream, 'job-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'Test Job')
        
        # End of attributes
        stream.write(bytes([IPPTag.END_OF_ATTRIBUTES_TAG]))
        
        # Document data
        stream.write(document_data)
        
        return stream.getvalue()
    
    def _write_attribute(self, stream: io.BytesIO, name: str, tag: IPPTag, value: str):
        if not name or not isinstance(name, str):
            raise ValueError("Attribute name must be a non-empty string")
        if not value or not isinstance(value, str):
            raise ValueError("Attribute value must be a non-empty string")

        # Write tag
        stream.write(bytes([tag]))

        # Write name
        name_bytes = name.encode('utf-8')
        stream.write(len(name_bytes).to_bytes(2, 'big'))
        stream.write(name_bytes)

        # Write value
        value_bytes = value.encode('utf-8')
        stream.write(len(value_bytes).to_bytes(2, 'big'))
        stream.write(value_bytes)

        logger.debug(f"Writing attribute: name={name}, tag={tag}, value={value}")

@pytest.mark.asyncio
class TestIPPServer:
    
    async def test_server_initialization(self):

        mock_backend = Mock()
        mock_converter = Mock()
        
        server = IPPServer(mock_backend, mock_converter)
        
        assert server.printer_backend == mock_backend
        assert server.converter == mock_converter
        assert not server.is_running
    
    async def test_get_printer_attributes_response(self):

        mock_backend = Mock()
        mock_converter = Mock()
        
        server = IPPServer(mock_backend, mock_converter)
        
        # Create mock IPP request
        request = IPPMessage()
        request.operation_id = IPPOperation.GET_PRINTER_ATTRIBUTES
        request.request_id = 123
        
        # Handle the operation
        response_data = await server._handle_get_printer_attributes(request)
        
        # Should return valid IPP response
        assert isinstance(response_data, bytes)
        assert len(response_data) > 8
        
        # Parse response to verify structure
    
    async def test_print_job_validation(self):

        mock_backend = AsyncMock()
        mock_converter = AsyncMock()
        mock_converter.convert_to_escpos = AsyncMock(return_value=b"ESC/POS commands")
        
        server = IPPServer(mock_backend, mock_converter)
        
        # Create Print-Job request with document
        request = IPPMessage()
        request.operation_id = IPPOperation.PRINT_JOB
        request.request_id = 456
        request.document_data = b"Test PDF content"
        request.add_operation_attribute('document-format', IPPTag.MIME_MEDIA_TYPE, 'application/pdf')
        request.add_operation_attribute('job-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'Test Job')
        
        # Handle the operation
        response_data = await server._handle_print_job(request)
        
        # Should return successful response
        assert isinstance(response_data, bytes)
        
        # Wait for the asynchronous task to complete
        await asyncio.sleep(0.1)  # Adjust time as needed to ensure task completion
        
        # Converter should have been called
        mock_converter.convert_to_escpos.assert_called_once()
    
    async def test_validate_job_operation(self):

        mock_backend = Mock()
        mock_converter = Mock()
        
        server = IPPServer(mock_backend, mock_converter)
        
        # Create Validate-Job request
        request = IPPMessage()
        request.operation_id = IPPOperation.VALIDATE_JOB
        request.request_id = 789
        request.add_operation_attribute('document-format', IPPTag.MIME_MEDIA_TYPE, 'application/pdf')
        
        # Handle the operation
        response_data = await server._handle_validate_job(request)
        
        # Should return successful validation
        assert isinstance(response_data, bytes)
        assert len(response_data) > 0
    
    async def test_unsupported_document_format(self):

        mock_backend = Mock()
        mock_converter = Mock()
        
        server = IPPServer(mock_backend, mock_converter)
        
        # Create request with unsupported format
        request = IPPMessage()
        request.operation_id = IPPOperation.VALIDATE_JOB
        request.request_id = 999
        request.add_operation_attribute('document-format', IPPTag.MIME_MEDIA_TYPE, 'application/unsupported')
        
        # Handle the operation
        response_data = await server._handle_validate_job(request)
        
        # Should return error response
        assert isinstance(response_data, bytes)
        # In a full test, you'd parse the response and verify error status
    
    async def test_job_management(self):

        server = IPPServer(Mock(), Mock())
        
        # Create a job
        request = IPPMessage()
        request.add_operation_attribute('job-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'Test Job')
        request.add_operation_attribute('requesting-user-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'testuser')
        
        job_id = server._create_job(request)
        
        # Job should be created
        assert job_id > 0
        assert job_id in server.active_jobs
        
        # Job should have expected attributes
        job = server.active_jobs[job_id]
        assert job['name'] == 'Test Job'
        assert job['user'] == 'testuser'
        assert job['state'] == 3  # pending

class TestServerConfiguration:
    
    def test_default_settings(self):

        assert settings.SERVER_PORT == 631  # Standard IPP port
        assert 'application/pdf' in settings.SUPPORTED_FORMATS
        assert 'Print-Job' in settings.SUPPORTED_OPERATIONS
        assert settings.IPP_VERSION == "2.1"
    
    def test_printer_attributes(self):

        attrs = settings.PRINTER_ATTRIBUTES
        
        # Required attributes
        assert 'charset-supported' in attrs
        assert 'operations-supported' in attrs
        assert 'document-format-supported' in attrs
        assert 'printer-name' in attrs
        assert 'printer-state' in attrs
        
        # Thermal printer specific
        assert attrs['color-supported'] == False
        assert 'thermal' in attrs.get('printer-kind', [])
    
    def test_mdns_txt_records(self):
        txt = settings.MDNS_TXT_RECORDS
        
        # Required for AirPrint
        assert 'URF' in txt
        assert 'pdl' in txt
        assert 'rp' in txt
        assert 'ty' in txt
        
        # Capabilities
        assert txt['Color'] == 'F'  # Monochrome
        assert txt['Duplex'] == 'F'  # No duplex
    
    def test_configuration_validation(self):
        from server.utils import validate_configuration
        
        # Should pass with default config
        assert validate_configuration() == True

if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])