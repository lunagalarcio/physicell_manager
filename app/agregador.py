#!/usr/bin/env python3
"""Consolida salidas PhysiCell dispersas por frame en tablas listas para análisis.

Por réplica genera:
- frames.csv: una fila por frame (tiempo, n células, estados, volumen/presión medios, contactos).
- celulas.csv: una fila por célula y frame (id, tipo, estado, posición, radio, volumen, presión).

Por experimento agrega todas sus réplicas con columna replica/run.
Solo datos reales; si falta un archivo el frame queda marcado sin datos.
"""
import os
import glob
import csv


def _frames_de(output_dir):
    snaps = sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))
    return snaps


def _indice_frame(path):
    import re
    m = re.search(r"(\d{8})", os.path.basename(path))
    return m.group(1) if m else None


def leer_frame(output_dir, snap_path):
    """Métricas y células de un frame cruzando SVG + cells.mat + XML + grafos."""
    import numpy as _np
    from .visor_widget import parse_snapshot_svg, leer_bounds, leer_grafo
    bounds = leer_bounds(output_dir)
    r = parse_snapshot_svg(snap_path, bounds)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error")}
    n = len(r["x"])
    tag = _indice_frame(snap_path)
    mats = sorted(glob.glob(os.path.join(output_dir, f"output{tag}_cells.mat"))) if tag else []
    xmls = sorted(glob.glob(os.path.join(output_dir, f"output{tag}.xml"))) if tag else []
    tiempo = None
    ids = list(range(n))
    estados = ["desconocido"] * n
    vols = [None] * n
    pres = [None] * n
    tipos = [None] * n
    rads = list(r["r"])
    if xmls:
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(xmls[0]).getroot()
            for el in root.iter():
                if el.tag.split("}")[-1] == "current_time":
                    tiempo = float(el.text)
                    break
        except Exception:
            pass
    if mats:
        try:
            import scipy.io as _sio
            m = _sio.loadmat(mats[0])["cells"]
            nc = m.shape[1]
            k = min(n, nc)
            try:
                ids = [int(v) for v in m[0].ravel().tolist()][:k] + list(range(k, n))
            except Exception:
                pass
            dead = m[26].ravel() if m.shape[0] > 26 else _np.zeros(nc)
            dmod = m[27].ravel() if m.shape[0] > 27 else _np.zeros(nc)
            for i in range(k):
                try:
                    is_dead = float(dead[i]) != 0.0
                except Exception:
                    is_dead = False
                if not is_dead:
                    estados[i] = "viva"
                else:
                    try:
                        code = int(float(dmod[i]))
                    except Exception:
                        code = -1
                    estados[i] = "apoptotica" if code == 100 else "necrotica"
                try:
                    vols[i] = float(m[4][i])
                except Exception:
                    pass
                try:
                    pres[i] = float(m[20][i])
                except Exception:
                    pass
                try:
                    tipos[i] = m[5][i]
                except Exception:
                    pass
        except Exception:
            pass
    vec = set()
    try:
        snaps_ord = sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))
        pos = snaps_ord.index(snap_path) if snap_path in snaps_ord else 0
        vec = leer_grafo(output_dir, pos, "neighbor")
    except Exception:
        vec = set()
    cels = []
    xs, ys = _np.asarray(r["x"], float), _np.asarray(r["y"], float)
    for i in range(n):
        cels.append({"id": ids[i] if i < len(ids) else i, "tipo": tipos[i],
                     "estado": estados[i], "x": float(xs[i]), "y": float(ys[i]), "z": 0.0,
                     "radio": float(rads[i]) if i < len(rads) else None,
                     "volumen": vols[i], "presion": pres[i]})
    return {"ok": True, "tiempo": tiempo, "celulas": cels, "contactos": len(vec)}


def _media(vals):
    v = [x for x in vals if x is not None]
    try:
        return sum(v) / len(v) if v else None
    except Exception:
        return None


def agregar_replica(output_dir, out_dir):
    """Escribe frames.csv y celulas.csv de una réplica. Retorna resumen."""
    os.makedirs(out_dir, exist_ok=True)
    f_frames = os.path.join(out_dir, "frames.csv")
    f_cels = os.path.join(out_dir, "celulas.csv")
    with open(f_frames, "w", newline="", encoding="utf-8") as ff, \
         open(f_cels, "w", newline="", encoding="utf-8") as fc:
        wf = csv.writer(ff)
        wc = csv.writer(fc)
        wf.writerow(["frame", "tiempo_min", "n", "vivas", "apoptoticas", "necroticas",
                     "desconocido", "vol_medio", "presion_media", "contactos"])
        wc.writerow(["frame", "tiempo_min", "id", "tipo", "estado", "x", "y", "z",
                     "radio", "volumen", "presion"])
        nframes = 0
        for i, snap in enumerate(_frames_de(output_dir)):
            fr = leer_frame(output_dir, snap)
            if not fr.get("ok"):
                wf.writerow([i, "", "", "", "", "", "", "", "", "sin datos"])
                continue
            cels = fr["celulas"]
            est = [c["estado"] for c in cels]
            wf.writerow([i, fr["tiempo"] if fr["tiempo"] is not None else "",
                         len(cels), est.count("viva"), est.count("apoptotica"),
                         est.count("necrotica"), est.count("desconocido"),
                         _media([c["volumen"] for c in cels]) or "",
                         _media([c["presion"] for c in cels]) or "", fr["contactos"]])
            for c in cels:
                wc.writerow([i, fr["tiempo"] if fr["tiempo"] is not None else "",
                             c["id"], c["tipo"], c["estado"], c["x"], c["y"], c["z"],
                             c["radio"], c["volumen"], c["presion"]])
            nframes += 1
    return {"ok": True, "frames": nframes, "frames_csv": f_frames, "celulas_csv": f_cels}


def agregar_experimento(db_path, experiment_id, out_base):
    """Consolida todas las réplicas con salida del experimento."""
    import sqlite3
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT run_number, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    runs = cur.fetchall()
    conn.close()
    os.makedirs(out_base, exist_ok=True)
    f_frames = os.path.join(out_base, "frames_todas.csv")
    f_cels = os.path.join(out_base, "celulas_todas.csv")
    rep_ok = 0
    with open(f_frames, "w", newline="", encoding="utf-8") as ff, \
         open(f_cels, "w", newline="", encoding="utf-8") as fc:
        wf = csv.writer(ff)
        wc = csv.writer(fc)
        wf.writerow(["replica", "frame", "tiempo_min", "n", "vivas", "apoptoticas",
                     "necroticas", "desconocido", "vol_medio", "presion_media", "contactos"])
        wc.writerow(["replica", "frame", "tiempo_min", "id", "tipo", "estado", "x", "y", "z",
                     "radio", "volumen", "presion"])
        for rnum, od in runs:
            cands = [os.path.join(od, "output"), od] if od else []
            src = next((d for d in cands if d and os.path.isdir(d)
                        and glob.glob(os.path.join(d, "snapshot*.svg"))), None)
            if not src:
                continue
            tmp = os.path.join(out_base, f"_rep{rnum}")
            r = agregar_replica(src, tmp)
            if not r.get("ok"):
                continue
            rep_ok += 1
            with open(r["frames_csv"], encoding="utf-8") as f:
                rd = csv.reader(f)
                next(rd, None)
                for row in rd:
                    wf.writerow([rnum] + row)
            with open(r["celulas_csv"], encoding="utf-8") as f:
                rd = csv.reader(f)
                next(rd, None)
                for row in rd:
                    wc.writerow([rnum] + row)
    import shutil
    for rnum, _od in runs:
        tmp = os.path.join(out_base, f"_rep{rnum}")
        if os.path.isdir(tmp):
            shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": True, "replicas": rep_ok, "frames_csv": f_frames, "celulas_csv": f_cels}
