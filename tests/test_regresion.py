#!/usr/bin/env python3
"""Suite de regresion con datos reales. Ejecutar: python tests/test_regresion.py"""
import os
import sys
import sqlite3
import tempfile

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
PHYS = r"C:\Users\PC\Downloads\gestor_physicell\gestor_physicell\PhysiCell"
OUT = os.path.join(PHYS, "output")
CFG = os.path.join(PHYS, "config", "PhysiCell_settings.xml")

fails = []


def check(nombre, cond, detalle=""):
    print(("OK  " if cond else "FALLO") + f" {nombre} {detalle}")
    if not cond:
        fails.append(nombre)


from app.xml_validator import validar_config
v = validar_config(CFG)
check("validador xml real", v.get("ok"), str(v.get("errores")))
v2 = validar_config(os.path.join(BASE, "config", "PhysiCell_settings.xml"))
check("validador xml biblioteca", v2.get("ok"), str(v2.get("errores")))
v3 = validar_config(os.path.join(BASE, "config", "PhysiCell_settings.xml").replace("PhysiCell_settings", "INEXISTENTE_X"))
check("validador inexistente", not v3.get("ok"))

from app.simulador import generar_replica_config, fijar_output_folder, registrar_run, actualizar_run, listar_runs
import xml.etree.ElementTree as ET
tmp = tempfile.mkdtemp()
out_xml = os.path.join(tmp, "rep.xml")
generar_replica_config(CFG, out_xml, seed=4242, output_folder=os.path.join(tmp, "out"))
root = ET.parse(out_xml).getroot()
check("replica seed+carpeta", root.find(".//save/folder").text.endswith("out"))

from app.visualizador import verificar_integridad, listar_archivos
vi = verificar_integridad(OUT)
check("integridad output real", vi.get("ok"), str(vi))
check("archivos listados", len(listar_archivos(OUT)) > 0)

from app.visor_widget import parse_snapshot_svg, leer_bounds, leer_grafo
import glob
snaps = sorted(glob.glob(os.path.join(OUT, "snapshot*.svg")))
b = leer_bounds(OUT)
r = parse_snapshot_svg(snaps[-1], b)
check("parse snapshot", r.get("ok") and r.get("n", 0) > 0, f"n={r.get('n')}")
check("tipos presentes", len(r.get("types", [])) == len(r.get("x", [])))
g = leer_grafo(OUT, 10**6, "neighbor")
check("grafo vecino", isinstance(g, set))

from app.comparacion import generar_grafica_comparacion
from app.nucleo import get_db_path, init_database
import tempfile as _tf
from app.agregador import agregar_replica
_ag = agregar_replica(OUT, os.path.join(_tf.gettempdir(), "agg_reg"))
check("consolidado replica", _ag.get("ok") and _ag.get("frames", 0) > 0, str(_ag.get("frames")))
db = init_database()
png = os.path.join(tempfile.gettempdir(), "cmp_reg.png")
rc = generar_grafica_comparacion(db, 4, png)
check("grafica comparacion", rc.get("ok") and os.path.isfile(png))

from app.reportes import generar_reporte_html, exportar_reporte_pdf
html = os.path.join(tempfile.gettempdir(), "rep_reg.html")
rr = generar_reporte_html(4, db, html)
check("reporte html", rr.get("ok"))
print("PDF: requiere QApplication; se prueba en GUI" if True else "")

conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM experiments")
n_exp = cur.fetchone()[0]
conn.close()
check("db experimentos>0", n_exp > 0, f"n={n_exp}")

print(f"\n{len(fails)} fallos: {fails}" if fails else "\nTODO OK")
sys.exit(1 if fails else 0)
