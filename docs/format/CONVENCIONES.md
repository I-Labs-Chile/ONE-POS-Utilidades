# Convenciones de formato y estilo

Fuente de verdad de facto: configs del repo + estilo observado en el código.

## Python

- Python 3.9+ (CI 3.12). Sin linter/formatter configurado en el repo; mantener el estilo existente.
- Comentarios y mensajes en **español neutro**.
- Logs de diagnóstico: `print()` con prefijo `#` (orientado a soporte de campo). No introducir `logging` nuevo en el núcleo sin motivo.
- Imports diferidos cuando el módulo es específico de una plataforma (ej. `win32print` solo dentro del backend Windows), para no romper Linux.

## Encodings de impresión

- Texto ESC/POS por defecto en `cp437` (con `errors="replace"`).
- Raster de imágenes: `GS v 0` con 1 bit por píxel.

## Commits

- Conventional Commits, en inglés, imperativo: `fix(windows): ...`, `feat(cabina): ...`, `docs: ...`.
- Sin punto final en la descripción.

## Branches

- Rama de integración: `main`. No hay `develop`.
- `pull` antes de trabajar y antes de `push`.

## Dependencias

- Toda dependencia Python nueva va en `requirements.txt` **y** en `pyproject.toml`.
- Usar markers de plataforma cuando aplique (ej. `pywin32; sys_platform == "win32"`).
