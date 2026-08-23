/* Cabina Fotográfica ONE-POS — lógica del kiosco
   Estados: PREVIEW → COUNTDOWN (x3 fotos) → REVIEW → PRINTING → PREVIEW */

const TOTAL_FOTOS = 3;

const $ = (id) => document.getElementById(id);
const video = $("video");
const canvas = $("canvas");
const countdownEl = $("countdown");
const flashEl = $("flash");
const camaraWrap = $("camaraWrap");
const thumbsEl = $("thumbs");
const msgEl = $("msg");

const btnAccion = $("btnAccion");
const btnImprimir = $("btnImprimir");
const btnRepetir = $("btnRepetir");
const pillCam = $("pillCam");
const pillPrinter = $("pillPrinter");
const camText = $("camText");
const printerText = $("printerText");

let estado = "PREVIEW";          // PREVIEW | COUNTDOWN | REVIEW | PRINTING
let stream = null;
let camaraLista = false;
let impresoraOk = false;
let impresoraNombre = "";
let tomas = [];                  // dataURL de cada toma

/* ---------- Utilidades UI ---------- */

function setDot(pill, cls) {
    pill.querySelector(".dot").className = "dot " + cls;
}

function setMsg(texto, tipo) {
    if (!texto) { msgEl.hidden = true; return; }
    msgEl.textContent = texto;
    msgEl.className = "msg " + tipo;
    msgEl.hidden = false;
}

function mostrarControles(modo) {
    // modo: "foto" | "revision" | "ninguno"
    btnAccion.hidden = modo !== "foto";
    btnImprimir.hidden = modo !== "revision";
    btnRepetir.hidden = modo !== "revision";
    thumbsEl.hidden = modo !== "revision";
}

/* ---------- Cámara ---------- */

async function iniciarCamara() {
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 1920 }, height: { ideal: 1080 }, facingMode: "user" },
            audio: false,
        });
        video.srcObject = stream;
        await video.play();
        camaraLista = true;
        const track = stream.getVideoTracks()[0];
        camText.textContent = "Cámara: " + (track.label || "detectada");
        setDot(pillCam, "ok");
    } catch (e) {
        camaraLista = false;
        camText.textContent = "Sin cámara: " + (e.name === "NotAllowedError"
            ? "permiso denegado" : "no detectada");
        setDot(pillCam, "error");
    }
    actualizarBotonFoto();
}

/* ---------- Salud de impresora ---------- */

async function checkSalud() {
    try {
        const r = await fetch("/salud");
        const d = await r.json();
        impresoraOk = !!d.impresora_disponible;
        impresoraNombre = d.impresora_nombre || "";
        printerText.textContent = impresoraOk
            ? "Impresora: " + (impresoraNombre || "lista")
            : "Impresora no disponible";
        setDot(pillPrinter, impresoraOk ? "ok" : "error");
    } catch {
        impresoraOk = false;
        printerText.textContent = "Servidor no disponible";
        setDot(pillPrinter, "error");
    }
    actualizarBotonFoto();
}

function actualizarBotonFoto() {
    btnAccion.disabled = !(camaraLista && impresoraOk && estado === "PREVIEW");
    if (!camaraLista) btnAccion.title = "Cámara no disponible";
    else if (!impresoraOk) btnAccion.title = "Impresora no disponible";
    else btnAccion.title = "";
}

/* ---------- Captura ---------- */

function capturarFrame() {
    // Dibuja el frame actual a resolución natural del stream
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    return canvas.toDataURL("image/jpeg", 0.92);
}

function dormir(ms) {
    return new Promise((r) => setTimeout(r, ms));
}

async function cuentaRegresiva(segundos) {
    for (let s = segundos; s >= 1; s--) {
        countdownEl.textContent = s;
        countdownEl.classList.remove("tick");
        void countdownEl.offsetWidth;      // reinicia animación
        countdownEl.classList.add("tick");
        await dormir(900);
    }
}

function flashCaptura() {
    flashEl.hidden = false;
    flashEl.style.animation = "none";
    void flashEl.offsetWidth;
    flashEl.style.animation = "";
    setTimeout(() => { flashEl.hidden = true; }, 500);
}

/* ---------- Flujo principal ---------- */

async function iniciarSesion() {
    if (estado !== "PREVIEW") return;
    if (!camaraLista) { setMsg("No hay cámara disponible.", "error"); return; }
    if (!impresoraOk) { setMsg("La impresora no está disponible.", "error"); return; }

    estado = "COUNTDOWN";
    mostrarControles("ninguno");
    setMsg(null);
    tomas = [];

    for (let i = 0; i < TOTAL_FOTOS && estado === "COUNTDOWN"; i++) {
        countdownEl.hidden = false;
        await cuentaRegresiva(3);
        countdownEl.hidden = true;
        if (estado !== "COUNTDOWN") break;   // cancelado

        tomas.push(capturarFrame());
        flashCaptura();
        await dormir(600);                   // respiro entre tomas
    }
    countdownEl.hidden = true;

    if (estado !== "COUNTDOWN") { resetPreview(); return; }

    estado = "REVIEW";
    mostrarControles("revision");
    thumbsEl.innerHTML = "";
    tomas.forEach((src) => {
        const img = document.createElement("img");
        img.src = src;
        thumbsEl.appendChild(img);
    });
    setMsg("¿Imprimimos esta tira?", "warn");
}

async function imprimirTira() {
    if (estado !== "REVIEW") return;
    estado = "PRINTING";
    mostrarControles("ninguno");
    btnAccion.disabled = true;
    setMsg("Enviando a imprimir…", "warn");

    try {
        const form = new FormData();
        for (let i = 0; i < tomas.length; i++) {
            const blob = dataURLtoBlob(tomas[i]);
            form.append("foto" + (i + 1), blob, "toma" + (i + 1) + ".jpg");
        }
        const r = await fetch("/captura", { method: "POST", body: form });
        const d = await r.json().catch(() => ({}));

        if (!r.ok) {
            setMsg(d.detail || "No se pudo enviar la tira.", "error");
            resetPreview();
            return;
        }

        const resultado = await esperarResultado(d.id);
        if (resultado === "impreso") {
            setMsg("¡Listo! Tira enviada a la impresora 🎉", "ok");
        } else if (resultado === "error") {
            setMsg("La impresión falló. Revisa la impresora e intenta de nuevo.", "error");
        } else {
            setMsg("Tira en cola de impresión.", "warn");
        }
    } catch {
        setMsg("Error de conexión con el servidor.", "error");
    }
    resetPreview();
}

async function esperarResultado(jobId) {
    // Consulta /cola hasta ver el trabajo impreso o con error (máx ~45 s)
    for (let i = 0; i < 45; i++) {
        await dormir(1000);
        try {
            const r = await fetch("/cola");
            const d = await r.json();
            if ((d.errores || []).some((j) => j.id === jobId)) return "error";
            if ((d.impresos || []).some((j) => j.id === jobId)) return "impreso";
            if (!(d.pendientes || []).some((j) => j.id === jobId)) {
                // Ya no está pendiente ni en caches visibles: asumir impreso reciente
                return "impreso";
            }
        } catch { /* reintenta */ }
    }
    return "timeout";
}

function repetirSesion() {
    if (estado !== "REVIEW") return;
    resetPreview();
}

function resetPreview() {
    estado = "PREVIEW";
    camaraWrap.classList.remove("frozen");
    mostrarControles("foto");
    actualizarBotonFoto();
    setTimeout(() => setMsg(null), 4000);
}

function dataURLtoBlob(dataURL) {
    const [meta, b64] = dataURL.split(",");
    const mime = meta.match(/:(.*?);/)[1];
    const bin = atob(b64);
    const arr = new Uint8Array(bin.length);
    for (let i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return new Blob([arr], { type: mime });
}

/* ---------- Eventos ---------- */

btnAccion.addEventListener("click", iniciarSesion);
btnImprimir.addEventListener("click", imprimirTira);
btnRepetir.addEventListener("click", repetirSesion);

document.addEventListener("keydown", (e) => {
    if (e.repeat) return;
    const k = e.key.toLowerCase();
    if (k === " " || k === "f") {
        e.preventDefault();
        iniciarSesion();
    } else if (k === "enter" || k === "a") {
        e.preventDefault();
        imprimirTira();
    } else if (k === "escape" || k === "r") {
        e.preventDefault();
        if (estado === "COUNTDOWN") { estado = "CANCELADO"; resetPreview(); }
        else repetirSesion();
    }
});

/* ---------- Arranque ---------- */

mostrarControles("foto");
iniciarCamara();
checkSalud();
setInterval(checkSalud, 3000);
