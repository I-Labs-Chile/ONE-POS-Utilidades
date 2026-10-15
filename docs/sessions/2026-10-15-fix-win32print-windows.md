# Sesión 2026-10-15 — Fix `No module named 'win32print'` en Windows

## Objetivo

Dejar el driver/utilidades listo para producción en Linux y Windows. Reporte de campo: en un PC Windows, al imprimir, error `No module named 'win32print'`.

## Causa raíz

El soporte Windows ya existía (`onepos_common/windows_spooler.py`, commit `a439542`), pero:

1. El clon local estaba **2 commits atrás**; se sincronizó con `origin/main` (hasta `83b0424`, incluye `onepos_common/`, `cabina/`, CI con Poppler).
2. `requirements.txt` **no incluía `pywin32`** (solo estaba en `pyproject.toml`). El CI y los builds locales instalan con `pip install -r requirements.txt`, por lo que `win32print` nunca se instalaba ni se podía empaquetar (el spec lo pide en `hiddenimports`, pero PyInstaller no puede incluir un paquete ausente).

## Cambios

- `requirements.txt`: se agregó `pywin32; sys_platform == "win32"`.
- `build/build_windows.bat`: guarda que verifica `import win32print` e instala `pywin32` si falta, antes de compilar (evita generar un `.exe` roto en silencio).
- `docs/INSTALACION.md`: fila de troubleshooting para `No module named 'win32print'`.
- Se creó `AGENTS.md` y `docs/{sessions,adr,format}/` (el repo no los tenía).

## Verificación

- `requirements.txt` parsea con `packaging`; el marker `sys_platform == "win32"` hace que en Linux **no** se instale `pywin32` (confirmado).
- Smoke test del servidor en Linux: `GET /` (200), `/salud`, `/estado`, `POST /test-impresora` responden correctamente (errores de impresora esperados, sin hardware).
- Lógica Windows validada en Linux con `win32print` simulado: `resolve_printer_name()` (patrón, exacto y sufijo "Copia 1"), `create_sender` con `PRINTER_BACKEND=windows` y emisión de bytes ESC/POS (`ESC @`, texto, corte).

## Pendientes / próximos pasos

- Probar en un PC Windows real: instalar driver POS, `pip install -r requirements.txt`, verificar `import win32print`, y validar release con `PRINTER_NAME` correcto.
- Evaluar bump `1.1.2` + tag `v1.1.2` para publicar el ejecutable corregido vía CI.
