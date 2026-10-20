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
        return self.ejecutar_cancelable(exe_path, config_path, cwd=cwd, timeout_ms=timeout_ms)

    def ejecutar_cancelable(self, exe_path, config_path, cwd=None, timeout_ms=300000, stop_flag=None, linea_cb=None, max_time_min=None):
        """Ejecuta PhysiCell con cancelación real y progreso por 'current simulated time'."""
        import re
        import time
        if not os.path.isfile(exe_path):
            return {"ok": False, "error": f"Ejecutable no existe: {exe_path}"}
        if not os.path.isfile(config_path):
            return {"ok": False, "error": f"Config no existe: {config_path}"}
        try:
            proc = subprocess.Popen(
                [exe_path, config_path],
                cwd=cwd or os.path.dirname(exe_path),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}
        t0 = time.time()
        out_tail = []
        cur_sim = None
        try:
            while True:
                if stop_flag is not None and stop_flag():
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            proc.kill()
                    except Exception:
                        pass
                    return {"ok": False, "cancelled": True, "error": "Cancelado por usuario", "stdout": "".join(out_tail)[-4000:]}
                if timeout_ms and (time.time() - t0) * 1000 > timeout_ms:
                    try:
                        proc.terminate()
                        try:
                            proc.wait(timeout=5)
                        except Exception:
                            proc.kill()
                    except Exception:
                        pass
                    return {"ok": False, "error": "Timeout de ejecucion", "stdout": "".join(out_tail)[-4000:]}
                line = proc.stdout.readline() if proc.stdout else ""
                if line:
                    out_tail.append(line)
                    if len(out_tail) > 400:
                        out_tail = out_tail[-400:]
                    m = re.search(r"current simulated time:\s*([\d.]+)", line)
                    if m and linea_cb:
                        try:
                            cur_sim = float(m.group(1))
                            linea_cb(cur_sim, line.strip())
                        except Exception:
                            pass
                elif proc.poll() is not None:
                    break
            rest = ""
            try:
                rest = proc.communicate(timeout=10)[0] or ""
            except Exception:
                rest = ""
            if rest:
                out_tail.append(rest)
            code = proc.returncode
            return {"ok": code == 0, "code": code, "stdout": "".join(out_tail)[-4000:]}
        except Exception as e:
            try:
                proc.kill()
            except Exception:
                pass
            return {"ok": False, "error": str(e)}
