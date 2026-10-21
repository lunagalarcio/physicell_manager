"""Tests para app/comparacion.py"""
import os

from app.comparacion import n_celulas_final, datos_comparacion, generar_grafica_comparacion


def test_n_celulas_final_carpeta_inexistente():
    """Carpeta inexistente debe devolver None."""
    assert n_celulas_final("/ruta/que/no/existe") is None


def test_n_celulas_final_carpeta_vacia(tmp_output_dir):
    """Carpeta vacía sin snapshots ni .mat debe devolver None."""
    assert n_celulas_final(tmp_output_dir) is None


def test_datos_comparacion_sin_experimento(tmp_db_ready):
    """datos_comparacion para experimento inexistente debe devolver lista vacía."""
    filas = datos_comparacion(tmp_db_ready, 99999)
    assert filas == []


def test_generar_grafica_comparacion_sin_runs(tmp_db_ready, tmp_exp_dir):
    """Gráfica de comparación sin runs debe generarse sin fallar (0 barras)."""
    out_png = os.path.join(tmp_exp_dir, "comparacion.png")
    resultado = generar_grafica_comparacion(tmp_db_ready, 99999, out_png)
    assert resultado["ok"] is True
    assert resultado["sin_datos"] == 0
    assert os.path.isfile(out_png)
