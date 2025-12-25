#!/bin/bash
# Script para crear un release de GitHub con los paquetes generados

set -e

# Colores
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Leer versión desde pyproject.toml
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION=$(grep '^version = ' "$PROJECT_DIR/pyproject.toml" | sed 's/version = "\(.*\)"/\1/')

if [ -z "$VERSION" ]; then
    echo -e "${RED}Error: No se pudo leer la versión desde pyproject.toml${NC}"
    exit 1
fi

TAG="v$VERSION"
RELEASE_NAME="ONE-POS Utilidades $TAG"
OUTPUT_DIR="$PROJECT_DIR/build/output"

echo "=========================================="
echo "Preparando release $TAG"
echo "=========================================="
echo ""

# Verificar que existen los paquetes
LINUX_PACKAGE="$OUTPUT_DIR/escpos-server-linux-x64-v$VERSION.tar.gz"
WINDOWS_PACKAGE="$OUTPUT_DIR/escpos-server-windows-x64-v$VERSION.zip"

if [ ! -f "$LINUX_PACKAGE" ]; then
    echo -e "${RED}Error: No existe el paquete Linux: $LINUX_PACKAGE${NC}"
    echo "Ejecuta primero: ./build_linux.sh"
    exit 1
fi

echo -e "${GREEN}✓ Paquete Linux encontrado:${NC} $(basename "$LINUX_PACKAGE")"

if [ ! -f "$WINDOWS_PACKAGE" ]; then
    echo -e "${YELLOW}⚠ Paquete Windows no encontrado:${NC} $(basename "$WINDOWS_PACKAGE")"
    echo "  El paquete debe generarse en Windows ejecutando build_windows.bat"
else
    echo -e "${GREEN}✓ Paquete Windows encontrado:${NC} $(basename "$WINDOWS_PACKAGE")"
fi

echo ""
echo "=========================================="
echo "Instrucciones para crear el release"
echo "=========================================="
echo ""
echo "1. Crear el tag localmente:"
echo "   ${GREEN}git tag -a $TAG -m 'Release $TAG'${NC}"
echo ""
echo "2. Subir el tag a GitHub:"
echo "   ${GREEN}git push origin $TAG${NC}"
echo ""
echo "3. Ir a GitHub:"
echo "   ${YELLOW}https://github.com/I-Labs-Chile/ONE-POS-Utilidades/releases/new${NC}"
echo ""
echo "4. Configurar el release:"
echo "   - Seleccionar tag: ${GREEN}$TAG${NC}"
echo "   - Título: ${GREEN}$RELEASE_NAME${NC}"
echo "   - Descripción: (ver abajo)"
echo ""
echo "5. Arrastrar los archivos:"
echo "   - ${GREEN}$(basename "$LINUX_PACKAGE")${NC}"
if [ -f "$WINDOWS_PACKAGE" ]; then
    echo "   - ${GREEN}$(basename "$WINDOWS_PACKAGE")${NC}"
fi
echo ""
echo "6. Publicar el release"
echo ""
echo "=========================================="
echo "Descripción sugerida para el release"
echo "=========================================="
echo ""
cat << 'EOF'
## 🖨️ ONE-POS Utilidades - Servidor de Impresión ESC/POS

Servidor HTTP ligero para gestión de impresoras térmicas ESC/POS en entornos retail.

### ✨ Características principales

- 📡 **Servidor HTTP/REST** - Puerto 8080 por defecto
- 🖼️ **Procesamiento de imágenes** - Normalización automática para mejorar calidad
- 🔌 **Auto-detección USB** - Conexión automática a impresoras USB
- 🌐 **Soporte TCP/IP** - Conexión a impresoras de red
- 📋 **Cola de trabajos** - Sistema de cola persistente
- 🎨 **Interfaz web** - Upload por drag & drop, clipboard paste
- 🔄 **3 algoritmos de normalización**:
  - Normalización de brillo
  - Auto-levels (expansión de histograma)
  - Floyd-Steinberg dithering

### 📦 Instalación

#### Linux (Ubuntu/Debian)

```bash
# Descomprimir
tar -xzf escpos-server-linux-x64-v1.0.0.tar.gz
cd escpos-server-linux-x64-v1.0.0

# Instalar dependencias del sistema
sudo apt-get update
sudo apt-get install -y poppler-utils libusb-1.0-0

# Dar permisos USB (impresoras USB)
sudo usermod -a -G lp $USER
# Cerrar sesión y volver a entrar

# Configurar (opcional)
cp .env.example .env
nano .env

# Ejecutar
./escpos-server
```

#### Windows

```cmd
# Descomprimir escpos-server-windows-x64-v1.0.0.zip

# Configurar (opcional)
copy .env.example .env
notepad .env

# Ejecutar
escpos-server.exe
```

### 🌐 Uso

Una vez iniciado, abre tu navegador en: **http://localhost:8080**

#### Endpoints disponibles

- `GET /` - Interfaz web
- `GET /salud` - Healthcheck (estado de impresora)
- `POST /imprimir` - Enviar imagen para imprimir
- `POST /imprimir/url` - Imprimir desde URL
- `POST /imprimir/pdf` - Imprimir PDF (requiere poppler)

### 📋 Requisitos del sistema

**Linux:**
- Ubuntu 20.04+ / Debian 11+
- `libusb-1.0-0` (para impresoras USB)
- `poppler-utils` (para PDFs)

**Windows:**
- Windows 10+ (64-bit)
- Drivers USB instalados (para impresoras USB)

### 🔧 Configuración

Variables de entorno (archivo `.env`):

```env
# Modo de conexión: usb, tcp, auto
PRINTER_TYPE=auto

# IP de impresora TCP (si PRINTER_TYPE=tcp)
PRINTER_IP=192.168.1.100

# Puerto HTTP del servidor
PORT=8080

# Host del servidor
HOST=0.0.0.0
```

### 📝 Notas

- **Tamaño ejecutable**: ~33 MB (Linux) / ~35 MB (Windows)
- **Dependencias**: Incluye Python, FastAPI, Pillow, NumPy embebidos
- **Primera ejecución Windows**: Puede mostrar alerta de seguridad (falso positivo)

### 🐛 Problemas conocidos

- **Linux**: Si no detecta impresora USB, verificar permisos con `groups` (debe incluir `lp`)
- **Windows Defender**: Puede marcar el ejecutable como sospechoso en primera ejecución

### 📖 Documentación completa

Ver [README.md](https://github.com/I-Labs-Chile/ONE-POS-Utilidades/blob/main/README.md) en el repositorio.

---

**Checksums:**

```
# Linux
sha256sum escpos-server-linux-x64-v1.0.0.tar.gz

# Windows
CertUtil -hashfile escpos-server-windows-x64-v1.0.0.zip SHA256
```
EOF
echo ""
echo "=========================================="
echo "Archivos listos para subir"
echo "=========================================="
echo ""
ls -lh "$OUTPUT_DIR"/*.tar.gz 2>/dev/null || true
ls -lh "$OUTPUT_DIR"/*.zip 2>/dev/null || true
echo ""
echo -e "${GREEN}✓ Script completado${NC}"
