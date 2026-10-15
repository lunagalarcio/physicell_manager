#!/usr/bin/env python3
"""Gestion de archivos XML sin limitar parametros."""
import os
import shutil
import xml.etree.ElementTree as ET


def importar_config(src_path, dst_dir):
    """Copia XML externo a carpeta destino. Retorna ruta destino."""
    if not os.path.isfile(src_path):
        return {"ok": False, "error": "Origen no existe"}
    os.makedirs(dst_dir, exist_ok=True)
    dst = os.path.join(dst_dir, os.path.basename(src_path))
    shutil.copyfile(src_path, dst)
    return {"ok": True, "path": dst}


def leer_texto(xml_path):
    with open(xml_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def guardar_texto(xml_path, texto):
    """Guarda texto y valida que sea XML bien formado."""
    try:
        ET.fromstring(texto)
    except ET.ParseError as e:
        return {"ok": False, "error": f"XML mal formado: {e}"}
    os.makedirs(os.path.dirname(xml_path) or ".", exist_ok=True)
    with open(xml_path, "w", encoding="utf-8") as f:
        f.write(texto)
    return {"ok": True, "path": xml_path}


def leer_seed(xml_path):
    """Extrae random_seed si existe, sin interpretar modelo."""
    try:
        tree = ET.parse(xml_path)
        for el in tree.getroot().iter():
            if el.tag.split("}")[-1] == "random_seed":
                return el.text
    except Exception:
        pass
    return None


def comparar_replicas(xml_paths):
    """Compara lista de XML por seed y tamano. Retorna filas."""
    import os
    filas = []
    for p in sorted(xml_paths):
        seed = leer_seed(p)
        size = os.path.getsize(p) if os.path.isfile(p) else -1
        filas.append({"path": p, "seed": seed, "bytes": size})
    return filas
