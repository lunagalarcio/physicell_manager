#!/usr/bin/env python3
"""Automatizacion de escenarios y replicas sin modificar PhysiCell."""
import os
import shutil
import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime


def get_db_path_local(get_db_path_fn):
    return get_db_path_fn()


def crear_escenario(conn, experiment_id, nombre, config_xml_path, parametros_json="{}"):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO escenarios (experiment_id, nombre, config_xml_path, parametros_json) VALUES (?,?,?,?)",
        (experiment_id, nombre, config_xml_path, parametros_json),
    )
    conn.commit()
    return cur.lastrowid


def listar_escenarios(conn, experiment_id):
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, config_xml_path FROM escenarios WHERE experiment_id=? ORDER BY id", (experiment_id,))
    return cur.fetchall()


def fijar_output_folder(xml_path, folder):
    """Reescribe <save><folder> para aislar salidas por réplica. No toca modelos."""
    tree = ET.parse(xml_path)
    root = tree.getroot()
    node = root.find(".//save/folder")
    if node is None:
        # crea save/folder si no existe
        save = root.find(".//save")
        if save is None:
            save = ET.SubElement(root, "save")
        node = ET.SubElement(save, "folder")
    node.text = folder
    tree.write(xml_path, encoding="unicode", xml_declaration=True)
    return folder


def generar_replica_config(base_xml, out_xml, seed=None, output_folder=None):
    """Copia base_xml a out_xml cambiando random_seed y carpeta de salida si se indican."""
    os.makedirs(os.path.dirname(out_xml) or ".", exist_ok=True)
    if seed is None and output_folder is None:
        shutil.copyfile(base_xml, out_xml)
        return out_xml
    tree = ET.parse(base_xml)
    root = tree.getroot()
    if seed is not None:
        changed = False
        for el in root.iter():
            name = el.tag.split("}")[-1]
            if name == "random_seed":
                el.text = str(seed)
                changed = True
        if not changed:
            for el in root.iter():
                name = el.tag.split("}")[-1]
                if name == "user_parameters":
                    sub = ET.SubElement(el, "random_seed")
                    sub.set("type", "int")
                    sub.text = str(seed)
                    break
    if output_folder is not None:
        node = root.find(".//save/folder")
        if node is None:
            save = root.find(".//save")
            if save is None:
                save = ET.SubElement(root, "save")
            node = ET.SubElement(save, "folder")
        node.text = output_folder
    tree.write(out_xml, encoding="unicode", xml_declaration=True)
    return out_xml


def registrar_run(conn, experiment_id, run_number, status="pending", output_dir="",
                  configuracion_id=None, escenario_id=None, batch_id=None):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (experiment_id, run_number, status, start_time, output_dir, "
        "configuracion_id, escenario_id, batch_id) VALUES (?,?,?,?,?,?,?,?)",
        (experiment_id, run_number, status, datetime.now().isoformat(timespec="seconds"),
         output_dir, configuracion_id, escenario_id, batch_id),
    )
    conn.commit()
    return cur.lastrowid


def crear_batch(conn, experiment_id, xml_path, exe_path, n_replicas,
                seed_base=1000, timeout_min=0, inactividad_min=10, notas=""):
    """Registra un lote de réplicas con la huella de lo que se ejecutó."""
    import platform
    import sys
    from .motor_physicell import hash_archivo

    cur = conn.cursor()
    cur.execute(
        """INSERT INTO batches (experiment_id, creado_en, n_replicas, xml_path, xml_sha256,
                                exe_path, exe_sha256, seed_base, timeout_min,
                                inactividad_min, python_version, plataforma, notas, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            experiment_id, datetime.now().isoformat(timespec="seconds"), int(n_replicas),
            str(xml_path or ""), hash_archivo(xml_path),
            str(exe_path or ""), hash_archivo(exe_path),
            int(seed_base), int(timeout_min or 0), int(inactividad_min or 0),
            platform.python_version(), f"{platform.system()} {platform.release()}",
            str(notas or "")[:1000], "running",
        ),
    )
    conn.commit()
    return cur.lastrowid


def actualizar_batch(conn, batch_id, status, error_message=None):
    if not batch_id:
        return
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE batches SET status=?, error_message=? WHERE id=?",
            (status, (str(error_message)[:4000] if error_message else None), batch_id),
        )
        conn.commit()
    except Exception:
        pass


_BATCH_CAMPOS = (
    "id", "experiment_id", "creado_en", "n_replicas", "xml_path", "xml_sha256",
    "exe_path", "exe_sha256", "seed_base", "timeout_min", "inactividad_min",
    "python_version", "plataforma", "notas", "status", "error_message",
)


def obtener_batch(conn, batch_id):
    """Datos de un lote (dict) o None si no existe."""
    if not batch_id:
        return None
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT " + ", ".join(_BATCH_CAMPOS) + " FROM batches WHERE id=?",
            (batch_id,),
        )
        row = cur.fetchone()
    except Exception:
        return None
    return dict(zip(_BATCH_CAMPOS, row)) if row else None


def actualizar_run(conn, run_id, status, end=False, configuracion_id=None,
                   error_message=None, log_path=None, pid=None):
    cur = conn.cursor()
    campos = ["status=?"]
    valores = [status]
    if end:
        campos.append("end_time=?")
        valores.append(datetime.now().isoformat(timespec="seconds"))
    if configuracion_id is not None:
        campos.append("configuracion_id=?")
        valores.append(configuracion_id)
    if error_message is not None:
        campos.append("error_message=?")
        valores.append(str(error_message)[:4000])
    if log_path is not None:
        campos.append("log_path=?")
        valores.append(str(log_path))
    if pid is not None:
        campos.append("pid=?")
        try:
            valores.append(int(pid))
        except (TypeError, ValueError):
            valores.append(None)
    valores.append(run_id)
    cur.execute(f"UPDATE runs SET {', '.join(campos)} WHERE id=?", tuple(valores))
    conn.commit()


def listar_runs(conn, experiment_id):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, run_number, status, start_time, end_time, output_dir, error_message, "
            "log_path, pid, batch_id FROM runs WHERE experiment_id=? ORDER BY id",
            (experiment_id,),
        )
        return cur.fetchall()
    except Exception:
        pass
    try:
        # Bases antiguas sin columnas log_path/pid/batch_id
        cur.execute(
            "SELECT id, run_number, status, start_time, end_time, output_dir, error_message "
            "FROM runs WHERE experiment_id=? ORDER BY id",
            (experiment_id,),
        )
        return [tuple(f) + (None, None, None) for f in cur.fetchall()]
    except Exception:
        cur.execute(
            "SELECT id, run_number, status, start_time, end_time, output_dir "
            "FROM runs WHERE experiment_id=? ORDER BY id",
            (experiment_id,),
        )
        return [tuple(f) + ("", None, None, None) for f in cur.fetchall()]


def crear_experimento(conn, title, description="", tags="", config_xml_path="", usuario_id=None):
    """Crea un experimento y retorna su id."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO experiments (title, description, tags, config_xml_path, usuario_id, created_at, last_modified) "
        "VALUES (?,?,?,?,?,CURRENT_TIMESTAMP,CURRENT_TIMESTAMP)",
        (title, description, tags, config_xml_path, usuario_id),
    )
    conn.commit()
    return cur.lastrowid


def listar_experimentos_por_usuario(conn, uid):
    """Lista experimentos con estadísticas filtrados por usuario."""
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.id, e.title, e.description, e.tags, e.config_xml_path,
                      e.binary_path, e.custom_cpp_path, e.custom_h_path, e.last_modified,
                      COUNT(r.id) as total_runs,
                      COALESCE(SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status IN ('failed', 'cancelled')
                                       THEN 1 ELSE 0 END), 0),
                      MAX(r.start_time)
               FROM experiments e
               LEFT JOIN runs r ON e.id = r.experiment_id
               WHERE e.usuario_id = ?
               GROUP BY e.id
               ORDER BY e.id DESC""",
            (uid,),
        )
        return cur.fetchall()
    except Exception:
        cur.execute(
            "SELECT id, title, description, tags, config_xml_path, binary_path, "
            "custom_cpp_path, custom_h_path, last_modified FROM experiments WHERE usuario_id=? ORDER BY id DESC",
            (uid,),
        )
        filas = cur.fetchall()
        return [f + (0, 0, 0, 0, None) for f in filas]


def obtener_experimento_por_usuario(conn, eid, uid):
    """Datos completos de un experimento solo si pertenece al usuario."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, description, tags, config_xml_path, binary_path, "
        "custom_cpp_path, custom_h_path, created_at, last_modified, usuario_id "
        "FROM experiments WHERE id=? AND usuario_id=?", (eid, uid)
    )
    return cur.fetchone()


def actualizar_experimento(conn, experiment_id, title, description, tags, binary_path="", custom_cpp_path="", custom_h_path=""):
    cur = conn.cursor()
    cur.execute(
        "UPDATE experiments SET title=?, description=?, tags=?, binary_path=?, custom_cpp_path=?, custom_h_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?",
        (title, description, tags, binary_path, custom_cpp_path, custom_h_path, experiment_id),
    )
    conn.commit()


def tanda_de_estados(filas):
    """Estados de las replica más recientes, agrupadas en su última tanda.

    ``filas`` son tuplas donde las tres primeras posiciones son
    ``(id, run_number, status)``. El número de réplica vuelve a empezar en 1
    en cada ejecución, así que la tanda más reciente se reconoce recorriendo
    las filas de la más nueva a la más vieja mientras ``run_number`` baje 1.
    """
    orden = sorted(
        (f for f in filas if len(f) >= 3), key=lambda f: f[0] or 0, reverse=True
    )
    if not orden:
        return []
    try:
        esperado = int(orden[0][1] or 1)
    except (TypeError, ValueError):
        return [orden[0][2]]
    tanda = []
    for _rid, run_number, status in orden:
        if run_number != esperado:
            break
        tanda.append(status)
        esperado -= 1
    return tanda


def estados_ultima_tanda(conn):
    """Devuelve ``{experiment_id: [estados de la última tanda de réplicas]}``.

    Usa ``batch_id`` cuando existe (lotes nuevos). Para ejecuciones antiguas
    sin lote, deduce la tanda por la numeración de réplicas.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT experiment_id, id, run_number, status, batch_id FROM runs "
            "ORDER BY experiment_id, id DESC"
        )
        filas = cur.fetchall()
    except Exception:
        return {}
    por_exp = {}
    for fila in filas:
        por_exp.setdefault(fila[0], []).append(fila)
    res = {}
    for eid, fs in por_exp.items():
        lote = fs[0][4] if len(fs[0]) > 4 else None
        if lote:
            res[eid] = [f[3] for f in fs if len(f) > 4 and f[4] == lote]
        else:
            res[eid] = tanda_de_estados([(f[1], f[2], f[3]) for f in fs])
    return res


def ultimo_batch(conn, experiment_id):
    """Id del lote más reciente de un experimento (o None)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT MAX(batch_id) FROM runs WHERE experiment_id=? AND batch_id IS NOT NULL",
            (experiment_id,),
        )
        row = cur.fetchone()
        return row[0] if row else None
    except Exception:
        return None


def estadisticas_experimento(conn, eid):
    """Devuelve estadísticas de runs para un experimento desde la DB."""
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(r.id),
                  SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN r.status IN ('failed', 'cancelled') THEN 1 ELSE 0 END),
                  MAX(r.start_time)
           FROM runs r WHERE r.experiment_id = ?""",
        (eid,),
    )
    row = cur.fetchone()
    tanda = estados_ultima_tanda(conn).get(eid, [])
    return {
        "total": row[0] or 0,
        "completadas": row[1] or 0,
        "en_curso": row[2] or 0,
        "falladas": row[3] or 0,
        "ultima_fecha": row[4],
        "ultima_tanda": tanda,
        "ultimo_estado": tanda[0] if tanda else None,
    }


def obtener_run_por_output_dir(conn, experiment_id, output_dir):
    """Busca el run_number de una ejecución por su carpeta de salida."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT run_number FROM runs WHERE experiment_id=? AND output_dir=? "
            "ORDER BY run_number DESC LIMIT 1",
            (experiment_id, output_dir),
        )
        row = cur.fetchone()
        return row[0] if row else 0
    except Exception:
        return 0


def actualizar_rutas_experimento(conn, eid, config_xml_path="",
                                 binary_path="", custom_cpp_path="",
                                 custom_h_path=""):
    """Actualiza solo las rutas de configuración/motor de un experimento."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE experiments SET config_xml_path=?, binary_path=?, custom_cpp_path=?, custom_h_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?",
        (config_xml_path, binary_path, custom_cpp_path, custom_h_path, eid),
    )
    conn.commit()


def vincular_escenario_a_configuracion(conn, escenario_id, configuracion_id):
    """Vincula un escenario a la configuración exacta que usó."""
    cur = conn.cursor()
    cur.execute(
        "UPDATE escenarios SET configuracion_id=? WHERE id=?",
        (configuracion_id, escenario_id),
    )
    conn.commit()


def listar_todos_los_runs(conn, limite=200):
    """Lista todas las ejecuciones de todos los experimentos (para página Ejecuciones)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT e.title, r.run_number, r.status, r.start_time, r.end_time, r.output_dir, "
            "r.error_message, r.log_path, r.pid, r.batch_id "
            "FROM runs r JOIN experiments e ON e.id=r.experiment_id ORDER BY r.start_time DESC LIMIT ?",
            (limite,),
        )
        return cur.fetchall()
    except Exception:
        pass
    try:
        cur.execute(
            "SELECT e.title, r.run_number, r.status, r.start_time, r.end_time, r.output_dir, "
            "r.error_message "
            "FROM runs r JOIN experiments e ON e.id=r.experiment_id ORDER BY r.start_time DESC LIMIT ?",
            (limite,),
        )
        return [tuple(f) + (None, None, None) for f in cur.fetchall()]
    except Exception:
        try:
            cur.execute(
                "SELECT e.title, r.run_number, r.status, r.start_time, r.end_time, r.output_dir "
                "FROM runs r JOIN experiments e ON e.id=r.experiment_id ORDER BY r.start_time DESC LIMIT ?",
                (limite,),
            )
            return [tuple(f) + ("", None, None, None) for f in cur.fetchall()]
        except Exception:
            return []


def leer_log(path, max_lineas=500):
    """Devuelve el final del registro de PhysiCell con una explicación si falta."""
    if not path:
        return ("Esta ejecución no tiene registro del motor guardado "
                "(es anterior a esta versión de la app).")
    if not os.path.isfile(path):
        return f"No se encontró el archivo de registro:\n{path}"
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lineas = f.readlines()
    except OSError as e:
        return f"No se pudo leer el registro ({e}):\n{path}"
    if not lineas:
        return "(el registro está vacío: el motor no llegó a escribir nada)"
    recorte = lineas[-max_lineas:]
    prefijo = ""
    if len(lineas) > max_lineas:
        prefijo = f"(mostrando las últimas {len(recorte)} de {len(lineas)} líneas)\n\n"
    return prefijo + "".join(recorte)


def eliminar_experimento(conn, experiment_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM runs WHERE experiment_id=?", (experiment_id,))
    cur.execute("DELETE FROM escenarios WHERE experiment_id=?", (experiment_id,))
    cur.execute("DELETE FROM experiments WHERE id=?", (experiment_id,))
    conn.commit()


def eliminar_escenario(conn, escenario_id):
    cur = conn.cursor()
    cur.execute("DELETE FROM escenarios WHERE id=?", (escenario_id,))
    conn.commit()


# ---------- Consultas de experimentos (para evitar SQL en la UI) ----------

def obtener_experimento(conn, eid):
    """Datos completos de un experimento. Retorna tupla o None."""
    cur = conn.cursor()
    cur.execute(
        "SELECT id, title, description, tags, config_xml_path, binary_path, "
        "custom_cpp_path, custom_h_path, created_at, last_modified "
        "FROM experiments WHERE id=?", (eid,)
    )
    return cur.fetchone()


def listar_experimentos(conn):
    """Lista simple id, title de todos los experimentos (para combos de selección)."""
    cur = conn.cursor()
    try:
        cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
        return cur.fetchall()
    except Exception:
        return []


def listar_experimentos_con_estadisticas(conn):
    """Lista experimentos con conteo y estados de runs (para la página Experimentos).

    Retorna filas con: id, title, description, tags, config_xml_path, binary_path,
    custom_cpp_path, custom_h_path, last_modified, total_runs, completadas,
    en_curso, falladas, ultima_fecha.
    """
    cur = conn.cursor()
    try:
        cur.execute(
            """SELECT e.id, e.title, e.description, e.tags, e.config_xml_path,
                      e.binary_path, e.custom_cpp_path, e.custom_h_path, e.last_modified,
                      COUNT(r.id) as total_runs,
                      COALESCE(SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END), 0),
                      COALESCE(SUM(CASE WHEN r.status IN ('failed', 'cancelled')
                                       THEN 1 ELSE 0 END), 0),
                      MAX(r.start_time)
               FROM experiments e
               LEFT JOIN runs r ON e.id = r.experiment_id
               GROUP BY e.id
               ORDER BY e.id DESC"""
        )
        return cur.fetchall()
    except Exception:
        # Fallback sin estadísticas si la tabla runs no existe aún
        cur.execute(
            "SELECT id, title, description, tags, config_xml_path, binary_path, "
            "custom_cpp_path, custom_h_path, last_modified FROM experiments ORDER BY id DESC"
        )
        filas = cur.fetchall()
        return [f + (0, 0, 0, 0, None) for f in filas]
