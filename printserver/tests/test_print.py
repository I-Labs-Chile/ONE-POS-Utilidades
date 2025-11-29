#!/usr/bin/env python3

import requests
import struct

# Construye solicitud IPP Print-Job mínima con atributos obligatorios y datos
def create_ipp_print_job():

    version = struct.pack('>BB', 2, 0)
    operation = struct.pack('>H', 2)
    request_id = struct.pack('>I', 999)
    op_attrs = b'\x01'

    charset_tag = struct.pack('B', 0x47)
    charset_name = b'attributes-charset'
    charset_value = b'utf-8'
    charset_attr = charset_tag + struct.pack('>H', len(charset_name)) + charset_name + \
                   struct.pack('>H', len(charset_value)) + charset_value
    
    lang_tag = struct.pack('B', 0x48)
    lang_name = b'attributes-natural-language'
    lang_value = b'en-us'
    lang_attr = lang_tag + struct.pack('>H', len(lang_name)) + lang_name + \
                struct.pack('>H', len(lang_value)) + lang_value
    
    uri_tag = struct.pack('B', 0x45)
    uri_name = b'printer-uri'
    uri_value = b'ipp://192.168.1.106:8631/ipp/printer'
    uri_attr = uri_tag + struct.pack('>H', len(uri_name)) + uri_name + \
               struct.pack('>H', len(uri_value)) + uri_value
    
    job_attrs = b'\x02'
    end_attrs = b'\x03'
    document_data = b'Test print job from Python IPP client\n'
    ipp_request = version + operation + request_id + \
                  op_attrs + charset_attr + lang_attr + uri_attr + \
                  job_attrs + end_attrs + document_data
    
    return ipp_request

# Envía la solicitud Print-Job al servidor IPP local y muestra respuesta básica
def test_print_job():
    print("Creando solicitud IPP Print-Job...")
    ipp_data = create_ipp_print_job()
    print(f"Tamaño de solicitud: {len(ipp_data)} bytes")
    print(f"Hex parcial: {ipp_data[:50].hex()}...")

    try:
        print("Enviando trabajo de impresión al servidor...")
        response = requests.post(
            'http://localhost:8631/ipp/printer',
            data=ipp_data,
            headers={'Content-Type': 'application/ipp'},
            timeout=10
        )
        print(f"Estado HTTP: {response.status_code}")
        print(f"Tamaño respuesta: {len(response.content)} bytes")
        print(f"Hex respuesta parcial: {response.content[:50].hex()}")
        if len(response.content) >= 8:
            version_maj, version_min, status_code, req_id = struct.unpack('>BBHI', response.content[:8])
            print(f"IPP Respuesta: v{version_maj}.{version_min}, status={status_code}, req_id={req_id}")
        return response.status_code == 200
    
    except Exception as e:
        print(f"Error enviando trabajo: {e}")
        return False

if __name__ == '__main__':
    test_print_job()