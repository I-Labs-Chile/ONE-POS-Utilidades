#!/usr/bin/env python3
"""
ONE-POS Network Printer - Instalador Universal
Este script detecta el sistema operativo y ejecuta el instalador correcto
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

# Colores ANSI
class Colors:
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_banner():
    """Muestra banner de bienvenida"""
    print(f"""
{Colors.CYAN}╔════════════════════════════════════════════════════╗
║                                                    ║
║        ONE-POS Network Printer Installer          ║
║              Universal / Multi-Platform            ║
║                                                    ║
╚════════════════════════════════════════════════════╝{Colors.END}
""")

def detect_os():
    """Detecta el sistema operativo"""
    system = platform.system().lower()
    
    print(f"{Colors.BLUE}🔍 Detectando sistema operativo...{Colors.END}")
    print(f"   Sistema: {platform.system()}")
    print(f"   Versión: {platform.release()}")
    print(f"   Arquitectura: {platform.machine()}")
    print()
    
    if system == "linux":
        return "linux"
    elif system == "windows":
        return "windows"
    elif system == "darwin":
        return "macos"
    else:
        return "unknown"

def check_root_permissions():
    """Verifica si se tienen permisos de administrador"""
    if platform.system() == "Windows":
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    else:
        return os.geteuid() == 0

def get_installer_path(os_type):
    """Obtiene la ruta al instalador correcto"""
    script_dir = Path(__file__).parent
    
    installers = {
        "linux": script_dir / "install-linux.sh",
        "windows": script_dir / "install-windows.ps1",
        "windows_bat": script_dir / "install-windows.bat",
    }
    
    if os_type == "linux":
        return installers["linux"]
    elif os_type == "windows":
        # Preferir PowerShell, fallback a BAT
        if installers["windows"].exists():
            return installers["windows"]
        return installers["windows_bat"]
    
    return None

def run_linux_installer(installer_path, server_ip, server_port):
    """Ejecuta el instalador de Linux"""
    print(f"{Colors.GREEN}🐧 Ejecutando instalador de Linux...{Colors.END}")
    print()
    
    if not installer_path.exists():
        print(f"{Colors.RED}❌ No se encontró el instalador: {installer_path}{Colors.END}")
        return False
    
    # Dar permisos de ejecución
    os.chmod(installer_path, 0o755)
    
    # Construir comando
    cmd = ["sudo", str(installer_path)]
    if server_ip:
        cmd.append(server_ip)
    if server_port:
        cmd.append(str(server_port))
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}❌ Error al ejecutar instalador: {e}{Colors.END}")
        return False
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Instalación cancelada por el usuario{Colors.END}")
        return False

def run_windows_installer(installer_path, server_ip, server_port):
    """Ejecuta el instalador de Windows"""
    print(f"{Colors.GREEN}🪟 Ejecutando instalador de Windows...{Colors.END}")
    print()
    
    if not installer_path.exists():
        print(f"{Colors.RED}❌ No se encontró el instalador: {installer_path}{Colors.END}")
        return False
    
    # Verificar tipo de instalador
    if installer_path.suffix == ".ps1":
        # PowerShell
        cmd = [
            "powershell.exe",
            "-ExecutionPolicy", "Bypass",
            "-File", str(installer_path)
        ]
        
        if server_ip:
            cmd.extend(["-ServerIP", server_ip])
        if server_port:
            cmd.extend(["-ServerPort", str(server_port)])
    else:
        # BAT
        cmd = [str(installer_path)]
        if server_ip:
            cmd.append(server_ip)
        if server_port:
            cmd.append(str(server_port))
    
    try:
        result = subprocess.run(cmd, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"{Colors.RED}❌ Error al ejecutar instalador: {e}{Colors.END}")
        return False
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Instalación cancelada por el usuario{Colors.END}")
        return False

def show_macos_instructions(server_ip, server_port):
    """Muestra instrucciones para macOS"""
    print(f"{Colors.CYAN}🍎 Instrucciones para macOS:{Colors.END}")
    print()
    print("macOS soporta IPP nativamente. Para agregar la impresora:")
    print()
    print(f"{Colors.BOLD}1. Abrir Preferencias del Sistema → Impresoras y Escáneres{Colors.END}")
    print(f"{Colors.BOLD}2. Clic en el botón '+' para agregar impresora{Colors.END}")
    print(f"{Colors.BOLD}3. Seleccionar la pestaña 'IP'{Colors.END}")
    print(f"{Colors.BOLD}4. Ingresar:{Colors.END}")
    print(f"   Protocolo: {Colors.GREEN}IPP (Internet Printing Protocol){Colors.END}")
    print(f"   Dirección: {Colors.GREEN}{server_ip or 'localhost'}{Colors.END}")
    print(f"   Cola: {Colors.GREEN}ipp/printer{Colors.END}")
    print(f"   Nombre: {Colors.GREEN}ONE-POS-Printer{Colors.END}")
    print(f"{Colors.BOLD}5. Clic en 'Agregar'{Colors.END}")
    print()
    print(f"URL completa: {Colors.CYAN}ipp://{server_ip or 'localhost'}:{server_port or 631}/ipp/printer{Colors.END}")
    print()

def prompt_server_info():
    """Solicita información del servidor al usuario"""
    print(f"{Colors.BLUE}📡 Información del servidor IPP:{Colors.END}")
    print()
    
    # IP del servidor
    server_ip = input(f"  Dirección IP del servidor [{Colors.GREEN}localhost{Colors.END}]: ").strip()
    if not server_ip:
        server_ip = "localhost"
    
    # Puerto
    server_port_str = input(f"  Puerto [{Colors.GREEN}631{Colors.END}]: ").strip()
    if not server_port_str:
        server_port = 631
    else:
        try:
            server_port = int(server_port_str)
        except ValueError:
            print(f"{Colors.YELLOW}⚠️  Puerto inválido, usando 631{Colors.END}")
            server_port = 631
    
    print()
    print(f"{Colors.CYAN}URL de la impresora: ipp://{server_ip}:{server_port}/ipp/printer{Colors.END}")
    print()
    
    return server_ip, server_port

def main():
    """Función principal"""
    print_banner()
    
    # Detectar sistema operativo
    os_type = detect_os()
    
    if os_type == "unknown":
        print(f"{Colors.RED}❌ Sistema operativo no soportado: {platform.system()}{Colors.END}")
        print()
        print("Sistemas soportados:")
        print("  • Linux (Ubuntu, Debian, Fedora, Arch, etc.)")
        print("  • Windows (10, 11)")
        print("  • macOS (con instalación manual)")
        return 1
    
    # Solicitar información del servidor
    server_ip, server_port = prompt_server_info()
    
    # Verificar permisos
    if os_type in ["linux", "windows"]:
        if not check_root_permissions():
            print(f"{Colors.YELLOW}⚠️  Se requieren permisos de administrador{Colors.END}")
            print()
            if os_type == "linux":
                print("Ejecuta el script con sudo:")
                print(f"  {Colors.GREEN}sudo python3 {sys.argv[0]}{Colors.END}")
            else:
                print("Ejecuta como Administrador:")
                print("  • Haz clic derecho en el script")
                print("  • Selecciona 'Ejecutar como administrador'")
            print()
            return 1
    
    # Obtener instalador correcto
    installer_path = get_installer_path(os_type)
    
    if installer_path is None:
        print(f"{Colors.RED}❌ No hay instalador disponible para {os_type}{Colors.END}")
        return 1
    
    # Ejecutar instalador según el sistema operativo
    if os_type == "linux":
        success = run_linux_installer(installer_path, server_ip, server_port)
    elif os_type == "windows":
        success = run_windows_installer(installer_path, server_ip, server_port)
    elif os_type == "macos":
        show_macos_instructions(server_ip, server_port)
        return 0
    else:
        print(f"{Colors.RED}❌ Sistema operativo no soportado{Colors.END}")
        return 1
    
    # Resultado final
    if success:
        print()
        print(f"{Colors.GREEN}✅ Instalación completada exitosamente{Colors.END}")
        return 0
    else:
        print()
        print(f"{Colors.RED}❌ La instalación falló{Colors.END}")
        print()
        print(f"Consulta el archivo README.md para instrucciones de instalación manual.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n\n{Colors.YELLOW}⚠️  Instalación cancelada por el usuario{Colors.END}")
        sys.exit(130)
    except Exception as e:
        print(f"\n{Colors.RED}❌ Error inesperado: {e}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
