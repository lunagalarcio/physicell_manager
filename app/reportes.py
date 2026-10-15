#!/usr/bin/env python3
"""Reportes de configuraciones, ejecuciones y resultados."""
import os
import sqlite3
import json
from datetime import datetime


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generar_reporte_html(experiment_id, db_path, out_html):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, config_xml_path, created_at FROM experiments WHERE id=?", (experiment_id,))
    exp = cur.fetchone()
    if not exp:
        conn.close()
        return {"ok": False, "error": "Experimento no existe"}
    cur.execute("SELECT id, nombre, config_xml_path FROM escenarios WHERE experiment_id=? ORDER BY id", (experiment_id,))
    escenarios = cur.fetchall()
    cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    runs = cur.fetchall()
    conn.close()
    eid, title, desc, cfg, created = exp
    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    parts = []
    parts.append("<html><head><meta charset='utf-8'><title>Reporte experimento</title></head><body>")
    parts.append(f"<h1>Experimento {eid}: {_esc(title)}</h1>")
    parts.append(f"<p>{_esc(desc)}</p>")
    parts.append(f"<p><b>Config base:</b> {_esc(cfg)}<br><b>Creado:</b> {_esc(created)}<br><b>Fecha reporte:</b> {datetime.now().isoformat(timespec='seconds')}</p>")
    parts.append("<h2>Escenarios</h2>")
    if escenarios:
        parts.append("<ul>")
        for sid, nom, cpath in escenarios:
            parts.append(f"<li>#{sid} {_esc(nom)} - {_esc(cpath)}</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>Sin escenarios registrados.</p>")
    parts.append("<h2>Replicas / Ejecuciones</h2>")
    if runs:
        parts.append("<table border='1' cellpadding='4'><tr><th>#</th><th>Estado</th><th>Inicio</th><th>Fin</th><th>Salida</th></tr>")
        for rnum, st, s0, s1, od in runs:
            parts.append(f"<tr><td>{rnum}</td><td>{_esc(st)}</td><td>{_esc(s0)}</td><td>{_esc(s1)}</td><td>{_esc(od)}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>Sin runs.</p>")
    parts.append("<p><i>Simulaciones ejecutadas por PhysiCell. Esta app no modifica modelos internos.</i></p>")
    parts.append("</body></html>")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return {"ok": True, "path": out_html}


def exportar_runs_csv(experiment_id, db_path, out_csv):
    import csv
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    rows = cur.fetchall()
    conn.close()
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_number", "status", "start_time", "end_time", "output_dir"])
        w.writerows(rows)
    return {"ok": True, "path": out_csv, "n": len(rows)}


def exportar_runs_json(experiment_id, db_path, out_json):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    rows = [{"run_number": a, "status": b, "start_time": c, "end_time": d, "output_dir": e} for a, b, c, d, e in cur.fetchall()]
    conn.close()
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"experiment_id": experiment_id, "runs": rows}, f, indent=2, ensure_ascii=False)
    return {"ok": True, "path": out_json, "n": len(rows)}
