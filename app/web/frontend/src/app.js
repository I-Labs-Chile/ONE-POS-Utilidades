const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const statusBox = document.getElementById("status");
const healthDot = document.getElementById("healthDot");
const healthText = document.getElementById("healthText");

let printerAvailable = false;

function showStatus(text, type) {
    statusBox.textContent = text;
    statusBox.className = "status " + type;
    statusBox.style.display = "block";
}

async function sendFile(file) {
    if (!printerAvailable) {
        showStatus("Impresora no disponible. Por favor, conecte la impresora.", "error");
        return;
    }

    showStatus("Enviando archivo a impresión…", "warn");

    const isPdf = file.name.toLowerCase().endsWith(".pdf");
    const url = isPdf ? "/imprimir" : "/imprimir-imagen";

    const data = new FormData();
    data.append("archivo", file);

    try {
        const resp = await fetch(url, { method: "POST", body: data });
        const json = await resp.json().catch(() => ({}));

        if (!resp.ok) {
            showStatus(
                json.detail || "No se pudo imprimir el documento",
                "error"
            );
        } else {
            showStatus("Documento enviado correctamente a la cola", "ok");
        }
    } catch (e) {
        showStatus("Error de conexión con el servidor", "error");
    }
}

dropzone.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", e => {
    if (e.target.files.length > 0) {
        sendFile(e.target.files[0]);
    }
});

dropzone.addEventListener("dragover", e => {
    e.preventDefault();
    dropzone.classList.add("drag");
});

dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("drag");
});

dropzone.addEventListener("drop", e => {
    e.preventDefault();
    dropzone.classList.remove("drag");
    if (e.dataTransfer.files.length > 0) {
        sendFile(e.dataTransfer.files[0]);
    }
});

document.addEventListener("paste", e => {
    const file = [...e.clipboardData.files][0];
    if (file) {
        sendFile(file);
    }
});

async function checkHealth() {
    try {
        const resp = await fetch("/salud");
        const data = await resp.json();

        printerAvailable = data.impresora_disponible;

        if (data.impresora_disponible) {
            if (data.cola_pendientes === 0) {
                healthDot.className = "dot ok";
                healthText.textContent = `Impresora conectada: ${data.impresora_nombre || "Impresora operativa"}`;
            } else {
                healthDot.className = "dot warn";
                healthText.textContent = `${data.cola_pendientes} trabajo(s) pendiente(s)`;
            }
            // Habilitar zona de drop
            dropzone.classList.remove("disabled");
        } else {
            healthDot.className = "dot error";
            healthText.textContent = "Impresora no conectada";
            // Deshabilitar zona de drop
            dropzone.classList.add("disabled");
        }
    } catch {
        printerAvailable = false;
        healthDot.className = "dot error";
        healthText.textContent = "Servidor no disponible";
        dropzone.classList.add("disabled");
    }
}

checkHealth();
setInterval(checkHealth, 3000);
