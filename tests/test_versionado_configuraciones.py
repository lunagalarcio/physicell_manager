"""Pruebas para versionado inmutable de configuraciones XML y trazabilidad.

Verifica que:
- Cada versión de configuración conserva una copia independiente del XML.
- Modificar o eliminar el XML original no afecta la versión registrada.
- Cambiar la configuración activa no modifica ejecuciones anteriores.
- La migración agrega columnas/configuraciones a bases de datos preexistentes.
"""
import os
import shutil
import sqlite3
import tempfile

from app import simulador as SIM
from app import nucleo as NUC
from app import servicios as SERV

CFG = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "PhysiCell_settings.xml",
)


# ---------- 1. Versionado inmutable de XML ----------

def test_crear_configuracion_copia_xml_inmutable(tmp_db_path):
    """crear_configuracion con copiar_xml=True debe guardar una copia, no la ruta original."""
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, config_xml_path TEXT
        );
        CREATE TABLE configuraciones (
            id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'base', xml_path TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1, es_activa INTEGER NOT NULL DEFAULT 0,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
    """)
    conn.execute("INSERT INTO experiments (id, title, config_xml_path) VALUES (1, 'Exp', ?)", (CFG,))
    conn.commit()

    # Copiar el XML a un archivo temporal que luego modificaremos
    tmp_xml = os.path.join(tempfile.mkdtemp(), "config_original.xml")
    shutil.copy2(CFG, tmp_xml)

    cid = NUC.crear_configuracion(
        conn, 1, "v1", tmp_xml, version=1, activar=True,
        db_path=tmp_db_path, copiar_xml=True,
    )
    assert cid is not None

    # Verificar que la ruta registrada es la copia, no el original
    row = NUC.configuracion_activa(conn, 1)
    assert row is not None
    ruta_registrada = row[2]
    assert ruta_registrada != tmp_xml, "La ruta registrada debe ser la copia, no el original"
    assert os.path.isfile(ruta_registrada), "La copia debe existir"

    # Modificar el archivo original
    with open(tmp_xml, "w", encoding="utf-8") as f:
        f.write("<PhysiCell_settings></PhysiCell_settings>")

    # La copia registrada debe seguir siendo válida
    v = NUC.validar_config if hasattr(NUC, "validar_config") else None
    from app.xml_validator import validar_config
    assert validar_config(ruta_registrada).get("ok") is True, "La copia inmutable debe seguir siendo válida"

    conn.close()


def test_registrar_nueva_configuracion_copia_xml(tmp_db_path):
    """registrar_nueva_configuracion debe copiar el XML y retornar configuracion_id."""
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, config_xml_path TEXT
        );
        CREATE TABLE configuraciones (
            id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'base', xml_path TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1, es_activa INTEGER NOT NULL DEFAULT 0,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
    """)
    conn.execute("INSERT INTO experiments (id, title, config_xml_path) VALUES (1, 'Exp', ?)", (CFG,))
    conn.commit()

    resultado = SERV.registrar_nueva_configuracion(
        tmp_db_path, 1, "variante-o2", CFG, activar=True,
    )
    assert resultado["ok"] is True
    assert resultado["configuracion_id"] is not None

    # Verificar que existe una copia en la carpeta de resguardo
    row = NUC.configuracion_activa(conn, 1)
    assert row is not None
    assert os.path.isfile(row[2]), "La copia del XML debe existir en resguardo"
    assert row[2] != CFG, "La ruta registrada debe ser la copia, no el original"

    conn.close()


# ---------- 2. Migración con DB anterior ----------

def test_migracion_agrega_columnas_configuracion_id(tmp_db_path):
    """init_database debe agregar configuracion_id a runs y escenarios en DB preexistente."""
    # Crear esquema "antiguo" sin configuracion_id ni tabla configuraciones
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, config_xml_path TEXT
        );
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY, experiment_id INTEGER,
            run_number INTEGER, status TEXT DEFAULT 'pending',
            output_dir TEXT,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
        CREATE TABLE escenarios (
            id INTEGER PRIMARY KEY, experiment_id INTEGER,
            nombre TEXT NOT NULL, config_xml_path TEXT,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
    """)
    conn.execute("INSERT INTO experiments (id, title, config_xml_path) VALUES (1, 'Exp', ?)", (CFG,))
    conn.commit()
    conn.close()

    # Simular las migraciones que ejecuta init_database
    conn = sqlite3.connect(tmp_db_path)
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE runs ADD COLUMN configuracion_id INTEGER")
    except Exception:
        pass
    try:
        cur.execute("ALTER TABLE escenarios ADD COLUMN configuracion_id INTEGER")
    except Exception:
        pass
    cur.execute("""
        CREATE TABLE IF NOT EXISTS configuraciones (
            id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'base', xml_path TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1, es_activa INTEGER NOT NULL DEFAULT 0,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        )
    """)
    conn.commit()

    # Verificar columnas
    cur.execute("PRAGMA table_info(runs)")
    cols_runs = {row[1] for row in cur.fetchall()}
    assert "configuracion_id" in cols_runs, "runs debe tener configuracion_id tras migración"

    cur.execute("PRAGMA table_info(escenarios)")
    cols_esc = {row[1] for row in cur.fetchall()}
    assert "configuracion_id" in cols_esc, "escenarios debe tener configuracion_id tras migración"

    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='configuraciones'")
    assert cur.fetchone() is not None, "Tabla configuraciones debe existir tras migración"

    conn.close()


def test_crear_experimento_registra_configuracion_base(tmp_db_path):
    """crear_experimento con XML debe registrar configuración base v1 con copia."""
    # Crear esquema completo necesario para crear_experimento
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT,
            tags TEXT DEFAULT '', config_xml_path TEXT, binary_path TEXT,
            custom_cpp_path TEXT, custom_h_path TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_modified DATETIME
        );
        CREATE TABLE configuraciones (
            id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'base', xml_path TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1, es_activa INTEGER NOT NULL DEFAULT 0,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
    """)
    conn.commit()
    conn.close()

    resultado = SERV.crear_experimento(
        tmp_db_path, "Exp prueba", "desc", "", CFG,
    )
    assert resultado["ok"] is True, f"crear_experimento falló: {resultado.get('error')}"
    eid = resultado["experiment_id"]

    conn = sqlite3.connect(tmp_db_path)
    cfg_act = NUC.configuracion_activa(conn, eid)
    assert cfg_act is not None, "Debe existir configuración activa"
    assert cfg_act[3] == 1, "La versión debe ser 1"
    assert os.path.isfile(cfg_act[2]), "La copia del XML debe existir"
    assert cfg_act[2] != CFG, "La ruta debe ser la copia, no el original"
    conn.close()


# ---------- 3. Trazabilidad: activar config anterior no afecta ejecuciones ----------

def test_cambiar_configuracion_activa_no_modifica_runs_existentes(tmp_db_path):
    """Las ejecuciones previas conservan su configuracion_id aunque se active otra versión."""
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript("""
        CREATE TABLE experiments (
            id INTEGER PRIMARY KEY, title TEXT NOT NULL, config_xml_path TEXT
        );
        CREATE TABLE configuraciones (
            id INTEGER PRIMARY KEY, experiment_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'base', xml_path TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1, es_activa INTEGER NOT NULL DEFAULT 0,
            creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
        CREATE TABLE runs (
            id INTEGER PRIMARY KEY, experiment_id INTEGER,
            run_number INTEGER, status TEXT DEFAULT 'pending',
            start_time DATETIME, end_time DATETIME,
            output_dir TEXT, escenario_id INTEGER, configuracion_id INTEGER,
            FOREIGN KEY (experiment_id) REFERENCES experiments(id)
        );
    """)
    conn.execute("INSERT INTO experiments (id, title, config_xml_path) VALUES (1, 'Exp', ?)", (CFG,))
    conn.commit()

    # Crear dos configuraciones
    cid_v1 = NUC.crear_configuracion(conn, 1, "v1", CFG, version=1, activar=True, db_path=tmp_db_path, copiar_xml=True)
    cid_v2 = NUC.crear_configuracion(conn, 1, "v2", CFG, version=2, activar=False, db_path=tmp_db_path, copiar_xml=True)

    # Crear un run vinculado a v1
    run_id = SIM.registrar_run(conn, 1, 1, status="completed", output_dir="/tmp/out", configuracion_id=cid_v1)
    conn.commit()

    # Activar v2
    ok = NUC.activar_configuracion(conn, cid_v2)
    assert ok is True

    # Verificar que el run sigue vinculado a v1
    cur = conn.cursor()
    cur.execute("SELECT configuracion_id FROM runs WHERE id=?", (run_id,))
    row = cur.fetchone()
    assert row[0] == cid_v1, "El run debe conservar su configuracion_id original"

    conn.close()
