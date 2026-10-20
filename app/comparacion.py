#!/usr/bin/env python3
"""Comparacion entre replicas/escenarios con graficos (sin analisis avanzado)."""
import os
import glob
import sqlite3


def n_celulas_final(output_dir):
    """Cuenta celulas del ultimo snapshot o final_cells.mat."""
    if not output_dir or not os.path.isdir(output_dir):
        return None
    # prefiere final_cells.mat
    for cand in (os.path.join(output_dir, "final_cells.mat"),
                 os.path.join(output_dir, "output", "final_cells.mat")):
        if os.path.isfile(cand):
            try:
                import scipy.io
                return int(scipy.io.loadmat(cand)["cells"].shape[1])
            except Exception:
                pass
    snaps = sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))
    if not snaps:
        snaps = sorted(glob.glob(os.path.join(output_dir, "output", "snapshot*.svg")))
    if snaps:
        # cuenta aproximada via parse rapido
        try:
            import xml.etree.ElementTree as ET
            root = ET.parse(snaps[-1]).getroot()
            for ch in root:
                if "id" in ch.attrib:
                    for c2 in ch:
                        if c2.attrib.get("id") == "cells":
                            return len(list(c2))
        except Exception:
            pass
    return None


def datos_comparacion(db_path, experiment_id):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT run_number, status, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    runs = cur.fetchall()
    conn.close()
    filas = []
    for rnum, st, od in runs:
        # output_dir puede ser replica dir o base; busca output real
        cand_dirs = []
        if od:
            cand_dirs += [od, os.path.join(od, "output")]
        for d in cand_dirs:
            n = n_celulas_final(d)
            if n is not None:
                break
        else:
            n = None
        filas.append({"run": rnum, "status": st, "n_final": n, "output": od})
    return filas


def generar_grafica_comparacion(db_path, experiment_id, out_png):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    filas = datos_comparacion(db_path, experiment_id)
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    runs = [f["run"] for f in filas]
    vals = [f["n_final"] if f["n_final"] is not None else 0 for f in filas]
    faltan = [f for f in filas if f["n_final"] is None]
    plt.figure(figsize=(7, 3.5))
    plt.bar(runs, vals)
    plt.xlabel("Replica / run")
    plt.ylabel("Celulas finales")
    plt.title(f"Comparacion experimento {experiment_id} ({len(filas)} runs)")
    plt.tight_layout()
    plt.savefig(out_png, dpi=110)
    plt.close()
    return {"ok": True, "path": out_png, "filas": filas, "sin_datos": len(faltan)}


def generar_grafica_temporal(output_dir, out_png):
    """Células por frame a lo largo del tiempo (datos reales de snapshots)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import glob as _g
    if not output_dir or not os.path.isdir(output_dir):
        return {"ok": False, "error": "Sin carpeta de salida"}
    snaps = sorted(_g.glob(os.path.join(output_dir, "snapshot*.svg")))
    if not snaps:
        return {"ok": False, "error": "Sin snapshots"}
    from .visor_widget import parse_snapshot_svg, leer_bounds
    b = leer_bounds(os.path.dirname(output_dir) if os.path.basename(output_dir) == "output" else output_dir)
    if b is None:
        b = leer_bounds(output_dir)
    xs, ns, ts = [], [], []
    for i, p in enumerate(snaps):
        try:
            r = parse_snapshot_svg(p, b)
            if r.get("ok"):
                xs.append(i)
                ns.append(r.get("n", 0))
                ts.append(r.get("time", ""))
        except Exception:
            pass
    if not xs:
        return {"ok": False, "error": "No se pudieron leer snapshots"}
    os.makedirs(os.path.dirname(out_png) or ".", exist_ok=True)
    plt.figure(figsize=(7, 3.2))
    plt.plot(xs, ns, marker="o")
    plt.xlabel("Frame")
    plt.ylabel("Células")
    plt.title(f"Evolución temporal ({len(xs)} frames)")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(out_png, dpi=110)
    plt.close()
    return {"ok": True, "path": out_png, "frames": len(xs), "tiempos": ts}
