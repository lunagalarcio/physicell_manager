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
