# Importar las bibliotecas necesarias
import sys
from datetime import datetime

# Función para generar un ticket de prueba completo con características ESC/POS
def generate_comprehensive_test():
    commands = []
    
    # Inicializar impresora
    commands.append(b'\x1B\x40')  # ESC @ - Inicializar
    
    # Encabezado con título centrado y grande
    commands.append(b'\x1B\x61\x01')  # Centrar
    commands.append(b'\x1D\x21\x11')  # Doble altura y ancho
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("=== PRUEBA COMPLETA ===\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append(b'\x1D\x21\x00')  # Tamaño normal
    
    # Fecha y hora
    now = datetime.now()
    commands.append(f"{now.strftime('%d/%m/%Y %H:%M:%S')}\n".encode('utf-8'))
    commands.append(b'\x1B\x61\x00')  # Alinear izquierda
    commands.append("\n".encode('utf-8'))
    
    # Separador
    commands.append(("=" * 32 + "\n").encode('utf-8'))
    
    # Pruebas de tamaño de texto
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("TAMAÑOS DE TEXTO:\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    
    commands.append("Tamaño normal\n".encode('utf-8'))
    commands.append(b'\x1D\x21\x01')  # Doble altura
    commands.append("Doble altura\n".encode('utf-8'))
    commands.append(b'\x1D\x21\x00')  # Tamaño normal
    commands.append(b'\x1D\x21\x10')  # Doble ancho
    commands.append("Doble ancho\n".encode('utf-8'))
    commands.append(b'\x1D\x21\x00')  # Tamaño normal
    commands.append(b'\x1D\x21\x11')  # Doble altura y ancho
    commands.append("Doble H+W\n".encode('utf-8'))
    commands.append(b'\x1D\x21\x00')  # Tamaño normal
    commands.append("\n".encode('utf-8'))
    
    # Separador
    commands.append(("-" * 32 + "\n").encode('utf-8'))
    
    # Pruebas de estilo de texto
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("ESTILOS DE TEXTO:\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append("Texto normal\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("Texto en NEGRITA\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append(b'\x1B\x34')  # Cursiva ON
    commands.append("Texto en cursiva\n".encode('utf-8'))
    commands.append(b'\x1B\x35')  # Cursiva OFF
    commands.append(b'\x1B\x2D\x01')  # Subrayado ON
    commands.append("Texto subrayado\n".encode('utf-8'))
    commands.append(b'\x1B\x2D\x00')  # Subrayado OFF
    commands.append(b'\x1D\x42\x01')  # Texto invertido ON
    commands.append("Texto INVERTIDO\n".encode('utf-8'))
    commands.append(b'\x1D\x42\x00')  # Texto invertido OFF
    commands.append("\n".encode('utf-8'))
    
    # Separador
    commands.append(("-" * 32 + "\n").encode('utf-8'))
    
    # Pruebas de alineación
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("ALINEACIONES:\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append(b'\x1B\x61\x00')  # Izquierda
    commands.append("Texto a la izquierda\n".encode('utf-8'))
    commands.append(b'\x1B\x61\x01')  # Centro
    commands.append("Texto centrado\n".encode('utf-8'))
    commands.append(b'\x1B\x61\x02')  # Derecha
    commands.append("Texto a la derecha\n".encode('utf-8'))
    commands.append(b'\x1B\x61\x00')  # Volver a izquierda
    commands.append("\n".encode('utf-8'))
    
    # Separador
    commands.append(("-" * 32 + "\n").encode('utf-8'))
    
    # Caracteres especiales y líneas
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("CARACTERES ESPECIALES:\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append(("▬" * 32 + "\n").encode('utf-8'))
    commands.append(("═" * 32 + "\n").encode('utf-8'))
    commands.append(("━" * 32 + "\n").encode('utf-8'))
    commands.append("★ ☆ ♥ ♦ ♣ ♠ • ◦ ▪ ▫\n".encode('utf-8'))
    commands.append("€ $ £ ¥ © ® ™ § ¶ †\n".encode('utf-8'))
    commands.append("\n".encode('utf-8'))
    
    # Separador
    commands.append(("-" * 32 + "\n").encode('utf-8'))
    
    # Código de barras
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("CODIGO DE BARRAS:\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append(b'\x1D\x48\x02')  # Mostrar números debajo
    commands.append(b'\x1D\x77\x02')  # Ancho de línea
    commands.append(b'\x1D\x68\x50')  # Altura del código
    commands.append(b'\x1D\x6B\x49\x0C')  # CODE128
    commands.append("123456789012".encode('utf-8'))
    commands.append("\n\n".encode('utf-8'))
    
    # Separador
    commands.append(("=" * 32 + "\n").encode('utf-8'))
    
    # Información del dispositivo
    commands.append(b'\x1B\x61\x01')  # Centrar
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("PRUEBA USB LP\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append("Impresora térmica ESC/POS\n".encode('utf-8'))
    commands.append("Device: /dev/usb/lp0\n".encode('utf-8'))
    commands.append(b'\x1B\x61\x00')  # Alinear izquierda
    commands.append("\n".encode('utf-8'))
    
    # Semi-corte
    commands.append("Realizando SEMI-CORTE...\n".encode('utf-8'))
    commands.append(b'\x1D\x56\x41')  # Semi-corte
    commands.append("\n".encode('utf-8'))
    
    # Corte completo
    commands.append(b'\x1B\x61\x01')  # Centrar
    commands.append(b'\x1B\x45\x01')  # Negrita ON
    commands.append("FIN DE PRUEBA\n".encode('utf-8'))
    commands.append(b'\x1B\x45\x00')  # Negrita OFF
    commands.append("Realizando CORTE COMPLETO...\n".encode('utf-8'))
    commands.append(b'\x1B\x61\x00')  # Alinear izquierda
    commands.append("\n\n".encode('utf-8'))
    commands.append(b'\x1D\x56\x42')  # Corte completo
    
    return b''.join(commands)

# Función para enviar datos a la impresora USB LP
def send_to_usb_lp(device='/dev/usb/lp0', custom_payload=None):
    if custom_payload is None:
        payload = generate_comprehensive_test()
    else:
        payload = custom_payload
    
    print(f"Enviando {len(payload)} bytes al dispositivo {device}...")
    with open(device, 'wb') as f:
        f.write(payload)
        f.flush()

# Punto de entrada principal del script
if __name__ == '__main__':
    dev = '/dev/usb/lp0'
    if len(sys.argv) > 1:
        dev = sys.argv[1]
    
    print(f"Enviando prueba COMPLETA a {dev}...")
    print("Esta prueba incluye:")
    print("- Diferentes tamaños de texto")
    print("- Estilos: negrita, cursiva, subrayado, invertido")
    print("- Alineaciones: izquierda, centro, derecha")
    print("- Caracteres especiales")
    print("- Código de barras")
    print("- Semi-corte y corte completo")
    print("-" * 50)
    
    try:
        send_to_usb_lp(dev)
        print("✓ Enviado exitosamente.")
        print("Revisa la impresora para ver el resultado completo.")
    except PermissionError:
        print("✗ Fallo por permisos: ejecuta con sudo o ajusta permisos/udev para el dispositivo.")
        print("  Solución: sudo python3 print_usb_lp.py")
        print("  O: sudo usermod -a -G lp $USER")
    except FileNotFoundError:
        print(f"✗ Dispositivo no encontrado: {dev}")
        print("  Revisa con: dmesg | grep -i printer")
        print("  Y: ls /dev/usb*")
    except Exception as e:
        print(f"✗ Error al escribir en el dispositivo: {e}")
