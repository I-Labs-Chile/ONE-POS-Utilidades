#!/usr/bin/env python3
import requests
import json
from pathlib import Path

def test_get_printer_attributes():

    # IPP Get-Printer-Attributes message
    ipp_message = bytearray()
    
    # IPP Header (8 bytes)
    ipp_message.extend([0x01, 0x01])  # Version 1.1
    ipp_message.extend([0x00, 0x0b])  # Get-Printer-Attributes (0x000b)
    ipp_message.extend([0x00, 0x00, 0x00, 0x01])  # Request ID
    
    # Operation attributes
    ipp_message.append(0x01)  # operation-attributes-tag
    
    # attributes-charset
    ipp_message.append(0x47)  # charset
    ipp_message.extend([0x00, 0x12])  # name length
    ipp_message.extend(b'attributes-charset')
    ipp_message.extend([0x00, 0x05])  # value length
    ipp_message.extend(b'utf-8')
    
    # attributes-natural-language
    ipp_message.append(0x48)  # naturalLanguage
    ipp_message.extend([0x00, 0x1b])  # name length
    ipp_message.extend(b'attributes-natural-language')
    ipp_message.extend([0x00, 0x05])  # value length
    ipp_message.extend(b'en-us')
    
    # printer-uri
    ipp_message.append(0x45)  # uri
    ipp_message.extend([0x00, 0x0b])  # name length
    ipp_message.extend(b'printer-uri')
    ipp_message.extend([0x00, 0x24])  # value length (36 bytes for the URI)
    ipp_message.extend(b'ipp://192.168.1.106:631/ipp/printer')
    
    # End of attributes
    ipp_message.append(0x03)
    
    # Send request
    try:
        response = requests.post(
            'http://192.168.1.106:631/ipp/printer',
            data=bytes(ipp_message),
            headers={'Content-Type': 'application/ipp'},
            timeout=10
        )
        
        print(f"✅ PC Test Response: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        print(f"Response length: {len(response.content)} bytes")
        
        # Save response for analysis
        Path("debug_logs").mkdir(exist_ok=True)
        with open("debug_logs/pc_response.bin", "wb") as f:
            f.write(response.content)
            
        return True
        
    except Exception as e:
        print(f"❌ PC Test Failed: {e}")
        return False

def analyze_debug_reports():

    debug_dir = Path("debug_logs")
    if not debug_dir.exists():
        print("No debug logs directory found")
        return
    
    reports = list(debug_dir.glob("report_*.json"))
    if not reports:
        print("No debug reports found")
        return
    
    print(f"\n🔍 Found {len(reports)} debug reports:")
    for report_file in reports:
        with open(report_file) as f:
            report = json.load(f)
            
        session_info = report.get('session_info', {})
        summary = report.get('summary', {})
        
        print(f"\n📊 {report_file.name}:")
        print(f"  Client: {session_info.get('client_type', 'unknown')} ({session_info.get('client_ip', 'unknown')})")
        print(f"  Requests: {summary.get('total_requests', 0)}")
        print(f"  IPP Analyses: {summary.get('ipp_analyses', 0)}")
        
        # Show IPP operations
        for analysis in report.get('ipp_analyses', []):
            header = analysis.get('header_analysis', {})
            print(f"    Operation: {header.get('operation_name', 'Unknown')}")
            print(f"    Attributes: {len(analysis.get('attributes', []))}")
            print(f"    Document size: {analysis.get('document_data_size', 0)} bytes")

def main():
    
    print("🧪 IPP Testing and Analysis Tool")
    print("=" * 40)
    
    print("\n1. Testing from PC...")
    test_get_printer_attributes()
    
    print("\n2. Analyzing debug reports...")
    analyze_debug_reports()
    
    print("\n📋 Instructions:")
    print("1. Start the server with debug mode")
    print("2. Try printing from Android")
    print("3. Run this script again to compare")

if __name__ == "__main__":
    main()