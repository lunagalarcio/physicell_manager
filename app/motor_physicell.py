#!/usr/bin/env python3
"""Motor complementario a PhysiCell: no modifica modelos internos."""
import os
import subprocess
from .xml_validator import validar_config


def _tail_texto(texto, n=12):
    """Devuelve las ultimas n lineas con contenido, para explicar un fallo."""
    lineas = [ln.rstrip() for ln in (texto or "").splitlines() if ln.strip()]
    return "\n".join(lineas[-n:]) if lineas else "(sin salida del motor)"


# Codigos NTSTATUS habituales al lanzar un binario en Windows.
_CODIGOS_WINDOWS = {
    0xC0000135: "No se encontró una DLL requerida (0xC0000135). Copia las DLLs del "
                "toolchain junto a project.exe o agrega su carpeta al PATH.",
    0xC0000139: "Punto de entrada no encontrado (0xC0000139). Las DLLs que acompañan al "
                "ejecutable no son del mismo toolchain con que fue compilado "
                "(caso típico: binario de ucrt64 con DLLs de mingw64).",
    0xC000007B: "Imagen no válida (0xC000007B). Mezcla de DLLs de 32 y 64 bits, o de "
                "toolchains distintos.",
    0xC0000005: "Infracción de acceso (0xC0000005). El motor se cerró de forma anómala.",
    0xC0000409: "Fallo de protección del sistema (0xC0000409).",
    0xC000001D: "Instrucción ilegal (0xC000001D).",
    0xC0000142: "No se pudo inicializar una DLL (0xC0000142).",
    0xC0000138: "No se encontró un procedimiento en una DLL (0xC0000138).",
}


def explicar_codigo_salida(code):
    """Traduce un codigo de salida de Windows a una explicacion legible."""
    try:
        sin_signo = int(code) & 0xFFFFFFFF
    except Exception:
        return ""
    return _CODIGOS_WINDOWS.get(sin_signo, "")


def verificar_binario(exe_path):
    """Revisa que el ejecutable de PhysiCell exista y sea usable.

    Devuelve una lista de problemas (vacía si el binario parece correcto).
    """
    problemas = []
    ruta = (exe_path or "").strip()
    if not ruta:
        return ["No se configuró la ruta del ejecutable de PhysiCell."]
    if not os.path.exists(ruta):
        return [f"El ejecutable no existe: {ruta}"]
    if not os.path.isfile(ruta):
        return [f"La ruta del ejecutable no es un archivo: {ruta}"]
    try:
        tam = os.path.getsize(ruta)
    except OSError as e:
        return [f"No se puede leer el ejecutable ({e}): {ruta}"]
    if tam == 0:
        problemas.append(f"El ejecutable está vacío (0 bytes): {ruta}")
    if os.name == "nt" and not ruta.lower().endswith(".exe"):
        problemas.append(
            f"En Windows el motor debe ser un archivo .exe: {ruta}"
        )
    return problemas


def hash_archivo(path):
    """SHA-256 de un archivo, para dejar huella del XML y del motor."""
    if not path or not os.path.isfile(path):
        return ""
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for bloque in iter(lambda: f.read(1024 * 1024), b""):
                h.update(bloque)
    except OSError:
        return ""
    return h.hexdigest()


def contar_salidas(output_dir):
    """Cuenta snapshots SVG, XML y .mat generados en una carpeta."""
    import glob as _glob
    if not output_dir or not os.path.isdir(output_dir):
        return 0, 0, 0
    return (
        len(_glob.glob(os.path.join(output_dir, "snapshot*.svg"))),
        len(_glob.glob(os.path.join(output_dir, "output*.xml"))),
        len(_glob.glob(os.path.join(output_dir, "output*_cells.mat"))),
    )


def intervalos_guardado(xml_path):
    """Lee del XML cada cuántos minutos guarda PhysiCell.

    Devuelve ``{"max_time", "svg", "full_data", "legacy"}``; 0 = desactivado.
    """
    res = {"max_time": 0.0, "svg": 0.0, "full_data": 0.0, "legacy": 0.0}
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(xml_path).getroot()
    except Exception:
        return res

    def _num(nodo):
        try:
            return float(nodo.text)
        except Exception:
            return 0.0

    mt = root.find(".//max_time")
    if mt is not None:
        res["max_time"] = _num(mt)
    save = root.find(".//save")
    if save is not None:
        for clave, etiquetas in (
            ("svg", ("svg", "SVG")),
            ("full_data", ("full_data",)),
            ("legacy", ("legacy_data",)),
        ):
            for et in etiquetas:
                nodo = save.find(et)
                if nodo is not None:
                    iv = nodo.find("interval")
                    if iv is not None:
                        res[clave] = _num(iv)
                        break
    return res


def _terminar_proceso(proc):
    """Termina el proceso y todos sus hijos (PhysiCell puede lanzar subprocesos)."""
    if proc is None:
        return
    try:
        if proc.poll() is not None:
            return
    except Exception:
        pass
    if os.name == "nt":
        # /T mata el árbol completo; /F fuerza el cierre
        try:
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                capture_output=True, timeout=10,
            )
        except Exception:
            pass
    else:
        import signal
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except Exception:
            pass
    try:
        proc.terminate()
        proc.wait(timeout=5)
        return
    except Exception:
        pass
    try:
        proc.kill()
        proc.wait(timeout=5)
    except Exception:
        pass


def _abrir_log(log_path, exe_path, config_path, cwd, pid):
    """Abre el registro de la ejecución y escribe la cabecera."""
    if not log_path:
        return None
    try:
        carpeta = os.path.dirname(log_path)
        if carpeta:
            os.makedirs(carpeta, exist_ok=True)
        f = open(log_path, "w", encoding="utf-8", errors="replace")
    except Exception:
        return None
    try:
        from datetime import datetime
        f.write("# Registro de ejecución de PhysiCell (PhysiCell Lab)\n")
        f.write(f"# Fecha: {datetime.now().isoformat(timespec='seconds')}\n")
        f.write(f"# Comando: \"{exe_path}\" \"{config_path}\"\n")
        f.write(f"# Carpeta de trabajo: {cwd or os.path.dirname(exe_path)}\n")
        f.write(f"# PID: {pid}\n\n")
        f.flush()
    except Exception:
        pass
    return f


def _cerrar_log(f):
    if f is None:
        return
    try:
        f.flush()
        f.close()
    except Exception:
        pass


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

    def ejecutar_cancelable(self, exe_path, config_path, cwd=None, timeout_ms=None,
                            stop_flag=None, linea_cb=None, max_time_min=None,
                            log_path=None, inicio_cb=None, inactividad_s=600):
        """Ejecuta PhysiCell con cancelación real, progreso y registro completo.

        - ``timeout_ms=None`` significa sin límite absoluto (recomendado para
          simulaciones largas: el límite de 10 min mataba ejecuciones válidas).
        - ``inactividad_s`` cancela si el motor deja de escribir durante ese
          tiempo, lo que sí indica un cuelgue real.
        - ``log_path`` guarda TODO lo que imprime el motor (stdout+stderr).
        - ``inicio_cb(pid)`` se llama en cuanto el proceso existe.
        """
        import re
        import time
        import queue
        import threading

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
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                start_new_session=(os.name != "nt"),
            )
        except OSError as e:
            return {
                "ok": False,
                "error": (
                    f"No se pudo iniciar PhysiCell ({e}).\n"
                    "Comprueba que el ejecutable sea válido para tu sistema y que "
                    "las DLL del toolchain estén junto a él."
                ),
                "log_path": log_path,
            }
        except Exception as e:
            return {"ok": False, "error": str(e), "log_path": log_path}

        pid = proc.pid
        if inicio_cb is not None:
            try:
                inicio_cb(pid)
            except Exception:
                pass
        t0 = time.time()
        ultima_actividad = t0
        log = _abrir_log(log_path, exe_path, config_path,
                         cwd or os.path.dirname(exe_path), pid)
        out_tail = []

        # Un hilo lee la salida para poder vigilar la inactividad aunque el
        # motor no imprima nada (readline bloquearía el bucle principal).
        cola = queue.Queue()

        def _lector():
            try:
                for ln in proc.stdout:
                    cola.put(ln)
            except Exception:
                pass
            finally:
                cola.put(None)

        hilo = threading.Thread(target=_lector, daemon=True)
        hilo.start()

        def _procesar(line):
            nonlocal ultima_actividad
            ultima_actividad = time.time()
            out_tail.append(line)
            if len(out_tail) > 400:
                del out_tail[:-400]
            if log is not None:
                try:
                    log.write(line)
                    log.flush()
                except Exception:
                    pass
            m = re.search(r"current simulated time:\s*([\d.]+)", line)
            if m and linea_cb:
                try:
                    linea_cb(float(m.group(1)), line.strip())
                except Exception:
                    pass

        def _cortar(estado, extra):
            _terminar_proceso(proc)
            duracion = time.time() - t0
            texto = f"{extra}\nDuración: {duracion:.1f} s · PID {pid}."
            if log is not None:
                try:
                    log.write(f"\n# {extra}\n# Fin: {duracion:.1f} s\n")
                except Exception:
                    pass
            res = {"ok": False, "error": texto, "stdout": "".join(out_tail)[-4000:],
                   "pid": pid, "log_path": log_path}
            if estado == "cancelled":
                res["cancelled"] = True
            return res

        try:
            while True:
                if stop_flag is not None and stop_flag():
                    return _cortar("cancelled", "Cancelado por el usuario.")

                ahora = time.time()
                if timeout_ms and (ahora - t0) * 1000 > timeout_ms:
                    limite = (f"{timeout_ms / 60000:g} min"
                              if timeout_ms >= 60000
                              else f"{timeout_ms / 1000:g} s")
                    return _cortar(
                        "timeout",
                        f"Timeout: el motor superó el límite de "
                        f"{limite} por réplica.",
                    )
                if inactividad_s and (ahora - ultima_actividad) > inactividad_s:
                    return _cortar(
                        "inactivo",
                        f"El motor dejó de escribir durante "
                        f"{inactividad_s / 60:.0f} min (posible cuelgue).",
                    )

                try:
                    item = cola.get(timeout=0.25)
                except queue.Empty:
                    if proc.poll() is not None:
                        # Drenar lo que quede pendiente antes de salir
                        while True:
                            try:
                                resto = cola.get_nowait()
                            except queue.Empty:
                                break
                            if resto is None:
                                break
                            _procesar(resto)
                        break
                    continue
                if item is None:
                    break
                _procesar(item)

            try:
                code = proc.wait(timeout=10)
            except Exception:
                _terminar_proceso(proc)
                code = proc.poll()
            duracion = time.time() - t0
            salida = "".join(out_tail)
            if code == 0:
                if log is not None:
                    try:
                        log.write(f"\n# Fin: código 0 tras {duracion:.1f} s\n")
                    except Exception:
                        pass
                return {"ok": True, "code": 0, "pid": pid,
                        "log_path": log_path, "stdout": salida[-4000:]}
            hexa = f"0x{(int(code) & 0xFFFFFFFF):08X}"
            partes = [
                f"PhysiCell terminó con código {code} ({hexa}) tras {duracion:.1f} s "
                f"(PID {pid})."
            ]
            pista = explicar_codigo_salida(code)
            if pista:
                partes.append(pista)
            if duracion < 1.5 and not salida.strip():
                partes.append(
                    "El proceso arrancó y terminó casi de inmediato sin escribir nada: "
                    "suele indicar DLLs incompatibles junto al ejecutable o un XML que "
                    "el motor no puede leer."
                )
            partes.append(f"Últimas líneas de salida:\n{_tail_texto(salida)}")
            if log is not None:
                try:
                    log.write(f"\n# Fin: código {code} ({hexa}) tras {duracion:.1f} s\n")
                except Exception:
                    pass
            return {
                "ok": False,
                "code": code,
                "error": "\n".join(partes),
                "stdout": salida[-4000:],
                "pid": pid,
                "log_path": log_path,
            }
        except Exception as e:
            _terminar_proceso(proc)
            return {"ok": False, "error": str(e), "pid": pid, "log_path": log_path}
        finally:
            try:
                if proc.stdout is not None:
                    proc.stdout.close()
            except Exception:
                pass
            _cerrar_log(log)

    def autodiagnostico(self, exe_path, xml_path, log_path=None, timeout_ms=90000):
        """Comprueba que el motor arranca y guarda resultados.

        Ejecuta PhysiCell con una copia temporal del XML y ``max_time`` igual al
        menor intervalo de guardado, así la prueba dura segundos.
        """
        import shutil
        import tempfile
        import time
        import xml.etree.ElementTree as ET

        problemas = verificar_binario(exe_path)
        if not os.path.isfile(xml_path or ""):
            problemas.append(f"El XML no existe: {xml_path}")
        else:
            v = validar_config(xml_path)
            if not v.get("ok"):
                problemas += [f"XML inválido: {e}" for e in v.get("errores", [])]
        if problemas:
            return {"ok": False, "problemas": problemas, "avisos": [],
                    "log_path": log_path, "duracion": 0.0}

        intervalos = intervalos_guardado(xml_path)
        avisos = []
        if intervalos["svg"] <= 0:
            avisos.append("El XML no guarda snapshots SVG: no habrá visualización 2D/3D.")
        if intervalos["full_data"] <= 0:
            avisos.append("El XML no guarda datos completos: no habrá output*.xml ni .mat.")

        pasos = [x for x in (intervalos["svg"], intervalos["full_data"],
                             intervalos["legacy"]) if x and x > 0]
        max_time = min(pasos) if pasos else 1.0

        tmp = tempfile.mkdtemp(prefix="physicell_diag_")
        out_dir = os.path.join(tmp, "output")
        os.makedirs(out_dir, exist_ok=True)
        xml_diag = os.path.join(tmp, "diagnostico.xml")
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            mt = root.find(".//max_time")
            if mt is not None:
                mt.text = f"{max_time:g}"
            folder = root.find(".//save/folder")
            if folder is not None:
                folder.text = out_dir
            tree.write(xml_diag, encoding="utf-8", xml_declaration=True)
        except Exception as e:
            shutil.rmtree(tmp, ignore_errors=True)
            return {"ok": False, "problemas": [f"No se pudo preparar el XML de prueba: {e}"],
                    "avisos": avisos, "log_path": log_path, "duracion": 0.0}

        t0 = time.time()
        r = self.ejecutar_cancelable(
            exe_path, xml_diag,
            cwd=os.path.dirname(exe_path),
            timeout_ms=timeout_ms,
            log_path=log_path or os.path.join(tmp, "diagnostico.log"),
            inactividad_s=90,
        )
        duracion = time.time() - t0
        n_svg, n_xml, n_mat = contar_salidas(out_dir)

        if not r.get("ok"):
            return {
                "ok": False,
                "problemas": [r.get("error") or "El motor falló sin detalle."],
                "avisos": avisos,
                "log_path": r.get("log_path") or log_path,
                "duracion": duracion,
                "salida": out_dir,
            }

        problemas = []
        if n_svg + n_xml + n_mat == 0:
            problemas.append(
                "El motor terminó bien pero no guardó ningún archivo en la carpeta "
                f"de prueba: {out_dir}"
            )
        if not problemas:
            shutil.rmtree(tmp, ignore_errors=True)
        return {
            "ok": not problemas,
            "problemas": problemas,
            "avisos": avisos,
            "duracion": duracion,
            "n_svg": n_svg,
            "n_xml": n_xml,
            "n_mat": n_mat,
            "max_time_probado": max_time,
            "log_path": r.get("log_path") or log_path,
            "salida": out_dir,
        }
