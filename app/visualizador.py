#!/usr/bin/env python3
"""Consulta y visualizacion de resultados PhysiCell sin analisis avanzado."""
import os
import glob
import xml.etree.ElementTree as ET


def listar_frames(output_dir):
    """Retorna dict con svg, outputs xml, mats ordenados."""
    if not output_dir or not os.path.isdir(output_dir):
        return {"svg": [], "xml": [], "mat": []}
    svg = sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))
    xmls = sorted(glob.glob(os.path.join(output_dir, "output*.xml")))
    # excluir initial.xml y config
    xmls = [p for p in xmls if os.path.basename(p) != "initial.xml"]
    mats = sorted(glob.glob(os.path.join(output_dir, "output*_microenvironment*.mat")))
    return {"svg": svg, "xml": xmls, "mat": mats}


def leer_svg_info(svg_path):
    """Cuenta agentes en snapshot SVG. No interpreta biologia."""
    try:
        tree = ET.parse(svg_path)
        root = tree.getroot()
        # busca nodo cells
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag == "g":
                aid = el.attrib.get("id", "")
                if aid == "cells":
                    return {"ok": True, "n_agentes": len(list(el)), "path": svg_path}
        # fallback: cuenta circles
        n = 0
        for el in root.iter():
            if el.tag.split("}")[-1] == "circle":
                n += 1
        return {"ok": True, "n_agentes": n, "path": svg_path}
    except Exception as e:
        return {"ok": False, "error": str(e), "path": svg_path}


def leer_output_xml_info(xml_path):
    """Lee current_time de un output XML."""
    try:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        t = None
        for el in root.iter():
            if el.tag.split("}")[-1] == "current_time":
                t = el.text
                break
        return {"ok": True, "current_time": t, "path": xml_path}
    except Exception as e:
        return {"ok": False, "error": str(e), "path": xml_path}


def resumen_resultados(output_dir):
    fr = listar_frames(output_dir)
    info = {"n_svg": len(fr["svg"]), "n_xml": len(fr["xml"]), "n_mat": len(fr["mat"])}
    if fr["svg"]:
        info["primero_svg"] = leer_svg_info(fr["svg"][0])
        info["ultimo_svg"] = leer_svg_info(fr["svg"][-1])
    if fr["xml"]:
        info["ultimo_xml"] = leer_output_xml_info(fr["xml"][-1])
    return info


def listar_archivos(output_dir):
    """Archivos de salida con tamaño, ordenados. Incluye subcarpeta output/ si existe."""
    import os as _o
    dirs = [output_dir, _o.path.join(output_dir, "output")] if output_dir else []
    seen = set()
    filas = []
    for d in dirs:
        if not d or not _o.path.isdir(d):
            continue
        for name in sorted(_o.listdir(d)):
            p = _o.path.join(d, name)
            if _o.path.isfile(p) and p not in seen:
                seen.add(p)
                try:
                    sz = _o.path.getsize(p)
                except Exception:
                    sz = -1
                filas.append((p, sz))
    return filas


def verificar_integridad(output_dir):
    """Comprueba presencia mínima: snapshots, outputs XML, cells .mat y grafos."""
    fr = listar_frames(output_dir)
    import os as _o
    cands = [output_dir, _o.path.join(output_dir or "", "output")]
    mats = []
    grafos = []
    for d in cands:
        if d and _o.path.isdir(d):
            mats += [p for p in __import__("glob").glob(_o.path.join(d, "*_cells.mat"))]
            grafos += [p for p in __import__("glob").glob(_o.path.join(d, "*_neighbor_graph.txt"))]
    faltan = []
    if not fr["svg"]:
        faltan.append("snapshot*.svg")
    if not fr["xml"]:
        faltan.append("output*.xml")
    if not mats:
        faltan.append("*_cells.mat")
    if not grafos:
        faltan.append("*_neighbor_graph.txt")
    return {"ok": not faltan, "faltan": faltan,
            "n_svg": len(fr["svg"]), "n_xml": len(fr["xml"]),
            "n_cells_mat": len(mats), "n_grafos": len(grafos)}
