#!/usr/bin/env python3
"""Núcleo compartido: datos por usuario, esquema SQLite y worker de réplicas.

Toda la lógica de negocio vive aquí; las ventanas (Notion legacy y Lab)
solo presentan. El motor de simulación sigue siendo exclusivamente PhysiCell.
"""
import os
import sys
import sqlite3
import hashlib
import json
import secrets
import traceback
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from .simulador import (
    generar_replica_config, registrar_run, actualizar_run,
    crear_batch, actualizar_batch,
)
from .motor_physicell import MotorPhysiCell, explicar_codigo_salida, verificar_binario


def _primera_linea(texto):
    """Primera linea con contenido, para resumir un motivo de fallo en una fila."""
    for ln in (texto or "").splitlines():
        if ln.strip():
            return ln.strip()[:200]
    return "sin detalle"


def _resumen_fallo(stdout, code=None):
    """Construye un motivo legible cuando el motor falla sin mensaje explicito."""
    lineas = [ln.strip() for ln in (stdout or "").splitlines() if ln.strip()]
    hexa = f" (0x{(int(code) & 0xFFFFFFFF):08X})" if code is not None else ""
    pista = explicar_codigo_salida(code) if code is not None else ""
    cabecera = f"PhysiCell terminó con código {code}{hexa}."
    if pista:
        cabecera += f"\n{pista}"
    if lineas:
        return f"{cabecera}\nÚltimas líneas de salida:\n" + "\n".join(lineas[-12:])
    return (f"{cabecera}\nSin salida del motor. Revisa que el ejecutable corresponda "
            "a tu modelo y que el XML sea compatible.")


def _contar_salidas(output_dir):
    """Cuenta snapshots, XML y .mat generados por PhysiCell.

    Mira tanto la carpeta de salida configurada como la raíz de la réplica,
    porque algunas versiones de PhysiCell guardan en la carpeta de trabajo.
    """
    import glob as _glob
    dirs = [output_dir, os.path.dirname(output_dir)] if output_dir else []
    n_svg = n_xml = n_mat = 0
    for d in dirs:
        if not d or not os.path.isdir(d):
            continue
        n_svg += len(_glob.glob(os.path.join(d, "snapshot*.svg")))
        n_xml += len(_glob.glob(os.path.join(d, "output*.xml")))
        n_mat += len(_glob.glob(os.path.join(d, "output*_cells.mat")))
    return n_svg, n_xml, n_mat


def _escribir_log_extra(log_path, texto):
    """Añade una nota al registro de la ejecución (sin fallar si no se puede)."""
    if not log_path:
        return
    try:
        with open(log_path, "a", encoding="utf-8", errors="replace") as f:
            f.write("\n" + str(texto) + "\n")
    except Exception:
        pass


class ReplicaWorker(QThread):
    prog = pyqtSignal(int, str)
    done = pyqtSignal(dict)
    fail = pyqtSignal(str)

    def __init__(self, experiment_id, base_xml, n_replicas, exe_path="", db_path="",
                 configuracion_id=None, escenario_id=None, timeout_min=0, inactividad_min=10):
        super().__init__()
        self.experiment_id = experiment_id
        self.base_xml = base_xml
        self.n_replicas = n_replicas
        self.exe_path = exe_path
        self.db_path = db_path
        self.configuracion_id = configuracion_id
        self.escenario_id = escenario_id
        self.timeout_min = timeout_min
        self.inactividad_min = inactividad_min
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        import sqlite3
        try:
            conn = sqlite3.connect(self.db_path)
            motor = MotorPhysiCell()
            base_dir = os.path.join(os.path.dirname(self.db_path), f"exp_{self.experiment_id}")
            os.makedirs(base_dir, exist_ok=True)
            # max_time para progreso real
            max_t = None
            try:
                import xml.etree.ElementTree as ET
                max_t = float(ET.parse(self.base_xml).getroot().find(".//max_time").text)
            except Exception:
                max_t = None
            fallos = []
            simuladas = 0
            # --- Lote: agrupa estas réplicas y guarda la huella de XML/motor ---
            try:
                batch_id = crear_batch(
                    conn, self.experiment_id, self.base_xml, self.exe_path,
                    self.n_replicas, seed_base=1001,
                    timeout_min=self.timeout_min,
                    inactividad_min=self.inactividad_min,
                )
            except Exception:
                batch_id = None
            timeout_ms = int(self.timeout_min * 60000) if self.timeout_min else None
            inactividad_s = max(60, int((self.inactividad_min or 10) * 60))
            for i in range(1, self.n_replicas + 1):
                if self._stop:
                    actualizar_batch(conn, batch_id, "cancelled", "Cancelado por el usuario")
                    self.fail.emit("Cancelado por usuario")
                    return
                rep_dir = os.path.join(base_dir, f"replica_{i}")
                os.makedirs(rep_dir, exist_ok=True)
                out_xml = os.path.join(rep_dir, f"replica_{i}.xml")
                run_id = None
                log_path = ""
                try:
                    generar_replica_config(self.base_xml, out_xml, seed=1000 + i,
                                           output_folder=os.path.join(rep_dir, "output"))
                    run_id = registrar_run(conn, self.experiment_id, i, status="running",
                                           output_dir=rep_dir, configuracion_id=self.configuracion_id,
                                           escenario_id=self.escenario_id, batch_id=batch_id)
                    # Registro completo del motor desde el primer momento
                    log_path = os.path.join(rep_dir, f"physicell_run_{run_id}.log")
                    actualizar_run(conn, run_id, "running", log_path=log_path)

                    # --- Verificación previa: ¿existe el proceso/ejecutable? ---
                    if not self.exe_path:
                        motivo = (
                            "No hay binario de PhysiCell configurado para este experimento: "
                            "solo se generó la configuración.\n"
                            "Asigna el ejecutable en la pestaña Configuración para poder simular."
                        )
                        _escribir_log_extra(log_path, motivo)
                        actualizar_run(conn, run_id, "registered", end=True,
                                       configuracion_id=self.configuracion_id,
                                       error_message=motivo)
                        self.prog.emit(int(i * 100 / self.n_replicas),
                                       f"Replica {i}/{self.n_replicas} registrada (sin binario)")
                        continue

                    problemas = verificar_binario(self.exe_path)
                    if problemas:
                        motivo = (
                            "No se puede ejecutar PhysiCell: " + problemas[0]
                            + ("" if len(problemas) == 1 else "\n- " + "\n- ".join(problemas[1:]))
                            + f"\nRuta configurada: {self.exe_path}"
                        )
                        _escribir_log_extra(log_path, motivo)
                        fallos.append(f"Réplica {i}: {_primera_linea(motivo)}")
                        actualizar_run(conn, run_id, "failed", end=True,
                                       configuracion_id=self.configuracion_id,
                                       error_message=motivo)
                        self.prog.emit(int(i * 100 / self.n_replicas),
                                       f"Replica {i}/{self.n_replicas} FALLO: {_primera_linea(motivo)}")
                        continue

                    base_pct = int((i - 1) * 100 / self.n_replicas)
                    paso = 100 / self.n_replicas
                    def _cb(sim_t, _ln, _b=base_pct, _p=paso):
                        if max_t:
                            pct = _b + min(1.0, sim_t / max_t) * _p
                            self.prog.emit(int(pct), f"Replica {i}/{self.n_replicas} t={sim_t:.0f}/{max_t:.0f} min")

                    def _inicio(pid, _i=i, _b=base_pct):
                        self.prog.emit(int(_b),
                                       f"Replica {_i}/{self.n_replicas}: PhysiCell iniciado (PID {pid})")

                    r = motor.ejecutar_cancelable(self.exe_path, out_xml, cwd=os.path.dirname(self.exe_path),
                                                  timeout_ms=timeout_ms, stop_flag=lambda: self._stop,
                                                  linea_cb=_cb, log_path=log_path,
                                                  inicio_cb=_inicio,
                                                  inactividad_s=inactividad_s)
                    # Guardar el PID real del proceso lanzado
                    if r.get("pid"):
                        actualizar_run(conn, run_id, "running", pid=r.get("pid"))

                    if r.get("cancelled"):
                        actualizar_run(conn, run_id, "cancelled", end=True,
                                       configuracion_id=self.configuracion_id,
                                       error_message="Cancelado por el usuario")
                        actualizar_batch(conn, batch_id, "cancelled", "Cancelado por el usuario")
                        conn.close()
                        self.fail.emit("Cancelado por usuario")
                        return
                    if r.get("ok"):
                        # El proceso terminó bien: comprobar que PhysiCell escribió resultados
                        salida_dir = os.path.join(rep_dir, "output")
                        n_svg, n_xml, n_mat = _contar_salidas(salida_dir)
                        if n_svg + n_xml + n_mat == 0:
                            motivo = (
                                "PhysiCell terminó con código 0 pero no generó archivos de salida "
                                f"(PID {r.get('pid') or 'desconocido'}).\n"
                                f"Carpeta revisada: {salida_dir}\n"
                                "El proceso arrancó, pero no guardó snapshots, XML ni .mat. "
                                "Revisa en el XML las opciones de guardado (save_svg, save_xml, "
                                "save_cells_mat) y las carpetas de salida."
                            )
                            _escribir_log_extra(log_path, motivo)
                            fallos.append(f"Réplica {i}: no generó archivos de salida")
                            actualizar_run(conn, run_id, "failed", end=True,
                                           configuracion_id=self.configuracion_id,
                                           error_message=motivo)
                            self.prog.emit(int(i * 100 / self.n_replicas),
                                           f"Replica {i}/{self.n_replicas} FALLO: sin archivos de salida")
                        else:
                            actualizar_run(conn, run_id, "completed", end=True,
                                           configuracion_id=self.configuracion_id)
                            simuladas += 1
                            self.prog.emit(
                                int(i * 100 / self.n_replicas),
                                f"Replica {i}/{self.n_replicas} lista: "
                                f"{n_svg} snapshots, {n_xml} XML, {n_mat} .mat",
                            )
                    else:
                        motivo = r.get("error") or _resumen_fallo(r.get("stdout", ""), r.get("code"))
                        if r.get("log_path"):
                            motivo += f"\nRegistro completo: {r['log_path']}"
                        fallos.append(f"Réplica {i}: {motivo}")
                        actualizar_run(conn, run_id, "failed", end=True,
                                       configuracion_id=self.configuracion_id,
                                       error_message=motivo)
                        self.prog.emit(int(i * 100 / self.n_replicas),
                                       f"Replica {i}/{self.n_replicas} FALLO: {_primera_linea(motivo)}")
                except Exception as e:
                    tb = traceback.format_exc()
                    motivo = f"{e}\n{tb[-1000:]}"
                    _escribir_log_extra(log_path, "Excepción de la app:\n" + tb)
                    fallos.append(f"Réplica {i}: {e}")
                    try:
                        if run_id is not None:
                            actualizar_run(conn, run_id, "failed", end=True,
                                           configuracion_id=self.configuracion_id,
                                           error_message=motivo)
                    except Exception:
                        pass
                    self.fail.emit(f"Réplica {i} falló: {motivo}")
                    try:
                        actualizar_batch(conn, batch_id, "failed", motivo)
                    except Exception:
                        pass
                    return
            if not fallos and simuladas == 0:
                estado_lote = "registered"
            elif not fallos:
                estado_lote = "completed"
            elif len(fallos) >= self.n_replicas:
                estado_lote = "failed"
            else:
                estado_lote = "partial"
            actualizar_batch(conn, batch_id, estado_lote,
                             "\n".join(fallos)[:4000] if fallos else None)
            conn.close()
            self.done.emit({
                "experiment_id": self.experiment_id,
                "replicas": self.n_replicas,
                "batch_id": batch_id,
                "fallos": fallos,
            })
        except Exception as e:
            tb = traceback.format_exc()
            try:
                if "conn" in locals():
                    actualizar_batch(conn, locals().get("batch_id"), "failed",
                                     f"{e}\n{tb[-1000:]}")
            except Exception:
                pass
            try:
                self.fail.emit(f"{e}\n\n{tb}")
            except Exception:
                pass


def get_user_data_dir():
    """Carpeta de datos especifica por usuario y SO."""
    if sys.platform.startswith('win'):
        base = os.environ.get('APPDATA') or os.path.expanduser('~')
        return os.path.join(base, "PhysiCell_Experiments")
    elif sys.platform.startswith('linux'):
        base = os.environ.get('XDG_DATA_HOME')
        if base:
            return os.path.join(base, "physicell_experiments")
        return os.path.join(os.path.expanduser('~'), '.local', 'share', 'physicell_experiments')
    else:
        base = os.path.expanduser('~/Library/Application Support')
        return os.path.join(base, "physicell-experiments")


def get_db_path():
    data_dir = get_user_data_dir()
    os.makedirs(data_dir, exist_ok=True)
    return os.path.join(data_dir, "experiments.db")


# ---------- Preferencias de la aplicacion ----------

PREFS_ARCHIVO = "engine_preferences.json"


def prefs_path():
    """Ruta del archivo JSON con las preferencias de la aplicacion."""
    return os.path.join(get_user_data_dir(), PREFS_ARCHIVO)


def cargar_preferencias():
    """Carga las preferencias persistidas. Devuelve un dict vacío si no existen."""
    try:
        with open(prefs_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def guardar_preferencias(prefs):
    """Persiste las preferencias de la aplicacion a disco."""
    path = prefs_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prefs, f, ensure_ascii=False)


def init_database():
    db_path = get_db_path()
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            config_xml_path TEXT,
            binary_path TEXT,
            custom_cpp_path TEXT,
            custom_h_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_modified DATETIME
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY,
            experiment_id INTEGER,
            run_number INTEGER,
            status TEXT DEFAULT 'pending',
            start_time DATETIME,
            end_time DATETIME,
            output_dir TEXT,
            error_message TEXT,
            log_path TEXT,
            pid INTEGER,
            batch_id INTEGER,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS escenarios (
            id INTEGER PRIMARY KEY,
            experiment_id INTEGER,
            nombre TEXT NOT NULL,
            config_xml_path TEXT,
            parametros_json TEXT DEFAULT '{}',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)
    try:
        cur.execute("ALTER TABLE experiments ADD COLUMN tags TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE experiments ADD COLUMN binary_path TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE experiments ADD COLUMN custom_cpp_path TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE experiments ADD COLUMN custom_h_path TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN escenario_id INTEGER")
    except Exception:
        pass
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY,
                experiment_id INTEGER,
                run_number INTEGER,
                tipo TEXT DEFAULT '2d',
                ruta_archivo TEXT,
                fps INTEGER DEFAULT 1,
                frames INTEGER DEFAULT 0,
                creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)
    except Exception:
        pass

    # --- Trazabilidad de configuraciones versionadas ---
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS configuraciones (
                id INTEGER PRIMARY KEY,
                experiment_id INTEGER NOT NULL,
                nombre TEXT NOT NULL DEFAULT 'base',
                xml_path TEXT NOT NULL,
                version INTEGER NOT NULL DEFAULT 1,
                es_activa INTEGER NOT NULL DEFAULT 0,
                creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)
    except Exception:
        pass

    # Vincular escenarios a una configuración (versión exacta del XML usada)
    try:
        cur.execute("ALTER TABLE escenarios ADD COLUMN configuracion_id INTEGER")
    except Exception:
        pass

    # Vincular cada ejecución a la configuración exacta que usó
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN configuracion_id INTEGER")
    except Exception:
        pass

    # Motivo del fallo de una ejecución (explicar el porqué, no solo "failed")
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN error_message TEXT")
    except Exception:
        pass

    # Registro completo de PhysiCell (stdout+stderr) y PID del proceso lanzado
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN log_path TEXT")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN pid INTEGER")
    except Exception:
        pass

    # Lote de ejecución: agrupa las réplicas lanzadas juntas y guarda su huella
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN batch_id INTEGER")
    except Exception:
        pass
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS batches (
                id INTEGER PRIMARY KEY,
                experiment_id INTEGER,
                creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
                n_replicas INTEGER,
                xml_path TEXT,
                xml_sha256 TEXT,
                exe_path TEXT,
                exe_sha256 TEXT,
                seed_base INTEGER,
                timeout_min INTEGER DEFAULT 0,
                inactividad_min INTEGER DEFAULT 10,
                python_version TEXT,
                plataforma TEXT,
                notas TEXT,
                status TEXT DEFAULT 'running',
                error_message TEXT,
                FOREIGN KEY (experiment_id) REFERENCES experiments(id)
            )
        """)
    except Exception:
        pass

    # Si no hay configuración base para experimentos existentes, crearla a partir de config_xml_path
    try:
        cur.execute("SELECT id, config_xml_path FROM experiments WHERE config_xml_path IS NOT NULL AND config_xml_path != ''")
        for eid, xml_path in cur.fetchall():
            cur.execute(
                "SELECT COUNT(*) FROM configuraciones WHERE experiment_id=? AND nombre='base'",
                (eid,),
            )
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO configuraciones (experiment_id, nombre, xml_path, version, es_activa) VALUES (?,?,?,1,1)",
                    (eid, "base", xml_path),
                )
    except Exception:
        pass

    # --- Autenticación: tabla de usuarios ---
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'usuario',
                activo INTEGER NOT NULL DEFAULT 1,
                creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
                ultimo_acceso DATETIME
            )
        """)
    except Exception:
        pass

    # Vincular experimentos a un usuario (propietario)
    try:
        cur.execute("ALTER TABLE experiments ADD COLUMN usuario_id INTEGER")
    except Exception:
        pass

    # Si no existe ningún usuario, crear uno por defecto (admin) para compatibilidad
    try:
        cur.execute("SELECT COUNT(*) FROM usuarios")
        if cur.fetchone()[0] == 0:
            pwd_hash = _hash_password("admin123")
            cur.execute(
                "INSERT INTO usuarios (username, email, password_hash, rol, activo) "
                "VALUES (?,?,?,?,1)",
                ("admin", "admin@localhost", pwd_hash),
            )
            admin_id = cur.lastrowid
            # Asignar experimentos existentes al admin por defecto
            cur.execute(
                "UPDATE experiments SET usuario_id=? WHERE usuario_id IS NULL",
                (admin_id,),
            )
    except Exception:
        pass

    conn.commit()
    conn.close()
    print(f"DB inicializada: {db_path}")
    return db_path


# ---------- Utilidades de contraseña ----------

def _hash_password(password: str) -> str:
    """Genera un hash seguro de la contraseña usando PBKDF2-HMAC-SHA256."""
    salt = secrets.token_hex(16)
    pwd_hash = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        100_000,
    )
    return f"pbkdf2_sha256$100000${salt}${pwd_hash.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verifica una contraseña contra su hash almacenado."""
    try:
        algorithm, iterations, salt, hash_value = stored_hash.split("$")
        # "pbkdf2_sha256" no es un nombre de hash válido para pbkdf2_hmac; se extrae solo "sha256"
        hash_name = algorithm.split("_", 1)[1] if "_" in algorithm else algorithm
        pwd_hash = hashlib.pbkdf2_hmac(
            hash_name,
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        return pwd_hash.hex() == hash_value
    except Exception:
        return False


# ---------- Gestión de usuarios ----------

def crear_usuario(conn, username, email, password, rol="usuario"):
    """Crea un nuevo usuario. Retorna el id o None si ya existe."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id FROM usuarios WHERE username=? OR email=?",
            (username, email),
        )
        if cur.fetchone():
            return None
        pwd_hash = _hash_password(password)
        cur.execute(
            "INSERT INTO usuarios (username, email, password_hash, rol, activo) "
            "VALUES (?,?,?,?,1)",
            (username, email, pwd_hash, rol),
        )
        conn.commit()
        return cur.lastrowid
    except Exception:
        conn.rollback()
        return None


def autenticar_usuario(conn, username, password):
    """Autentica un usuario. Retorna dict con datos del usuario o None."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, username, email, password_hash, rol, activo FROM usuarios WHERE username=?",
            (username,),
        )
        row = cur.fetchone()
        if not row:
            return None
        uid, uname, email, pwd_hash, rol, activo = row
        if not activo:
            return None
        if not _verify_password(password, pwd_hash):
            return None
        cur.execute(
            "UPDATE usuarios SET ultimo_acceso=CURRENT_TIMESTAMP WHERE id=?",
            (uid,),
        )
        conn.commit()
        return {
            "id": uid,
            "username": uname,
            "email": email,
            "rol": rol,
        }
    except Exception:
        return None


def obtener_usuario_por_id(conn, uid):
    """Retorna dict con datos del usuario o None."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, username, email, rol, activo FROM usuarios WHERE id=?",
            (uid,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "username": row[1],
            "email": row[2],
            "rol": row[3],
            "activo": bool(row[4]),
        }
    except Exception:
        return None


def listar_usuarios(conn):
    """Lista todos los usuarios (sin hashes de contraseña)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, username, email, rol, activo, creado_en FROM usuarios ORDER BY id"
        )
        return cur.fetchall()
    except Exception:
        return []


def cambiar_rol_usuario(conn, uid, rol):
    """Cambia el rol de un usuario."""
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE usuarios SET rol=? WHERE id=?",
            (rol, uid),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def desactivar_usuario(conn, uid):
    """Desactiva un usuario (no se puede eliminar si tiene experimentos)."""
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE usuarios SET activo=0 WHERE id=?",
            (uid,),
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False


def registrar_video(conn, experiment_id, run_number, tipo="2d", ruta_archivo="", fps=1, frames=0):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO videos (experiment_id, run_number, tipo, ruta_archivo, fps, frames) VALUES (?,?,?,?,?,?)",
        (experiment_id, run_number, tipo, ruta_archivo, fps, frames),
    )
    conn.commit()
    return cur.lastrowid


def listar_videos(conn, experiment_id):
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, run_number, tipo, ruta_archivo, fps, frames, creado_en FROM videos WHERE experiment_id=? ORDER BY id DESC",
            (experiment_id,),
        )
        return cur.fetchall()
    except Exception:
        return []


# ---------- Configuraciones versionadas (trazabilidad) ----------

def _copiar_xml_resguardo(db_path, experiment_id, version, xml_path):
    """Copia el XML a una carpeta de resguardo inmutable por experimento.

    Retorna la ruta de la copia si tuvo éxito, o la ruta original si no se pudo copiar.
    """
    if not xml_path or not os.path.isfile(xml_path):
        return xml_path
    try:
        data_dir = os.path.dirname(db_path) if db_path else ""
        resguardo_dir = os.path.join(data_dir, "configs", f"exp_{experiment_id}")
        os.makedirs(resguardo_dir, exist_ok=True)
        nombre_archivo = f"v{version}.xml"
        destino = os.path.join(resguardo_dir, nombre_archivo)
        if os.path.abspath(xml_path) != os.path.abspath(destino):
            import shutil
            shutil.copy2(xml_path, destino)
        return destino
    except Exception:
        return xml_path


def crear_configuracion(conn, experiment_id, nombre, xml_path, version=None,
                        activar=True, db_path=None, copiar_xml=False):
    """Registra una nueva versión de configuración para un experimento.

    Si se indica version, se usa esa; si no, se calcula la siguiente disponible.
    Solo una configuración por experimento puede estar activa a la vez.
    Si copiar_xml=True y se indica db_path, se copia el archivo XML a una
    carpeta de resguardo inmutable antes de registrar la ruta.
    """
    cur = conn.cursor()
    if version is None:
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM configuraciones WHERE experiment_id=?",
            (experiment_id,),
        )
        version = cur.fetchone()[0]
    if activar:
        cur.execute(
            "UPDATE configuraciones SET es_activa=0 WHERE experiment_id=?",
            (experiment_id,),
        )
    xml_registro = xml_path
    if copiar_xml and db_path:
        xml_registro = _copiar_xml_resguardo(db_path, experiment_id, version, xml_path)
    cur.execute(
        "INSERT INTO configuraciones (experiment_id, nombre, xml_path, version, es_activa) "
        "VALUES (?,?,?,?,?)",
        (experiment_id, nombre, xml_registro, version, 1 if activar else 0),
    )
    conn.commit()
    return cur.lastrowid


def configuracion_activa(conn, experiment_id):
    """Retorna (id, nombre, xml_path, version) de la configuración activa o None."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, nombre, xml_path, version FROM configuraciones "
            "WHERE experiment_id=? AND es_activa=1 ORDER BY version DESC LIMIT 1",
            (experiment_id,),
        )
        return cur.fetchone()
    except Exception:
        return None


def listar_configuraciones(conn, experiment_id):
    """Lista todas las configuraciones (versiones) de un experimento."""
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT id, nombre, xml_path, version, es_activa, creado_en "
            "FROM configuraciones WHERE experiment_id=? ORDER BY version",
            (experiment_id,),
        )
        return cur.fetchall()
    except Exception:
        return []


def activar_configuracion(conn, configuracion_id):
    """Marca una configuración como activa (desactiva las demás de su experimento)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT experiment_id FROM configuraciones WHERE id=?", (configuracion_id,)
    )
    row = cur.fetchone()
    if not row:
        return False
    experiment_id = row[0]
    cur.execute(
        "UPDATE configuraciones SET es_activa=0 WHERE experiment_id=?",
        (experiment_id,),
    )
    cur.execute(
        "UPDATE configuraciones SET es_activa=1 WHERE id=?", (configuracion_id,)
    )
    conn.commit()
    return True


def run_con_configuracion(conn, experiment_id, run_number, status="pending",
                          output_dir="", configuracion_id=None, escenario_id=None):
    """Registra una ejecución vinculada a una configuración exacta."""
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO runs (experiment_id, run_number, status, start_time, output_dir, "
        "configuracion_id, escenario_id) VALUES (?,?,?,?,?,?,?)",
        (experiment_id, run_number, status,
         datetime.now().isoformat(timespec="seconds"), output_dir,
         configuracion_id, escenario_id),
    )
    conn.commit()
    return cur.lastrowid


def actualizar_run_con_config(conn, run_id, status, end=False, configuracion_id=None):
    """Actualiza el estado de una ejecución, opcionalmente reasignando su configuración."""
    cur = conn.cursor()
    if end:
        cur.execute(
            "UPDATE runs SET status=?, end_time=?, configuracion_id=? WHERE id=?",
            (status, datetime.now().isoformat(timespec="seconds"),
             configuracion_id, run_id),
        )
    else:
        cur.execute(
            "UPDATE runs SET status=?, configuracion_id=? WHERE id=?",
            (status, configuracion_id, run_id),
        )
    conn.commit()
