#!/usr/bin/env python3
"""Consolida salidas PhysiCell dispersas por frame en tablas listas para análisis
y dataset científico. Incluye todas las variables del .mat y del entorno.

Por réplica genera:
- frames.csv: métricas por frame (tiempo, n células, estados, vol/pres medios, contactos,
  + variables adicionales del .mat: nrad, dmod, ctype, adh, contactos detallados).
- celulas.csv: una fila por célula y frame con TODAS las variables disponibles del .mat:
  id, tipo, estado, posición, radio, volumen, presión, nuc_real, daño, migración,
  adherencia, contactos, + metadatos de frame.

Por experimento agrega todas sus réplicas con columna replica/run.
Incluye también datos de micromatrices.dat/mat para sustrato/entorno.
Marca 'sin datos' cuando un archivo no existe, no omite filas.
"""
import os
import glob
import csv
import numpy as np

from .visor_widget import detectar_fila_nrad


def _frames_de(output_dir):
    """Encuentra todos los archivos de snapshot SVG por frame."""
    snaps = sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))
    return snaps


def _indice_frame(path):
    import re
    m = re.search(r"(\d{8})", os.path.basename(path))
    return m.group(1) if m else None


def _cargar_cells_mat(output_dir, tag=None):
    """Intenta cargar cells.mat y devuelve arrays de todas las variables útiles."""
    import scipy.io as _sio
    # Buscar cells.mat con o sin tag de frame
    patterns = []
    if tag:
        patterns.append(os.path.join(output_dir, f"output{tag}_cells.mat"))
    patterns.append(os.path.join(output_dir, "cells.mat"))
    patterns.append(os.path.join(output_dir, "cells_0000.mat"))
    patterns.append(os.path.join(output_dir, "cells_0001.mat"))
    mats = []
    for p in patterns:
        if os.path.isfile(p):
            mats.append(p)
    if not mats:
        return None
    # Usar el primero que exista y tenga datos
    try:
        m = _sio.loadmat(mats[0])["cells"]
        ncols = m.shape[1]
        # Extraer todas las filas conocidas del .mat de PhysiCell
        # Fila 0: IDs, 1: x, 2: y, 3: z, 4: vol, 5: ctype, 6: cycle, 7: ...
        # Fila 8: nrad (radio nuclear real), 9: ..., 20: pres, 26: dead, 27: dmod
        out = {}
        # IDs
        try:
            ids_raw = m[0].ravel().tolist() if m.shape[0] > 0 else list(range(ncols))
            out["ids"] = [int(v) for v in ids_raw]
        except Exception:
            out["ids"] = list(range(ncols))
        # Posiciones
        try:
            out["x"] = [float(v) for v in m[1].ravel().tolist()] if m.shape[0] > 1 else [None] * ncols
        except Exception:
            out["x"] = [None] * ncols
        try:
            out["y"] = [float(v) for v in m[2].ravel().tolist()] if m.shape[0] > 2 else [None] * ncols
        except Exception:
            out["y"] = [None] * ncols
        try:
            out["z"] = [float(v) for v in m[3].ravel().tolist()] if m.shape[0] > 3 else [None] * ncols
        except Exception:
            out["z"] = [None] * ncols
        # Volumen
        try:
            out["vols"] = [float(v) for v in m[4].ravel().tolist()] if m.shape[0] > 4 else [None] * ncols
        except Exception:
            out["vols"] = [None] * ncols
        # Tipo celular
        try:
            out["ctype"] = [int(v) if v is not None else None for v in m[5].ravel().tolist()] if m.shape[0] > 5 else [None] * ncols
        except Exception:
            out["ctype"] = [None] * ncols
        # Phase del ciclo
        try:
            out["cycle"] = [float(v) if v is not None else None for v in m[6].ravel().tolist()] if m.shape[0] > 6 else [None] * ncols
        except Exception:
            out["cycle"] = [None] * ncols
        # Radio nuclear real (nrad): detectar fila válida en lugar de asumir índice fijo
        out["nrad"] = detectar_fila_nrad(m, ncols) if m.shape[0] > 0 else [None] * ncols
        # Presión
        try:
            out["pres"] = [float(v) for v in m[20].ravel().tolist()] if m.shape[0] > 20 else [None] * ncols
        except Exception:
            out["pres"] = [None] * ncols
        # Daño
        try:
            out["dano"] = [float(v) for v in m[27].ravel().tolist()] if m.shape[0] > 27 else [None] * ncols
        except Exception:
            out["dano"] = [None] * ncols
        # Adhesión
        try:
            out["adh"] = [float(v) for v in m[31].ravel().tolist()] if m.shape[0] > 31 else [None] * ncols
        except Exception:
            out["adh"] = [None] * ncols
        # Contactos por célula
        try:
            out["contactos_cel"] = [float(v) for v in m[36].ravel().tolist()] if m.shape[0] > 36 else [None] * ncols
        except Exception:
            out["contactos_cel"] = [None] * ncols
        # Fila 26: dead (1=muerta, 0=viva)
        try:
            out["dead"] = [float(v) for v in m[26].ravel().tolist()] if m.shape[0] > 26 else [None] * ncols
        except Exception:
            out["dead"] = [None] * ncols
        # Fila 27: dmod (código de muerte: 100=apoptosis, otros=necrosis)
        try:
            out["dmod"] = [float(v) for v in m[27].ravel().tolist()] if m.shape[0] > 27 else [None] * ncols
        except Exception:
            out["dmod"] = [None] * ncols
        return out
    except Exception:
        return None


def _leer_estado_celula(vals, key="viva"):
    """Convierte valores del .mat a estado legible."""
    try:
        v = float(vals) if vals is not None else 0.0
    except Exception:
        v = 0.0
    if v == 0.0:
        return "viva"
    # dmod: 100=apoptosis, demás=necrosis
    try:
        c = int(float(vals))
    except Exception:
        c = -1
    return "apoptotica" if c == 100 else "necrotica"


def leer_frame(output_dir, snap_path):
    """Métricas y células de un frame cruzando SVG + cells.mat + XML + grafos.
    Ahora incluye TODAS las variables del .mat disponibles."""
    import numpy as _np
    from .visor_widget import parse_snapshot_svg, leer_bounds, leer_grafo
    bounds = leer_bounds(output_dir)
    r = parse_snapshot_svg(snap_path, bounds)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error")}
    n = len(r["x"])
    tag = _indice_frame(snap_path)
    cells_mat = _cargar_cells_mat(output_dir, tag)
    xmls = sorted(glob.glob(os.path.join(output_dir, f"output{tag}.xml"))) if tag else []
    tiempo = None
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
    # Datos defaults por si no hay .mat
    ids = list(range(n))
    tipos = [None] * n
    estados = ["desconocido"] * n
    vols = [None] * n
    pres = [None] * n
    nrad = [None] * n  # radio nuclear real
    danos = [None] * n
    adhs = [None] * n
    contactos_cel = [None] * n
    ciclos = [None] * n
    dead_vals = [None] * n
    dmod_vals = [None] * n
    # Cruzar con cells.mat si está disponible
    if cells_mat and cells_mat.get("ok"):
        d = cells_mat
        ncols = len(d.get("ids", [n]))
        k = min(n, ncols)
        # IDs from .mat
        ids = d.get("ids", list(range(n)))[:k] + list(range(k, n))
        # States from dead/dmod
        for i in range(k):
            dv = d.get("dead", [None])[i] if i < len(d.get("dead", [])) else None
            dmod_v = d.get("dmod", [None])[i] if i < len(d.get("dmod", [])) else None
            if dv is not None and float(dv) != 0.0:
                estados[i] = _leer_estado_celula(dmod_v)
            else:
                estados[i] = "viva"
        # Volume, pressure, and other variables from .mat
        var_map = {
            "vols": vols, "pres": pres, "nrad": nrad,
            "dano": danos, "adh": adhs, "contactos_cel": contactos_cel,
            "cycle": ciclos
        }
        for varname, target in var_map.items():
            src = d.get(varname, [None] * ncols)
            for i in range(k):
                target[i] = src[i] if i < len(src) else None
        # Dead values for reference
        dead_vals = d.get("dead", [None] * ncols)[:k] + [None] * max(0, n - k)
        dmod_vals = d.get("dmod", [None] * ncols)[:k] + [None] * max(0, n - k)
    # Gráfico/Contactos desde SVG
    vec = set()
    try:
        snaps_ord = sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))
        pos = snaps_ord.index(snap_path) if snap_path in snaps_ord else 0
        vec = leer_grafo(output_dir, pos, "neighbor")
    except Exception:
        vec = set()
    # Construir registros de célula
    cels = []
    xs = _np.asarray(r["x"], float) if r.get("x") is not None and len(r.get("x", [])) > 0 else _np.zeros(n)
    ys = _np.asarray(r["y"], float) if r.get("y") is not None and len(r.get("y", [])) > 0 else _np.zeros(n)
    for i in range(n):
        ctype_val = tipos[i] if i < len(tipos) else None
        cels.append({
            "id": ids[i] if i < len(ids) else i,
            "tipo": ctype_val,
            "estado": estados[i],
            "x": float(xs[i]),
            "y": float(ys[i]),
            "z": 0.0,
            "radio": float(r["r"][i]) if r.get("r") is not None and len(r.get("r", [])) > i else None,
            "volumen": vols[i],
            "presion": pres[i],
            "nuc_real": nrad[i],
            "dano": danos[i],
            "adhesion": adhs[i],
            "contactos_celula": contactos_cel[i],
            "ciclo": ciclos[i],
            "dead_val": dead_vals[i] if i < len(dead_vals) else None,
            "dmod_val": dmod_vals[i] if i < len(dmod_vals) else None
        })
    return {"ok": True, "tiempo": tiempo, "celulas": cels, "contactos": len(vec),
            "n_frames_total": n, "metadatos": cells_mat}


def _media(vals):
    v = [x for x in vals if x is not None]
    try:
        return sum(v) / len(v) if v else None
    except Exception:
        return None


def agregar_replica(output_dir, out_dir):
    """Escribe frames.csv y celulas.csv de una réplica. Retorna resumen.
    Ahora incluye todas las variables PhysiCell disponibles."""
    os.makedirs(out_dir, exist_ok=True)
    f_frames = os.path.join(out_dir, "frames.csv")
    f_cels = os.path.join(out_dir, "celulas.csv")
    with open(f_frames, "w", newline="", encoding="utf-8") as ff, \
         open(f_cels, "w", newline="", encoding="utf-8") as fc:
        wf = csv.writer(ff)
        wc = csv.writer(fc)
        # --- frames.csv: métricas por frame ---
        wf.writerow([
            "frame", "tiempo_min", "n_total", "n_vivas", "n_apoptoticas", "n_necroticas",
            "n_desconocido", "vol_medio", "presion_media", "contactos_grafo",
            "vol_medio_vivas", "presion_media_vivas", "vol_medio_apoptoticas",
            "presion_media_apoptoticas", "n_celulas_con_datos_mat"
        ])
        # --- celulas.csv: una por célula TODAS las variables ---
        # columns: frame, tiempo, id, tipo, estado, x, y, z, radio, volumen, presion,
        # nuc_real, dano, adhesion, contactos_celula, ciclo, dead_val, dmod_val
        wc.writerow([
            "frame", "tiempo_min", "id", "tipo", "estado", "x", "y", "z",
            "radio", "volumen", "presion", "nuc_real", "dano", "adhesion",
            "contactos_celula", "ciclo", "dead_val", "dmod_val"
        ])
        nframes = 0
        for i, snap in enumerate(_frames_de(output_dir)):
            fr = leer_frame(output_dir, snap)
            if not fr.get("ok"):
                # Fila de frame sin datos
                wf.writerow([i, "", "", "", "", "", "", "", "", "",
                             "", "", "", "", "", "", ""])
                # Filas de células con "sin datos" - poner None en todas menos frame
                n_total = fr.get("n_frames_total", 0)
                for _ in range(n_total):
                    wc.writerow(["", "", "", "", "", "", "", "", "", "", "", "", "", "", "", ""])
                continue
            cels = fr["celulas"]
            est = [c["estado"] for c in cels]
            n_total = fr.get("n_frames_total", len(cels))
            n_vivas = est.count("viva")
            n_apop = est.count("apoptotica")
            n_nec = est.count("necrotica")
            n_descon = est.count("desconocido")
            # Medias generales
            vol_media = _media([c["volumen"] for c in cels]) if cels else None
            pres_media = _media([c["presion"] for c in cels]) if cels else None
            # Medias por estado
            cels_vivas = [c for c in cels if c["estado"] == "viva"]
            cels_apop = [c for c in cels if c["estado"] == "apoptotica"]
            cels_nec = [c for c in cels if c["estado"] == "necrotica"]
            vol_media_v = _media([c["volumen"] for c in cels_vivas]) if cels_vivas else None
            pres_media_v = _media([c["presion"] for c in cels_vivas]) if cels_vivas else None
            vol_media_n = _media([c["volumen"] for c in cels_apop]) if cels_apop else None
            pres_media_n = _media([c["presion"] for c in cels_apop]) if cels_apop else None
            # Cuántas tienen datos del .mat
            n_con_mat = sum(1 for c in cels if c.get("dead_val") is not None or c.get("volumen") is not None)
            # Medias de variables específicas por estado
            mv_v = _media([c["volumen"] for c in cels_vivas]) if cels_vivas else None
            pr_v = _media([c["presion"] for c in cels_vivas]) if cels_vivas else None
            mv_n = _media([c["volumen"] for c in cels_apop]) if cels_apop else None
            pr_n = _media([c["presion"] for c in cels_apop]) if cels_apop else None
            wf.writerow([i, fr["tiempo"] if fr["tiempo"] is not None else "",
                         n_total, n_vivas, n_apop, n_descon,
                         vol_media, pres_media, fr["contactos"],
                         vol_media_v, pres_media_v, vol_media_n, pres_media_n,
                         n_con_mat])
            for c in cels:
                wc.writerow([i, fr["tiempo"] if fr["tiempo"] is not None else "",
                             c["id"], c["tipo"], c["estado"], c["x"], c["y"], c["z"],
                             c["radio"], c["volumen"], c["presion"],
                             c.get("nuc_real"), c.get("dano"), c.get("adhesion"),
                             c.get("contactos_celula"), c.get("ciclo"),
                             c.get("dead_val"), c.get("dmod_val")])
            nframes += 1
    return {"ok": True, "frames": nframes, "frames_csv": f_frames, "celulas_csv": f_cels}


def agregar_experimento(db_path, experiment_id, out_base):
    """Consolida todas las réplicas con salida del experimento.
    Genera frames_todas.csv y celulas_todas.csv con columna replica/run."""
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
        wf.writerow(["replica", "frame", "tiempo_min", "n_total", "n_vivas", "n_apoptoticas",
                     "n_necroticas", "n_desconocido", "vol_medio", "presion_media",
                     "contactos_grafo", "vol_medio_vivas", "presion_media_vivas",
                     "vol_medio_apoptoticas", "presion_media_apoptoticas",
                     "n_celulas_con_datos_mat"])
        wc.writerow(["replica", "frame", "tiempo_min", "id", "tipo", "estado", "x", "y", "z",
                     "radio", "volumen", "presion", "nuc_real", "dano", "adhesion",
                     "contactos_celula", "ciclo", "dead_val", "dmod_val"])
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
            # Leer y agregar rows al consolidated
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