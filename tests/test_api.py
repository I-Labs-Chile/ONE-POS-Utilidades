# -*- coding: utf-8 -*-
# Pruebas básicas de la API usando requests

import requests

BASE = "http://localhost:8080"

def test_salud():
    r = requests.get(f"{BASE}/salud", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert "ip_local" in data
    assert "impresora" in data

def test_estado():
    r = requests.get(f"{BASE}/estado", timeout=5)
    assert r.status_code == 200
    data = r.json()
    assert "ip" in data
    assert "impresora" in data
    assert "cola" in data

