#!/usr/bin/env python3
"""Capa de servicios de aplicación de PhysiCell Lab.

Coordina casos de uso entre la interfaz, el acceso a datos (simulador, nucleo)
y la infraestructura (motor_physicell, xml_validator, config_manager).
La UI nunca ejecuta SQL directamente; solicita operaciones a estos servicios.
"""
import os
import sqlite3
from datetime import datetime

from . import simulador as SIM
from . import nucleo as NUC
from .xml_validator import validar_config


# ---------- Gestión de experimentos ----------

def crear_experimento(db_path, title, description="", tags="", config_xml_path=""):
    """Crea un experimento y, si se indica XML, registra su configuración base (v1).

    El XML se copia a una carpeta de resguardo inmutable antes de registrar.
    """
    conn = sqlite3.connect(db_path)
    try:
        eid = SIM.crear_experimento(conn, title, description, tags, config_xml_path)
        if config_xml_path:
            NUC.crear_configuracion(
                conn, eid, nombre="base", xml_path=config_xml_path,
                version=1, activar=True,
                db_path=db_path, copiar_xml=True,
            )
        conn.commit()
        return {"ok": True, "experiment_id": eid}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def actualizar_experimento(db_path, eid, title, description, tags,
                           binary_path="", custom_cpp_path="", custom_h_path=""):
    conn = sqlite3.connect(db_path)
    try:
        SIM.actualizar_experimento(
            conn, eid, title, description, tags,
            binary_path, custom_cpp_path, custom_h_path,
        )
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def eliminar_experimento(db_path, eid):
    conn = sqlite3.connect(db_path)
    try:
        SIM.eliminar_experimento(conn, eid)
        conn.commit()
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def actualizar_rutas_experimento(db_path, eid, config_xml_path="",
                                 binary_path="", custom_cpp_path="",
                                 custom_h_path=""):
    """Actualiza solo las rutas de configuración/motor de un experimento."""
    conn = sqlite3.connect(db_path)
    try:
        SIM.actualizar_rutas_experimento(
            conn, eid, config_xml_path, binary_path, custom_cpp_path, custom_h_path,
        )
        return {"ok": True}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def obtener_experimento_completo(db_path, eid):
    """Retorna dict con datos del experimento, configuración activa y estadísticas."""
    conn = sqlite3.connect(db_path)
    try:
        row = SIM.obtener_experimento(conn, eid)
        if not row:
            return {"ok": False, "error": "Experimento no existe"}
        eid_, title, desc, tags, cfg, binp, cpp, h, creado, modif = row
        cfg_act = NUC.configuracion_activa(conn, eid)
        stats = SIM.estadisticas_experimento(conn, eid) if hasattr(SIM, "estadisticas_experimento") else None
        escenarios = SIM.listar_escenarios(conn, eid)
        configuraciones = NUC.listar_configuraciones(conn, eid)
        return {
            "ok": True,
            "experimento": {
                "id": eid_, "title": title, "description": desc, "tags": tags,
                "config_xml_path": cfg, "binary_path": binp,
                "custom_cpp_path": cpp, "custom_h_path": h,
                "created_at": creado, "last_modified": modif,
            },
            "configuracion_activa": {
                "id": cfg_act[0], "nombre": cfg_act[1], "xml_path": cfg_act[2],
                "version": cfg_act[3],
            } if cfg_act else None,
            "configuraciones": [
                {"id": c[0], "nombre": c[1], "xml_path": c[2],
                 "version": c[3], "es_activa": bool(c[4]), "creado_en": c[5]}
                for c in configuraciones
            ],
            "escenarios": [
                {"id": s[0], "nombre": s[1], "config_xml_path": s[2],
                 "configuracion_id": s[4] if len(s) > 4 else None}
                for s in escenarios
            ],
            "estadisticas": stats,
        }
    finally:
        conn.close()


# ---------- Gestión de configuraciones versionadas ----------

def registrar_nueva_configuracion(db_path, experiment_id, nombre, xml_path, activar=True):
    """Valida el XML y registra una nueva versión de configuración.

    El XML se copia a una carpeta de resguardo inmutable antes de registrar,
    para que la versión quede vinculada al contenido exacto usado en su momento.
    """
    if not validar_config(xml_path).get("ok"):
        return {"ok": False, "error": "El XML no es válido"}
    conn = sqlite3.connect(db_path)
    try:
        cid = NUC.crear_configuracion(
            conn, experiment_id, nombre, xml_path,
            version=None, activar=activar,
            db_path=db_path, copiar_xml=True,
        )
        conn.commit()
        return {"ok": True, "configuracion_id": cid}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


def activar_configuracion_servicio(db_path, configuracion_id):
    conn = sqlite3.connect(db_path)
    try:
        ok = NUC.activar_configuracion(conn, configuracion_id)
        conn.commit()
        return {"ok": ok}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


# ---------- Gestión de escenarios ----------

def crear_escenario_servicio(db_path, experiment_id, nombre, config_xml_path,
                             parametros_json="{}"):
    """Crea un escenario (variante) vinculado a la configuración activa del experimento."""
    if not validar_config(config_xml_path).get("ok"):
        return {"ok": False, "error": "El XML del escenario no es válido"}
    conn = sqlite3.connect(db_path)
    try:
        cfg_act = NUC.configuracion_activa(conn, experiment_id)
        configuracion_id = cfg_act[0] if cfg_act else None
        sid = SIM.crear_escenario(
            conn, experiment_id, nombre, config_xml_path, parametros_json,
        )
        # Vincular escenario a la configuración si existe la columna
        try:
            SIM.vincular_escenario_a_configuracion(conn, sid, configuracion_id)
        except Exception:
            pass
        conn.commit()
        return {"ok": True, "escenario_id": sid}
    except Exception as e:
        conn.rollback()
        return {"ok": False, "error": str(e)}
    finally:
        conn.close()


# ---------- Ejecución de simulaciones ----------

def validar_para_ejecutar(db_path, experiment_id, xml_path, exe_path):
    """Valida que todo esté listo para lanzar réplicas. Retorna errores si los hay."""
    errores = []
    if not xml_path or not os.path.isfile(xml_path):
        errores.append("No se ha asignado un XML de experimento válido.")
    else:
        v = validar_config(xml_path)
        if not v.get("ok"):
            errores.append("XML inválido: " + "; ".join(v.get("errores", [])))
    if not exe_path or not os.path.isfile(exe_path):
        errores.append("No se ha configurado el ejecutable PhysiCell (project.exe).")
    return {"ok": len(errores) == 0, "errores": errores}


def iniciar_ejecucion(db_path, experiment_id, xml_path, n_replicas, exe_path,
                      progreso_cb=None, terminado_cb=None, error_cb=None):
    """Lanza el worker de réplicas. Registra cada ejecución con su configuración."""
    from .nucleo import ReplicaWorker, get_db_path

    # Determinar configuración activa para asociar a las ejecuciones
    conn = sqlite3.connect(db_path)
    try:
        cfg_act = NUC.configuracion_activa(conn, experiment_id)
        configuracion_id = cfg_act[0] if cfg_act else None
    finally:
        conn.close()

    worker = ReplicaWorker(experiment_id, xml_path, n_replicas, exe_path, db_path,
                           configuracion_id=configuracion_id)

    if progreso_cb:
        worker.prog.connect(progreso_cb)
    if terminado_cb:
        worker.done.connect(terminado_cb)
    if error_cb:
        worker.fail.connect(error_cb)

    worker.start()
    return worker


# ---------- Consultas de lectura ----------

def listar_experimentos_servicio(db_path):
    """Lista experimentos con estadísticas (para la página Experimentos y Resumen)."""
    conn = sqlite3.connect(db_path)
    try:
        return SIM.listar_experimentos_con_estadisticas(conn)
    finally:
        conn.close()


def listar_escenarios_servicio(db_path, experiment_id):
    conn = sqlite3.connect(db_path)
    try:
        return SIM.listar_escenarios(conn, experiment_id)
    finally:
        conn.close()


def listar_runs_servicio(db_path, experiment_id):
    conn = sqlite3.connect(db_path)
    try:
        return SIM.listar_runs(conn, experiment_id)
    finally:
        conn.close()


def listar_configuraciones_servicio(db_path, experiment_id):
    conn = sqlite3.connect(db_path)
    try:
        return NUC.listar_configuraciones(conn, experiment_id)
    finally:
        conn.close()
