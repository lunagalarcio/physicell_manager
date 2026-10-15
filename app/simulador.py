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


def generar_replica_config(base_xml, out_xml, seed=None):
    """Copia base_xml a out_xml cambiando random_seed si se indica."""
    os.makedirs(os.path.dirname(out_xml) or ".", exist_ok=True)
    if seed is None:
        shutil.copyfile(base_xml, out_xml)
        return out_xml
    tree = ET.parse(base_xml)
    root = tree.getroot()
    changed = False
    for el in root.iter():
        name = el.tag.split("}")[-1]
        if name == "random_seed":
            el.text = str(seed)
            changed = True
    # si no existe tag, crea en user_parameters si existe
    if not changed:
        for el in root.iter():
            name = el.tag.split("}")[-1]
            if name == "user_parameters":
                sub = ET.SubElement(el, "random_seed")
                sub.set("type", "int")
                sub.text = str(seed)
                changed = True
                break
    tree.write(out_xml, encoding="unicode", xml_declaration=True)
    return out_xml


def registrar_run(conn, experiment_id, run_number, status="pending", output_dir=""):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (experiment_id, run_number, status, start_time, output_dir) VALUES (?,?,?,?,?)",
        (experiment_id, run_number, status, datetime.now().isoformat(timespec="seconds"), output_dir),
    )
    conn.commit()
    return cur.lastrowid


def actualizar_run(conn, run_id, status, end=False):
    cur = conn.cursor()
    if end:
        cur.execute(
            "UPDATE runs SET status=?, end_time=? WHERE id=?",
            (status, datetime.now().isoformat(timespec="seconds"), run_id),
        )
    else:
        cur.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
    conn.commit()


def listar_runs(conn, experiment_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT id, run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number",
        (experiment_id,),
    )
    return cur.fetchall()
