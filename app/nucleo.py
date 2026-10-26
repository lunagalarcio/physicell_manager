#!/usr/bin/env python3
"""Núcleo compartido: datos por usuario, esquema SQLite y worker de réplicas.

Toda la lógica de negocio vive aquí; las ventanas (Notion legacy y Lab)
solo presentan. El motor de simulación sigue siendo exclusivamente PhysiCell.
"""
import os
import sys
import sqlite3
import hashlib
import secrets
import traceback
from datetime import datetime
from PyQt6.QtCore import QThread, pyqtSignal
from .simulador import generar_replica_config, registrar_run, actualizar_run
from .motor_physicell import MotorPhysiCell


class ReplicaWorker(QThread):
    prog = pyqtSignal(int, str)
    done = pyqtSignal(dict)
    fail = pyqtSignal(str)

    def __init__(self, experiment_id, base_xml, n_replicas, exe_path="", db_path="",
                 configuracion_id=None):
        super().__init__()
        self.experiment_id = experiment_id
        self.base_xml = base_xml
        self.n_replicas = n_replicas
        self.exe_path = exe_path
        self.db_path = db_path
        self.configuracion_id = configuracion_id
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
            for i in range(1, self.n_replicas + 1):
                if self._stop:
                    self.fail.emit("Cancelado por usuario")
                    return
                rep_dir = os.path.join(base_dir, f"replica_{i}")
                os.makedirs(rep_dir, exist_ok=True)
                out_xml = os.path.join(rep_dir, f"replica_{i}.xml")
                try:
                    generar_replica_config(self.base_xml, out_xml, seed=1000 + i,
                                           output_folder=os.path.join(rep_dir, "output"))
                    run_id = registrar_run(conn, self.experiment_id, i, status="running",
                                           output_dir=rep_dir, configuracion_id=self.configuracion_id)
                    if self.exe_path and os.path.isfile(self.exe_path):
                        base_pct = int((i - 1) * 100 / self.n_replicas)
                        paso = 100 / self.n_replicas
                        def _cb(sim_t, _ln, _b=base_pct, _p=paso):
                            if max_t:
                                pct = _b + min(1.0, sim_t / max_t) * _p
                                self.prog.emit(int(pct), f"Replica {i}/{self.n_replicas} t={sim_t:.0f}/{max_t:.0f} min")
                        r = motor.ejecutar_cancelable(self.exe_path, out_xml, cwd=os.path.dirname(self.exe_path),
                                                      timeout_ms=600000, stop_flag=lambda: self._stop, linea_cb=_cb)
                        if r.get("cancelled"):
                            actualizar_run(conn, run_id, "cancelled", end=True,
                                           configuracion_id=self.configuracion_id)
                            conn.close()
                            self.fail.emit("Cancelado por usuario")
                            return
                        actualizar_run(conn, run_id, "completed" if r.get("ok") else "failed", end=True,
                                       configuracion_id=self.configuracion_id)
                    else:
                        # Sin binario PhysiCell no hay simulacion: solo config generada
                        actualizar_run(conn, run_id, "registered", end=True,
                                       configuracion_id=self.configuracion_id)
                except Exception as e:
                    tb = traceback.format_exc()
                    try:
                        if 'run_id' in locals():
                            actualizar_run(conn, run_id, "failed", end=True,
                                           configuracion_id=self.configuracion_id)
                    except Exception:
                        pass
                    self.fail.emit(f"Réplica {i} falló: {e}\n{tb[-1000:]}")
                    return
                self.prog.emit(int(i * 100 / self.n_replicas), f"Replica {i}/{self.n_replicas} lista (PhysiCell)")
            conn.close()
            self.done.emit({"experiment_id": self.experiment_id, "replicas": self.n_replicas})
        except Exception as e:
            tb = traceback.format_exc()
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
