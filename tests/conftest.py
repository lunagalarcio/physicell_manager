"""Fixtures compartidas para la suite de tests de PhysiCell Lab.

Todos los tests usan tempfile y el XML de ejemplo del repositorio.
No dependen de datos reales de PhysiCell instalado ni de rutas absolutas de Windows.
"""
import os
import sys
import tempfile
import sqlite3

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

CFG = os.path.join(BASE, "config", "PhysiCell_settings.xml")

# Esquema SQL replicado de app/nucleo.py (init_database) para crear tablas
# en una DB temporal sin depender de get_db_path() (que apunta al usuario).
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    config_xml_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_modified DATETIME,
    tags TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER,
    run_number INTEGER,
    status TEXT DEFAULT 'pending',
    start_time DATETIME,
    end_time DATETIME,
    output_dir TEXT,
    escenario_id INTEGER,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
CREATE TABLE IF NOT EXISTS escenarios (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER,
    nombre TEXT NOT NULL,
    config_xml_path TEXT,
    parametros_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
"""


@pytest.fixture(scope="session")
def base_dir():
    return BASE


@pytest.fixture(scope="session")
def cfg_path():
    return CFG


@pytest.fixture
def tmp_output_dir():
    """Carpeta temporal de output (vacía, sin snapshots reales)."""
    d = tempfile.mkdtemp(prefix="physicell_test_output_")
    os.makedirs(os.path.join(d, "output"), exist_ok=True)
    yield d


@pytest.fixture
def tmp_replica_dir():
    """Carpeta temporal de una réplica (con output isolado)."""
    d = tempfile.mkdtemp(prefix="physicell_test_replica_")
    os.makedirs(os.path.join(d, "output"), exist_ok=True)
    yield d


@pytest.fixture
def tmp_db_path():
    """Ruta a un archivo de base de datos SQLite temporal (vacío, sin tablas)."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture
def tmp_db_ready(tmp_db_path):
    """Ruta a un archivo de base de datos SQLite temporal con tablas ya creadas."""
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    conn.close()
    yield tmp_db_path


@pytest.fixture
def db_conn(tmp_db_path):
    """Conexión SQLite a una DB temporal con las tablas de experiments/runs/escenarios ya creadas."""
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def tmp_exp_dir():
    """Carpeta temporal de experimento (exp_X)."""
    d = tempfile.mkdtemp(prefix="physicell_test_exp_")
    yield d
