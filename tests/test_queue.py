# -*- coding: utf-8 -*-
# Pruebas de la cola de impresión

import os
import time
from app.core.queue import PrintQueue, PrintJob, JobState

def test_queue_basic(tmp_path):
    os.environ["QUEUE_DIR"] = str(tmp_path)
    q = PrintQueue()
    j1 = PrintJob(id="1", client_ip="127.0.0.1", original_filename="a.pdf", received_at=int(time.time()), state=JobState.PENDING, pdf_path=str(tmp_path/"a.pdf"), error_message="")
    j2 = PrintJob(id="2", client_ip="127.0.0.1", original_filename="b.pdf", received_at=int(time.time()), state=JobState.PENDING, pdf_path=str(tmp_path/"b.pdf"), error_message="")
    q.enqueue(j1)
    q.enqueue(j2)
    assert q.count_pending() == 2
    job = q.dequeue()
    assert job.id == "1"
    q.mark_processing(job)
    q.mark_printed(job)
    assert q.count_last_printed() == 1
    status = q.status()
    assert len(status["pendientes"]) == 1
    assert len(status["impresos"]) == 1

