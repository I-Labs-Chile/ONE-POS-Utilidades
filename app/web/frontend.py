# -*- coding: utf-8 -*-
# Módulo de interfaz web
# Genera la página HTML para subir documentos PDF

from fastapi.responses import HTMLResponse


def render_upload_page() -> HTMLResponse:
    # Genera una página simple para subir un PDF y mostrar respuestas de la API
    html = """<!DOCTYPE html>
<html lang=\"es\">
<head>
    <meta charset=\"utf-8\" />
    <title>Servidor de impresión ESC/POS</title>
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <style>
        body { font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; margin: 0; padding: 0; background: #f4f4f5; }
        header { background: #0f172a; color: #e5e7eb; padding: 1rem 1.5rem; }
        header h1 { margin: 0; font-size: 1.2rem; }
        main { max-width: 960px; margin: 1.5rem auto; padding: 1rem 1.5rem; background: #ffffff; border-radius: 0.5rem; box-shadow: 0 1px 3px rgba(15,23,42,0.1); }
        h2 { margin-top: 0; font-size: 1.1rem; color: #111827; }
        p { margin: 0.25rem 0 0.5rem 0; color: #4b5563; font-size: 0.9rem; }
        label { display: block; margin-bottom: 0.5rem; font-weight: 500; color: #111827; }
        input[type=file] { display: block; margin-bottom: 0.75rem; font-size: 0.9rem; }
        button { background: #0f766e; color: #ecfeff; border: none; border-radius: 0.375rem; padding: 0.5rem 1rem; cursor: pointer; font-size: 0.9rem; font-weight: 500; }
        button:hover { background: #115e59; }
        button:disabled { background: #9ca3af; cursor: not-allowed; }
        .fila { margin-bottom: 1rem; }
        .resultado, .cola, .estado { margin-top: 1rem; padding: 0.75rem; border-radius: 0.375rem; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size: 0.8rem; white-space: pre-wrap; background: #f9fafb; border: 1px solid #e5e7eb; max-height: 260px; overflow: auto; }
        .acciones-secundarias { margin-top: 0.75rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
        .acciones-secundarias button { background: #374151; }
        .acciones-secundarias button:hover { background: #111827; }
        footer { max-width: 960px; margin: 0 auto 1.5rem auto; padding: 0 1.5rem; font-size: 0.75rem; color: #6b7280; }
        .badge { display: inline-block; padding: 0.15rem 0.4rem; border-radius: 9999px; background: #e0f2fe; color: #0369a1; font-size: 0.7rem; margin-left: 0.25rem; }
    </style>
</head>
<body>
<header>
    <h1>ONE-POS · Servidor de impresión ESC/POS<span class=\"badge\">web</span></h1>
</header>
<main>
    <section>
        <h2>Subir documento PDF</h2>
        <p>Selecciona un archivo PDF para enviarlo al servidor de impresión. El trabajo se encola y será procesado por el worker de forma secuencial.</p>
        <form id=\"form-subida\">
            <div class=\"fila\">
                <label for=\"archivo\">Archivo PDF</label>
                <input id=\"archivo\" name=\"archivo\" type=\"file\" accept=\"application/pdf\" required />
            </div>
            <button id=\"btn-enviar\" type=\"submit\">Enviar a impresión</button>
        </form>
        <div id=\"resultado\" class=\"resultado\"></div>
        <div class=\"acciones-secundarias\">
            <button type=\"button\" id=\"btn-cola\">Ver cola</button>
            <button type=\"button\" id=\"btn-estado\">Ver estado</button>
            <button type=\"button\" id=\"btn-salud\">Ver salud</button>
                <button type=\"button\" id=\"btn-test\">Probar impresora</button>
        </div>
        <div id=\"cola\" class=\"cola\"></div>
        <div id=\"estado\" class=\"estado\"></div>
    </section>
</main>
<footer>
    <span>Interfaz mínima para diagnóstico en campo. Endpoints usados: /imprimir, /cola, /estado, /salud.</span>
</footer>
<script>
(function() {
    const form = document.getElementById('form-subida');
    const inputArchivo = document.getElementById('archivo');
    const btnEnviar = document.getElementById('btn-enviar');
    const divResultado = document.getElementById('resultado');
    const divCola = document.getElementById('cola');
    const divEstado = document.getElementById('estado');
    const btnCola = document.getElementById('btn-cola');
    const btnEstado = document.getElementById('btn-estado');
    const btnSalud = document.getElementById('btn-salud');
    const btnTest = document.getElementById('btn-test');

    function mostrarJSON(elemento, data) {
        try {
            elemento.textContent = JSON.stringify(data, null, 2);
        } catch (e) {
            elemento.textContent = String(data);
        }
    }

    form.addEventListener('submit', async function(ev) {
        ev.preventDefault();
        if (!inputArchivo.files || !inputArchivo.files[0]) {
            alert('Debes seleccionar un archivo PDF.');
            return;
        }
        const archivo = inputArchivo.files[0];
        const formData = new FormData();
        formData.append('archivo', archivo);
        btnEnviar.disabled = true;
        btnEnviar.textContent = 'Enviando...';
        divResultado.textContent = 'Enviando archivo al servidor...';
        try {
            const resp = await fetch('/imprimir', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json().catch(() => ({}));
            if (!resp.ok) {
                mostrarJSON(divResultado, { error: true, status: resp.status, detalle: data.detail || data });
            } else {
                mostrarJSON(divResultado, data);
            }
        } catch (err) {
            mostrarJSON(divResultado, { error: true, mensaje: String(err) });
        } finally {
            btnEnviar.disabled = false;
            btnEnviar.textContent = 'Enviar a impresión';
        }
    });

    btnCola.addEventListener('click', async function() {
        divCola.textContent = 'Consultando /cola...';
        try {
            const resp = await fetch('/cola');
            const data = await resp.json().catch(() => ({}));
            mostrarJSON(divCola, data);
        } catch (err) {
            mostrarJSON(divCola, { error: true, mensaje: String(err) });
        }
    });

    btnEstado.addEventListener('click', async function() {
        divEstado.textContent = 'Consultando /estado...';
        try {
            const resp = await fetch('/estado');
            const data = await resp.json().catch(() => ({}));
            mostrarJSON(divEstado, data);
        } catch (err) {
            mostrarJSON(divEstado, { error: true, mensaje: String(err) });
        }
    });

    btnSalud.addEventListener('click', async function() {
        divEstado.textContent = 'Consultando /salud...';
        try {
            const resp = await fetch('/salud');
            const data = await resp.json().catch(() => ({}));
            mostrarJSON(divEstado, data);
        } catch (err) {
            mostrarJSON(divEstado, { error: true, mensaje: String(err) });
        }
    });

    btnTest.addEventListener('click', async function() {
        divResultado.textContent = 'Ejecutando prueba de impresora...';
        try {
            const resp = await fetch('/test-impresora', { method: 'POST' });
            const data = await resp.json().catch(() => ({}));
            mostrarJSON(divResultado, data);
        } catch (err) {
            mostrarJSON(divResultado, { error: true, mensaje: String(err) });
        }
    });
})();
</script>
</body>
</html>
"""
    return HTMLResponse(content=html, status_code=200)
