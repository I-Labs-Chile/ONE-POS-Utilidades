# ADR-0001 — Impresión en Windows vía spooler RAW (win32print)

- **Fecha**: 2026-10-15
- **Estado**: aceptado

## Contexto

En Linux la impresora térmica se maneja en caliente por USB (`pyusb`/`libusb` o escribiendo a `/dev/usb/lp*`). En Windows no hay acceso a esos nodos y, tras instalar el driver POS de fábrica, la impresora solo existe como **cola de impresión del spooler** (p. ej. `POS-58`, o `POS-58 (Copia 1)` si el driver se reinstala).

## Decisión

En Windows la impresión ESC/POS se envía como trabajo **RAW** al spooler mediante `pywin32`:

- `win32print.OpenPrinter` → `StartDocPrinter(..., "RAW")` → `WritePrinter` → `EndPagePrinter`/`EndDocPrinter`/`ClosePrinter`.
- La selección de impresora (`resolve_printer_name`) prioriza `PRINTER_NAME`/`WINDOWS_PRINTER_NAME`, luego patrones (`POS-58`, `POS-80`, `thermal`, `receipt`) y por último la primera impresora instalada.
- El backend se elige en `onepos_common/printer_manager.create_sender()` según `platform.system()` (override de desarrollo con `PRINTER_BACKEND`).

## Consecuencias

- **Dependencia obligatoria**: `pywin32` en Windows. Debe estar en `requirements.txt` (`pywin32; sys_platform == "win32"`) **y** en `pyproject.toml`. Si falta, el ejecutable compila pero falla en runtime con `No module named 'win32print'` (los `hiddenimports` del spec no pueden empaquetar un paquete ausente).
- El corte de papel (`GS V`) puede ser ignorado por algunos drivers; se trata como best-effort.
- Para imprimir PDF se requiere igualmente Poppler (`pdftoppm.exe`) en Windows; es ortogonal a este ADR (ver `docs/BUILD.md`).

## Notas de mantenimiento

- No reintroducir `win32print` como import a nivel de módulo en código que corre en Linux: `windows_spooler.py` lo importa arriba y solo se importa cuando la plataforma es Windows.
- El smoke test del cambio de dependencia puede hacerse en Linux con un `win32print` simulado (ver `docs/sessions/`).
