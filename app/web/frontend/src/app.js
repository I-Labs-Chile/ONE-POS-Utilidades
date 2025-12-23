const dropzone = document.getElementById("dropzone");
const fileInput = document.getElementById("fileInput");
const statusBox = document.getElementById("status");
const healthDot = document.getElementById("healthDot");
const healthText = document.getElementById("healthText");

function showStatus(text, type) {
    statusBox.textContent = text;
    statusBox.className = "status " + type;
    statusBox.style.display = "block";
}

async function sendFile(file) {
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

        if (data.ok && data.cola_pendientes === 0) {
            healthDot.className = "dot ok";
            healthText.textContent = "Impresora operativa";
        } else if (data.ok && data.cola_pendientes > 0) {
            healthDot.className = "dot warn";
            healthText.textContent = `${data.cola_pendientes} trabajo(s) pendiente(s)`;
        } else {
            healthDot.className = "dot error";
            healthText.textContent = "Error de impresora";
        }
    } catch {
        healthDot.className = "dot error";
        healthText.textContent = "Servidor no disponible";
    }
}

checkHealth();
setInterval(checkHealth, 5000);
