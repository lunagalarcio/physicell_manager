#!/usr/bin/env python3
"""Suite de regresion portable. Ejecutar: python tests/test_regresion.py

Usa tempfile y el XML de ejemplo del repositorio (config/PhysiCell_settings.xml).
No depende de rutas absolutas de Windows ni de datos reales de PhysiCell instalado.
"""
import os
import sys
import sqlite3
import tempfile
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

CFG = os.path.join(BASE, "config", "PhysiCell_settings.xml")
TMP = tempfile.mkdtemp(prefix="physicell_test_")
OUT = os.path.join(TMP, "output")
os.makedirs(OUT, exist_ok=True)

fails = []
skips = []


def check(nombre, cond, detalle=""):
    print(("OK  " if cond else "FALLO") + f" {nombre} {detalle}")
    if not cond:
        fails.append(nombre)


def skip(nombre, motivo="sin datos reales de PhysiCell"):
    print(("SKIP ") + f" {nombre} ({motivo})")
    skips.append(nombre)


if __name__ == "__main__":
    # --- 1. Validador XML ---
    from app.xml_validator import validar_config

    v = validar_config(CFG)
    check("validador xml ejemplo repo", v.get("ok"), str(v.get("errores")))

    v2 = validar_config(os.path.join(BASE, "config", "PhysiCell_settings.xml"))
    check("validador xml ejemplo repo (2)", v2.get("ok"), str(v2.get("errores")))

    v3 = validar_config(os.path.join(TMP, "INEXISTENTE.xml"))
    check("validador inexistente", not v3.get("ok"))

    # --- 2. Simulador: generar configuracion de replica ---
    from app.simulador import (
        generar_replica_config, fijar_output_folder,
        registrar_run, actualizar_run, listar_runs,
    )
    import xml.etree.ElementTree as ET

    out_xml = os.path.join(TMP, "rep.xml")
    generar_replica_config(CFG, out_xml, seed=4242, output_folder=os.path.join(TMP, "out"))
    root = ET.parse(out_xml).getroot()
    check("replica seed+carpeta", root.find(".//save/folder").text.endswith("out"))

    # fijar_output_folder sobre una copia
    out_xml2 = os.path.join(TMP, "rep2.xml")
    generar_replica_config(CFG, out_xml2)
    fijar_output_folder(out_xml2, os.path.join(TMP, "out2"))
    root2 = ET.parse(out_xml2).getroot()
    check("fijar output folder", root2.find(".//save/folder").text == os.path.join(TMP, "out2"))

    # --- 3. Visualizador: integridad y listado sobre carpeta vacia ---
    from app.visualizador import verificar_integridad, listar_archivos

    vi = verificar_integridad(OUT)
    check("integridad carpeta vacia (no falla)", isinstance(vi, dict) and "faltan" in vi)
    check("archivos listados carpeta vacia", isinstance(listar_archivos(OUT), list))

    # parse_snapshot_svg / leer_grafo sin snapshots: graceful
    from app.visor_widget import parse_snapshot_svg, leer_bounds, leer_grafo
    b = leer_bounds(OUT)
    check("leer_bounds carpeta vacia", b is None)

    snaps = sorted(glob.glob(os.path.join(OUT, "snapshot*.svg")))
    if snaps:
        r = parse_snapshot_svg(snaps[-1], b)
        check("parse snapshot real", r.get("ok") and r.get("n", 0) > 0, f"n={r.get('n')}")
        g = leer_grafo(OUT, 0, "neighbor")
        check("grafo vecino real", isinstance(g, set))
    else:
        skip("parse snapshot real", "no hay snapshot*.svg en output temporal")
        skip("grafo vecino real", "no hay snapshot*.svg en output temporal")

    # --- 4. Consolidacion de replica sobre carpeta vacia ---
    from app.agregador import agregar_replica
    _ag = agregar_replica(OUT, os.path.join(TMP, "agg_reg"))
    check("consolidado replica vacia no falla", _ag.get("ok") is True)
    check("consolidado replica vacia frames=0", _ag.get("frames", -1) == 0)

    # --- 5. Base de datos y grafica comparacion ---
    from app.nucleo import get_db_path, init_database, ReplicaWorker
    db = init_database()
    conn = sqlite3.connect(db)
    cur = conn.cursor()
    cur.execute("INSERT INTO experiments (title, description, tags, config_xml_path) VALUES (?,?,?,?)",
                ("Test regresion", "prueba portable", "", CFG))
    conn.commit()
    eid = cur.lastrowid
    cur.execute("SELECT COUNT(*) FROM experiments")
    n_exp = cur.fetchone()[0]
    conn.close()
    check("db experimentos > 0", n_exp > 0, f"n={n_exp}")

    from app.comparacion import generar_grafica_comparacion
    png = os.path.join(TMP, "cmp_reg.png")
    rc = generar_grafica_comparacion(db, eid, png)
    check("grafica comparacion generada", rc.get("ok") and os.path.isfile(png))

    # --- 6. Reporte HTML sobre experimento creado ---
    from app.reportes import generar_reporte_html
    html = os.path.join(TMP, "rep_reg.html")
    rr = generar_reporte_html(eid, db, html)
    check("reporte html generado", rr.get("ok"))

    # reporte sobre experimento inexistente
    rr2 = generar_reporte_html(999999, db, os.path.join(TMP, "rep_inexistente.html"))
    check("reporte inexistente retorna error", not rr2.get("ok") and "error" in rr2)

    print(f"\n{len(fails)} fallos, {len(skips)} saltados: {fails}" if fails else f"\nTODO OK ({len(skips)} saltados)")
