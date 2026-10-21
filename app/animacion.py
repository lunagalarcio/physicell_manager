"""Exportación de animaciones (película) de simulaciones PhysiCell.

Genera GIF o MP4 a partir de los snapshots SVG de una réplica.
Requiere matplotlib (ya dependencia del proyecto) y, para MP4, ffmpeg.
"""
import glob as _g
import os
import xml.etree.ElementTree as ET

import numpy as np

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.animation as animation
    import matplotlib.pyplot as plt
    from matplotlib.patches import Circle
    MATPLOTLIB_OK = True
except Exception:  # pragma: no cover
    MATPLOTLIB_OK = False

from .visor_widget import parse_snapshot_svg, leer_bounds


def _leer_frame_svg(snap_path: str, bounds: dict):
    """Extrae círculos de un snapshot SVG usando el parser del visor."""
    r = parse_snapshot_svg(snap_path, bounds)
    if not r.get("ok"):
        return None
    return r


def exportar_pelicula(
    output_dir: str,
    salida: str,
    formato: str = "gif",
    fps: int = 5,
    dpi: int = 100,
    mostrar_tiempo: bool = True,
) -> str:
    """Genera una animación (GIF o MP4) de los snapshots de una réplica.

    Parámetros:
        output_dir: carpeta que contiene los snapshot*.svg
        salida: ruta del archivo de salida (.gif o .mp4)
        formato: "gif" o "mp4"
        fps: frames por segundo
        dpi: resolución de la imagen generada
        mostrar_tiempo: si se muestra el tiempo simulado en cada frame

    Retorna la ruta del archivo generado.
    """
    if not MATPLOTLIB_OK:
        raise ImportError("matplotlib no está disponible para generar animaciones")

    snaps = sorted(_g.glob(os.path.join(output_dir, "snapshot*.svg")))
    if not snaps:
        raise ValueError("No se encontraron snapshot*.svg en la carpeta indicada")

    # Leer bounds del primer snapshot para fijar ejes
    bounds = None
    try:
        from .visor_widget import leer_bounds as _leer_bounds
        bounds = _leer_bounds(output_dir)
    except Exception:
        bounds = None

    # Precargar datos de todos los frames para evitar leer SVG repetidamente
    frames_data = []
    for p in snaps:
        r = _leer_frame_svg(p, bounds)
        if r:
            frames_data.append(r)
        else:
            frames_data.append(None)

    fig, ax = plt.subplots(figsize=(6, 6), dpi=dpi)
    ax.set_aspect("equal")
    if bounds:
        ax.set_xlim(bounds["xmin"], bounds["xmax"])
        ax.set_ylim(bounds["ymin"], bounds["ymax"])
    ax.set_facecolor("#17191B")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_visible(False)

    tiempo_txt = ax.text(
        0.02, 0.95, "", transform=ax.transAxes,
        color="white", fontsize=10, fontweight="bold",
        bbox=dict(facecolor="black", alpha=0.6, pad=3),
    )

    def _init():
        tiempo_txt.set_text("")
        return (tiempo_txt,)

    def _animar(i):
        ax.clear()
        ax.set_aspect("equal")
        if bounds:
            ax.set_xlim(bounds["xmin"], bounds["xmax"])
            ax.set_ylim(bounds["ymin"], bounds["ymax"])
        ax.set_facecolor("#17191B")
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)

        d = frames_data[i]
        if d and d.get("ok"):
            x = d.get("x", [])
            y = d.get("y", [])
            r = d.get("r", [])
            rgba = d.get("rgba", [])
            for k in range(len(x)):
                circ = Circle(
                    (x[k], y[k]),
                    r[k] if k < len(r) else 5.0,
                    facecolor=rgba[k] if k < len(rgba) else "lime",
                    edgecolor="black",
                    linewidth=0.4,
                    alpha=0.9,
                )
                ax.add_patch(circ)

        if mostrar_tiempo and d and d.get("time"):
            tiempo_txt.set_text(d["time"])
        else:
            tiempo_txt.set_text(f"Frame {i+1}/{len(snaps)}")
        return (tiempo_txt,)

    anim = animation.FuncAnimation(
        fig, _animar, frames=len(snaps),
        init_func=_init, interval=1000 / max(fps, 1), blit=False
    )

    os.makedirs(os.path.dirname(salida) or ".", exist_ok=True)

    if formato.lower() == "gif":
        writer = animation.PillowWriter(fps=fps)
        anim.save(salida, writer=writer, dpi=dpi)
    elif formato.lower() in ("mp4", "mov"):
        try:
            writer = animation.FFMpegWriter(fps=fps)
            anim.save(salida, writer=writer, dpi=dpi)
        except Exception as e:
            raise RuntimeError(
                "Para exportar MP4 se necesita ffmpeg instalado. "
                "Use formato 'gif' o instale ffmpeg."
            ) from e
    else:
        raise ValueError(f"Formato no soportado: {formato}. Use 'gif' o 'mp4'.")

    plt.close(fig)
    return salida
