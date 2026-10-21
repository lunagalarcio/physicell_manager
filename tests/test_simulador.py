"""Tests para app/simulador.py"""
import os
import sqlite3

from app import simulador as SIM


def test_generar_replica_config_seed_y_carpeta(cfg_path, tmp_output_dir):
    """generar_replica_config debe cambiar random_seed y carpeta de salida."""
    out_xml = os.path.join(tmp_output_dir, "rep.xml")
    out_folder = os.path.join(tmp_output_dir, "out")
    SIM.generar_replica_config(cfg_path, out_xml, seed=4242, output_folder=out_folder)

    import xml.etree.ElementTree as ET
    root = ET.parse(out_xml).getroot()
    seed_el = root.find(".//random_seed")
    folder_el = root.find(".//save/folder")
    assert seed_el is not None and seed_el.text == "4242"
    assert folder_el is not None and folder_el.text == out_folder


def test_generar_replica_config_sin_cambios_es_copia(cfg_path, tmp_output_dir):
    """Si no se indica seed ni carpeta, debe ser una copia exacta."""
    out_xml = os.path.join(tmp_output_dir, "copia.xml")
    SIM.generar_replica_config(cfg_path, out_xml)
    with open(cfg_path, "rb") as a, open(out_xml, "rb") as b:
        assert a.read() == b.read()


def test_fijar_output_folder(cfg_path, tmp_output_dir):
    """fijar_output_folder debe reescribir <save><folder>."""
    out_xml = os.path.join(tmp_output_dir, "con_folder.xml")
    SIM.generar_replica_config(cfg_path, out_xml)
    nuevo = os.path.join(tmp_output_dir, "mi_output")
    SIM.fijar_output_folder(out_xml, nuevo)

    import xml.etree.ElementTree as ET
    root = ET.parse(out_xml).getroot()
    folder = root.find(".//save/folder")
    assert folder is not None and folder.text == nuevo


def test_crear_y_listar_escenario(db_conn, cfg_path):
    """crear_escenario y listar_escenarios deben funcionar."""
    conn = db_conn
    cur = conn.cursor()
    cur.execute("INSERT INTO experiments (title, description, tags, config_xml_path) VALUES (?,?,?,?)",
                ("Exp test", "desc", "", cfg_path))
    conn.commit()
    eid = cur.lastrowid

    sid = SIM.crear_escenario(conn, eid, "variante-1", cfg_path, "{}")
    assert sid is not None

    escenarios = SIM.listar_escenarios(conn, eid)
    assert len(escenarios) == 1
    assert escenarios[0][1] == "variante-1"
    assert escenarios[0][2] == cfg_path


def test_registrar_y_actualizar_run(db_conn, cfg_path):
    """registrar_run y actualizar_run deben persistir estado."""
    conn = db_conn
    cur = conn.cursor()
    cur.execute("INSERT INTO experiments (title, description, tags, config_xml_path) VALUES (?,?,?,?)",
                ("Exp test", "desc", "", cfg_path))
    conn.commit()
    eid = cur.lastrowid

    run_id = SIM.registrar_run(conn, eid, 1, status="running", output_dir="/tmp/out")
    assert run_id is not None

    SIM.actualizar_run(conn, run_id, "completed", end=True)
    runs = SIM.listar_runs(conn, eid)
    assert len(runs) == 1
    assert runs[0][2] == "completed"
    assert runs[0][4] is not None  # end_time


def test_eliminar_experimento_borra_runs_y_escenarios(db_conn, cfg_path):
    """eliminar_experimento debe borrar cascada runs y escenarios."""
    conn = db_conn
    cur = conn.cursor()
    cur.execute("INSERT INTO experiments (title, description, tags, config_xml_path) VALUES (?,?,?,?)",
                ("Exp test", "desc", "", cfg_path))
    conn.commit()
    eid = cur.lastrowid

    SIM.crear_escenario(conn, eid, "v1", cfg_path, "{}")
    SIM.registrar_run(conn, eid, 1, status="completed", output_dir="/tmp/out")
    conn.commit()

    SIM.eliminar_experimento(conn, eid)
    conn.commit()

    cur.execute("SELECT COUNT(*) FROM experiments WHERE id=?", (eid,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM escenarios WHERE experiment_id=?", (eid,))
    assert cur.fetchone()[0] == 0
    cur.execute("SELECT COUNT(*) FROM runs WHERE experiment_id=?", (eid,))
    assert cur.fetchone()[0] == 0


def test_esquema_tiene_tablas_esperadas(db_conn):
    """La DB temporal debe tener las tablas experiments, runs y escenarios."""
    cur = db_conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tablas = {row[0] for row in cur.fetchall()}
    assert "experiments" in tablas
    assert "runs" in tablas
    assert "escenarios" in tablas
