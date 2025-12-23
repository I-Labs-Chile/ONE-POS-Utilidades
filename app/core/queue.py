# -*- coding: utf-8 -*-
# Implementación de cola de impresión con persistencia ligera
# Mantiene últimos 10 impresos y todos los no impresos

import os
import json
import threading
from enum import Enum
from dataclasses import dataclass, asdict
from typing import List, Optional

QUEUE_DIR = os.path.abspath(os.environ.get("QUEUE_DIR", "./data"))
QUEUE_FILE = os.path.join(QUEUE_DIR, "queue.json")
JOBS_DIR = os.path.join(QUEUE_DIR, "jobs")
MAX_PRINTED_CACHE = 10

class JobState(str, Enum):
    PENDING = "pendiente"
    PROCESSING = "procesando"
    PRINTED = "impreso"
    ERROR = "error"

@dataclass
class PrintJob:
    id: str
    client_ip: str
    original_filename: str
    received_at: int
    state: JobState
    pdf_path: str
    error_message: str = ""
    # Tipo de contenido asociado al trabajo: "pdf" o "image"
    kind: str = "pdf"

class PrintQueue:
    def __init__(self):
        # Crear directorios necesarios
        os.makedirs(QUEUE_DIR, exist_ok=True)
        os.makedirs(JOBS_DIR, exist_ok=True)
        self._lock = threading.Lock()
        self._queue: List[PrintJob] = []
        self._printed_cache: List[PrintJob] = []
        self._load()

    def get_jobs_dir(self) -> str:
        return JOBS_DIR

    def enqueue(self, job: PrintJob):
        with self._lock:
            self._queue.append(job)
            self._save()

    def dequeue(self) -> Optional[PrintJob]:
        with self._lock:
            if not self._queue:
                return None
            job = self._queue.pop(0)
            self._save()
            return job

    def mark_processing(self, job: PrintJob):
        with self._lock:
            job.state = JobState.PROCESSING
            self._save()

    def mark_printed(self, job: PrintJob):
        with self._lock:
            job.state = JobState.PRINTED
            # Agregar al cache de impresos y recortar
            self._printed_cache.insert(0, job)
            if len(self._printed_cache) > MAX_PRINTED_CACHE:
                self._printed_cache = self._printed_cache[:MAX_PRINTED_CACHE]
            self._save()

    def mark_error(self, job: PrintJob, message: str):
        with self._lock:
            job.state = JobState.ERROR
            job.error_message = message
            self._save()

    def status(self):
        with self._lock:
            return {
                "pendientes": [asdict(j) for j in self._queue],
                "impresos": [asdict(j) for j in self._printed_cache],
            }

    def count_pending(self) -> int:
        with self._lock:
            return len(self._queue)

    def count_last_printed(self) -> int:
        with self._lock:
            return len(self._printed_cache)

    def _load(self):
        # Cargar estado si existe
        try:
            if os.path.exists(QUEUE_FILE):
                with open(QUEUE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._queue = [PrintJob(**j) for j in data.get("pendientes", [])]
                self._printed_cache = [PrintJob(**j) for j in data.get("impresos", [])]
        except Exception as e:
            # Log básico en consola
            print(f"# Error cargando cola: {e}")

    def _save(self):
        # Guardar estado
        try:
            data = {
                "pendientes": [asdict(j) for j in self._queue],
                "impresos": [asdict(j) for j in self._printed_cache],
            }
            with open(QUEUE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"# Error guardando cola: {e}")
