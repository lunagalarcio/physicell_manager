"""Pruebas funcionales de PhysiCell Lab — Casos de Prueba CP01–CP13 (Tabla 17).

Cada ``test_CPnn`` implementa un caso funcional a partir del comportamiento
esperado de la Tabla 17, trazando el caso al requerimiento funcional
(RF01–RF13) y, cuando aplica, a la regla de no falla (RNF09) que lo sustenta:

    CP01 -> RF04  Crear experimento con nombre y descripción (id único, fecha).
    CP02 -> RF05  Crear escenarios y réplicas dentro de un experimento.
    CP03 -> RF01, RF02  Importar un XML válido de PhysiCell.
    CP04 -> RF02  Importar un XML mal formado (rechazo con mensaje descriptivo).
    CP05 -> RF03  Editar y guardar una configuración (nueva versión, recuperable).
    CP06 -> RF06, RF07  Ejecutar una simulación de una réplica (estado final).
    CP07 -> RF06, RF07  Ejecutar varias réplicas por lote (semilla, fechas, duración).
    CP08 -> RNF09  Ejecutar una simulación con error (estado fallida + error).
    CP09 -> RF08  Consultar los resultados de una ejecución.
    CP10 -> RF09, RF10  Visualizar un estado temporal (3D) con rotar/ampliar/desplazar.
    CP11 -> RF11  Comparar escenarios o réplicas.
    CP12 -> RF12  Generar y exportar un reporte.
    CP13 -> RF13  Consultar la trazabilidad desde un resultado.
"""
import os
import sqlite3
from datetime import datetime

from app import servicios as SERV
from app import simulador as SIM
from app import nucleo as NUC
from app import reportes as REP
from app import exportacion as EXP
from app import comparacion as CMP
from app import estadistica as EST
from app import motor_physicell as MOT
from app import visualizador as VIS
from app import visor_widget as VW
from app import xml_validator as XV

BATCH_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER,
    creado_en TEXT,
    n_replicas INTEGER,
    xml_path TEXT,
    xml_sha256 TEXT,
    exe_path TEXT,
    exe_sha256 TEXT,
    seed_base INTEGER,
    timeout_min INTEGER,
    inactividad_min INTEGER,
    python_version TEXT,
    plataforma TEXT,
    notas TEXT,
    status TEXT,
    error_message TEXT
)
"""

INITIAL_XML = """<?xml version="1.0" encoding="UTF-8"?>
<PhysiCell_settings>
    <microenvironment>
        <domain>
            <mesh>
                <bounding_box>-500 -500 -10 500 500 10</bounding_box>
            </mesh>
        </domain>
    </microenvironment>
</PhysiCell_settings>
"""

SNAPSHOT_SVG = """<?xml version="1.0" encoding="UTF-8"?>
<PhysiCell_frames>
    <cell id="0" type="default">
        <cells id="cells">
            <circle cx="100" cy="100" r="5" fill="rgb(255,0,0)"/>
        </cells>
    </cell>
</PhysiCell_frames>
"""


# ----------------------------------------------------------------------
# Helpers comunes para los casos funcionales
# ----------------------------------------------------------------------

def _crear_experimento(db_path, titulo, descripcion, cfg_path, tags="funcional"):
    """Crea un experimento (y su configuración base v1) a través del servicio."""
    res = SERV.crear_experimento(db_path, titulo, descripcion, tags, cfg_path)
    assert res.get("ok") is True, f"crear_experimento falló: {res.get('error')}"
    return res["experiment_id"]


def _avanzar_run(db_conn, run_id, status, error_message=None):
    """Simula el ciclo de vida de una réplica: ejecutando -> estado final."""
    SIM.actualizar_run(db_conn, run_id, "running")
    SIM.actualizar_run(db_conn, run_id, status, end=True, error_message=error_message)


def _asegurar_columnas_y_lote(db_conn):
    """Agrega las tablas/columnas que usa el motor de réplicas en el esquema SQL de prueba."""
    db_conn.execute(BATCH_TABLE_SQL)
    cols = {row[1] for row in db_conn.execute("PRAGMA table_info(runs)").fetchall()}
    if "batch_id" not in cols:
        db_conn.execute("ALTER TABLE runs ADD COLUMN batch_id INTEGER")
    db_conn.commit()


# ======================================================================
# CP01 – RF04: Crear un experimento con nombre y descripción
# ======================================================================

def test_CP01_crear_experimento_registra_metadatos_y_config_base(tmp_db_ready, cfg_path):
    """CP01: crear un experimento con nombre y descripción debe registrarse con
    identificador único y fecha de creación."""
    eid1 = _crear_experimento(tmp_db_ready, "Experimento CP01", "Descripcion CP01", cfg_path)
    eid2 = _crear_experimento(tmp_db_ready, "Experimento CP01", "Otra descripcion CP01", cfg_path)
    assert eid1 > 0 and eid2 > 0, "El experimento debe tener identificador propio"
    assert eid1 != eid2, "Cada experimento debe tener identificador unico"

    conn = sqlite3.connect(tmp_db_ready)
    for eid, titulo, desc in (
        (eid1, "Experimento CP01", "Descripcion CP01"),
        (eid2, "Experimento CP01", "Otra descripcion CP01"),
    ):
        row = conn.execute(
            "SELECT id, title, description, created_at FROM experiments WHERE id=?",
            (eid,),
        ).fetchone()
        assert row is not None, "El experimento debe existir en la base de datos"
        assert row[0] == eid
        assert row[1] == titulo, "El nombre del experimento debe conservarse"
        assert row[2] == desc, "La descripcion del experimento debe conservarse"
        assert row[3] is not None, "Debe registrarse la fecha de creacion"
    cfg = NUC.configuracion_activa(conn, eid1)
    conn.close()

    assert cfg is not None, "Crear experimento debe registrar una configuracion base"
    assert cfg[3] == 1, "La configuracion base debe ser la version 1"


# ======================================================================
# CP02 – RF05: Crear escenarios y réplicas dentro de un experimento
# ======================================================================

def test_CP02_crear_escenario_y_replica_asociadas(tmp_db_ready, cfg_path, tmp_replica_dir):
    """CP02: crear escenarios y réplicas dentro de un experimento debe dejarlas
    asociadas jerarquicamente al experimento."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP02", "Descripcion CP02", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    _asegurar_columnas_y_lote(conn)
    sid = SIM.crear_escenario(conn, eid, "escenario-1", cfg_path, "{}")
    cfg_id = NUC.configuracion_activa(conn, eid)[0]
    run_id = SIM.registrar_run(
        conn, eid, 1, status="pending", output_dir=tmp_replica_dir,
        escenario_id=sid, configuracion_id=cfg_id,
    )

    # El escenario queda asociado al experimento
    cur = conn.execute("SELECT experiment_id FROM escenarios WHERE id=?", (sid,))
    assert cur.fetchone()[0] == eid

    # La réplica queda asociada al experimento y al escenario
    cur = conn.execute(
        "SELECT experiment_id, escenario_id, configuracion_id FROM runs WHERE id=?",
        (run_id,),
    )
    run = cur.fetchone()
    assert run[0] == eid, "La replica debe pertenecer al experimento"
    assert run[1] == sid, "La replica debe pertenecer al escenario"
    assert run[2] == cfg_id, "La replica debe estar asociada a la configuracion"
    conn.close()


# ======================================================================
# CP03 – RF01/RF02: Importar un archivo XML valido de PhysiCell
# ======================================================================

def test_CP03_importar_xml_valido_carga_y_valida(tmp_db_ready, cfg_path):
    """CP03: importar un XML valido de PhysiCell debe cargarse y validarse sin errores."""
    resultado = XV.validar_config(cfg_path)
    assert resultado["ok"] is True
    assert resultado["errores"] == []

    eid = _crear_experimento(tmp_db_ready, "Experimento CP03", "Descripcion CP03", cfg_path)
    completo = SERV.obtener_experimento_completo(tmp_db_ready, eid)
    assert completo.get("ok") is True, f"obtener_experimento_completo fallo: {completo.get('error')}"

    exp = completo["experimento"]
    assert exp["id"] == eid
    assert exp["title"] == "Experimento CP03"
    assert exp["description"] == "Descripcion CP03"

    cfg_activa = completo["configuracion_activa"]
    assert cfg_activa is not None
    assert cfg_activa["version"] == 1, "La configuracion base registrada debe ser la version 1"


# ======================================================================
# CP04 – RF02: Importar un archivo XML mal formado
# ======================================================================

def test_CP04_importar_xml_mal_formado_rechazado(tmp_output_dir, tmp_db_ready, cfg_path):
    """CP04: importar un XML mal formado debe rechazarse con un mensaje descriptivo."""
    mal = os.path.join(tmp_output_dir, "mal_formado.xml")
    with open(mal, "w", encoding="utf-8") as f:
        f.write("<PhysiCell_settings><domain><x_min>0</x_min>")

    resultado = XV.validar_config(mal)
    assert resultado["ok"] is False, "El XML mal formado debe rechazarse"
    assert len(resultado["errores"]) > 0, "Debe haber un mensaje de error descriptivo"
    assert any("mal formado" in e.lower() for e in resultado["errores"]), \
        "El mensaje debe describir el error de sintaxis XML"

    eid = _crear_experimento(tmp_db_ready, "Experimento CP04", "Descripcion CP04", cfg_path)
    exe = os.path.join(tmp_output_dir, "project.exe")
    with open(exe, "w", encoding="utf-8"):
        pass
    validacion = SERV.validar_para_ejecutar(tmp_db_ready, eid, mal, exe)
    assert validacion["ok"] is False, "La validacion en ejecucion debe fallar para XML mal formado"
    assert len(validacion["errores"]) > 0, "Debe haber un error de validacion del XML"
    assert any("xml" in e.lower() for e in validacion["errores"]), \
        "Debe reportarse el XML invalido en los errores de validacion"


# ======================================================================
# CP05 – RF03: Editar y guardar una configuracion (versionado)
# ======================================================================

def test_CP05_editar_y_guardar_configuracion_version(tmp_db_ready, tmp_db_path, cfg_path):
    """CP05: editar y guardar una configuracion debe crear una nueva version y la
    anterior debe poder recuperarse."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP05", "Descripcion CP05", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    cfg_activa_previa = NUC.configuracion_activa(conn, eid)
    assert cfg_activa_previa is not None
    cid1 = cfg_activa_previa[0]
    cid2 = NUC.crear_configuracion(
        conn, eid, "v2", cfg_path, version=2, activar=True, db_path=tmp_db_path, copiar_xml=True,
    )
    conn.close()

    conn = sqlite3.connect(tmp_db_ready)
    cfgs = NUC.listar_configuraciones(conn, eid)
    assert len(cfgs) == 2, "Debe existir la version base y la nueva version"
    por_version = {c[3]: c for c in cfgs}
    assert por_version[2][4] == 1, "La nueva version (v2) debe activarse"
    assert por_version[1][4] == 0, "La version anterior (v1) debe desactivarse"
    assert NUC.activar_configuracion(conn, cid1) is True
    cfg_activa = NUC.configuracion_activa(conn, eid)
    cfgs = NUC.listar_configuraciones(conn, eid)
    conn.close()

    assert cfg_activa is not None
    assert cfg_activa[3] == 1, "La version anterior (v1) debe poder recuperarse"
    assert cfg_activa[0] == cid1
    assert len(cfgs) == 2, "La edicion debe conservar la version anterior"


# ======================================================================
# CP06 – RF06/RF07: Ejecutar una simulacion de una replica
# ======================================================================

def test_CP06_ejecutar_simulacion_de_replica_transicion_estado(
    tmp_db_ready, cfg_path, tmp_replica_dir,
):
    """CP06: ejecutar una simulacion de una replica debe pasar de pendiente a
    ejecutando y a completada."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP06", "Descripcion CP06", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    _asegurar_columnas_y_lote(conn)
    cfg_id = NUC.configuracion_activa(conn, eid)[0]

    assert SIM.listar_runs(conn, eid) == [], "Al crear el experimento no debe haber ejecuciones"

    run_id = SIM.registrar_run(
        conn, eid, 1, status="pending", output_dir=tmp_replica_dir, configuracion_id=cfg_id,
    )
    _avanzar_run(conn, run_id, "completed")

    runs = SIM.listar_runs(conn, eid)
    assert len(runs) == 1
    run = runs[0]
    assert run[1] == 1, "El run_number debe identificarse como la replica 1"
    assert run[2] == "completed", "El estado final debe ser completada"
    assert run[3] is not None, "Debe registrarse la fecha de inicio"
    assert run[4] is not None, "Debe registrarse la fecha de fin"
    conn.close()


# ======================================================================
# CP07 – RF06/RF07: Ejecutar varias replicas por lote
# ======================================================================

def test_CP07_ejecutar_varias_replicas_por_lote(tmp_db_ready, cfg_path, tmp_replica_dir, db_conn):
    """CP07: ejecutar varias replicas por lote debe registrar semilla, fechas y duracion."""
    db_conn.executescript(BATCH_TABLE_SQL)
    eid = _crear_experimento(tmp_db_ready, "Experimento CP07", "Descripcion CP07", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    cfg_id = NUC.configuracion_activa(conn, eid)[0]
    batch_id = SIM.crear_batch(
        conn, eid, cfg_path, exe_path=os.path.join(tmp_replica_dir, "project.exe"),
        n_replicas=3, seed_base=1000, timeout_min=0, inactividad_min=10,
    )
    batch = SIM.obtener_batch(conn, batch_id)
    assert batch is not None
    assert batch["n_replicas"] == 3, "El lote debe registrar las 3 replicas"
    assert batch["seed_base"] == 1000, "El lote debe registrar la semilla base"
    assert batch["status"] == "running"

    run_ids = []
    for i in range(1, 4):
        run_ids.append(
            SIM.registrar_run(
                conn, eid, i, status="pending", output_dir=tmp_replica_dir,
                configuracion_id=cfg_id, batch_id=batch_id,
            )
        )
    for rid in run_ids:
        _avanzar_run(conn, rid, "completed")
    SIM.actualizar_batch(conn, batch_id, "completed")
    conn.commit()

    batch = SIM.obtener_batch(conn, batch_id)
    assert batch["status"] == "completed", "El lote debe cerrarse como completado"

    runs = SIM.listar_runs(conn, eid)
    assert len(runs) == 3, "El lote de 3 replicas debe generar 3 ejecuciones"
    runs_ordenados = sorted(runs, key=lambda r: r[1])
    for i, run in enumerate(runs_ordenados, start=1):
        assert run[1] == i, "Las replicas del lote deben numerarse de 1 a n"
        assert run[2] == "completed"
        assert run[3] is not None and run[4] is not None, "Debe registrar inicio y fin"
        duracion = datetime.fromisoformat(run[4]) - datetime.fromisoformat(run[3])
        assert duracion.total_seconds() >= 0, "La duracion no puede ser negativa"
    conn.close()


# ======================================================================
# CP08 – RNF09: Ejecutar una simulacion con error
# ======================================================================

def test_CP08_ejecutar_simulacion_con_error_estado_fallida(
    tmp_db_ready, cfg_path, tmp_replica_dir,
):
    """CP08: ejecutar una simulacion con error debe dejar el estado fallida con el
    error registrado (RNF09)."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP08", "Descripcion CP08", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    _asegurar_columnas_y_lote(conn)
    cfg_id = NUC.configuracion_activa(conn, eid)[0]
    run_id = SIM.registrar_run(
        conn, eid, 1, status="pending", output_dir=tmp_replica_dir, configuracion_id=cfg_id,
    )
    SIM.actualizar_run(
        conn, run_id, "failed", end=True,
        error_message="PhysiCell: error de ejecucion simulada (codigo 1)",
    )
    conn.commit()

    runs = SIM.listar_runs(conn, eid)
    assert len(runs) == 1
    run = runs[0]
    assert run[2] == "failed", "El estado debe pasar a fallida"
    assert run[4] is not None, "Debe registrar la fecha de fin"
    assert run[6] is not None, "Debe registrar el mensaje de error"
    assert "error de ejecucion" in run[6].lower()
    conn.close()


# ======================================================================
# CP09 – RF08: Consultar los resultados de una ejecucion
# ======================================================================

def test_CP09_consultar_resultados_de_ejecucion(
    tmp_db_ready, cfg_path, tmp_replica_dir,
):
    """CP09: consultar los resultados de una ejecucion debe listarlos asociados al
    experimento, escenario y replica."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP09", "Descripcion CP09", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    _asegurar_columnas_y_lote(conn)
    sid = SIM.crear_escenario(conn, eid, "escenario-1", cfg_path, "{}")
    cfg_id = NUC.configuracion_activa(conn, eid)[0]
    run_id = SIM.registrar_run(
        conn, eid, 1, status="completed", output_dir=tmp_replica_dir,
        escenario_id=sid, configuracion_id=cfg_id,
    )
    _avanzar_run(conn, run_id, "completed")
    conn.commit()

    runs = SIM.listar_runs(conn, eid)
    assert len(runs) == 1, "Debe listar la ejecucion del experimento"
    assert runs[0][2] == "completed"

    escenarios = SIM.listar_escenarios(conn, eid)
    assert len(escenarios) == 1
    assert escenarios[0][0] == sid
    assert escenarios[0][1] == "escenario-1"

    datos = EST.datos_por_experimento(tmp_db_ready, eid)
    assert len(datos) == 1, "Los resultados deben estar asociados a la ejecucion"
    assert datos[0]["run"] == 1
    assert "n_celulas_final" in datos[0]

    resumen = VIS.resumen_resultados(tmp_replica_dir)
    assert resumen["n_svg"] == 0
    assert resumen["n_xml"] == 0
    assert resumen["n_mat"] == 0
    conn.close()


# ======================================================================
# CP10 – RF09/RF10: Visualizar un estado temporal en 3D
# ======================================================================

def test_CP10_visualizar_estado_temporal_en_3d(tmp_output_dir):
    """CP10: visualizar un estado temporal debe mostrar el frame, leer los bounds y
    permitir la lectura del estado (rotar/ampliar/desplazar es de la capa 3D)."""
    with open(os.path.join(tmp_output_dir, "initial.xml"), "w", encoding="utf-8") as f:
        f.write(INITIAL_XML)
    for i, contenido in enumerate((SNAPSHOT_SVG, SNAPSHOT_SVG)):
        with open(os.path.join(tmp_output_dir, f"snapshot-{i}.svg"), "w", encoding="utf-8") as f:
            f.write(contenido)

    snaps = VW.listar_snapshots(tmp_output_dir)
    assert len(snaps) == 2, "Debe listar los snapshots temporalmente ordenados"

    bounds = VW.leer_bounds(tmp_output_dir)
    assert bounds is not None, "Debe leer los bounds del initial.xml"
    assert bounds["xmin"] == -500.0
    assert bounds["xmax"] == 500.0
    assert bounds["zmin"] == -10.0
    assert bounds["zmax"] == 10.0

    for snap in snaps:
        frame = VW.parse_snapshot_svg(snap, bounds)
        assert frame["ok"] is True, f"El frame temporal debe parsearse: {snap}"
        assert int(frame["n"]) >= 1

    info = VIS.leer_svg_info(snaps[0])
    assert info["ok"] is True
    assert info["n_agentes"] >= 1

    frames = VIS.listar_frames(tmp_output_dir)
    assert len(frames["svg"]) == 2, "Debe listar los frames del estado temporal"


# ======================================================================
# CP11 – RF11: Comparar escenarios o replicas
# ======================================================================

def test_CP11_comparar_replicas_muestra_resultados(tmp_db_ready, cfg_path, tmp_replica_dir, tmp_exp_dir):
    """CP11: comparar escenarios o replicas debe mostrar los resultados lado a lado."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP11", "Descripcion CP11", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    _asegurar_columnas_y_lote(conn)
    cfg_id = NUC.configuracion_activa(conn, eid)[0]
    for i in (1, 2):
        run_id = SIM.registrar_run(
            conn, eid, i, status="completed", output_dir=tmp_replica_dir,
            configuracion_id=cfg_id,
        )
        _avanzar_run(conn, run_id, "completed")
    conn.close()

    datos = CMP.datos_comparacion(tmp_db_ready, eid)
    assert len(datos) == 2, "La comparacion debe contemplar ambas replicas"
    for fila in datos:
        assert fila["run"] in (1, 2)
        assert fila["status"] == "completed"

    out_png = os.path.join(tmp_exp_dir, "comparacion.png")
    grafica = CMP.generar_grafica_comparacion(tmp_db_ready, eid, out_png)
    assert grafica["ok"] is True
    assert os.path.isfile(out_png), "Debe generarse la grafica de comparacion"


# ======================================================================
# CP12 – RF12: Generar y exportar un reporte
# ======================================================================

def test_CP12_generar_y_exportar_reporte(tmp_db_ready, cfg_path, tmp_exp_dir):
    """CP12: generar y exportar un reporte debe producir un archivo con las
    configuraciones, ejecuciones y resultados."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP12", "Descripcion CP12", cfg_path)

    out_html = os.path.join(tmp_exp_dir, "reporte.html")
    reporte = REP.generar_reporte_html(eid, tmp_db_ready, out_html)
    assert reporte.get("ok") is True, f"generar_reporte_html fallo: {reporte.get('error')}"
    assert os.path.isfile(out_html), "Debe generarse el archivo del reporte"

    with open(out_html, "r", encoding="utf-8") as f:
        contenido = f.read()
    assert "Experimento CP12" in contenido, "El reporte debe incluir el experimento"

    out_csv = os.path.join(tmp_exp_dir, "runs.csv")
    csv_res = REP.exportar_runs_csv(eid, tmp_db_ready, out_csv)
    assert csv_res.get("ok") is True
    assert os.path.isfile(out_csv)

    out_json = os.path.join(tmp_exp_dir, "runs.json")
    json_res = REP.exportar_runs_json(eid, tmp_db_ready, out_json)
    assert json_res.get("ok") is True
    assert os.path.isfile(out_json)


# ======================================================================
# CP13 – RF13: Consultar la trazabilidad desde un resultado
# ======================================================================

def test_CP13_consultar_trazabilidad_desde_resultado(tmp_db_ready, cfg_path, tmp_replica_dir):
    """CP13: consultar la trazabilidad desde un resultado debe identificar la
    ejecucion, version de configuracion, replica, escenario y experimento."""
    eid = _crear_experimento(tmp_db_ready, "Experimento CP13", "Descripcion CP13", cfg_path)
    conn = sqlite3.connect(tmp_db_ready)
    _asegurar_columnas_y_lote(conn)
    cfg_id = NUC.configuracion_activa(conn, eid)[0]
    sid = SIM.crear_escenario(conn, eid, "escenario-1", cfg_path, "{}")
    run_id = SIM.registrar_run(
        conn, eid, 1, status="completed", output_dir=tmp_replica_dir,
        escenario_id=sid, configuracion_id=cfg_id,
    )
    _avanzar_run(conn, run_id, "completed")

    cur = conn.execute(
        "SELECT r.experiment_id, r.escenario_id, r.configuracion_id, c.version "
        "FROM runs r JOIN configuraciones c ON r.configuracion_id = c.id WHERE r.id=?",
        (run_id,),
    )
    trazabilidad = cur.fetchone()
    conn.close()

    assert trazabilidad is not None
    assert trazabilidad[0] == eid, "La ejecucion debe pertenecer al experimento"
    assert trazabilidad[1] == sid, "La ejecucion debe estar asociada al escenario"
    assert trazabilidad[2] is not None, "La ejecucion debe tener configuracion"
    assert trazabilidad[3] == 1, "La ejecucion debe referenciar la version 1 de configuracion"
