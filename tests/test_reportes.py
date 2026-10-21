"""Tests para app/reportes.py"""
import os

from app.reportes import generar_reporte_html, extraer_parametros


def test_generar_reporte_html_experimento_inexistente(tmp_db_ready):
    """Reporte para experimento inexistente debe devolver ok=False."""
    out_html = os.path.join(str(tmp_db_ready) + "_dir", "reporte.html")
    resultado = generar_reporte_html(99999, tmp_db_ready, out_html)
    assert resultado["ok"] is False
    assert "error" in resultado


def test_extraer_parametros_xml_inexistente():
    """XML inexistente debe devolver ok=False."""
    resultado = extraer_parametros("/ruta/que/no/existe.xml")
    assert resultado["ok"] is False
    assert "error" in resultado


def test_extraer_parametros_xml_ejemplo(cfg_path):
    """XML de ejemplo del repo debe extraer parámetros correctamente."""
    resultado = extraer_parametros(cfg_path)
    assert resultado["ok"] is True
    assert "dominio" in resultado
    assert "max_time" in resultado
    assert "sustratos" in resultado
    assert "tipos" in resultado
    assert resultado["dominio"]["x_min"] == "-500"
    assert resultado["dominio"]["x_max"] == "500"
