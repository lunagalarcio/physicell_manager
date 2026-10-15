#!/usr/bin/env python3
"""Motor complementario a PhysiCell: no modifica modelos internos."""
import os
import subprocess
from .xml_validator import validar_config


class MotorPhysiCell:
    def __init__(self, physicell_root=None):
        self.physicell_root = physicell_root

    def resolver_binario(self):
        """Busca binario PhysiCell compilado sin compilar ni modificar modelo."""
        candidatos = []
        if self.physicell_root:
            candidatos += [
                os.path.join(self.physicell_root, "project.exe"),
                os.path.join(self.physicell_root, "project"),
            ]
        for c in candidatos:
            if os.path.isfile(c):
                return c
        return ""

    def validar(self, xml_path):
        return validar_config(xml_path)

    def info_ejecucion(self, xml_path):
        """Info basica sin ejecutar: valida y retorna comando sugerido."""
        v = self.validar(xml_path)
        cmd = "make run" if self.physicell_root else "./project ./config/PhysiCell_settings.xml"
        return {"valido": v["ok"], "detalle": v, "comando_sugerido": cmd}

    def ejecutar(self, exe_path, config_path, cwd=None, timeout_ms=60000):
        """Ejecuta binario PhysiCell ya compilado. Retorna dict resultado."""
        if not os.path.isfile(exe_path):
            return {"ok": False, "error": f"Ejecutable no existe: {exe_path}"}
        if not os.path.isfile(config_path):
            return {"ok": False, "error": f"Config no existe: {config_path}"}
        try:
            proc = subprocess.run(
                [exe_path, config_path],
                cwd=cwd or os.path.dirname(exe_path),
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000,
            )
            return {
                "ok": proc.returncode == 0,
                "code": proc.returncode,
                "stdout": proc.stdout[-4000:],
                "stderr": proc.stderr[-4000:],
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Timeout de ejecucion"}
        except Exception as e:
            return {"ok": False, "error": str(e)}
