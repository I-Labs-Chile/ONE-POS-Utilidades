#!/usr/bin/env python3

import requests
import struct

def create_ipp_print_job():

    # IPP version 2.0, Print-Job operation (2), request ID
    version = struct.pack('>BB', 2, 0)  # major, minor version
    operation = struct.pack('>H', 2)    # Print-Job operation
    request_id = struct.pack('>I', 999) # Request ID
    
    # Operation attributes tag
    op_attrs = b'\x01'
    
    # Attributes charset (required)
    charset_tag = struct.pack('B', 0x47)  # charset tag
    charset_name = b'attributes-charset'
    charset_value = b'utf-8'
    charset_attr = charset_tag + struct.pack('>H', len(charset_name)) + charset_name + \
                   struct.pack('>H', len(charset_value)) + charset_value
    
    # Attributes natural language (required)
    lang_tag = struct.pack('B', 0x48)  # natural-language tag
    lang_name = b'attributes-natural-language'
    lang_value = b'en-us'
    lang_attr = lang_tag + struct.pack('>H', len(lang_name)) + lang_name + \
                struct.pack('>H', len(lang_value)) + lang_value
    
    # Printer URI (required)
    uri_tag = struct.pack('B', 0x45)  # uri tag
    uri_name = b'printer-uri'
    uri_value = b'ipp://192.168.1.106:8631/ipp/printer'
    uri_attr = uri_tag + struct.pack('>H', len(uri_name)) + uri_name + \
               struct.pack('>H', len(uri_value)) + uri_value
    
    # Job attributes tag
    job_attrs = b'\x02'
    
    # End of attributes tag
    end_attrs = b'\x03'
    
    # Simple document data (test message)
    document_data = b'Test print job from Python IPP client\n'
    
    # Combine all parts
    ipp_request = version + operation + request_id + \
                  op_attrs + charset_attr + lang_attr + uri_attr + \
                  job_attrs + end_attrs + document_data
    
    return ipp_request

def test_print_job():
    
    print("Creating IPP Print-Job request...")
    ipp_data = create_ipp_print_job()
    
    print(f"Request size: {len(ipp_data)} bytes")
    print(f"Request hex: {ipp_data[:50].hex()}...")
    
    try:
        print("Sending print job to server...")
        response = requests.post(
            'http://localhost:8631/ipp/printer',
            data=ipp_data,
            headers={'Content-Type': 'application/ipp'},
            timeout=10
        )
        
        print(f"Response status: {response.status_code}")
        print(f"Response size: {len(response.content)} bytes")
        print(f"Response hex: {response.content[:50].hex()}")
        
        # Try to decode the response
        if len(response.content) >= 8:
            version_maj, version_min, status_code, req_id = struct.unpack('>BBHI', response.content[:8])
            print(f"IPP Response: v{version_maj}.{version_min}, status={status_code}, req_id={req_id}")
        
        return response.status_code == 200
        
    except Exception as e:
        print(f"Error sending print job: {e}")
        return False

if __name__ == '__main__':
    test_print_job()