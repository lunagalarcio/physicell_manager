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
    """Valida un XML de PhysiCell. Retorna dict con ok, errores, warnings."""
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

    def find_any(tag):
        # busca tag exacto en cualquier nivel
        for el in root.iter():
            # quita namespace si existe
            name = el.tag.split("}")[-1]
            if name == tag:
                return True
        return False

    for sec in REQUIRED_SECTIONS:
        if not find_any(sec):
            result["errores"].append(f"Falta seccion: {sec}")

    for tag in REQUIRED_TAGS:
        if not find_any(tag):
            result["warnings"].append(f"Falta tag recomendado: {tag}")

    if not result["errores"]:
        result["ok"] = True
    return result
