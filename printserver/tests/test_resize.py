#!/usr/bin/env python3

from pathlib import Path
import sys
import socket

# Inserta la raíz del proyecto para permitir importaciones del servidor
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from server.converter import DocumentConverter
from config.settings import settings
import asyncio

# Obtiene IP local preferente para mostrar configuración de red (con fallback)
def get_local_ip():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.settimeout(1)
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except Exception:
        try:
            return socket.gethostbyname(socket.gethostname())
        except Exception:
            return "localhost"

# Muestra parámetros de conexión IPP y configuración para clientes externos
def show_network_config():
    local_ip = get_local_ip()
    print("=" * 50)
    print("📡 CONFIGURACIÓN DE RED PARA CLIENTES")
    print("=" * 50)
    print(f"IP del servidor: {local_ip}")
    print(f"Puerto: {settings.SERVER_PORT}")
    print(f"URI IPP: ipp://{local_ip}:{settings.SERVER_PORT}/ipp/print")
    print(f"Interfaz web: http://{local_ip}:{settings.SERVER_PORT}/")
    print()
    print("📱 USAR EN APLICACIONES (NetPrinter, etc.):")
    print(f"  Host/IP: {local_ip}")
    print(f"  Puerto: {settings.SERVER_PORT}")
    print(f"  Protocolo: IPP")
    print(f"  Ruta: /ipp/print")
    print("=" * 50)
    print()

# Prueba conversión de un PDF existente a comandos ESC/POS guardando salida
async def test_pdf_conversion():
    print(f"⚙️  Configuración de impresora:")
    print(f"  PRINTER_WIDTH_MM: {settings.PRINTER_WIDTH_MM}mm")
    print(f"  PRINTER_MAX_PIXELS: {settings.PRINTER_MAX_PIXELS}px")
    print(f"  PRINTER_DPI: {settings.PRINTER_DPI}")
    print()
    show_network_config()

    converter = DocumentConverter()
    search_paths = [
        Path(__file__).parent,
        Path(__file__).parent.parent,
        Path.cwd(),
    ]

    test_files = ["test_document.pdf", "test.pdf", "documento.pdf", "prueba.pdf"]
    found_file = None
    for search_path in search_paths:
        for test_file in test_files:
            file_path = search_path / test_file
            if file_path.exists():
                found_file = file_path
                break
        if found_file:
            break

    if found_file:
        with open(found_file, 'rb') as f:
            pdf_data = f.read()
        print(f"📄 Convirtiendo {found_file.name}...")
        print(f"📊 Tamaño original: {len(pdf_data)} bytes")
        try:
            escpos_data = await converter.convert_to_escpos(pdf_data, 'application/pdf')
            print(f"✅ Conversión completada: {len(escpos_data)} bytes de datos ESC/POS")
            output_file = Path(__file__).parent / 'output.escpos'
            with open(output_file, 'wb') as f:
                f.write(escpos_data)
            print(f"💾 Resultado guardado en {output_file}")
        except Exception as e:
            print(f"❌ Error en conversión: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("📄 No se encontró ningún archivo PDF de prueba")
        print("🔍 Archivos buscados:", test_files)
        print("📁 Directorios buscados:", [str(p) for p in search_paths])

if __name__ == "__main__":
    asyncio.run(test_pdf_conversion())