#!/bin/bash
# Script de empaquetado para Linux (Debian/Ubuntu)
# Genera un ejecutable standalone con PyInstaller

set -e

echo "=========================================="
echo "ONE-POS Utilidades - Build para Linux"
echo "=========================================="
echo ""

# Colores para output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Directorio base del proyecto
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$BUILD_DIR/dist"
OUTPUT_DIR="$BUILD_DIR/output"

echo -e "${YELLOW}Directorio del proyecto:${NC} $PROJECT_DIR"
echo ""

# Verificar que estamos en el directorio correcto
if [ ! -f "$PROJECT_DIR/run.py" ]; then
    echo -e "${RED}Error: No se encuentra run.py${NC}"
    echo "Ejecuta este script desde la carpeta build/"
    exit 1
fi

# Limpiar builds anteriores
echo -e "${YELLOW}Limpiando builds anteriores...${NC}"
rm -rf "$BUILD_DIR/dist"
rm -rf "$BUILD_DIR/build_temp"
rm -rf "$BUILD_DIR/*.spec"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Verificar/instalar PyInstaller
echo -e "${YELLOW}Verificando PyInstaller...${NC}"
if ! $PROJECT_DIR/.venv/bin/python -c "import PyInstaller" 2>/dev/null; then
    echo "Instalando PyInstaller..."
    $PROJECT_DIR/.venv/bin/pip install pyinstaller
fi

# Información de versión
VERSION=$(grep -oP 'version\s*=\s*"\K[^"]+' "$PROJECT_DIR/pyproject.toml" 2>/dev/null || echo "1.0.0")
APP_NAME="escpos-server-linux-x64-v${VERSION}"

echo -e "${GREEN}Versión:${NC} $VERSION"
echo -e "${GREEN}Nombre del ejecutable:${NC} $APP_NAME"
echo ""

# Crear spec file personalizado
echo -e "${YELLOW}Generando configuración de PyInstaller...${NC}"
cat > "$BUILD_DIR/escpos-linux.spec" << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['../run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('../app', 'app'),
    ],
    hiddenimports=[
        'app',
        'app.web',
        'app.web.api',
        'app.web.frontend',
        'app.core',
        'app.core.worker',
        'app.core.queue',
        'app.core.test_print',
        'app.utils',
        'app.utils.escpos',
        'app.utils.image',
        'app.utils.network',
        'app.utils.usb_printer',
        'app.utils.usb_detector',
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        'usb.backend',
        'usb.backend.libusb1',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='escpos-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
EOF

# Compilar con PyInstaller
echo -e "${YELLOW}Compilando aplicación...${NC}"
cd "$BUILD_DIR"
$PROJECT_DIR/.venv/bin/pyinstaller --clean escpos-linux.spec

# Verificar que se creó el ejecutable
if [ ! -f "$DIST_DIR/escpos-server" ]; then
    echo -e "${RED}Error: No se generó el ejecutable${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Ejecutable generado correctamente${NC}"
echo ""

# Crear estructura del release
echo -e "${YELLOW}Creando paquete de distribución...${NC}"
RELEASE_DIR="$OUTPUT_DIR/$APP_NAME"
mkdir -p "$RELEASE_DIR"

# Copiar ejecutable
cp "$DIST_DIR/escpos-server" "$RELEASE_DIR/"
chmod +x "$RELEASE_DIR/escpos-server"

# Copiar launcher de terminal
if [ -f "$BUILD_DIR/launch-server.sh" ]; then
    cp "$BUILD_DIR/launch-server.sh" "$RELEASE_DIR/"
    chmod +x "$RELEASE_DIR/launch-server.sh"
fi

# Crear archivo .desktop para lanzadores de aplicaciones
cat > "$RELEASE_DIR/escpos-server.desktop" << 'DESKTOPEOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Servidor de Impresión ESC/POS
Comment=Servidor de impresión para impresora térmica Q-Cube con logs visibles
Exec=bash -c "cd '%k' && ./launch-server.sh"
Icon=printer
Terminal=false
Categories=Utility;Office;
Keywords=printer;escpos;thermal;server;
DESKTOPEOF

chmod +x "$RELEASE_DIR/escpos-server.desktop"

# Crear directorio de datos
mkdir -p "$RELEASE_DIR/data"

# Crear archivo de configuración de ejemplo
cat > "$RELEASE_DIR/.env.example" << 'ENVEOF'
# Configuración de la impresora
PRINTER_IF=usb
# PRINTER_IF=tcp

# Para impresoras TCP
# PRINTER_HOST=192.168.1.100
# PRINTER_PORT=9100

# Para impresoras USB específicas (autodetección si se omite)
# USB_VENDOR=0x04b8
# USB_PRODUCT=0x0202

# Configuración del papel
PAPER_WIDTH_PX=384
# PAPER_WIDTH_PX=576  # Para papel de 80mm

# Puerto del servidor
SERVER_PORT=8080

# Directorio de datos
QUEUE_DIR=./data
ENVEOF

# Crear README de distribución
cat > "$RELEASE_DIR/README.txt" << 'README'
═══════════════════════════════════════════════════════════════
  SERVIDOR DE IMPRESIÓN ESC/POS PARA IMPRESORA TÉRMICA Q-CUBE
═══════════════════════════════════════════════════════════════

INICIO RÁPIDO
-------------

1. Conecta tu impresora térmica por USB

2. Ejecuta el servidor haciendo DOBLE CLICK en:
   
   📄 escpos-server.desktop
   
   Esto abrirá una terminal mostrando los logs del servidor.

3. Abre tu navegador en:
   
   🌐 http://localhost:8080

4. ¡Listo! Arrastra archivos PDF o imágenes para imprimir.

CERRAR EL SERVIDOR
------------------

Simplemente cierra la terminal que se abrió, o presiona Ctrl+C.

INSTALACIÓN (Primera vez)
-------------------------

1. Instalar dependencias del sistema:
   
   sudo apt-get update
   sudo apt-get install -y poppler-utils libusb-1.0-0

2. Dar permisos de acceso a la impresora USB:
   
   sudo usermod -a -G lp $USER
   
   Luego cierra sesión y vuelve a entrar.

CONFIGURACIÓN (Opcional)
------------------------

Si necesitas cambiar configuraciones (puerto, tipo de papel, etc.):

1. Copia el archivo de ejemplo:
   
   cp .env.example .env

2. Edita la configuración:
   
   nano .env

3. Reinicia el servidor

FORMAS DE EJECUTAR
------------------

Opción 1 - CON TERMINAL Y LOGS (RECOMENDADO):

   Doble click en: escpos-server.desktop
   O ejecuta: ./launch-server.sh

Opción 2 - DIRECTO (sin ver logs):

   ./escpos-server

Opción 3 - EN SEGUNDO PLANO:

   nohup ./escpos-server > server.log 2>&1 &
   
   Para detener:
   pkill escpos-server
   
   (Cierra sesión y vuelve a entrar)

3. Configurar la aplicación:
   
   cp .env.example .env
   nano .env
   
   (Edita según tu configuración)

EJECUCIÓN
---------

Opción 1 - Con terminal y logs visibles (RECOMENDADO):

    ./launch-server.sh

Esto abrirá una terminal donde podrás ver los logs en tiempo real.
Para detener el servidor, simplemente cierra la terminal o presiona Ctrl+C.

Opción 2 - Ejecutar directamente (sin logs visibles):

    ./escpos-server

Opción 3 - En segundo plano con logs en archivo:

    nohup ./escpos-server > server.log 2>&1 &

INSTALACIÓN EN EL SISTEMA (OPCIONAL)
------------------------------------

Para poder ejecutar el servidor haciendo doble click desde el explorador 
de archivos o agregarlo al menú de aplicaciones:

1. Simplemente haz doble click en el archivo:
   
   escpos-server.desktop
   
   Si te pregunta, selecciona "Confiar y ejecutar" o "Marcar como ejecutable".

2. Para agregar al menú de aplicaciones (opcional):

   cp escpos-server.desktop ~/.local/share/applications/
   
   O para todos los usuarios:
   
   sudo cp escpos-server.desktop /usr/share/applications/

Nota: El archivo .desktop ejecutará automáticamente launch-server.sh,
que abrirá una terminal con los logs visibles.

ACCESO DESDE OTROS DISPOSITIVOS
-------------------------------

Para imprimir desde otro computador o celular en la misma red:

1. Averigua la IP del servidor:
   
   ip addr show | grep inet

2. Desde otro dispositivo, abre el navegador en:
   
   http://IP-DEL-SERVIDOR:8080
   
   Ejemplo: http://192.168.1.100:8080

SOLUCIÓN DE PROBLEMAS
---------------------

❌ "No se encuentra la impresora"
   → Verifica que esté conectada: lsusb
   → Revisa los permisos: ls -l /dev/usb/lp*

❌ "Permission denied en /dev/usb/lp0"
   → Ejecuta: sudo usermod -a -G lp $USER
   → Cierra sesión y vuelve a entrar

❌ "Puerto 8080 en uso"
   → Cambia el puerto en el archivo .env
   → O mata el proceso: sudo lsof -ti:8080 | xargs kill

❌ Los logs no se muestran
   → El ejecutable siempre genera logs en la terminal
   → Si usas ./escpos-server directamente, verás los logs ahí mismo
   → Si usas launch-server.sh, se abre una terminal nueva con logs

VER LOGS EN TIEMPO REAL
-----------------------

Los logs se muestran automáticamente en la terminal cuando ejecutas
el servidor. Incluyen:

- ✓ Estado de conexión de la impresora
- ✓ Trabajos de impresión recibidos
- ✓ Errores y advertencias
- ✓ Información de red y configuración

SERVICIO SYSTEMD (OPCIONAL - Para servidores 24/7)
--------------------------------------------------

Si necesitas que el servidor se inicie automáticamente al arrancar
el sistema y se ejecute en segundo plano:

1. Crear archivo de servicio:

   sudo nano /etc/systemd/system/escpos-server.service

2. Contenido del archivo:

   [Unit]
   Description=ONE-POS ESC/POS Print Server
   After=network.target

   [Service]
   Type=simple
   User=TU_USUARIO
   WorkingDirectory=/ruta/completa/donde/está/el/ejecutable
   ExecStart=/ruta/completa/donde/está/el/ejecutable/escpos-server
   Restart=always
   RestartSec=10

   [Install]
   WantedBy=multi-user.target

3. Activar y arrancar:

   sudo systemctl daemon-reload
   sudo systemctl enable escpos-server
   sudo systemctl start escpos-server

4. Ver logs del servicio:

   sudo journalctl -u escpos-server -f

5. Controlar el servicio:

   sudo systemctl status escpos-server   # Ver estado
   sudo systemctl stop escpos-server     # Detener
   sudo systemctl restart escpos-server  # Reiniciar

SOPORTE
-------

GitHub: https://github.com/I-Labs-Chile/ONE-POS-Utilidades

═══════════════════════════════════════════════════════════════
README

# Copiar licencia
if [ -f "$PROJECT_DIR/LICENSE" ]; then
    cp "$PROJECT_DIR/LICENSE" "$RELEASE_DIR/"
fi

# Crear tarball
echo -e "${YELLOW}Comprimiendo paquete...${NC}"
cd "$OUTPUT_DIR"
tar -czf "${APP_NAME}.tar.gz" "$APP_NAME"

# Información final
echo ""
echo -e "${GREEN}=========================================="
echo "Build completado exitosamente"
echo "==========================================${NC}"
echo ""
echo -e "${GREEN}Ejecutable:${NC} $RELEASE_DIR/escpos-server"
echo -e "${GREEN}Paquete:${NC} $OUTPUT_DIR/${APP_NAME}.tar.gz"
echo ""
echo -e "${YELLOW}Tamaño del ejecutable:${NC}"
ls -lh "$RELEASE_DIR/escpos-server" | awk '{print $5}'
echo ""
echo -e "${YELLOW}Tamaño del paquete:${NC}"
ls -lh "$OUTPUT_DIR/${APP_NAME}.tar.gz" | awk '{print $5}'
echo ""
echo -e "${YELLOW}Para probar:${NC}"
echo "  cd $RELEASE_DIR"
echo "  ./escpos-server"
echo ""
