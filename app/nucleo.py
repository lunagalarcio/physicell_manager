#!/usr/bin/env python3
"""Núcleo compartido: datos por usuario, esquema SQLite y worker de réplicas.

Toda la lógica de negocio vive aquí; las ventanas (Notion legacy y Lab)
solo presentan. El motor de simulación sigue siendo exclusivamente PhysiCell.
"""
import os
import sys
import sqlite3
from PyQt6.QtCore import QThread, pyqtSignal
from .simulador import generar_replica_config, registrar_run, actualizar_run
from .motor_physicell import MotorPhysiCell


class ReplicaWorker(QThread):
    prog = pyqtSignal(int, str)
    done = pyqtSignal(dict)
    fail = pyqtSignal(str)

    def __init__(self, experiment_id, base_xml, n_replicas, exe_path="", db_path=""):
        super().__init__()
        self.experiment_id = experiment_id
        self.base_xml = base_xml
        self.n_replicas = n_replicas
        self.exe_path = exe_path
        self.db_path = db_path
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
                generar_replica_config(self.base_xml, out_xml, seed=1000 + i, output_folder=os.path.join(rep_dir, "output"))
                run_id = registrar_run(conn, self.experiment_id, i, status="running", output_dir=rep_dir)
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
                        actualizar_run(conn, run_id, "cancelled", end=True)
                        conn.close()
                        self.fail.emit("Cancelado por usuario")
                        return
                    actualizar_run(conn, run_id, "completed" if r.get("ok") else "failed", end=True)
                else:
                    # Sin binario PhysiCell no hay simulacion: solo config generada
                    actualizar_run(conn, run_id, "registered", end=True)
                self.prog.emit(int(i * 100 / self.n_replicas), f"Replica {i}/{self.n_replicas} lista (PhysiCell)")
            conn.close()
            self.done.emit({"experiment_id": self.experiment_id, "replicas": self.n_replicas})
        except Exception as e:
            try:
                self.fail.emit(str(e))
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
    conn.commit()
    conn.close()
    print(f"DB inicializada: {db_path}")
    return db_path


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
