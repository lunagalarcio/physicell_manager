#!/usr/bin/env python3
"""Automatizacion de escenarios y replicas sin modificar PhysiCell."""
import os
import shutil
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime


def get_db_path_local(get_db_path_fn):
    return get_db_path_fn()


def crear_escenario(conn, experiment_id, nombre, config_xml_path, parametros_json="{}"):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO escenarios (experiment_id, nombre, config_xml_path, parametros_json) VALUES (?,?,?,?)",
        (experiment_id, nombre, config_xml_path, parametros_json),
    )
    conn.commit()
    return cur.lastrowid


def listar_escenarios(conn, experiment_id):
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, config_xml_path FROM escenarios WHERE experiment_id=? ORDER BY id", (experiment_id,))
    return cur.fetchall()


def fijar_output_folder(xml_path, folder):
    """Reescribe <save><folder> para aislar salidas por réplica. No toca modelos."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    node = root.find(".//save/folder")
    if node is None:
        # crea save/folder si no existe
        save = root.find(".//save")
        if save is None:
            save = ET.SubElement(root, "save")
        node = ET.SubElement(save, "folder")
    node.text = folder
    tree.write(xml_path, encoding="unicode", xml_declaration=True)
    return folder


def generar_replica_config(base_xml, out_xml, seed=None, output_folder=None):
    """Copia base_xml a out_xml cambiando random_seed y carpeta de salida si se indican."""
    os.makedirs(os.path.dirname(out_xml) or ".", exist_ok=True)
    if seed is None and output_folder is None:
        shutil.copyfile(base_xml, out_xml)
        return out_xml
    tree = ET.parse(base_xml)
    root = tree.getroot()
    if seed is not None:
        changed = False
        for el in root.iter():
            name = el.tag.split("}")[-1]
            if name == "random_seed":
                el.text = str(seed)
                changed = True
        if not changed:
            for el in root.iter():
                name = el.tag.split("}")[-1]
                if name == "user_parameters":
                    sub = ET.SubElement(el, "random_seed")
                    sub.set("type", "int")
                    sub.text = str(seed)
                    break
    if output_folder is not None:
        node = root.find(".//save/folder")
        if node is None:
            save = root.find(".//save")
            if save is None:
                save = ET.SubElement(root, "save")
            node = ET.SubElement(save, "folder")
        node.text = output_folder
    tree.write(out_xml, encoding="unicode", xml_declaration=True)
    return out_xml


def registrar_run(conn, experiment_id, run_number, status="pending", output_dir="",
                  configuracion_id=None, escenario_id=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (experiment_id, run_number, status, start_time, output_dir, "
        "configuracion_id, escenario_id) VALUES (?,?,?,?,?,?,?)",
        (experiment_id, run_number, status, datetime.now().isoformat(timespec="seconds"),
         output_dir, configuracion_id, escenario_id),
    )
    conn.commit()
    return cur.lastrowid


def actualizar_run(conn, run_id, status, end=False, configuracion_id=None):
    cur = conn.cursor()
    if end:
        cur.execute(
            "UPDATE runs SET status=?, end_time=?, configuracion_id=? WHERE id=?",
            (status, datetime.now().isoformat(timespec="seconds"),
             configuracion_id, run_id),
        )
    else:
        cur.execute(
            "UPDATE runs SET status=?, configuracion_id=? WHERE id=?",
            (status, configuracion_id, run_id),
        )
    conn.commit()


def listar_runs(conn, experiment_id):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number",
            (experiment_id,),
        )
    except Exception:
        cur.execute(
            "SELECT id, run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number",
            (experiment_id,),
        )
    return cur.fetchall()


def crear_experimento(conn, title, description="", tags="", config_xml_path="", usuario_id=None):
    """Crea un experimento y retorna su id."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO experiments (title, description, tags, config_xml_path, usuario_id, created_at, last_modified) "
        "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        (title, description, tags, config_xml_path, usuario_id),
    )
    conn.commit()
    return cur.lastrowid


def listar_experimentos_por_usuario(conn, uid):
    """Lista experimentos con estadísticas filtrados por usuario."""
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.id, e.title, e.description, e.tags, e.config_xml_path,
                      e.binary_path, e.custom_cpp_path, e.custom_h_path, e.last_modified,
                      COUNT(r.id) as total_runs,
                      COALESCE(SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status IN ('failed', 'cancelled')
                                       THEN 1 ELSE 0 END), 0),
                      MAX(r.start_time)
               FROM experiments e
               LEFT JOIN runs r ON e.id = r.experiment_id
               WHERE e.usuario_id = ?
               GROUP BY e.id
               ORDER BY e.id DESC""",
            (uid,),
        )
        return cur.fetchall()
    except Exception:
        cur.execute(
            "SELECT id, title, description, tags, config_xml_path, binary_path, "
            "custom_cpp_path, custom_h_path, last_modified FROM experiments WHERE usuario_id=? ORDER BY id DESC",
            (uid,),
        )
        filas = cur.fetchall()
        return [f + (0, 0, 0, 0, None) for f in filas]


def obtener_experimento_por_usuario(conn, eid, uid):
    """Datos completos de un experimento solo si pertenece al usuario."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, description, tags, config_xml_path, binary_path, "
        "custom_cpp_path, custom_h_path, created_at, last_modified, usuario_id "
        "FROM experiments WHERE id=? AND usuario_id=?", (eid, uid)
    )
    return cur.fetchone()


def actualizar_experimento(conn, experiment_id, title, description, tags, binary_path="", custom_cpp_path="", custom_h_path=""):
    cur = conn.cursor()
    cur.execute(
        "UPDATE experiments SET title=?, description=?, tags=?, binary_path=?, custom_cpp_path=?, custom_h_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?",
        (title, description, tags, binary_path, custom_cpp_path, custom_h_path, experiment_id),
    )
    conn.commit()


def estadisticas_experimento(conn, eid):
    """Devuelve estadísticas de runs para un experimento desde la DB."""
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(r.id),
                  SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN r.status IN ('failed', 'cancelled') THEN 1 ELSE 0 END),
                  MAX(r.start_time)
           FROM runs r WHERE r.experiment_id = ?""",
        (eid,),
    )
    row = cur.fetchone()
    return {
        "total": row[0] or 0,
        "completadas": row[1] or 0,
        "en_curso": row[2] or 0,
        "falladas": row[3] or 0,
        "ultima_fecha": row[4],
    }


def obtener_run_por_output_dir(conn, experiment_id, output_dir):
    """Busca el run_number de una ejecución por su carpeta de salida."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT run_number FROM runs WHERE experiment_id=? AND output_dir=? "
            "ORDER BY run_number DESC LIMIT 1",
            (experiment_id, output_dir),
        )
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def actualizar_rutas_experimento(conn, eid, config_xml_path="",
                                 binary_path="", custom_cpp_path="",
                                 custom_h_path=""):
    """Actualiza solo las rutas de configuración/motor de un experimento."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE experiments SET config_xml_path=?, binary_path=?, custom_cpp_path=?, custom_h_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?",
        (config_xml_path, binary_path, custom_cpp_path, custom_h_path, eid),
    )
    conn.commit()


def vincular_escenario_a_configuracion(conn, escenario_id, configuracion_id):
    """Vincula un escenario a la configuración exacta que usó."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE escenarios SET configuracion_id=? WHERE id=?",
        (configuracion_id, escenario_id),
    )
    conn.commit()


def listar_todos_los_runs(conn, limite=200):
    """Lista todas las ejecuciones de todos los experimentos (para página Ejecuciones)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT e.title, r.run_number, r.status, r.start_time, r.end_time, r.output_dir "
            "FROM runs r JOIN experiments e ON e.id=r.experiment_id ORDER BY r.start_time DESC LIMIT ?",
            (limite,),
        )
        return cur.fetchall()
    except Exception:
        return []


def eliminar_experimento(conn, experiment_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM runs WHERE experiment_id=?", (experiment_id,))
    cur.execute("DELETE FROM escenarios WHERE experiment_id=?", (experiment_id,))
    cur.execute("DELETE FROM experiments WHERE id=?", (experiment_id,))
    conn.commit()


def eliminar_escenario(conn, escenario_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM escenarios WHERE id=?", (escenario_id,))
    conn.commit()


# ---------- Consultas de experimentos (para evitar SQL en la UI) ----------

def obtener_experimento(conn, eid):
    """Datos completos de un experimento. Retorna tupla o None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, description, tags, config_xml_path, binary_path, "
        "custom_cpp_path, custom_h_path, created_at, last_modified "
        "FROM experiments WHERE id=?", (eid,)
    )
    return cur.fetchone()


def listar_experimentos(conn):
    """Lista simple id, title de todos los experimentos (para combos de selección)."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
        return cur.fetchall()
    except Exception:
        return []


def listar_experimentos_con_estadisticas(conn):
    """Lista experimentos con conteo y estados de runs (para la página Experimentos).

    Retorna filas con: id, title, description, tags, config_xml_path, binary_path,
    custom_cpp_path, custom_h_path, last_modified, total_runs, completadas,
    en_curso, falladas, ultima_fecha.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.id, e.title, e.description, e.tags, e.config_xml_path,
                      e.binary_path, e.custom_cpp_path, e.custom_h_path, e.last_modified,
                      COUNT(r.id) as total_runs,
                      COALESCE(SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status IN ('failed', 'cancelled')
                                       THEN 1 ELSE 0 END), 0),
                      MAX(r.start_time)
               FROM experiments e
               LEFT JOIN runs r ON e.id = r.experiment_id
               GROUP BY e.id
               ORDER BY e.id DESC"""
        )
        return cur.fetchall()
    except Exception:
        # Fallback sin estadísticas si la tabla runs no existe aún
        cur.execute(
            "SELECT id, title, description, tags, config_xml_path, binary_path, "
            "custom_cpp_path, custom_h_path, last_modified FROM experiments ORDER BY id DESC"
        )
        filas = cur.fetchall()
        return [f + (0, 0, 0, 0, None) for f in filas]
