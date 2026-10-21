"""Exportación de datos de PhysiCell a formatos científicos estándar.

Permite generar archivos .mat (MATLAB), HDF5 y JSON estructurado a partir
de los datos consolidados de un experimento (réplicas y células).
"""
import csv
import glob as _g
import json
import os
import sqlite3
import subprocess
import tempfile
from typing import Dict, List, Optional

import numpy as np
from scipy import io as sio

try:
    import h5py
    H5PY_OK = True
except Exception:  # pragma: no cover - dependencia opcional
    H5PY_OK = False

from .agregador import agregar_experimento, leer_frame, _frames_de  # noqa: F401
from .visor_widget import listar_snapshots, parse_snapshot_svg, leer_bounds


def _tiene_ffmpeg() -> bool:
    """Verifica si ffmpeg está disponible en el sistema."""
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
        return True
    except Exception:
        return False


def _unir_frames_a_video(frames_png: List[str], salida_mp4: str, fps: int = 1) -> dict:
    """Une una lista de imágenes PNG en un video MP4 usando ffmpeg.

    Si ffmpeg no está disponible, retorna error con instrucciones.
    """
    if not _tiene_ffmpeg():
        return {
            "ok": False,
            "error": (
                "ffmpeg no está instalado en el sistema. "
                "Instálelo y asegúrese de que esté en el PATH del sistema.\n"
                "Windows: descargue de https://ffmpeg.org y agregue bin/ al PATH.\n"
                "Linux: sudo apt-get install ffmpeg\n"
                "macOS: brew install ffmpeg"
            ),
        }
    os.makedirs(os.path.dirname(salida_mp4) or ".", exist_ok=True)
    # Crear archivo de lista para ffmpeg (concat demuxer)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as lst:
        for fp in frames_png:
            lst.write(f"file '{fp}'\n")
        lista_path = lst.name
    try:
        cmd = [
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-r", str(fps), "-i", lista_path,
            "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            salida_mp4,
        ]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if r.returncode != 0:
            return {"ok": False, "error": r.stderr or "ffmpeg falló sin mensaje"}
        return {"ok": True, "path": salida_mp4, "frames": len(frames_png), "fps": fps}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Timeout generando video (más de 5 minutos)"}
    except Exception as e:
        return {"ok": False, "error": str(e)}
    finally:
        try:
            os.unlink(lista_path)
        except Exception:
            pass
        for fp in frames_png:
            try:
                os.unlink(fp)
            except Exception:
                pass


def _renderizar_frame_2d_png(output_dir: str, idx: int, tmp_png: str,
                             show_substrato: bool = True,
                             show_vecinos: bool = True,
                             show_uniones: bool = True,
                             filtro_tipo: str = "Todos") -> dict:
    """Renderiza un frame 2D de PhysiCell a archivo PNG usando matplotlib."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    from matplotlib.collections import PatchCollection, LineCollection
    import matplotlib.colors as mplc

    snaps = listar_snapshots(output_dir)
    if not snaps:
        return {"ok": False, "error": "Sin snapshot*.svg"}
    idx = max(0, min(len(snaps) - 1, idx))
    bounds = leer_bounds(output_dir)
    r = parse_snapshot_svg(snaps[idx], bounds)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "?")}

    fig, ax = plt.subplots(figsize=(6, 4), dpi=150)
    x, y, rv, rgba = r["x"], r["y"], r["r"], r["rgba"]
    tipos = list(r.get("types", []))

    if filtro_tipo and filtro_tipo != "Todos" and len(tipos) == len(x):
        mask = np.array([str(t) == filtro_tipo for t in tipos])
        x, y, rv, rgba = x[mask], y[mask], rv[mask], rgba[mask]

    if len(x):
        patches = [Circle((x_[0], y_[0]), s_[0]) for x_, y_, s_ in
                   zip(np.atleast_1d(x), np.atleast_1d(y), np.atleast_1d(rv))]
        col = PatchCollection(patches, facecolor=rgba, edgecolor="black", linewidth=0.5)
        ax.add_collection(col)

    if bounds:
        ax.set_xlim(bounds["xmin"], bounds["xmax"])
        ax.set_ylim(bounds["ymin"], bounds["ymax"])
    ax.set_aspect("equal")
    ax.set_facecolor("white")
    ax.set_title(f"{r.get('time', '')} ({r.get('n', 0)} agents)", fontsize=9)
    ax.axis("off")
    fig.tight_layout(pad=0.2)
    fig.savefig(tmp_png, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return {"ok": True, "path": tmp_png, "idx": idx, "time": r.get("time", "")}


def generar_video_2d(output_dir: str, salida_mp4: str, fps: int = 1,
                     filtro_tipo: str = "Todos") -> dict:
    """Genera un video MP4 2D a partir de los snapshots SVG de una réplica.

    Renderiza cada frame con matplotlib y los une con ffmpeg.
    """
    if not output_dir or not os.path.isdir(output_dir):
        return {"ok": False, "error": "Carpeta de salida no válida"}
    snaps = listar_snapshots(output_dir)
    if not snaps:
        return {"ok": False, "error": "Sin snapshot*.svg en la carpeta de salida"}

    frames_png = []
    tmpdir = tempfile.mkdtemp(prefix="pc_video_2d_")
    try:
        for i in range(len(snaps)):
            tmp_png = os.path.join(tmpdir, f"frame_{i:06d}.png")
            r = _renderizar_frame_2d_png(output_dir, i, tmp_png, filtro_tipo=filtro_tipo)
            if r.get("ok"):
                frames_png.append(tmp_png)
            else:
                return {"ok": False, "error": f"Error renderizando frame {i}: {r.get('error')}"}

        if not frames_png:
            return {"ok": False, "error": "No se renderizó ningún frame"}

        return _unir_frames_a_video(frames_png, salida_mp4, fps=fps)
    finally:
        # Limpiar directorio temporal de frames PNG intermedios (se borran dentro de _unir_frames_a_video)
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass


def _renderizar_frame_3d_vtk_png(output_dir: str, idx: int, tmp_png: str) -> dict:
    """Renderiza un frame 3D VTK a archivo PNG usando PyVista."""
    try:
        import pyvista as pv
    except Exception:
        return {"ok": False, "error": "PyVista no está instalado"}

    from .visor3d_vtk import _snapshots, leer_estado_celular

    snaps = _snapshots(output_dir)
    if not snaps:
        return {"ok": False, "error": "Sin snapshot*.svg"}
    idx = max(0, min(len(snaps) - 1, idx))

    estado = leer_estado_celular(output_dir, idx)
    if not estado.get("ok"):
        return {"ok": False, "error": estado.get("error", "?")}

    x = np.array(estado.get("x", []), dtype=float)
    y = np.array(estado.get("y", []), dtype=float)
    z = np.array(estado.get("z", []), dtype=float)
    r = np.array(estado.get("r", []), dtype=float)
    estados = estado.get("estados", ["desconocido"] * len(x))
    tipos = estado.get("tipos", [""] * len(x))

    plotter = pv.Plotter(off_screen=True, window_size=[800, 600])
    plotter.set_background("white")

    if len(x):
        # Mapear estados a colores
        color_map = {
            "viva": "#4ADE80",
            "apoptotica": "#FACC15",
            "necrotica": "#EF4444",
        }
        colores = [color_map.get(e, "#CCCCCC") for e in estados]

        # Glyph de esferas por grupo de radio para rendimiento
        unique_r = sorted(set(round(float(v), 2) for v in r)) if len(r) else []
        for rad in unique_r:
            mask = np.array([round(float(v), 2) == rad for v in r])
            if not mask.any():
                continue
            xs = x[mask]; ys = y[mask]; zs = z[mask]
            cs = [colores[i] for i in np.where(mask)[0]]
            sphere = pv.Sphere(radius=float(rad))
            # Crear nube de puntos y usar glyph
            pts = pv.PolyData(np.column_stack([xs, ys, zs]))
            pts["color"] = cs
            glyph = pts.glyph(geom=sphere, scale=False, tolerance=0.01)
            plotter.add_mesh(glyph, color=None, scalars=None, show_scalar_bar=False,
                             rgb=True, lighting=True)

    plotter.camera_position = "iso"
    plotter.enable_anti_aliasing()
    plotter.screenshot(tmp_png)
    plotter.close()
    return {"ok": True, "path": tmp_png, "idx": idx, "n": len(x)}


def generar_video_3d_vtk(output_dir: str, salida_mp4: str, fps: int = 1) -> dict:
    """Genera un video MP4 3D VTK a partir de los snapshots de una réplica.

    Renderiza cada frame con PyVista/VTK y los une con ffmpeg.
    """
    if not output_dir or not os.path.isdir(output_dir):
        return {"ok": False, "error": "Carpeta de salida no válida"}
    try:
        import pyvista as pv  # noqa: F401
    except Exception:
        return {"ok": False, "error": "PyVista no está instalado"}

    from .visor3d_vtk import _snapshots
    snaps = _snapshots(output_dir)
    if not snaps:
        return {"ok": False, "error": "Sin snapshot*.svg en la carpeta de salida"}

    frames_png = []
    tmpdir = tempfile.mkdtemp(prefix="pc_video_3d_")
    try:
        for i in range(len(snaps)):
            tmp_png = os.path.join(tmpdir, f"frame_{i:06d}.png")
            r = _renderizar_frame_3d_vtk_png(output_dir, i, tmp_png)
            if r.get("ok"):
                frames_png.append(tmp_png)
            else:
                return {"ok": False, "error": f"Error renderizando frame {i}: {r.get('error')}"}

        if not frames_png:
            return {"ok": False, "error": "No se renderizó ningún frame"}

        return _unir_frames_a_video(frames_png, salida_mp4, fps=fps)
    finally:
        try:
            os.rmdir(tmpdir)
        except Exception:
            pass


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
