"""Exportación de datos de PhysiCell a formatos científicos estándar.

Permite generar archivos .mat (MATLAB), HDF5 y JSON estructurado a partir
de los datos consolidados de un experimento (réplicas y células).
"""
import csv
import json
import os
import sqlite3
from typing import Dict, List, Optional

import numpy as np
from scipy import io as sio

try:
    import h5py
    H5PY_OK = True
except Exception:  # pragma: no cover - dependencia opcional
    H5PY_OK = False

from .agregador import agregar_exporimento if False else agregar_experimento  # noqa: F401
from .agregador import agregar_experimento, leer_frame, _frames_de  # noqa: F401


def _obtener_datos_experimento(db_path: str, experiment_id: int) -> dict:
    """Recopila datos de todas las réplicas de un experimento."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, title, description, config_xml_path FROM experiments WHERE id=?",
            (experiment_id,),
        )
        exp = cur.fetchone()
        if not exp:
            conn.close()
            return {}
        exp_id, title, desc, config_xml = exp

        cur.execute(
            "SELECT run_number, status, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number",
            (experiment_id,),
        )
        runs = cur.fetchall()
    except Exception:
        conn.close()
        return {}
    conn.close()

    replicas = []
    for run_num, status, output_dir in runs:
        cands = []
        if output_dir:
            cands += [output_dir, os.path.join(output_dir, "output")]
        src = next(
            (d for d in cands if d and os.path.isdir(d)),
            None,
        )
        metricas = {"run": run_num, "status": status, "output_dir": output_dir or ""}
        if src:
            snaps = _frames_de(src)
            ultimo = snaps[-1] if snaps else None
            if ultimo:
                fr = leer_frame(src, ultimo)
                if fr.get("ok"):
                    celdas = fr["celulas"]
                    vols = [c["volumen"] for c in celdas if c.get("volumen") is not None]
                    metricas.update({
                        "n_celulas": len(celdas),
                        "volumen_medio": float(sum(vols) / len(vols)) if vols else 0.0,
                        "n_frames": len(snaps),
                    })
        replicas.append(metricas)

    return {
        "experimento": {
            "id": exp_id,
            "title": title,
            "description": desc,
            "config_xml": config_xml,
        },
        "replicas": replicas,
    }


def exportar_mat(db_path: str, experiment_id: int, salida_mat: str) -> str:
    """Exporta datos de un experimento a archivo .mat de MATLAB."""
    datos = _obtener_datos_experimento(db_path, experiment_id)
    if not datos:
        raise ValueError("Experimento no encontrado o sin datos")

    mdict = {
        "experimento_id": np.array([datos["experimento"]["id"]]),
        "experimento_titulo": datos["experimento"]["title"],
        "n_replicas": np.array([len(datos["replicas"])]),
    }

    for i, rep in enumerate(datos["replicas"]):
        prefix = f"rep{i+1}"
        mdict[f"{prefix}_run"] = np.array([rep.get("run", 0)])
        mdict[f"{prefix}_n_celulas"] = np.array([rep.get("n_celulas", 0)])
        mdict[f"{prefix}_volumen_medio"] = np.array([rep.get("volumen_medio", 0.0)])

    os.makedirs(os.path.dirname(salida_mat) or ".", exist_ok=True)
    sio.savemat(salida_mat, mdict)
    return salida_mat


def exportar_hdf5(db_path: str, experiment_id: int, salida_h5: str) -> str:
    """Exporta datos de un experimento a HDF5 (requiere h5py)."""
    if not H5PY_OK:  # pragma: no cover - depende de dependencia opcional
        raise ImportError(
            "h5py no está instalado. Instálelo con: pip install h5py"
        )

    import h5py  # type: ignore

    datos = _obtener_datos_experimento(db_path, experiment_id)
    if not datos:
        raise ValueError("Experimento no encontrado o sin datos")

    os.makedirs(os.path.dirname(salida_h5) or ".", exist_ok=True)
    with h5py.File(salida_h5, "w") as f:
        f.attrs["experimento_id"] = datos["experimento"]["id"]
        f.attrs["titulo"] = datos["experimento"]["title"].encode("utf-8")
        f.attrs["n_replicas"] = len(datos["replicas"])

        grp = f.create_group("replicas")
        for i, rep in enumerate(datos["replicas"]):
            rg = grp.create_group(f"rep{i+1}")
            rg.attrs["run"] = rep.get("run", 0)
            rg.attrs["status"] = rep.get("status", "").encode("utf-8")
            rg.attrs["n_celulas"] = rep.get("n_celulas", 0)
            rg.attrs["volumen_medio"] = rep.get("volumen_medio", 0.0)

    return salida_h5


def exportar_json_estructurado(db_path: str, experiment_id: int, salida_json: str) -> str:
    """Exporta JSON estructurado con metadatos y datos celulares por réplica."""
    datos = _obtener_datos_experimento(db_path, experiment_id)
    if not datos:
        raise ValueError("Experimento no encontrado o sin datos")

    os.makedirs(os.path.dirname(salida_json) or ".", exist_ok=True)
    with open(salida_json, "w", encoding="utf-8") as f:
        json.dump(datos, f, indent=2, ensure_ascii=False)
    return salida_json


def exportar_datos_celulares_csv(
    db_path: str, experiment_id: int, salida_csv: str
) -> str:
    """Exporta una tabla plana con todas las células de todas las réplicas.

    Requiere que las réplicas hayan sido consolidadas previamente con
    app.agregador.agregar_experimento o que existan los snapshots.
    """
    import glob as _g

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT run_number, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number",
            (experiment_id,),
        )
        runs = cur.fetchall()
    except Exception:
        runs = []
    conn.close()

    os.makedirs(os.path.dirname(salida_csv) or ".", exist_ok=True)
    with open(salida_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "experimento", "run", "frame", "tiempo_min", "id", "tipo", "estado",
            "x", "y", "z", "radio", "volumen", "presion", "nuc_real",
            "danho", "adhesion", "contactos_celula", "ciclo",
        ])

        for run_num, output_dir in runs:
            cands = []
            if output_dir:
                cands += [output_dir, os.path.join(output_dir, "output")]
            src = next(
                (d for d in cands if d and os.path.isdir(d)),
                None,
            )
            if not src:
                continue
            snaps = sorted(_g.glob(os.path.join(src, "snapshot*.svg")))
            for i, snap in enumerate(snaps):
                fr = leer_frame(src, snap)
                if not fr.get("ok"):
                    continue
                for c in fr["celulas"]:
                    w.writerow([
                        experiment_id, run_num, i,
                        fr.get("tiempo", ""),
                        c.get("id"), c.get("tipo"), c.get("estado"),
                        c.get("x"), c.get("y"), c.get("z"),
                        c.get("radio"), c.get("volumen"), c.get("presion"),
                        c.get("nuc_real"), c.get("danho"), c.get("adhesion"),
                        c.get("contactos_celula"), c.get("ciclo"),
                    ])
    return salida_csv
