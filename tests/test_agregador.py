"""Tests para app/agregador.py"""
import os
import csv
import pytest

from app.agregador import agregar_replica, agregar_experimento, leer_frame


def test_agregar_replica_carpeta_vacia(tmp_output_dir):
    """agregar_replica sobre carpeta vacía no falla y devuelve frames=0."""
    resultado = agregar_replica(tmp_output_dir, os.path.join(tmp_output_dir, "agg_out"))
    assert resultado["ok"] is True
    assert resultado["frames"] == 0


def test_agregar_experimento_sin_runs(tmp_db_ready):
    """agregar_experimento sin runs debe devolver replicas=0 sin fallar."""
    resultado = agregar_experimento(tmp_db_ready, 999, tmp_db_ready + "_agg")
    assert resultado["ok"] is True
    assert resultado["replicas"] == 0


def test_leer_frame_archivo_inexistente(tmp_output_dir):
    """leer_frame con archivo inexistente lanza FileNotFoundError (ET.parse)."""
    with pytest.raises(FileNotFoundError):
        leer_frame(tmp_output_dir, "no_existe.svg")
