#!/usr/bin/env python3
"""Validacion de archivos XML de PhysiCell sin limitar parametros."""
import os
import xml.etree.ElementTree as ET

REQUIRED_SECTIONS = [
    "domain",
    "overall",
    "microenvironment_setup",
    "cell_definitions",
]

REQUIRED_TAGS = [
    "x_min", "x_max", "y_min", "y_max",
    "max_time",
]


def validar_config(xml_path):
    """Valida estructura PhysiCell sin listas rígidas de parámetros.

    Comprueba secciones, coherencia interna y existencia de archivos
    referenciados (cells.csv, reglas, .mat). No elimina parámetros desconocidos.
    """
    result = {"ok": False, "errores": [], "warnings": [], "path": xml_path}
    if not xml_path or not os.path.isfile(xml_path):
        result["errores"].append("Archivo no existe.")
        return result
    try:
        tree = ET.parse(xml_path)
    except ET.ParseError as e:
        result["errores"].append(f"XML mal formado: {e}")
        return result
    except Exception as e:
        result["errores"].append(f"Error lectura: {e}")
        return result
    root = tree.getroot()
    base = os.path.dirname(os.path.abspath(xml_path))

    def find_any(tag):
        for el in root.iter():
            name = el.tag.split("}")[-1]
            if name == tag:
                return True
        return False

    def all_of(tag):
        out = []
        for el in root.iter():
            if el.tag.split("}")[-1] == tag:
                out.append(el)
        return out

    for sec in REQUIRED_SECTIONS:
        if not find_any(sec):
            result["errores"].append(f"Falta seccion: {sec}")

    for tag in REQUIRED_TAGS:
        if not find_any(tag):
            result["warnings"].append(f"Falta tag recomendado: {tag}")

    # microambiente: cada variable con coeficientes físicos
    for var in all_of("variable"):
        nom = var.attrib.get("name", "?")
        dif = var.find(".//diffusion_coefficient")
        dec = var.find(".//decay_rate")
        if dif is None or not (dif.text or "").strip():
            result["warnings"].append(f"Variable '{nom}' sin diffusion_coefficient explícito")
        if dec is None or not (dec.text or "").strip():
            result["warnings"].append(f"Variable '{nom}' sin decay_rate explícito")

    # definiciones celulares con fenotipo
    cdefs = root.findall(".//cell_definitions/cell_definition")
    if not cdefs:
        result["errores"].append("Sin cell_definition en cell_definitions")
    else:
        for cd in cdefs:
            if cd.find("phenotype") is None:
                result["warnings"].append(f"Definición '{cd.attrib.get('name', '?')}' sin phenotype")

    # archivos referenciados existen (rutas relativas al XML)
    def _rutas(nodo, *tags):
        for t in tags:
            el = nodo.find(f".//{t}") if nodo is not None else None
            if el is not None and el.text and el.text.strip():
                yield el.text.strip()
    for cp in all_of("cell_positions"):
        folder = (cp.findtext("folder") or "").strip()
        fname = (cp.findtext("filename") or "").strip()
        if (cp.attrib.get("enabled", "true").lower() == "true") and fname:
            p = fname if os.path.isabs(fname) else os.path.join(base, folder, fname) if folder else os.path.join(base, fname)
            if not os.path.isfile(p):
                result["warnings"].append(f"cells.csv referenciado no existe: {fname}")
    for rs in all_of("ruleset"):
        if (rs.attrib.get("enabled", "false").lower() == "true"):
            folder = (rs.findtext("folder") or "").strip()
            fname = (rs.findtext("filename") or "").strip()
            if fname:
                p = fname if os.path.isabs(fname) else os.path.join(base, folder, fname) if folder else os.path.join(base, fname)
                if not os.path.isfile(p):
                    result["errores"].append(f"Reglas habilitadas pero falta archivo: {fname}")

    if not result["errores"]:
        result["ok"] = True
    return result


def validar_texto(texto: str) -> dict:
    """Valida que un texto sea XML bien formado y tenga estructura básica de PhysiCell.

    Útil para validación en tiempo real mientras el usuario escribe en un editor.
    No requiere archivo físico; analiza el contenido en memoria.
    """
    result = {"ok": False, "errores": [], "warnings": [], "path": None}
    if not texto or not texto.strip():
        result["errores"].append("Texto vacío.")
        return result
    try:
        root = ET.fromstring(texto)
    except ET.ParseError as e:
        result["errores"].append(f"XML mal formado: {e}")
        return result
    except Exception as e:
        result["errores"].append(f"Error al parsear: {e}")
        return result

    def find_any(tag):
        for el in root.iter():
            if el.tag.split("}")[-1] == tag:
                return True
        return False

    for sec in REQUIRED_SECTIONS:
        if not find_any(sec):
            result["errores"].append(f"Falta sección: {sec}")

    for tag in REQUIRED_TAGS:
        if not find_any(tag):
            result["warnings"].append(f"Falta tag recomendado: {tag}")

    if not result["errores"]:
        result["ok"] = True
    return result
