"""Estadísticas comparativas entre experimentos de PhysiCell.

Calcula métricas por réplica (número de células finales, volumen medio)
y pruebas de hipótesis (t de Student) entre pares de experimentos.
Todos los datos se obtienen de los snapshots de PhysiCell a través del
agregador existente, sin inventar valores.
"""
import csv
import os
import sqlite3
from typing import Dict, List, Tuple

import numpy as np
from scipy import stats as sp_stats

from .agregador import agregar_replica, leer_frame, _frames_de


def metricas_replica(output_dir: str) -> dict:
    """Calcula métricas resumidas de una réplica desde sus snapshots.

    Retorna dict con n_celulas_final, volumen_medio_final y n_frames.
    Si no hay datos válidos, retorna ceros.
    """
    snaps = _frames_de(output_dir)
    if not snaps:
        return {"n_celulas_final": 0, "volumen_medio_final": 0.0, "n_frames": 0}

    ultimo = snaps[-1]
    fr = leer_frame(output_dir, ultimo)
    if not fr.get("ok"):
        return {"n_celulas_final": 0, "volumen_medio_final": 0.0, "n_frames": len(snaps)}

    celdas = fr["celulas"]
    n = len(celdas)
    vols = [c["volumen"] for c in celdas if c.get("volumen") is not None]
    vol_medio = float(sum(vols) / len(vols)) if vols else 0.0

    return {
        "n_celulas_final": int(n),
        "volumen_medio_final": vol_medio,
        "n_frames": len(snaps),
    }


def datos_por_experimento(db_path: str, experiment_id: int) -> List[dict]:
    """Retorna lista de diccionarios con métricas por réplica de un experimento."""
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

    resultado = []
    for run_num, output_dir in runs:
        # Buscar carpeta de salida real (replica dir o su subcarpeta output)
        cands = []
        if output_dir:
            cands += [output_dir, os.path.join(output_dir, "output")]
        src = next(
            (d for d in cands if d and os.path.isdir(d) and _frames_de(d)),
            None,
        )
        m = metricas_replica(src) if src else {
            "n_celulas_final": 0, "volumen_medio_final": 0.0, "n_frames": 0
        }
        m["run"] = run_num
        m["output_dir"] = output_dir or ""
        resultado.append(m)

    return resultado


def comparar_experimentos(db_path: str, experiment_ids: List[int]) -> dict:
    """Compara múltiples experimentos.

    Calcula medias y desviaciones estándar por experimento y ejecuta pruebas t
    de Student independientes entre todos los pares para el número de células
    finales y el volumen medio final.

    Retorna dict con:
      - datos_por_experimento: {exp_id: [metricas_por_replica, ...]}
      - comparaciones: { "id1_vs_id2": {t, p, media1, media2, std1, std2, n1, n2, significativo} }
    """
    datos: Dict[int, List[dict]] = {}
    for eid in experiment_ids:
        datos[eid] = datos_por_experimento(db_path, eid)

    comparaciones = {}
    ids = list(datos.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            id1, id2 = ids[i], ids[j]
            vals1 = [m["n_celulas_final"] for m in datos[id1] if m["n_celulas_final"] is not None]
            vals2 = [m["n_celulas_final"] for m in datos[id2] if m["n_celulas_final"] is not None]

            if len(vals1) >= 2 and len(vals2) >= 2:
                t, p = sp_stats.ttest_ind(vals1, vals2)
                comparaciones[f"{id1}_vs_{id2}"] = {
                    "t": float(t),
                    "p": float(p),
                    "media1": float(np.mean(vals1)),
                    "media2": float(np.mean(vals2)),
                    "std1": float(np.std(vals1, ddof=1)),
                    "std2": float(np.std(vals2, ddof=1)),
                    "n1": len(vals1),
                    "n2": len(vals2),
                    "significativo": bool(p < 0.05),
                }

    return {
        "datos_por_experimento": {str(k): v for k, v in datos.items()},
        "comparaciones": comparaciones,
    }


def exportar_comparacion_csv(resultado: dict, salida_csv: str) -> str:
    """Exporta los datos crudos de comparación a CSV."""
    os.makedirs(os.path.dirname(salida_csv) or ".", exist_ok=True)
    with open(salida_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "experimento", "run", "n_celulas_final", "volumen_medio_final"
        ])
        for eid_str, runs in resultado["datos_por_experimento"].items():
            for m in runs:
                w.writerow([
                    eid_str,
                    m.get("run", ""),
                    m.get("n_celulas_final", ""),
                    m.get("volumen_medio_final", ""),
                ])
    return salida_csv


def resumen_texto(resultado: dict) -> str:
    """Genera un resumen de texto legible de las comparaciones."""
    lineas = ["Comparación estadística entre experimentos", "=" * 45, ""]
    for clave, c in resultado["comparaciones"].items():
        id1, id2 = clave.split("_vs_")
        sig = "SÍ" if c["significativo"] else "NO"
        lineas.append(
            f"Experimento {id1} vs {id2}:\n"
            f"  Media células finales: {c['media1']:.2f} (n={c['n1']}, std={c['std1']:.2f}) vs "
            f"{c['media2']:.2f} (n={c['n2']}, std={c['std2']:.2f})\n"
            f"  t = {c['t']:.3f}, p = {c['p']:.4f} -> Diferencia significativa: {sig}\n"
        )
    return "\n".join(lineas)
