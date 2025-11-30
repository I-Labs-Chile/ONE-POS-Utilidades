import os
import subprocess
import re
from serial.tools import list_ports

# Función para listar información de los puertos seriales
def list_ports_info():
    return list_ports.comports()

# Función para imprimir información de los puertos seriales
def print_ports():
    ports = list_ports_info()
    print("=== PUERTOS SERIALES ===")
    if not ports:
        print("No se encontraron puertos seriales.")
        return
        
    for p in ports:
        print("device:", p.device)
        print("  name:       ", getattr(p, 'name', None))
        print("  description:", getattr(p, 'description', None))
        print("  hwid:       ", getattr(p, 'hwid', None))
        vid = getattr(p, 'vid', None)
        pid = getattr(p, 'pid', None)
        if vid and pid:
            print("  vid:pid:    ", f"{vid:04x}:{pid:04x}")
        else:
            print("  vid:pid:    ", None)
        print("  manufacturer:", getattr(p, 'manufacturer', None))
        print("  product:     ", getattr(p, 'product', None))
        print("---")

# Función para verificar impresoras USB conectadas
def check_usb_printers():
    print("\n=== IMPRESORAS USB (usblp) ===")
    
    # Buscar dispositivos USB de impresoras
    usb_devices = []
    if os.path.exists("/dev/usb"):
        for device in os.listdir("/dev/usb"):
            if device.startswith("lp"):
                device_path = f"/dev/usb/{device}"
                usb_devices.append(device_path)
                print(f"Dispositivo USB encontrado: {device_path}")
    
    # Verificar información en dmesg
    try:
        result = subprocess.run(['dmesg'], capture_output=True, text=True)
        dmesg_output = result.stdout
        
        # Buscar mensajes relacionados con usblp y la impresora
        printer_lines = []
        for line in dmesg_output.split('\n'):
            if any(keyword in line.lower() for keyword in ['usblp', 'printer', 'xprinter']):
                printer_lines.append(line.strip())
        
        if printer_lines:
            print("\nInformación de dmesg sobre impresoras:")
            for line in printer_lines[-10:]:
                print(f"  {line}")
        
        # Extraer información específica de la impresora
        xprinter_info = extract_xprinter_info(dmesg_output)
        if xprinter_info:
            print(f"\nImpresora Xprinter detectada:")
            for key, value in xprinter_info.items():
                print(f"  {key}: {value}")
                
    except Exception as e:
        print(f"Error al ejecutar dmesg: {e}")
    
    return usb_devices

# Función para extraer información de Xprinter desde dmesg
def extract_xprinter_info(dmesg_output):
    info = {}
    
    # Patrones para extraer información de la impresora
    patterns = {
        'manufacturer': r'Manufacturer:\s*(.+?)(?:\s|$)',
        'product': r'Product:\s*(.+?)(?:\s|$)',
        'usblp_device': r'(usblp\d+)',
        'vendor_id': r'idVendor=([0-9a-fA-F]{4})',
        'product_id': r'idProduct=([0-9a-fA-F]{4})'
    }
    
    for key, pattern in patterns.items():
        matches = re.findall(pattern, dmesg_output, re.IGNORECASE)
        if matches:
            info[key] = matches[-1]  # Obtener el último resultado coincidente
    
    return info if info else None

# Función para probar si el dispositivo USB de la impresora es accesible
def test_usb_printer(device_path="/dev/usb/lp0"):
    print(f"\n=== PRUEBA DE ACCESO A {device_path} ===")
    
    if not os.path.exists(device_path):
        print(f"El dispositivo {device_path} no existe.")
        return False
    
    try:
        # Verificar si se puede abrir el dispositivo
        with open(device_path, "wb") as f:
            print(f"Dispositivo {device_path} accesible para escritura.")
            return True
    except PermissionError:
        print(f"Sin permisos para acceder a {device_path}. Ejecuta como root o añade tu usuario al grupo lp.")
        return False
    except Exception as e:
        print(f"Error al acceder a {device_path}: {e}")
        return False

# Función para enviar una impresión de prueba a la impresora USB
def send_test_print(device_path="/dev/usb/lp0", test_text="Prueba de impresion\n"):
    print(f"\n=== ENVÍO DE PRUEBA A {device_path} ===")
    
    if not test_usb_printer(device_path):
        return False
    
    try:
        with open(device_path, "wb") as f:
            # Enviar texto de prueba
            f.write(test_text.encode('utf-8'))
            # Enviar avance de página para cortar papel (si es compatible)
            f.write(b'\x0c')
        print(f"Texto enviado exitosamente: '{test_text.strip()}'")
        return True
    except Exception as e:
        print(f"Error al enviar datos: {e}")
        return False

# Función para buscar un dispositivo por palabra clave
def find_by_keyword(keyword):
    ports = list_ports_info()
    for p in ports:
        parts = [str(getattr(p, 'device', '')), str(getattr(p, 'description', '')), str(getattr(p, 'hwid', '')),
                 str(getattr(p, 'vid', '')), str(getattr(p, 'pid', '')), str(getattr(p, 'product', ''))]
        meta = " ".join([x for x in parts if x and x != 'None'])
        if keyword.lower() in meta.lower():
            return getattr(p, 'device', None), getattr(p, 'description', None), getattr(p, 'hwid', None)
    return None

# Punto de entrada principal del script
if __name__ == "__main__":
    print("DETECCIÓN DE IMPRESORAS - SERIAL Y USB")
    print("=" * 50)
    
    # Verificar puertos seriales
    # print_ports()
    
    # Verificar impresoras USB
    usb_devices = check_usb_printers()
    
    # Probar acceso a las impresoras USB detectadas
    if usb_devices:
        for device in usb_devices:
            test_usb_printer(device)
    
    # Verificar dispositivos USB comunes
    common_paths = ["/dev/usb/lp0", "/dev/usb/lp1"]
    for path in common_paths:
        if os.path.exists(path) and path not in usb_devices:
            test_usb_printer(path)
    
    # Buscar impresora serial si es necesario
    kw = "Unknown-3"
    print(f"\n=== BÚSQUEDA SERIAL: '{kw}' ===")
    found = find_by_keyword(kw)
    if found:
        print("Encontrado:", found)
    else:
        print("No encontrado en puertos seriales.")
    
    print("\n" + "=" * 50)
    print("INSTRUCCIONES:")
    print("- Para impresoras USB (usblp): usar /dev/usb/lp0")
    print("- Enviar datos RAW: with open('/dev/usb/lp0', 'wb') as f: f.write(datos)")
    print("- Si no tienes permisos: sudo python3 detect_printer.py")
    print("- O agregar usuario al grupo lp: sudo usermod -a -G lp $USER")
