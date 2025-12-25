#!/bin/bash
# Script para crear un release en GitHub
# Requiere: gh (GitHub CLI) instalado y autenticado

set -e

VERSION="v1.0.0"
TAG="$VERSION"
RELEASE_NAME="ONE-POS Utilidades $VERSION"
REPO="I-Labs-Chile/ONE-POS-Utilidades"

echo "========================================="
echo "  Creando Release $VERSION"
echo "========================================="
echo ""

# Verificar que gh esté instalado
if ! command -v gh &> /dev/null; then
    echo "❌ Error: GitHub CLI (gh) no está instalado"
    echo ""
    echo "Instalar con:"
    echo "  Ubuntu/Debian: sudo apt install gh"
    echo "  O descargar desde: https://cli.github.com/"
    exit 1
fi

# Verificar que esté autenticado
if ! gh auth status &> /dev/null; then
    echo "❌ Error: No estás autenticado en GitHub CLI"
    echo ""
    echo "Ejecutar: gh auth login"
    exit 1
fi

# Verificar que existan los archivos
LINUX_FILE="build/output/escpos-server-linux-x64-${VERSION}.tar.gz"
WINDOWS_FILE="build/output/escpos-server-windows-x64-${VERSION}.zip"

if [ ! -f "$LINUX_FILE" ]; then
    echo "❌ Error: No se encuentra $LINUX_FILE"
    echo "Ejecutar primero: ./build/build-linux.sh"
    exit 1
fi

if [ ! -f "$WINDOWS_FILE" ]; then
    echo "⚠️  Advertencia: No se encuentra $WINDOWS_FILE"
    echo "El build de Windows se debe hacer desde Windows"
    echo ""
    read -p "¿Continuar solo con Linux? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    WINDOWS_FILE=""
fi

# Crear release notes
RELEASE_NOTES="## 🎉 ONE-POS Utilidades $VERSION

Servidor de impresión ESC/POS ligero y robusto para retail.

### ✨ Características Principales

- 🖨️ Impresión de PDFs e imágenes en impresoras térmicas ESC/POS
- 🌐 Interfaz web moderna con drag & drop
- 📊 Normalización automática de imágenes para mejor calidad
- 🔄 Cola de trabajos con persistencia
- 📱 Código QR automático al iniciar
- 🚀 Sin drivers del sistema (comunicación directa USB/TCP)

### 📦 Descarga

**Linux (Ubuntu/Debian/Raspberry Pi):**
- Descargar \`escpos-server-linux-x64-${VERSION}.tar.gz\`
- Requiere: \`poppler-utils\` y \`libusb-1.0-0\`
- Ejecutar con: \`sudo ./escpos-server\`

**Windows:**
- Descargar \`escpos-server-windows-x64-${VERSION}.zip\`
- Requiere: Poppler para Windows
- Ejecutar como Administrador

### 📖 Documentación

Ver el [README](https://github.com/$REPO#readme) para instrucciones detalladas.

### 🐛 Reportar Problemas

[Issues](https://github.com/$REPO/issues)
"

echo "📝 Release Notes:"
echo "$RELEASE_NOTES"
echo ""

# Confirmar
read -p "¿Crear release en GitHub? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelado"
    exit 1
fi

# Crear el release
echo ""
echo "🚀 Creando release en GitHub..."

if [ -z "$WINDOWS_FILE" ]; then
    # Solo Linux
    gh release create "$TAG" \
        "$LINUX_FILE" \
        --repo "$REPO" \
        --title "$RELEASE_NAME" \
        --notes "$RELEASE_NOTES"
else
    # Linux y Windows
    gh release create "$TAG" \
        "$LINUX_FILE" \
        "$WINDOWS_FILE" \
        --repo "$REPO" \
        --title "$RELEASE_NAME" \
        --notes "$RELEASE_NOTES"
fi

echo ""
echo "✅ Release creado exitosamente!"
echo ""
echo "Ver en: https://github.com/$REPO/releases/tag/$TAG"
