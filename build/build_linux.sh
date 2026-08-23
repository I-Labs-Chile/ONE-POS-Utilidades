#!/bin/bash
# Build de releases para Linux (x86_64).
# Uso: build/build_linux.sh [servidor|cabina|ambos]   (default: ambos)
# Requisitos del sistema destino: poppler-utils y libusb-1.0-0 para el
# servidor; solo libusb-1.0-0 para la cabina (no se incluyen en el paquete).
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$PROJECT_DIR/build"
DIST_DIR="$BUILD_DIR/dist"
OUTPUT_DIR="$BUILD_DIR/output"
PY="$PROJECT_DIR/.venv/bin/python"
PYINSTALLER="$PROJECT_DIR/.venv/bin/pyinstaller"

TARGET="${1:-ambos}"
case "$TARGET" in
    servidor|cabina|ambos) ;;
    *) echo "Error: target inválido '$TARGET' (usa: servidor, cabina o ambos)"; exit 1 ;;
esac

[ -f "$PROJECT_DIR/run.py" ] || { echo "Error: no se encuentra run.py"; exit 1; }
if [ "$TARGET" != "servidor" ] && [ ! -f "$PROJECT_DIR/run_cabina.py" ]; then
    echo "Error: no se encuentra run_cabina.py"; exit 1
fi
[ -x "$PY" ] || { echo "Error: no existe .venv (crea el entorno e instala requirements.txt)"; exit 1; }

# Versión única fuente de verdad: pyproject.toml
VERSION="$(sed -n 's/^version = "\(.*\)"/\1/p' "$PROJECT_DIR/pyproject.toml")"
VERSION="${VERSION:-0.0.0}"

echo "==> ONE-POS Utilidades ${VERSION} (Linux) — target: $TARGET"
command -v pdftoppm >/dev/null || echo "Advertencia: pdftoppm no está instalado; el servidor lo requiere en el equipo destino."

if ! "$PY" -c "import PyInstaller" 2>/dev/null; then
    echo "==> Instalando PyInstaller..."
    "$PROJECT_DIR/.venv/bin/pip" install pyinstaller
fi

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

build_target() {
    local tgt="$1"
    local spec exe app_name
    case "$tgt" in
        servidor)
            spec="escpos-linux.spec"; exe="escpos-server"
            app_name="escpos-server-linux-x64-v${VERSION}" ;;
        cabina)
            spec="escpos-cabina-linux.spec"; exe="escpos-cabina"
            app_name="escpos-cabina-linux-x64-v${VERSION}" ;;
    esac

    echo "==> Compilando $tgt ($spec)..."
    rm -rf "$BUILD_DIR/build_temp_${exe}"
    (cd "$BUILD_DIR" && "$PYINSTALLER" --clean --noconfirm --workpath "build_temp_${exe}" "$spec")

    [ -f "$DIST_DIR/$exe" ] || { echo "Error: no se generó el ejecutable $exe"; exit 1; }

    local release_dir="$OUTPUT_DIR/$app_name"
    mkdir -p "$release_dir/data"
    cp "$DIST_DIR/$exe" "$release_dir/"
    chmod +x "$release_dir/$exe"

    if [ "$tgt" = "servidor" ]; then
        cp "$BUILD_DIR/launch-server.sh" "$release_dir/"
        cp "$BUILD_DIR/escpos-server.desktop" "$release_dir/"
        cp "$PROJECT_DIR/.env.example" "$release_dir/"
        cat > "$release_dir/LEEME.txt" << 'EOF'
SERVIDOR DE IMPRESION ESC/POS - INICIO RAPIDO
=============================================
1) Dependencias unica vez:
   sudo apt-get install -y poppler-utils libusb-1.0-0
   sudo usermod -a -G lp $USER   # cerrar sesion y volver a entrar
2) Doble click en escpos-server.desktop (o ejecutar ./launch-server.sh)
3) Abrir http://localhost:8080 y arrastrar PDF o imagenes

Configuracion opcional: cp .env.example .env
Guia completa: https://github.com/I-Labs-Chile/ONE-POS-Utilidades/tree/main/docs
EOF
    else
        cp "$BUILD_DIR/launch-cabina.sh" "$release_dir/"
        cp "$BUILD_DIR/escpos-cabina.desktop" "$release_dir/"
        cp "$PROJECT_DIR/cabina/.env.example" "$release_dir/"
        cat > "$release_dir/LEEME.txt" << 'EOF'
CABINA FOTOGRAFICA ONE-POS - INICIO RAPIDO
==========================================
1) Dependencia unica vez:
   sudo apt-get install -y libusb-1.0-0
   sudo usermod -a -G lp $USER   # cerrar sesion y volver a entrar
2) Doble click en escpos-cabina.desktop (o ejecutar ./launch-cabina.sh)
3) Abrir http://localhost:8081, permite la camara y presiona FOTO.
   Teclado: Espacio/F foto | Enter/A imprimir | Esc/R repetir

Configuracion opcional: cp .env.example .env
Guia completa: https://github.com/I-Labs-Chile/ONE-POS-Utilidades/tree/main/docs
EOF
    fi
    chmod +x "$release_dir/launch-"*.sh 2>/dev/null || true
    cp "$PROJECT_DIR/LICENSE" "$release_dir/"

    (cd "$OUTPUT_DIR" && tar -czf "${app_name}.tar.gz" "$app_name")
}

case "$TARGET" in
    servidor) build_target servidor ;;
    cabina)   build_target cabina ;;
    ambos)    build_target servidor; build_target cabina ;;
esac

echo "==> Listo:"
ls -lh "$OUTPUT_DIR"/*.tar.gz | awk '{print "    paquete: " $5, $9}'
