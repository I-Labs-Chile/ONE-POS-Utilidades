from typing import Dict, List, Any, Optional, Union, Tuple
from enum import IntEnum
import logging
import struct
import io

logger = logging.getLogger(__name__)

class IPPTag(IntEnum):
    # Delimiter tags
    OPERATION_ATTRIBUTES_TAG = 0x01
    JOB_ATTRIBUTES_TAG = 0x02
    END_OF_ATTRIBUTES_TAG = 0x03
    PRINTER_ATTRIBUTES_TAG = 0x04
    UNSUPPORTED_ATTRIBUTES_TAG = 0x05
    
    # Value tags
    UNSUPPORTED = 0x10
    DEFAULT = 0x11
    UNKNOWN = 0x12
    NO_VALUE = 0x13
    NOT_SETTABLE = 0x15
    DELETE_ATTRIBUTE = 0x16
    ADMIN_DEFINE = 0x17
    
    # Integer tags
    INTEGER = 0x21
    BOOLEAN = 0x22
    ENUM = 0x23
    
    # String tags
    OCTET_STRING = 0x30
    DATETIME = 0x31
    RESOLUTION = 0x32
    RANGE_OF_INTEGER = 0x33
    COLLECTION = 0x34
    TEXT_WITH_LANGUAGE = 0x35
    NAME_WITH_LANGUAGE = 0x36
    
    # Character string tags
    TEXT_WITHOUT_LANGUAGE = 0x41
    NAME_WITHOUT_LANGUAGE = 0x42
    KEYWORD = 0x44
    URI = 0x45
    URI_SCHEME = 0x46
    CHARSET = 0x47
    NATURAL_LANGUAGE = 0x48
    MIME_MEDIA_TYPE = 0x49

class IPPOperation(IntEnum):
    PRINT_JOB = 0x0002
    PRINT_URI = 0x0003
    VALIDATE_JOB = 0x0004
    CREATE_JOB = 0x0005
    SEND_DOCUMENT = 0x0006
    SEND_URI = 0x0007
    CANCEL_JOB = 0x0008
    GET_JOB_ATTRIBUTES = 0x0009
    GET_JOBS = 0x000a
    GET_PRINTER_ATTRIBUTES = 0x000b
    HOLD_JOB = 0x000c
    RELEASE_JOB = 0x000d
    RESTART_JOB = 0x000e
    PAUSE_PRINTER = 0x0010
    RESUME_PRINTER = 0x0011
    PURGE_JOBS = 0x0012

class IPPStatusCode(IntEnum):
    # Successful status codes
    SUCCESSFUL_OK = 0x0000
    SUCCESSFUL_OK_IGNORED_OR_SUBSTITUTED_ATTRIBUTES = 0x0001
    SUCCESSFUL_OK_CONFLICTING_ATTRIBUTES = 0x0002
    
    # Informational status codes
    INFORMATIONAL_OK = 0x0100
    
    # Redirection status codes
    REDIRECTION_OTHER_SITE = 0x0200
    
    # Client error status codes
    CLIENT_ERROR_BAD_REQUEST = 0x0400
    CLIENT_ERROR_FORBIDDEN = 0x0401
    CLIENT_ERROR_NOT_AUTHENTICATED = 0x0402
    CLIENT_ERROR_NOT_AUTHORIZED = 0x0403
    CLIENT_ERROR_NOT_POSSIBLE = 0x0404
    CLIENT_ERROR_TIMEOUT = 0x0405
    CLIENT_ERROR_NOT_FOUND = 0x0406
    CLIENT_ERROR_GONE = 0x0407
    CLIENT_ERROR_REQUEST_ENTITY_TOO_LARGE = 0x0408
    CLIENT_ERROR_REQUEST_VALUE_TOO_LONG = 0x0409
    CLIENT_ERROR_DOCUMENT_FORMAT_NOT_SUPPORTED = 0x040a
    CLIENT_ERROR_ATTRIBUTES_OR_VALUES_NOT_SUPPORTED = 0x040b
    CLIENT_ERROR_URI_SCHEME_NOT_SUPPORTED = 0x040c
    CLIENT_ERROR_CHARSET_NOT_SUPPORTED = 0x040d
    CLIENT_ERROR_CONFLICTING_ATTRIBUTES = 0x040e
    CLIENT_ERROR_COMPRESSION_NOT_SUPPORTED = 0x040f
    CLIENT_ERROR_COMPRESSION_ERROR = 0x0410
    CLIENT_ERROR_DOCUMENT_FORMAT_ERROR = 0x0411
    CLIENT_ERROR_DOCUMENT_ACCESS_ERROR = 0x0412
    
    # Server error status codes
    SERVER_ERROR_INTERNAL_ERROR = 0x0500
    SERVER_ERROR_OPERATION_NOT_SUPPORTED = 0x0501
    SERVER_ERROR_SERVICE_UNAVAILABLE = 0x0502
    SERVER_ERROR_VERSION_NOT_SUPPORTED = 0x0503
    SERVER_ERROR_DEVICE_ERROR = 0x0504
    SERVER_ERROR_TEMPORARY_ERROR = 0x0505
    SERVER_ERROR_NOT_ACCEPTING_JOBS = 0x0506
    SERVER_ERROR_BUSY = 0x0507
    SERVER_ERROR_JOB_CANCELED = 0x0508
    SERVER_ERROR_MULTIPLE_DOCUMENT_JOBS_NOT_SUPPORTED = 0x0509

class IPPAttribute:
    
    def __init__(self, name: str, tag: IPPTag, value: Any):
        self.name = name
        self.tag = tag
        self.value = value
    
    def __repr__(self):
        return f"IPPAttribute(name='{self.name}', tag={self.tag.name}, value={self.value})"

class IPPMessage:
    
    def __init__(self):
        self.version_major: int = 2
        self.version_minor: int = 1
        self.operation_id: int = 0
        self.request_id: int = 0
        self.operation_attributes: Dict[str, IPPAttribute] = {}
        self.job_attributes: Dict[str, IPPAttribute] = {}
        self.printer_attributes: Dict[str, IPPAttribute] = {}
        self.unsupported_attributes: Dict[str, IPPAttribute] = {}
        self.document_data: Optional[bytes] = None
    
    def add_operation_attribute(self, name: str, tag: IPPTag, value: Any):
        self.operation_attributes[name] = IPPAttribute(name, tag, value)
    
    def add_printer_attribute(self, name: str, tag: IPPTag, value: Any):
        self.printer_attributes[name] = IPPAttribute(name, tag, value)
    
    def add_job_attribute(self, name: str, tag: IPPTag, value: Any):
        self.job_attributes[name] = IPPAttribute(name, tag, value)

class IPPParser:
    
    @staticmethod
    def parse_request(data: bytes) -> IPPMessage:
        if len(data) < 8:
            raise ValueError("IPP message too short")
        
        stream = io.BytesIO(data)
        message = IPPMessage()
        
        # Parse IPP header (8 bytes)
        header = struct.unpack(">BBHHI", stream.read(8))
        message.version_major = header[0]
        message.version_minor = header[1]
        message.operation_id = header[2]
        message.request_id = header[3]
        
        logger.debug(f"Parsing IPP message: version={message.version_major}.{message.version_minor}, "
                    f"operation={message.operation_id}, request_id={message.request_id}")
        
        # Parse attributes
        current_group = None
        
        while True:
            # Read tag
            tag_bytes = stream.read(1)
            if not tag_bytes:
                break
            
            tag = ord(tag_bytes)
            
            if tag == IPPTag.END_OF_ATTRIBUTES_TAG:
                # End of attributes, rest is document data
                remaining = stream.read()
                if remaining:
                    message.document_data = remaining
                break
            
            # Check for group delimiter tags
            if tag in [IPPTag.OPERATION_ATTRIBUTES_TAG, IPPTag.JOB_ATTRIBUTES_TAG, 
                      IPPTag.PRINTER_ATTRIBUTES_TAG, IPPTag.UNSUPPORTED_ATTRIBUTES_TAG]:
                current_group = tag
                continue
            
            # Parse attribute
            attribute = IPPParser._parse_attribute(stream, IPPTag(tag))
            if attribute and current_group is not None:
                if current_group == IPPTag.OPERATION_ATTRIBUTES_TAG:
                    message.operation_attributes[attribute.name] = attribute
                elif current_group == IPPTag.JOB_ATTRIBUTES_TAG:
                    message.job_attributes[attribute.name] = attribute
                elif current_group == IPPTag.PRINTER_ATTRIBUTES_TAG:
                    message.printer_attributes[attribute.name] = attribute
                elif current_group == IPPTag.UNSUPPORTED_ATTRIBUTES_TAG:
                    message.unsupported_attributes[attribute.name] = attribute
        
        return message
    
    @staticmethod
    def _parse_attribute(stream: io.BytesIO, tag: IPPTag) -> Optional[IPPAttribute]:
        try:
            # Read name length
            name_len = struct.unpack(">H", stream.read(2))[0]
            
            # Read name
            name = ""
            if name_len > 0:
                name = stream.read(name_len).decode('utf-8')
            
            # Read value length
            value_len = struct.unpack(">H", stream.read(2))[0]
            
            # Read and parse value based on tag
            value_bytes = stream.read(value_len) if value_len > 0 else b""
            value = IPPParser._parse_value(tag, value_bytes)
            
            return IPPAttribute(name, tag, value)
            
        except Exception as e:
            logger.error(f"Error parsing attribute: {e}")
            return None
    
    @staticmethod
    def _parse_value(tag: IPPTag, value_bytes: bytes) -> Any:
        if not value_bytes:
            return None
        
        try:
            if tag == IPPTag.INTEGER or tag == IPPTag.ENUM:
                return struct.unpack(">I", value_bytes)[0]
            elif tag == IPPTag.BOOLEAN:
                return ord(value_bytes) != 0
            elif tag in [IPPTag.TEXT_WITHOUT_LANGUAGE, IPPTag.NAME_WITHOUT_LANGUAGE, 
                        IPPTag.KEYWORD, IPPTag.URI, IPPTag.CHARSET, IPPTag.NATURAL_LANGUAGE,
                        IPPTag.MIME_MEDIA_TYPE]:
                return value_bytes.decode('utf-8')
            elif tag == IPPTag.OCTET_STRING:
                return value_bytes
            elif tag == IPPTag.DATETIME:
                # Parse RFC 1903 DateAndTime format
                if len(value_bytes) >= 8:
                    return struct.unpack(">HBBBBBB", value_bytes[:8])
                return value_bytes
            elif tag == IPPTag.RESOLUTION:
                # Parse resolution (cross-feed, feed, units)
                if len(value_bytes) >= 9:
                    return struct.unpack(">IIB", value_bytes[:9])
                return value_bytes
            elif tag == IPPTag.RANGE_OF_INTEGER:
                # Parse range (lower, upper)
                if len(value_bytes) >= 8:
                    return struct.unpack(">II", value_bytes[:8])
                return value_bytes
            else:
                return value_bytes
                
        except Exception as e:
            logger.warning(f"Error parsing value for tag {tag}: {e}")
            return value_bytes
    
    @staticmethod
    def build_response(operation_id: int, request_id: int, status_code: IPPStatusCode, 
                      attributes: Dict[str, Any]) -> bytes:
        stream = io.BytesIO()
        
        # Write IPP header
        stream.write(struct.pack(">BBHHI", 2, 1, status_code, request_id))
        
        # Write operation attributes group
        stream.write(bytes([IPPTag.OPERATION_ATTRIBUTES_TAG]))
        
        # Add required operation attributes
        IPPParser._write_attribute(stream, "attributes-charset", IPPTag.CHARSET, "utf-8")
        IPPParser._write_attribute(stream, "attributes-natural-language", IPPTag.NATURAL_LANGUAGE, "en")
        
        # Determine attribute group type based on operation
        if operation_id == IPPOperation.GET_PRINTER_ATTRIBUTES:
            # Write printer attributes
            stream.write(bytes([IPPTag.PRINTER_ATTRIBUTES_TAG]))
            for name, value in attributes.items():
                tag = IPPParser._get_attribute_tag(value)
                IPPParser._write_attribute(stream, name, tag, value)
        else:
            # Write job attributes for job operations
            stream.write(bytes([IPPTag.JOB_ATTRIBUTES_TAG]))
            for name, value in attributes.items():
                tag = IPPParser._get_attribute_tag(value)
                IPPParser._write_attribute(stream, name, tag, value)
        
        # End of attributes
        stream.write(bytes([IPPTag.END_OF_ATTRIBUTES_TAG]))
        
        return stream.getvalue()
    
    @staticmethod
    def _write_attribute(stream: io.BytesIO, name: str, tag: IPPTag, value: Any):
        # Write tag
        stream.write(bytes([tag]))
        
        # Write name
        name_bytes = name.encode('utf-8')
        stream.write(struct.pack(">H", len(name_bytes)))
        stream.write(name_bytes)
        
        # Serialize value
        value_bytes = IPPParser._serialize_value(tag, value)
        stream.write(struct.pack(">H", len(value_bytes)))
        stream.write(value_bytes)
    
    @staticmethod
    def _serialize_value(tag: IPPTag, value: Any) -> bytes:
        if value is None:
            return b""
        
        try:
            if tag == IPPTag.INTEGER or tag == IPPTag.ENUM:
                return struct.pack(">I", int(value))
            elif tag == IPPTag.BOOLEAN:
                return bytes([1 if value else 0])
            elif tag in [IPPTag.TEXT_WITHOUT_LANGUAGE, IPPTag.NAME_WITHOUT_LANGUAGE, 
                        IPPTag.KEYWORD, IPPTag.URI, IPPTag.CHARSET, IPPTag.NATURAL_LANGUAGE,
                        IPPTag.MIME_MEDIA_TYPE]:
                return str(value).encode('utf-8')
            elif tag == IPPTag.OCTET_STRING:
                return value if isinstance(value, bytes) else str(value).encode('utf-8')
            elif tag == IPPTag.RESOLUTION and isinstance(value, tuple) and len(value) >= 3:
                return struct.pack(">IIB", value[0], value[1], value[2])
            elif tag == IPPTag.RANGE_OF_INTEGER and isinstance(value, tuple) and len(value) >= 2:
                return struct.pack(">II", value[0], value[1])
            else:
                return str(value).encode('utf-8')
                
        except Exception as e:
            logger.warning(f"Error serializing value for tag {tag}: {e}")
            return str(value).encode('utf-8')
    
    @staticmethod
    def _get_attribute_tag(value: Any) -> IPPTag:
        if isinstance(value, bool):
            return IPPTag.BOOLEAN
        elif isinstance(value, int):
            return IPPTag.INTEGER
        elif isinstance(value, str):
            # Use keyword for short strings, text for longer ones
            return IPPTag.KEYWORD if len(value) < 50 else IPPTag.TEXT_WITHOUT_LANGUAGE
        elif isinstance(value, list):
            # For lists, use the tag of the first element
            if value and len(value) > 0:
                return IPPParser._get_attribute_tag(value[0])
            return IPPTag.TEXT_WITHOUT_LANGUAGE
        elif isinstance(value, bytes):
            return IPPTag.OCTET_STRING
        else:
            return IPPTag.TEXT_WITHOUT_LANGUAGE