"""Tests para app/visor_widget.py y app/visor3d_vtk.py (funciones puras)."""
import os
import pytest

from app.visor_widget import listar_snapshots, leer_bounds, parse_snapshot_svg, leer_grafo


def test_listar_snapshots_carpeta_inexistente():
    """Carpeta inexistente debe devolver lista vacía."""
    assert listar_snapshots("/ruta/que/no/existe") == []


def test_listar_snapshots_carpeta_vacia(tmp_output_dir):
    """Carpeta vacía debe devolver lista vacía."""
    assert listar_snapshots(tmp_output_dir) == []


def test_leer_bounds_sin_initial_xml(tmp_output_dir):
    """Sin initial.xml, leer_bounds debe devolver None."""
    assert leer_bounds(tmp_output_dir) is None


def test_parse_snapshot_svg_archivo_inexistente():
    """Archivo SVG inexistente lanza FileNotFoundError (ET.parse)."""
    with pytest.raises(FileNotFoundError):
        parse_snapshot_svg("/ruta/que/no/existe.svg", None)


def test_leer_grafo_carpeta_sin_grafos(tmp_output_dir):
    """Sin archivos de grafo, leer_grafo debe devolver set vacío."""
    grafos = leer_grafo(tmp_output_dir, 0, "neighbor")
    assert grafos == set()
