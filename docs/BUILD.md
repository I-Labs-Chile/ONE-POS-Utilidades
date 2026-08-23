# Guía de build y release

Genera los binarios distribuidos con PyInstaller a partir de specs versionados. Hay **dos utilidades independientes** (servidor y cabina) × **dos plataformas** = 4 paquetes.

## Requisitos

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# PyInstaller se instala automáticamente si falta
```

La versión del paquete se lee de `pyproject.toml` (fuente única). Para publicar una nueva versión: actualizar `version` ahí, commitear y crear el tag.

## Builds locales

Ambos scripts aceptan un target: `servidor`, `cabina` o `ambos` (default).

### Linux

```bash
./build/build_linux.sh          # ambos
./build/build_linux.sh cabina   # solo la cabina
```

Produce `build/output/escpos-{server|cabina}-linux-x64-vX.Y.Z.tar.gz` con:

- `escpos-server` / `escpos-cabina` (binarios onefile)
- `launch-*.sh` + `*.desktop` (lanzadores con logs visibles)
- `.env.example`, `LEEME.txt`, `LICENSE`

**Requisitos en el equipo destino (no van dentro del binario):** servidor → `poppler-utils` + `libusb-1.0-0`; cabina → solo `libusb-1.0-0`.

### Windows

```bat
build\build_windows.bat            :: ambos
build\build_windows.bat servidor   :: solo el servidor
```

Para incluir Poppler en el release del servidor (necesario para imprimir PDF):

```bat
set POPPLER_DIR=C:\ruta\a\poppler\Library\bin
build\build_windows.bat
```

Copia `pdftoppm.exe` + DLLs junto al ejecutable y lo anota en el LEEME.

## CI (GitHub Actions)

El workflow [`.github/workflows/release.yml`](../.github/workflows/release.yml) se dispara al crear un tag `v*`:

1. Verifica que el tag coincida con la versión de `pyproject.toml`
2. Compila en `ubuntu-22.04` y `windows-latest` (Windows incluye Poppler 24.08 automáticamente vía `POPPLER_DIR`)
3. Crea un GitHub Release con los 4 paquetes y notas automáticas

```bash
# Publicar: bump de versión, commit, tag y push
sed -i 's/^version = ".*"/version = "1.1.0"/' pyproject.toml
git commit -am "release v1.1.0" && git tag v1.1.0 && git push origin main v1.1.0
```

## Detalles técnicos

- Specs estáticos en `build/`:
  - Servidor: `escpos-linux.spec`, `escpos-windows.spec`
  - Cabina: `escpos-cabina-linux.spec`, `escpos-cabina-windows.spec`
- El código térmico compartido vive en `onepos_common/`; cada spec empaqueta su app (`app/` para el servidor, `cabina/` para la cabina) más esa librería — nunca ambas apps juntas
- El spec de Windows del servidor **excluye** PyUSB/libusb y `onepos_common.usb_*`: la impresión va por el spooler RAW (`win32print`). El spec de Linux incluye los backends USB; el de cabina excluye `app` completo
- Los frontends viajan como data files (`app/web/frontend`, `cabina/frontend`) y se localizan vía `sys._MEIPASS` cuando corren empaquetados
- Salidas intermedias (`build/dist`, `build/build_temp*`) están ignoradas por git

## Checklist de release

1. Actualizar `version` en `pyproject.toml` y commitear
2. (Opcional) build local: `./build/build_linux.sh ambos` → probar tarballs
3. `git tag vX.Y.Z && git push origin vX.Y.Z`
4. El workflow genera el Release con los 4 artefactos
5. Probar los zips/tarballs en equipos limpios
