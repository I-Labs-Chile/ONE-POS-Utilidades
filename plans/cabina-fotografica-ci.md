# Plan: Cabina Fotográfica + CI de Releases (utilidades totalmente separadas)

## Contexto y decisiones cerradas con el usuario

Repo = utilidades para la impresora térmica que vende I-Labs. La utilidad de
impresión web y la nueva cabina fotográfica deben ser **productos totalmente
independientes**: procesos, puertos, datos, endpoints, binarios, configuración
y artefactos de release separados. Sin endpoints cruzados.

| Decisión | Elección |
|---|---|
| Código interno de impresión | Librería interna común `onepos_common/` (fixes una sola vez) |
| Estructura `app/` actual | Intacta (cabina entra como carpeta hermana) |
| Activación cabina | Binario aparte `escpos-cabina` |
| Poppler en Windows | Sí, se incluye en el release (fix pendiente PDFs) |
| Plataformas CI | Windows + Linux |
| UX | Countdown + 3 fotos → tira vertical impresa + logo i-labs + QR Instagram (`CABINA_QR_URL`, default `https://www.instagram.com/ilabs.cl/`) |
| Releases | Un release por tag `v*` con 4 artefactos (server/cabina × zip/tar.gz) |

## Estado actual del repo (delta ya aplicado antes del bloqueo)

Ejecutado con `git mv` (renombres puros, sin cambios de contenido, sin commit):

```
app/core/queue.py            -> onepos_common/queue.py            (R)
app/core/worker.py           -> onepos_common/worker.py           (RM*)
app/utils/escpos.py          -> onepos_common/escpos.py           (RM)
app/utils/image.py           -> onepos_common/image.py            (R)
app/utils/network.py         -> onepos_common/network.py          (R)
app/utils/usb_detector.py    -> onepos_common/usb_detector.py     (R)
app/utils/usb_printer.py     -> onepos_common/usb_printer.py      (R)
app/printer/manager.py       -> onepos_common/printer_manager.py  (RM)
app/printer/windows_spooler.py -> onepos_common/windows_spooler.py(RM)
```
(*) RM = renombrado+modificado: contiene los fixes de la sesión anterior aún sin commit.
Además siguen pendientes sin commit los cambios previos (README corto, docs/,
builds simplificados, fixes POS-58/pdftoppm/cola atómica, .env descomitado).

Si el usuario prefiere revertir antes de ejecutar: `git mv onepos_common/<f> app/...`
y recrear directorios. Si aprueba ejecutar, este estado ES el Paso 1a completado.

## Arquitectura final

```
ONE-POS-Utilidades/
├── app/                        # UTILIDAD 1: servidor impresión web (API+frontend+bienvenida)
├── cabina/                     # UTILIDAD 2: cabina fotográfica (autónoma)
│   ├── __init__.py
│   ├── api.py                  # FastAPI propia: GET / (kiosco), GET /salud, POST /captura
│   ├── compose.py              # tira: 3 fotos crop 4:3→384px apiladas + logo + QR
│   ├── .env.example            # SERVER_PORT=8081, QUEUE_DIR=./data-cabina, CABINA_QR_URL
│   └── frontend/
│       ├── index.html          # kiosco fullscreen oscuro
│       └── src/{cabina.js, cabina.css, empresa.png (copia propia)}
├── onepos_common/              # stack térmico compartido (sin deps de app/ ni cabina/)
│   ├── __init__.py             # NUEVO: docstring "no importar app/ ni cabina/"
│   ├── queue.py worker.py escpos.py image.py network.py
│   ├── usb_detector.py usb_printer.py printer_manager.py windows_spooler.py
│   └── status.py               # NUEVO: monitor de impresora extraído de api.py (hilo 3s)
├── run.py                      # servidor (intacto en comportamiento)
├── run_cabina.py               # entrypoint cabina: setdefault PORT=8081, QUEUE_DIR=./data-cabina
├── build/                      # 4 specs estáticos + scripts parametrizados
└── .github/workflows/release.yml
```

## Pasos de implementación

### Paso 1 — Extracción onepos_common (1a ya hecho físicamente)

**1b. Imports y desacoplo**
- `onepos_common/__init__.py`: docstring regla "no importar app/ ni cabina/".
- Internos common: `worker.py` → imports de `onepos_common.queue/.printer_manager/.image`;
  `escpos.py` → `onepos_common.usb_printer`; `usb_printer.py` → `onepos_common.usb_detector`;
  `printer_manager.py` → `onepos_common.{windows_spooler,escpos}`.
- **Desacoplo bienvenida**: hoy `worker._print_welcome()` importa
  `app.core.test_print` (dependencia inversa). Cambio a inyección:
  `PrintWorker(queue, selftest_fn=None)`; `_print_welcome` no-op si es None.
  `app/web/api.py` lo cablea: `worker.selftest_fn = lambda: run_printer_selftest(worker)`.
  Cabina v1 no configura selftest.
- **Monitor de impresora** (`check_printer_availability` ~55 líneas de api.py)
  → `onepos_common/status.py`: `start_printer_monitor() -> dict` (estado +
  lock accesible). Servidor y cabina consumen el mismo contrato `/salud`.
- `app/web/api.py`: imports → onepos_common (queue/worker/status/network);
  mantiene `app/core/test_print.py` y su frontend tal cual.
- Grep cero referencias vivas a `app.utils.*`, `app.printer.*`,
  `app.core.queue`, `app.core.worker`.

**1c. Verificación de no-regresión (hard gate antes de tocar cabina)**
- py_compile de todo; arranque real :18099 con QUEUE_DIR temporal;
  `/salud`, `/`, `/static/app.js`, `/cola` idénticos a comportamiento previo;
  POST `/imprimir` rechaza no-PDF.

### Paso 2 — Utilidad cabina

**2a. compose.py (+deps)**
- Dep nueva `qrcode==7.4.2` en requirements.txt y pyproject.toml (usa Pillow ya presente).
- `compose_strip(paths: list[str], target_width:int, logo_path:str, qr_url:str) -> Image`:
  - cada foto: center-crop 4:3 → resize a target_width (LANCZOS), alto 3/4 ancho
  - fondo blanco, margen 12px, gap 10px entre fotos
  - fila inferior: logo empresa.png (~55% del ancho, aspecto preservado) + QR
    qrcode (box ~35% del ancho) lado a lado centrados
  - devuelve imagen RGB **en color**: el dithering mono ocurre UNA vez después
    en el pipeline común (mejor calidad que componer ya dicotomizado)
- Test local: generar 3 JPEG con PIL, componer, verificar dimensiones/modo.

**2b. api.py + run_cabina.py**
- `POST /captura`: multipart `foto1,foto2,foto3` → validar extensión/tamaño,
  guardar temporales en data-cabina/jobs → compose_strip → guardar PNG compuesto
  → enqueue PrintJob(kind="image") → `{id, estado}`. Cero cambios en cola/worker comunes.
- `GET /salud`: mismo contrato que servidor (ok, impresora_disponible, nombre, error).
- `GET /`: index.html del kiosco (patrón render + soporte `_MEIPASS`).
- Montaje `/static` → cabina/frontend/src.
- startup: worker común + monitor común; shutdown limpio.
- `run_cabina.py`: load_dotenv → os.environ.setdefault(SERVER_PORT=8081,
  QUEUE_DIR=./data-cabina) ANTES de importar módulos → banner CABINA → uvicorn.

**2c. Frontend kiosco**
- Estados: PREVIEW → COUNTDOWN(3·2·1 overlay grande) → captura flash → ×3 →
  REVIEW (3 miniaturas + botones) → PRINTING → PREVIEW.
- Teclas: Espacio/F iniciar · Enter/A imprimir · Esc/R repetir · botones táctiles gigantes equivalentes.
- getUserMedia para preview y captura (frame a canvas → JPEG blob); cámara
  listada vía enumerateDevices tras permiso; bloqueo total si falta cámara o impresora.
- Barra estado: /salud cada 3s (dot impresora) + nombre cámara.
- Tras POST /captura: polling simple a /cola para confirmar impresión o error
  del job y mostrar resultado antes de resetear.

**2d. Verificación end-to-end local**
- Arrancar run_cabina.py en :18081 con QUEUE_DIR temp; GET / sirve kiosco;
  /static/cabina.js 200; POST /captura con 3 JPEG reales → PNG compuesto en
  jobs/, job en cola como image, worker marca error sin impresora (esperado aquí),
  inspección del PNG compuesto (dimensiones esperadas por fórmula).

### Paso 3 — Builds

- Specs nuevos: `build/escpos-cabina-{linux,windows}.spec` (entry ../run_cabina.py,
  datas ../cabina; hiddenimports cabina.* + onepos_common.* + uvicorn bits;
  windows: excluye usb backends, hidden win32print; NUNCA empaqueta app/).
- Specs servidor existentes: actualizar hiddenimports/excludes a onepos_common.
- Scripts parametrizados: `build_linux.sh [servidor|cabina|ambos]` /
  `build_windows.bat [servidor|cabina|ambos]` (default ambos); nombres
  `escpos-server-*` y `escpos-cabina-*`; LEEME y .env.example propios por utilidad.
- `POPPLER_DIR` opcional: si definido, copiar binarios poppler junto al exe
  (Windows) antes de comprimir → PDFs funcionan out-of-the-box.
- `pause` del bat solo si `not defined CI`.
- bash -n + prueba de ambos targets en Linux local.

### Paso 4 — GitHub Actions (.github/workflows/release.yml)

- Trigger: push tags `v*`; permissions contents:write.
- Guard: tag == version de pyproject.toml, sino fallar.
- Job windows-latest: Python 3.12 → venv .venv → pip -r requirements.txt +
  pyinstaller → descargar Poppler pinneado (oschwartz10612/poppler-windows
  v24.08.0-0) → expandir → POPPLER_DIR seteado → `build\build_windows.bat ambos`
  → upload artifacts (2 zips).
- Job ubuntu-latest: venv + pip → `./build/build_linux.sh ambos` → artifacts (2 tar.gz).
- Job release (needs ambos): checkout tag fetch-depth 0 → gh release create
  $TAG --generate-notes con los 4 archivos.
- Validación local: parseo YAML; primera validación real ocurre al pushear tag.

### Paso 5 — Documentación

- Nueva `docs/CABINA.md`: uso, teclas, config, autostart kiosco (NSSM/systemd),
  nota de convivencia (puertos/directorios distintos; en Linux no imprimir en
  paralelo desde ambas utilidades al mismo dispositivo lp*).
- README.md: sección "Utilidades" con ambos productos + links.
- docs/BUILD.md: targets duales, Poppler, flujo CI.
- docs/ARQUITECTURA.md: diagrama monorepo, regla de dependencias de onepos_common.
- docs/INSTALACION.md: link a CABINA.md.

## Riesgos / notas

- Los renombres git mv preservan historia; churn de imports mecánico y verificable con grep.
- empresa.png se duplica a propósito (productos independientes).
- Workflow CI no es plenamente validable localmente; specs y builds sí.
- Todo queda SIN commit salvo instrucción explícita del usuario.
