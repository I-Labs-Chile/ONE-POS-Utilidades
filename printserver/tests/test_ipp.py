sys.path.insert(0, str(Path(__file__).parent.parent))
from server.ipp_parser import (IPPParser, IPPMessage, IPPOperation, IPPStatusCode, IPPTag, IPPAttribute)
from unittest.mock import Mock, AsyncMock, patch
from server.ipp_server import IPPServer
from config.settings import settings
from pathlib import Path
import logging
import asyncio
import pytest
import json
import sys
import io

logger = logging.getLogger(__name__)

class TestIPPParser:
    # Analiza una solicitud IPP mínima y valida atributos requeridos
    def test_parse_simple_request(self):
        request_data = self._create_minimal_ipp_request(
            operation=IPPOperation.GET_PRINTER_ATTRIBUTES,
            request_id=123
        )
        message = IPPParser.parse_request(request_data)
        assert message.version_major == 2
        assert message.version_minor == 1
        assert message.operation_id == IPPOperation.GET_PRINTER_ATTRIBUTES
        assert message.request_id == 123
        assert 'attributes-charset' in message.operation_attributes
        assert 'attributes-natural-language' in message.operation_attributes
    # Construye respuesta IPP y verifica encabezado básico
    def test_build_response(self):
        attributes = {
            'printer-name': 'Test Printer',
            'printer-state': 3,
            'document-format-supported': ['application/pdf', 'image/jpeg']
        }
        response_data = IPPParser.build_response(
            operation_id=IPPOperation.GET_PRINTER_ATTRIBUTES,
            request_id=456,
            status_code=IPPStatusCode.SUCCESSFUL_OK,
            attributes=attributes
        )
        assert isinstance(response_data, bytes)
        assert len(response_data) > 8
        assert response_data[0] == 2
        assert response_data[1] == 1
    # Solicitud Print-Job con datos de documento y verificación de formato
    def test_parse_print_job_request(self):
        document_data = b"Test document content"
        request_data = self._create_print_job_request(document_data)
        message = IPPParser.parse_request(request_data)
        assert message.operation_id == IPPOperation.PRINT_JOB
        assert message.document_data == document_data
        assert 'document-format' in message.operation_attributes
    # Serializa atributos IPP de distintos tipos para confirmar robustez
    def test_attribute_serialization(self):
        test_cases = [
            ('string-attr', IPPTag.TEXT_WITHOUT_LANGUAGE, 'Test String'),
            ('integer-attr', IPPTag.INTEGER, 42),
            ('boolean-attr', IPPTag.BOOLEAN, True),
            ('uri-attr', IPPTag.URI, 'ipp://example.com/printer'),
        ]
        for name, tag, value in test_cases:
            response = IPPParser.build_response(
                operation_id=IPPOperation.GET_PRINTER_ATTRIBUTES,
                request_id=1,
                status_code=IPPStatusCode.SUCCESSFUL_OK,
                attributes={name: value}
            )
            assert isinstance(response, bytes)
            assert len(response) > 0
    # Crea solicitud IPP mínima con atributos requeridos
    def _create_minimal_ipp_request(self, operation: int, request_id: int) -> bytes:
        stream = io.BytesIO()
        stream.write(bytes([2, 1]))
        stream.write(operation.to_bytes(2, 'big'))
        stream.write(request_id.to_bytes(4, 'big'))
        stream.write(bytes([IPPTag.OPERATION_ATTRIBUTES_TAG]))
        self._write_attribute(stream, 'attributes-charset', IPPTag.CHARSET, 'utf-8')
        self._write_attribute(stream, 'attributes-natural-language', IPPTag.NATURAL_LANGUAGE, 'en')
        self._write_attribute(stream, 'printer-uri', IPPTag.URI, 'ipp://localhost/printer')
        stream.write(bytes([IPPTag.END_OF_ATTRIBUTES_TAG]))
        return stream.getvalue()
    # Crea solicitud Print-Job con formato y nombre de trabajo
    def _create_print_job_request(self, document_data: bytes) -> bytes:
        stream = io.BytesIO()
        stream.write(bytes([2, 1]))
        stream.write(IPPOperation.PRINT_JOB.to_bytes(2, 'big'))
        stream.write((123).to_bytes(4, 'big'))
        stream.write(bytes([IPPTag.OPERATION_ATTRIBUTES_TAG]))
        self._write_attribute(stream, 'attributes-charset', IPPTag.CHARSET, 'utf-8')
        self._write_attribute(stream, 'attributes-natural-language', IPPTag.NATURAL_LANGUAGE, 'en')
        self._write_attribute(stream, 'printer-uri', IPPTag.URI, 'ipp://localhost/printer')
        self._write_attribute(stream, 'document-format', IPPTag.MIME_MEDIA_TYPE, 'application/pdf')
        self._write_attribute(stream, 'job-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'Test Job')
        stream.write(bytes([IPPTag.END_OF_ATTRIBUTES_TAG]))
        stream.write(document_data)
        return stream.getvalue()
    # Escribe atributo IPP (validación de nombre y valor antes de serializar)
    def _write_attribute(self, stream: io.BytesIO, name: str, tag: IPPTag, value: str):
        if not name or not isinstance(name, str):
            raise ValueError("Attribute name must be a non-empty string")
        if not value or not isinstance(value, str):
            raise ValueError("Attribute value must be a non-empty string")
        stream.write(bytes([tag]))
        name_bytes = name.encode('utf-8')
        stream.write(len(name_bytes).to_bytes(2, 'big'))
        stream.write(name_bytes)
        value_bytes = value.encode('utf-8')
        stream.write(len(value_bytes).to_bytes(2, 'big'))
        stream.write(value_bytes)
        logger.debug(f"Writing attribute: name={name}, tag={tag}, value={value}")

@pytest.mark.asyncio
class TestIPPServer:
    # Inicializa servidor IPP con backend y convertidor simulados
    async def test_server_initialization(self):
        mock_backend = Mock()
        mock_converter = Mock()
        server = IPPServer(mock_backend, mock_converter)
        assert server.printer_backend == mock_backend
        assert server.converter == mock_converter
        assert not server.is_running
    # Genera respuesta de atributos de impresora desde manejador dedicado
    async def test_get_printer_attributes_response(self):
        mock_backend = Mock()
        mock_converter = Mock()
        server = IPPServer(mock_backend, mock_converter)
        request = IPPMessage()
        request.operation_id = IPPOperation.GET_PRINTER_ATTRIBUTES
        request.request_id = 123
        response_data = await server._handle_get_printer_attributes(request)
        assert isinstance(response_data, bytes)
        assert len(response_data) > 8
    # Valida flujo Print-Job: conversión y respuesta exitosa
    async def test_print_job_validation(self):
        mock_backend = AsyncMock()
        mock_converter = AsyncMock()
        mock_converter.convert_to_escpos = AsyncMock(return_value=b"ESC/POS commands")
        server = IPPServer(mock_backend, mock_converter)
        request = IPPMessage()
        request.operation_id = IPPOperation.PRINT_JOB
        request.request_id = 456
        request.document_data = b"Test PDF content"
        request.add_operation_attribute('document-format', IPPTag.MIME_MEDIA_TYPE, 'application/pdf')
        request.add_operation_attribute('job-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'Test Job')
        response_data = await server._handle_print_job(request)
        assert isinstance(response_data, bytes)
        await asyncio.sleep(0.1)
        mock_converter.convert_to_escpos.assert_called_once()
    # Valida operación Validate-Job con formato soportado
    async def test_validate_job_operation(self):
        mock_backend = Mock()
        mock_converter = Mock()
        server = IPPServer(mock_backend, mock_converter)
        request = IPPMessage()
        request.operation_id = IPPOperation.VALIDATE_JOB
        request.request_id = 789
        request.add_operation_attribute('document-format', IPPTag.MIME_MEDIA_TYPE, 'application/pdf')
        response_data = await server._handle_validate_job(request)
        assert isinstance(response_data, bytes)
        assert len(response_data) > 0
    # Respuesta esperada en validación de formato no soportado
    async def test_unsupported_document_format(self):
        mock_backend = Mock()
        mock_converter = Mock()
        server = IPPServer(mock_backend, mock_converter)
        request = IPPMessage()
        request.operation_id = IPPOperation.VALIDATE_JOB
        request.request_id = 999
        request.add_operation_attribute('document-format', IPPTag.MIME_MEDIA_TYPE, 'application/unsupported')
        response_data = await server._handle_validate_job(request)
        assert isinstance(response_data, bytes)
    # Manejo básico de creación y almacenamiento de trabajos activos
    async def test_job_management(self):
        server = IPPServer(Mock(), Mock())
        request = IPPMessage()
        request.add_operation_attribute('job-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'Test Job')
        request.add_operation_attribute('requesting-user-name', IPPTag.NAME_WITHOUT_LANGUAGE, 'testuser')
        job_id = server._create_job(request)
        assert job_id > 0
        assert job_id in server.active_jobs
        job = server.active_jobs[job_id]
        assert job['name'] == 'Test Job'
        assert job['user'] == 'testuser'
        assert job['state'] == 3

class TestServerConfiguration:
    # Valida configuración por defecto del servidor IPP
    def test_default_settings(self):
        assert settings.SERVER_PORT == 631
        assert 'application/pdf' in settings.SUPPORTED_FORMATS
        assert 'Print-Job' in settings.SUPPORTED_OPERATIONS
        assert settings.IPP_VERSION == "2.1"
    # Verifica atributos base y específicos de impresora térmica
    def test_printer_attributes(self):
        attrs = settings.PRINTER_ATTRIBUTES
        assert 'charset-supported' in attrs
        assert 'operations-supported' in attrs
        assert 'document-format-supported' in attrs
        assert 'printer-name' in attrs
        assert 'printer-state' in attrs
        assert attrs['color-supported'] == False
        assert 'thermal' in attrs.get('printer-kind', [])
    # TXT records necesarios para anuncio mDNS/AirPrint
    def test_mdns_txt_records(self):
        txt = settings.MDNS_TXT_RECORDS
        assert 'URF' in txt
        assert 'pdl' in txt
        assert 'rp' in txt
        assert 'ty' in txt
        assert txt['Color'] == 'F'
        assert txt['Duplex'] == 'F'
    # Validación de configuración mediante utilidad interna
    def test_configuration_validation(self):
        from server.utils import validate_configuration
        assert validate_configuration() == True

if __name__ == "__main__":
    pytest.main([__file__, "-v"])