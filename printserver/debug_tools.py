#!/usr/bin/env python3
import asyncio
import logging
import time
from typing import Dict, List, Optional, Any
import json
from pathlib import Path

logger = logging.getLogger(__name__)

class IPPTrafficAnalyzer:

    def __init__(self, output_dir: str = "debug_logs"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.sessions = {}
        
    def start_session(self, client_ip: str, client_type: str = "unknown") -> str:
        session_id = f"{client_ip}_{int(time.time())}"
        self.sessions[session_id] = {
            'client_ip': client_ip,
            'client_type': client_type,
            'start_time': time.time(),
            'requests': [],
            'raw_data': []
        }
        logger.info(f"🔍 Started debugging session for {client_type} client: {session_id}")
        return session_id
        
    def log_request(self, session_id: str, request_data: bytes, headers: dict, 
                   path: str, method: str) -> None:

        if session_id not in self.sessions:
            logger.warning(f"Session {session_id} not found")
            return
            
        request_info = {
            'timestamp': time.time(),
            'method': method,
            'path': path,
            'headers': dict(headers),
            'content_length': len(request_data),
            'raw_data_preview': self._safe_preview(request_data, 200)
        }
        
        self.sessions[session_id]['requests'].append(request_info)
        
        # Guardar datos raw en archivo separado
        raw_file = self.output_dir / f"{session_id}_raw_{len(self.sessions[session_id]['raw_data'])}.bin"
        with open(raw_file, 'wb') as f:
            f.write(request_data)
            
        self.sessions[session_id]['raw_data'].append(str(raw_file))
        
        logger.debug(f"📊 Logged request for session {session_id}: {method} {path}, {len(request_data)} bytes")
        
    def analyze_ipp_message(self, session_id: str, ipp_data: bytes) -> Dict[str, Any]:

        analysis = {
            'timestamp': time.time(),
            'total_size': len(ipp_data),
            'header_analysis': {},
            'attributes': [],
            'document_data_size': 0,
            'errors': []
        }
        
        try:
            if len(ipp_data) < 8:
                analysis['errors'].append("Data too short for IPP header")
                return analysis
                
            # Analizar header IPP
            version_major, version_minor = ipp_data[0], ipp_data[1]
            operation_id = int.from_bytes(ipp_data[2:4], 'big')
            request_id = int.from_bytes(ipp_data[4:8], 'big')
            
            analysis['header_analysis'] = {
                'version': f"{version_major}.{version_minor}",
                'operation_id': f"0x{operation_id:04x}",
                'operation_name': self._get_operation_name(operation_id),
                'request_id': request_id
            }
            
            # Analizar atributos
            offset = 8
            current_group = None
            
            while offset < len(ipp_data):
                if offset + 1 >= len(ipp_data):
                    break
                    
                tag = ipp_data[offset]
                offset += 1
                
                if tag == 0x01:  # operation-attributes-tag
                    current_group = 'operation'
                    continue
                elif tag == 0x02:  # job-attributes-tag
                    current_group = 'job'
                    continue
                elif tag == 0x04:  # printer-attributes-tag
                    current_group = 'printer'
                    continue
                elif tag == 0x03:  # end-of-attributes-tag
                    # Document data follows
                    doc_size = len(ipp_data) - offset
                    analysis['document_data_size'] = doc_size
                    if doc_size > 0:
                        analysis['document_preview'] = self._safe_preview(ipp_data[offset:], 100)
                    break
                
                # Parse attribute
                if offset + 2 >= len(ipp_data):
                    break
                    
                name_length = int.from_bytes(ipp_data[offset:offset+2], 'big')
                offset += 2
                
                if offset + name_length >= len(ipp_data):
                    break
                    
                name = ipp_data[offset:offset+name_length].decode('utf-8', errors='ignore')
                offset += name_length
                
                if offset + 2 >= len(ipp_data):
                    break
                    
                value_length = int.from_bytes(ipp_data[offset:offset+2], 'big')
                offset += 2
                
                if offset + value_length > len(ipp_data):
                    break
                    
                value_data = ipp_data[offset:offset+value_length]
                offset += value_length
                
                attr_info = {
                    'group': current_group,
                    'name': name,
                    'tag': f"0x{tag:02x}",
                    'value_length': value_length,
                    'value_preview': self._safe_preview(value_data, 50)
                }
                
                analysis['attributes'].append(attr_info)
                
        except Exception as e:
            analysis['errors'].append(f"Analysis error: {str(e)}")
            
        if session_id in self.sessions:
            self.sessions[session_id].setdefault('ipp_analyses', []).append(analysis)
            
        return analysis
        
    def _get_operation_name(self, operation_id: int) -> str:

        operations = {
            0x0002: 'Print-Job',
            0x0004: 'Validate-Job',
            0x000a: 'Get-Jobs',
            0x000b: 'Get-Printer-Attributes'
        }
        return operations.get(operation_id, f'Unknown-0x{operation_id:04x}')
        
    def _safe_preview(self, data: bytes, max_length: int) -> str:

        if not data:
            return ""
            
        preview_data = data[:max_length]
        try:
            # Intentar decodificar como texto
            text = preview_data.decode('utf-8', errors='ignore')
            if all(ord(c) >= 32 or c in '\n\r\t' for c in text):
                return f"TEXT: {repr(text)}"
        except:
            pass
            
        # Mostrar como hex
        hex_str = preview_data.hex()
        return f"HEX: {hex_str[:100]}{'...' if len(hex_str) > 100 else ''}"
        
    def save_session_report(self, session_id: str) -> str:

        if session_id not in self.sessions:
            return ""
            
        session = self.sessions[session_id]
        report_file = self.output_dir / f"report_{session_id}.json"
        
        # Preparar reporte
        report = {
            'session_info': {
                'session_id': session_id,
                'client_ip': session['client_ip'],
                'client_type': session['client_type'],
                'start_time': session['start_time'],
                'duration': time.time() - session['start_time']
            },
            'summary': {
                'total_requests': len(session['requests']),
                'total_raw_files': len(session['raw_data']),
                'ipp_analyses': len(session.get('ipp_analyses', []))
            },
            'requests': session['requests'],
            'ipp_analyses': session.get('ipp_analyses', []),
            'raw_files': session['raw_data']
        }
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, default=str)
            
        logger.info(f"📋 Session report saved: {report_file}")
        return str(report_file)
        
    def compare_sessions(self, android_session_id: str, pc_session_id: str) -> Dict[str, Any]:

        comparison = {
            'timestamp': time.time(),
            'android_session': android_session_id,
            'pc_session': pc_session_id,
            'differences': [],
            'similarities': []
        }
        
        android_session = self.sessions.get(android_session_id)
        pc_session = self.sessions.get(pc_session_id)
        
        if not android_session or not pc_session:
            comparison['error'] = "One or both sessions not found"
            return comparison
            
        # Comparar número de peticiones
        android_requests = len(android_session['requests'])
        pc_requests = len(pc_session['requests'])
        
        if android_requests != pc_requests:
            comparison['differences'].append({
                'type': 'request_count',
                'android': android_requests,
                'pc': pc_requests
            })
            
        # Comparar análisis IPP
        android_analyses = android_session.get('ipp_analyses', [])
        pc_analyses = pc_session.get('ipp_analyses', [])
        
        for i, (android_analysis, pc_analysis) in enumerate(zip(android_analyses, pc_analyses)):
            # Comparar headers
            android_header = android_analysis.get('header_analysis', {})
            pc_header = pc_analysis.get('header_analysis', {})
            
            if android_header != pc_header:
                comparison['differences'].append({
                    'type': 'ipp_header',
                    'request_index': i,
                    'android': android_header,
                    'pc': pc_header
                })
                
            # Comparar atributos
            android_attrs = {attr['name']: attr for attr in android_analysis.get('attributes', [])}
            pc_attrs = {attr['name']: attr for attr in pc_analysis.get('attributes', [])}
            
            android_attr_names = set(android_attrs.keys())
            pc_attr_names = set(pc_attrs.keys())
            
            if android_attr_names != pc_attr_names:
                comparison['differences'].append({
                    'type': 'attributes',
                    'request_index': i,
                    'android_only': list(android_attr_names - pc_attr_names),
                    'pc_only': list(pc_attr_names - android_attr_names)
                })
                
        # Guardar comparación
        comp_file = self.output_dir / f"comparison_{android_session_id}_vs_{pc_session_id}.json"
        with open(comp_file, 'w', encoding='utf-8') as f:
            json.dump(comparison, f, indent=2, default=str)
            
        logger.info(f"📊 Comparison saved: {comp_file}")
        return comparison

# Instancia global del analizador
traffic_analyzer = IPPTrafficAnalyzer()