"""Pruebas no funcionales de PhysiCell Lab.

Categorías cubiertas (ISO/IEC 25010):
  RNF01 – Rendimiento / Eficiencia temporal
  RNF02 – Fiabilidad / Tolerancia a fallos
  RNF03 – Seguridad / Autenticación y contraseñas
  RNF04 – Portabilidad / Independencia de rutas absolutas
  RNF05 – Mantenibilidad / Consistencia de módulos
  RNF06 – Capacidad / Escalabilidad de la base de datos
  RNF07 – Usabilidad / Mensajes de error descriptivos
  RNF08 – Integridad de datos / Inmutabilidad de configuraciones
  RNF09 – Recuperabilidad / Manejo graceful de errores

Cada test_RNFnn implementa un criterio de calidad no funcional.
"""
import os
import re
import sys
import time
import sqlite3
import tempfile
import threading
import hashlib

import pytest

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

CFG = os.path.join(BASE, "config", "PhysiCell_settings.xml")

# Esquema mínimo compartido (mismo que conftest.py pero local para evitar
# dependencia de orden de fixtures en sub-módulos no estándar).
_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    config_xml_path TEXT,
    binary_path TEXT,
    custom_cpp_path TEXT,
    custom_h_path TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_modified DATETIME,
    tags TEXT DEFAULT '',
    usuario_id INTEGER
);
CREATE TABLE IF NOT EXISTS usuarios (
    id INTEGER PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol TEXT NOT NULL DEFAULT 'usuario',
    activo INTEGER NOT NULL DEFAULT 1,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    ultimo_acceso DATETIME
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER,
    run_number INTEGER,
    status TEXT DEFAULT 'pending',
    start_time DATETIME,
    end_time DATETIME,
    output_dir TEXT,
    escenario_id INTEGER,
    configuracion_id INTEGER,
    error_message TEXT,
    log_path TEXT,
    pid INTEGER,
    batch_id INTEGER,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
CREATE TABLE IF NOT EXISTS batches (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    n_replicas INTEGER,
    xml_path TEXT,
    xml_sha256 TEXT,
    exe_path TEXT,
    exe_sha256 TEXT,
    seed_base INTEGER DEFAULT 1000,
    timeout_min INTEGER DEFAULT 0,
    inactividad_min INTEGER DEFAULT 10,
    python_version TEXT,
    plataforma TEXT,
    notas TEXT,
    status TEXT DEFAULT 'running',
    error_message TEXT
);
CREATE TABLE IF NOT EXISTS escenarios (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER,
    nombre TEXT NOT NULL,
    config_xml_path TEXT,
    parametros_json TEXT DEFAULT '{}',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
CREATE TABLE IF NOT EXISTS configuraciones (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    nombre TEXT NOT NULL DEFAULT 'base',
    xml_path TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    es_activa INTEGER NOT NULL DEFAULT 0,
    creado_en DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);
"""


@pytest.fixture
def db_listo():
    """Base de datos temporal con todas las tablas creadas."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    conn.close()
    yield path
    try:
        os.remove(path)
    except OSError:
        pass


@pytest.fixture
def conn_listo(db_listo):
    """Conexión abierta a la DB temporal lista."""
    conn = sqlite3.connect(db_listo)
    conn.executescript(_SCHEMA_SQL)
    conn.commit()
    yield conn
    conn.close()


# ======================================================================
# RNF01 – Rendimiento: las operaciones principales deben completarse en
#          tiempo acotado (SLA interno de la capa de servicios).
# ======================================================================

class TestRendimiento:
    """RNF01 – Eficiencia temporal."""

    def test_RNF01_1_validar_xml_en_menos_de_1_segundo(self):
        """Validar un XML de PhysiCell debe completarse en < 1 s."""
        from app.xml_validator import validar_config
        inicio = time.monotonic()
        resultado = validar_config(CFG)
        duracion = time.monotonic() - inicio
        assert resultado["ok"] is True
        assert duracion < 1.0, (
            f"validar_config tardó {duracion:.3f} s (límite: 1 s)"
        )

    def test_RNF01_2_crear_experimento_en_menos_de_200ms(self, db_listo):
        """crear_experimento debe persistir en base de datos en < 200 ms."""
        from app import servicios as SERV
        inicio = time.monotonic()
        res = SERV.crear_experimento(db_listo, "Perf test", "desc", "", CFG)
        duracion = time.monotonic() - inicio
        assert res["ok"] is True
        assert duracion < 0.2, (
            f"crear_experimento tardó {duracion:.3f} s (límite: 0,2 s)"
        )

    def test_RNF01_3_insertar_100_runs_en_menos_de_2_segundos(self, conn_listo, db_listo):
        """Insertar 100 runs en la DB debe completarse en < 2 s."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "Bulk perf", "bulk", "", CFG)
        assert res["ok"] is True
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)
        cfg_id = NUC.configuracion_activa(conn, eid)[0]

        inicio = time.monotonic()
        for i in range(1, 101):
            SIM.registrar_run(
                conn, eid, i, status="pending",
                output_dir=tempfile.mkdtemp(),
                configuracion_id=cfg_id,
            )
        conn.commit()
        conn.close()
        duracion = time.monotonic() - inicio
        assert duracion < 2.0, (
            f"Inserción de 100 runs tardó {duracion:.3f} s (límite: 2 s)"
        )

    def test_RNF01_4_generar_replica_config_en_menos_de_500ms(self):
        """generar_replica_config debe producir el XML de réplica en < 500 ms."""
        from app.simulador import generar_replica_config
        tmpdir = tempfile.mkdtemp()
        out_xml = os.path.join(tmpdir, "replica_perf.xml")
        inicio = time.monotonic()
        generar_replica_config(CFG, out_xml, seed=9999,
                               output_folder=os.path.join(tmpdir, "output"))
        duracion = time.monotonic() - inicio
        assert os.path.isfile(out_xml)
        assert duracion < 0.5, (
            f"generar_replica_config tardó {duracion:.3f} s (límite: 0,5 s)"
        )

    def test_RNF01_5_listar_experimentos_con_100_registros_en_menos_de_500ms(self, db_listo):
        """listar_experimentos_con_estadisticas con 100 experimentos < 500 ms."""
        from app import simulador as SIM
        conn = sqlite3.connect(db_listo)
        for i in range(100):
            SIM.crear_experimento(conn, f"Exp {i}", "", "", CFG)
        conn.commit()
        conn.close()

        from app import servicios as SERV
        inicio = time.monotonic()
        lista = SERV.listar_experimentos_servicio(db_listo)
        duracion = time.monotonic() - inicio
        assert len(lista) >= 100
        assert duracion < 0.5, (
            f"listar_experimentos tardó {duracion:.3f} s (límite: 0,5 s)"
        )


# ======================================================================
# RNF02 – Fiabilidad: el sistema debe recuperarse correctamente ante
#          entradas inválidas y no propagar excepciones no controladas.
# ======================================================================

class TestFiabilidad:
    """RNF02 – Tolerancia a fallos y recuperación graceful."""

    def test_RNF02_1_validar_xml_inexistente_no_lanza_excepcion(self):
        """validar_config con ruta inexistente no debe lanzar excepción."""
        from app.xml_validator import validar_config
        resultado = validar_config("/ruta/absolutamente/inexistente.xml")
        assert resultado["ok"] is False
        assert len(resultado["errores"]) > 0

    def test_RNF02_2_validar_xml_vacio_no_lanza_excepcion(self):
        """validar_config con archivo vacío debe devolver error, no excepción."""
        from app.xml_validator import validar_config
        tmpfile = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tmpfile.write(b"")
        tmpfile.close()
        try:
            resultado = validar_config(tmpfile.name)
            assert resultado["ok"] is False
        finally:
            os.unlink(tmpfile.name)

    def test_RNF02_3_leer_bounds_carpeta_vacia_devuelve_none(self):
        """leer_bounds sobre carpeta sin initial.xml debe devolver None, no excepción."""
        from app.visor_widget import leer_bounds
        tmpdir = tempfile.mkdtemp()
        resultado = leer_bounds(tmpdir)
        assert resultado is None

    def test_RNF02_4_crear_experimento_title_vacio_manejado(self, db_listo):
        """crear_experimento con título vacío no debe romper la base de datos."""
        from app import servicios as SERV
        # El sistema puede aceptar o rechazar, pero no debe lanzar excepción sin control
        try:
            res = SERV.crear_experimento(db_listo, "", "", "", "")
            # Si acepta, debe retornar un dict con 'ok'
            assert "ok" in res
        except Exception as e:
            pytest.fail(f"crear_experimento lanzó excepción no controlada: {e}")

    def test_RNF02_5_listar_runs_experimento_inexistente_devuelve_lista(self, conn_listo):
        """listar_runs con un ID de experimento inexistente debe devolver lista vacía."""
        from app import simulador as SIM
        resultado = SIM.listar_runs(conn_listo, 999999)
        assert isinstance(resultado, list)
        assert len(resultado) == 0

    def test_RNF02_6_generar_replica_config_xml_invalido_manejado(self):
        """generar_replica_config con XML mal formado no debe dejar archivos corruptos sin excepción."""
        from app.simulador import generar_replica_config
        tmpdir = tempfile.mkdtemp()
        mal_xml = os.path.join(tmpdir, "mal.xml")
        with open(mal_xml, "w") as f:
            f.write("<incompleto>")
        out_xml = os.path.join(tmpdir, "replica_mal.xml")
        try:
            generar_replica_config(mal_xml, out_xml, seed=1)
            # Si no lanza excepción, el archivo destino puede existir pero
            # debería ser manejado de forma controlada (copia del original)
        except Exception:
            # Es aceptable que lance excepción, pero el archivo original
            # no debe ser modificado
            pass
        assert os.path.isfile(mal_xml), "El XML original no debe ser modificado"

    def test_RNF02_7_actualizar_run_inexistente_no_falla(self, conn_listo):
        """actualizar_run con un ID de run inexistente no debe lanzar excepción."""
        from app import simulador as SIM
        try:
            SIM.actualizar_run(conn_listo, 999999, "completed", end=True)
        except Exception as e:
            pytest.fail(f"actualizar_run lanzó excepción con ID inexistente: {e}")

    def test_RNF02_8_obtener_batch_inexistente_devuelve_none(self, conn_listo):
        """obtener_batch con ID inexistente debe devolver None, no excepción."""
        from app import simulador as SIM
        resultado = SIM.obtener_batch(conn_listo, 999999)
        assert resultado is None

    def test_RNF02_9_concurrencia_lecturas_simultaneas(self, db_listo):
        """Múltiples lecturas concurrentes a la DB no deben causar corrupción."""
        from app import servicios as SERV
        from app import simulador as SIM

        res = SERV.crear_experimento(db_listo, "Concurrencia", "", "", CFG)
        assert res["ok"] is True

        errores = []

        def leer():
            try:
                conn = sqlite3.connect(db_listo)
                SIM.listar_experimentos_con_estadisticas(conn)
                conn.close()
            except Exception as e:
                errores.append(str(e))

        hilos = [threading.Thread(target=leer) for _ in range(10)]
        for h in hilos:
            h.start()
        for h in hilos:
            h.join(timeout=5)

        assert len(errores) == 0, (
            f"Lecturas concurrentes produjeron errores: {errores}"
        )


# ======================================================================
# RNF03 – Seguridad: contraseñas hasheadas, sin texto plano en DB,
#          credenciales inválidas rechazadas.
# ======================================================================

class TestSeguridad:
    """RNF03 – Seguridad de autenticación."""

    def test_RNF03_1_contraseña_no_se_almacena_en_texto_plano(self, conn_listo):
        """La contraseña nunca debe almacenarse en texto plano en la base de datos."""
        from app import nucleo as NUC
        NUC.crear_usuario(conn_listo, "testuser", "test@example.com", "secreto123")
        cur = conn_listo.cursor()
        cur.execute("SELECT password_hash FROM usuarios WHERE username='testuser'")
        row = cur.fetchone()
        assert row is not None
        stored_hash = row[0]
        assert "secreto123" not in stored_hash, (
            "La contraseña NO debe aparecer en texto plano en la base de datos"
        )
        # El hash debe seguir el esquema PBKDF2
        assert stored_hash.startswith("pbkdf2_"), (
            "El hash debe usar PBKDF2 (esquema seguro)"
        )

    def test_RNF03_2_autenticacion_falla_con_contraseña_incorrecta(self, conn_listo):
        """autenticar_usuario debe retornar None con contraseña incorrecta."""
        from app import nucleo as NUC
        NUC.crear_usuario(conn_listo, "user2", "user2@example.com", "correcta")
        resultado = NUC.autenticar_usuario(conn_listo, "user2", "incorrecta")
        assert resultado is None, (
            "La autenticación debe fallar con contraseña incorrecta"
        )

    def test_RNF03_3_autenticacion_exitosa_con_credenciales_correctas(self, conn_listo):
        """autenticar_usuario debe retornar datos del usuario con credenciales correctas."""
        from app import nucleo as NUC
        NUC.crear_usuario(conn_listo, "user3", "user3@example.com", "mi_clave_segura")
        resultado = NUC.autenticar_usuario(conn_listo, "user3", "mi_clave_segura")
        assert resultado is not None
        assert resultado["username"] == "user3"
        assert "password_hash" not in resultado, (
            "El dict del usuario no debe exponer el hash de contraseña"
        )

    def test_RNF03_4_usuario_duplicado_rechazado(self, conn_listo):
        """crear_usuario con nombre/email duplicado debe retornar None, no excepción."""
        from app import nucleo as NUC
        uid1 = NUC.crear_usuario(conn_listo, "dup", "dup@example.com", "pass1")
        uid2 = NUC.crear_usuario(conn_listo, "dup", "dup@example.com", "pass2")
        assert uid1 is not None
        assert uid2 is None, (
            "Registrar usuario duplicado debe retornar None, no crear duplicado"
        )

    def test_RNF03_5_usuario_inactivo_no_puede_autenticarse(self, conn_listo):
        """Un usuario desactivado no debe poder autenticarse."""
        from app import nucleo as NUC
        uid = NUC.crear_usuario(conn_listo, "inactivo", "inact@example.com", "pass")
        assert uid is not None
        NUC.desactivar_usuario(conn_listo, uid)
        resultado = NUC.autenticar_usuario(conn_listo, "inactivo", "pass")
        assert resultado is None, (
            "Usuario desactivado no debe poder autenticarse"
        )

    def test_RNF03_6_hash_usa_iteraciones_suficientes(self, conn_listo):
        """El hash PBKDF2 debe usar al menos 100.000 iteraciones."""
        from app import nucleo as NUC
        NUC.crear_usuario(conn_listo, "itertest", "iter@test.com", "clave")
        cur = conn_listo.cursor()
        cur.execute("SELECT password_hash FROM usuarios WHERE username='itertest'")
        row = cur.fetchone()
        partes = row[0].split("$")
        # Formato: pbkdf2_sha256$iteraciones$salt$hash
        assert len(partes) == 4
        iteraciones = int(partes[1])
        assert iteraciones >= 100_000, (
            f"PBKDF2 debe usar >= 100.000 iteraciones, usa {iteraciones}"
        )

    def test_RNF03_7_autenticacion_usuario_inexistente_devuelve_none(self, conn_listo):
        """autenticar_usuario con username inexistente debe devolver None."""
        from app import nucleo as NUC
        resultado = NUC.autenticar_usuario(conn_listo, "noexiste", "clave")
        assert resultado is None

    def test_RNF03_8_authservice_login_logout(self, db_listo):
        """AuthService: login correcto, estado autenticado y logout funcionan."""
        from app import servicios as SERV
        from app import nucleo as NUC
        conn = sqlite3.connect(db_listo)
        NUC.crear_usuario(conn, "admin2", "admin2@ex.com", "admin_pass")
        conn.commit()
        conn.close()

        auth = SERV.AuthService(db_listo)
        assert not auth.esta_autenticado()

        res = auth.login("admin2", "admin_pass")
        assert res["ok"] is True
        assert auth.esta_autenticado()
        assert auth.usuario_actual["username"] == "admin2"

        auth.logout()
        assert not auth.esta_autenticado()
        assert auth.usuario_actual is None


# ======================================================================
# RNF04 – Portabilidad: el sistema no debe depender de rutas absolutas
#          propias del entorno de desarrollo.
# ======================================================================

class TestPortabilidad:
    """RNF04 – Independencia de rutas absolutas."""

    def test_RNF04_1_xml_ejemplo_en_carpeta_config(self):
        """El XML de ejemplo del repositorio debe existir en config/ relativo al proyecto."""
        assert os.path.isfile(CFG), (
            f"El XML de ejemplo debe existir en config/ del repositorio: {CFG}"
        )

    def test_RNF04_2_generar_replica_config_acepta_rutas_relativas(self):
        """generar_replica_config debe funcionar con rutas absolutas generadas en tiempo de ejecución."""
        from app.simulador import generar_replica_config
        tmpdir = tempfile.mkdtemp()
        out_xml = os.path.join(tmpdir, "replica_port.xml")
        generar_replica_config(CFG, out_xml, seed=42,
                               output_folder=os.path.join(tmpdir, "out"))
        assert os.path.isfile(out_xml), (
            "generar_replica_config debe producir el XML en la ruta indicada"
        )

    def test_RNF04_3_xml_replica_no_contiene_rutas_de_desarrollo(self):
        """El XML de réplica generado no debe contener rutas del entorno de desarrollo."""
        from app.simulador import generar_replica_config
        import xml.etree.ElementTree as ET
        tmpdir = tempfile.mkdtemp()
        out_xml = os.path.join(tmpdir, "replica_clean.xml")
        output_folder = os.path.join(tmpdir, "output")
        generar_replica_config(CFG, out_xml, seed=1234, output_folder=output_folder)
        tree = ET.parse(out_xml)
        contenido = ET.tostring(tree.getroot(), encoding="unicode")
        # La ruta de output debe apuntar al tmp del test, no a rutas hardcodeadas
        assert output_folder in contenido, (
            "La ruta de salida de la réplica debe reflejar la carpeta del test"
        )

    def test_RNF04_4_db_temporal_funciona_en_cualquier_carpeta(self):
        """La base de datos debe funcionar correctamente en cualquier directorio temporal."""
        tmpdir = tempfile.mkdtemp()
        db_path = os.path.join(tmpdir, "subdir", "experiments.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        conn = sqlite3.connect(db_path)
        conn.executescript(_SCHEMA_SQL)
        conn.commit()
        from app import simulador as SIM
        eid = SIM.crear_experimento(conn, "Port test", "", "", CFG)
        conn.commit()
        conn.close()
        assert eid > 0

    def test_RNF04_5_modulo_xml_validator_sin_dependencias_de_entorno(self):
        """xml_validator no debe importar módulos que requieran entorno gráfico."""
        import importlib
        import app.xml_validator as xv
        # Verificar que el módulo puede importarse sin QApplication activa
        assert hasattr(xv, "validar_config")
        assert callable(xv.validar_config)


# ======================================================================
# RNF05 – Mantenibilidad: los módulos principales deben exponer las
#          interfaces esperadas (contratos de API interna).
# ======================================================================

class TestMantenibilidad:
    """RNF05 – Consistencia de contratos de API interna."""

    def test_RNF05_1_servicios_expone_funciones_principales(self):
        """El módulo servicios debe exponer todas las funciones de alto nivel."""
        from app import servicios as SERV
        funciones_esperadas = [
            "crear_experimento",
            "actualizar_experimento",
            "eliminar_experimento",
            "obtener_experimento_completo",
            "registrar_nueva_configuracion",
            "activar_configuracion_servicio",
            "crear_escenario_servicio",
            "validar_para_ejecutar",
            "listar_experimentos_servicio",
        ]
        for f in funciones_esperadas:
            assert hasattr(SERV, f), (
                f"servicios debe exponer '{f}' (contrato de API interna)"
            )

    def test_RNF05_2_nucleo_expone_funciones_de_usuarios(self):
        """El módulo nucleo debe exponer las funciones de gestión de usuarios."""
        from app import nucleo as NUC
        funciones = [
            "crear_usuario", "autenticar_usuario", "desactivar_usuario",
            "listar_usuarios", "cambiar_rol_usuario",
            "crear_configuracion", "configuracion_activa", "activar_configuracion",
        ]
        for f in funciones:
            assert hasattr(NUC, f), (
                f"nucleo debe exponer '{f}' (contrato de API interna)"
            )

    def test_RNF05_3_simulador_expone_funciones_de_runs(self):
        """El módulo simulador debe exponer las funciones de gestión de runs."""
        from app import simulador as SIM
        funciones = [
            "registrar_run", "actualizar_run", "listar_runs",
            "crear_escenario", "listar_escenarios",
            "crear_batch", "obtener_batch", "actualizar_batch",
            "generar_replica_config", "fijar_output_folder",
        ]
        for f in funciones:
            assert hasattr(SIM, f), (
                f"simulador debe exponer '{f}' (contrato de API interna)"
            )

    def test_RNF05_4_xml_validator_devuelve_estructura_estandar(self):
        """validar_config debe siempre retornar dict con 'ok', 'errores' y 'warnings'."""
        from app.xml_validator import validar_config
        for path in [CFG, "/no/existe.xml", ""]:
            res = validar_config(path)
            assert isinstance(res, dict), f"Debe retornar dict para path={path!r}"
            assert "ok" in res, "Resultado debe tener clave 'ok'"
            assert "errores" in res, "Resultado debe tener clave 'errores'"
            assert "warnings" in res, "Resultado debe tener clave 'warnings'"

    def test_RNF05_5_servicios_crear_experimento_devuelve_estructura_estandar(self, db_listo):
        """crear_experimento siempre debe devolver dict con 'ok'."""
        from app import servicios as SERV
        for title, cfg in [("Válido", CFG), ("", ""), ("Test", "/no/existe.xml")]:
            try:
                res = SERV.crear_experimento(db_listo, title, "", "", cfg)
                assert "ok" in res, (
                    f"crear_experimento debe retornar dict con 'ok' para title={title!r}"
                )
            except Exception as e:
                pytest.fail(f"crear_experimento lanzó excepción no controlada: {e}")


# ======================================================================
# RNF06 – Capacidad: la DB debe manejar volúmenes moderados sin degradar.
# ======================================================================

class TestCapacidad:
    """RNF06 – Escalabilidad de la base de datos."""

    def test_RNF06_1_insertar_y_recuperar_1000_experimentos(self, db_listo):
        """La base de datos debe soportar 1.000 experimentos sin errores."""
        from app import simulador as SIM
        conn = sqlite3.connect(db_listo)
        for i in range(1000):
            SIM.crear_experimento(conn, f"Exp cap {i}", "", "", "")
        conn.commit()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM experiments")
        total = cur.fetchone()[0]
        conn.close()
        assert total >= 1000

    def test_RNF06_2_insertar_500_runs_en_un_experimento(self, db_listo):
        """Un experimento puede tener 500 réplicas registradas sin corrupción."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "Gran lote", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)
        cfg_id = NUC.configuracion_activa(conn, eid)[0]
        for i in range(1, 501):
            SIM.registrar_run(conn, eid, i, status="completed",
                              output_dir=tempfile.mkdtemp(),
                              configuracion_id=cfg_id)
        conn.commit()

        runs = SIM.listar_runs(conn, eid)
        conn.close()
        assert len(runs) == 500

    def test_RNF06_3_xml_grande_no_degrada_validacion(self):
        """Un XML válido pero de mayor tamaño debe validarse sin timeout."""
        import xml.etree.ElementTree as ET
        from app.xml_validator import validar_config

        # Construir un XML más grande a partir del original
        tree = ET.parse(CFG)
        root = tree.getroot()
        # Duplicar nodos de usuario (simular config extensa)
        up = root.find(".//user_parameters")
        if up is not None:
            for i in range(50):
                el = ET.SubElement(up, f"param_extra_{i}")
                el.set("type", "double")
                el.text = str(i * 0.1)

        tmpfile = tempfile.NamedTemporaryFile(suffix=".xml", delete=False)
        tree.write(tmpfile.name, encoding="unicode", xml_declaration=True)
        tmpfile.close()
        try:
            inicio = time.monotonic()
            res = validar_config(tmpfile.name)
            duracion = time.monotonic() - inicio
            assert duracion < 2.0, (
                f"Validación de XML grande tardó {duracion:.3f} s (límite: 2 s)"
            )
        finally:
            os.unlink(tmpfile.name)


# ======================================================================
# RNF07 – Usabilidad: los mensajes de error deben ser descriptivos y
#          en español, orientados al usuario final.
# ======================================================================

class TestUsabilidad:
    """RNF07 – Mensajes de error descriptivos."""

    def test_RNF07_1_xml_mal_formado_mensaje_descriptivo(self):
        """El error de XML mal formado debe mencionar 'mal formado' o 'parse'."""
        from app.xml_validator import validar_config
        tmpfile = tempfile.NamedTemporaryFile(suffix=".xml", delete=False,
                                             mode="w", encoding="utf-8")
        tmpfile.write("<incompleto><sin>cerrar")
        tmpfile.close()
        try:
            res = validar_config(tmpfile.name)
            assert res["ok"] is False
            msg_completo = " ".join(res["errores"]).lower()
            assert any(kw in msg_completo for kw in ["mal formado", "parse", "error"]), (
                f"El error debe ser descriptivo, obtenido: {res['errores']}"
            )
        finally:
            os.unlink(tmpfile.name)

    def test_RNF07_2_xml_sin_cell_definitions_mensaje_descriptivo(self):
        """El error de XML sin cell_definitions debe indicar la sección faltante."""
        from app.xml_validator import validar_config
        xml_sin_celulas = """<?xml version="1.0"?>
<PhysiCell_settings>
  <domain><x_min>-500</x_min><x_max>500</x_max>
           <y_min>-500</y_min><y_max>500</y_max></domain>
  <overall><max_time>1000</max_time></overall>
  <microenvironment_setup></microenvironment_setup>
</PhysiCell_settings>"""
        tmpfile = tempfile.NamedTemporaryFile(suffix=".xml", delete=False,
                                             mode="w", encoding="utf-8")
        tmpfile.write(xml_sin_celulas)
        tmpfile.close()
        try:
            res = validar_config(tmpfile.name)
            assert res["ok"] is False
            msgs = " ".join(res["errores"]).lower()
            assert "cell_definition" in msgs or "celula" in msgs or "cell" in msgs, (
                f"El mensaje debe mencionar cell_definitions: {res['errores']}"
            )
        finally:
            os.unlink(tmpfile.name)

    def test_RNF07_3_validar_para_ejecutar_sin_xml_mensaje_descriptivo(self, db_listo):
        """validar_para_ejecutar sin XML debe producir error descriptivo con 'xml'."""
        from app import servicios as SERV
        from app import simulador as SIM
        conn = sqlite3.connect(db_listo)
        eid = SIM.crear_experimento(conn, "Sin xml", "", "", "")
        conn.commit()
        conn.close()
        res = SERV.validar_para_ejecutar(db_listo, eid, "", "/exe/project.exe")
        assert res["ok"] is False
        msgs = " ".join(res["errores"]).lower()
        assert "xml" in msgs, (
            f"El error debe mencionar 'xml': {res['errores']}"
        )

    def test_RNF07_4_validar_para_ejecutar_sin_exe_mensaje_descriptivo(self, db_listo):
        """validar_para_ejecutar sin ejecutable debe producir error que mencione 'exe' o 'ejecutable'."""
        from app import servicios as SERV
        res = SERV.validar_para_ejecutar(db_listo, 1, CFG, "")
        assert res["ok"] is False
        msgs = " ".join(res["errores"]).lower()
        assert any(kw in msgs for kw in ["exe", "ejecutable", "binario", "physi"]), (
            f"El error debe describir la falta de ejecutable: {res['errores']}"
        )


# ======================================================================
# RNF08 – Integridad de datos: las configuraciones versionadas deben
#          ser inmutables; las ejecuciones conservan su config_id.
# ======================================================================

class TestIntegridadDatos:
    """RNF08 – Inmutabilidad de configuraciones y trazabilidad."""

    def test_RNF08_1_copia_xml_es_independiente_del_original(self, conn_listo, db_listo):
        """La copia del XML de resguardo debe ser independiente del archivo original."""
        from app import nucleo as NUC
        import shutil

        tmpdir = tempfile.mkdtemp()
        copia_original = os.path.join(tmpdir, "original.xml")
        shutil.copy2(CFG, copia_original)

        conn = sqlite3.connect(db_listo)
        conn.executescript(_SCHEMA_SQL)
        conn.execute("INSERT INTO experiments (id, title, config_xml_path, usuario_id) VALUES (1, 'Exp', ?, 1)", (copia_original,))
        conn.commit()

        cid = NUC.crear_configuracion(
            conn, 1, "base", copia_original, version=1,
            activar=True, db_path=db_listo, copiar_xml=True,
        )
        row = NUC.configuracion_activa(conn, 1)
        ruta_copia = row[2]
        conn.close()

        # Modificar el original
        with open(copia_original, "w", encoding="utf-8") as f:
            f.write("<modificado/>")

        # La copia de resguardo debe seguir siendo el XML válido
        from app.xml_validator import validar_config
        res = validar_config(ruta_copia)
        assert res["ok"] is True, (
            "La copia inmutable debe seguir siendo válida tras modificar el original"
        )

    def test_RNF08_2_runs_conservan_configuracion_id_tras_cambio_de_activa(self, db_listo):
        """Cambiar la configuración activa no debe alterar el configuracion_id de runs previos."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "Traza", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)
        cfg_v1 = NUC.configuracion_activa(conn, eid)
        cid_v1 = cfg_v1[0]

        run_id = SIM.registrar_run(conn, eid, 1, status="completed",
                                   output_dir=tempfile.mkdtemp(),
                                   configuracion_id=cid_v1)
        conn.commit()

        cid_v2 = NUC.crear_configuracion(
            conn, eid, "v2", CFG, version=2, activar=True,
            db_path=db_listo, copiar_xml=True,
        )

        cur = conn.cursor()
        cur.execute("SELECT configuracion_id FROM runs WHERE id=?", (run_id,))
        cfg_en_run = cur.fetchone()[0]
        conn.close()

        assert cfg_en_run == cid_v1, (
            "El run debe conservar su configuracion_id original tras activar v2"
        )

    def test_RNF08_3_sha256_del_xml_en_batch_es_correcto(self, db_listo):
        """El campo xml_sha256 del batch debe corresponder al hash real del XML."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "SHA batch", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)
        NUC.configuracion_activa(conn, eid)

        tmpdir = tempfile.mkdtemp()
        fake_exe = os.path.join(tmpdir, "project.exe")
        with open(fake_exe, "w") as f:
            f.write("fake")

        bid = SIM.crear_batch(conn, eid, CFG, fake_exe,
                              n_replicas=1, seed_base=1000)
        conn.commit()
        batch = SIM.obtener_batch(conn, bid)
        conn.close()

        with open(CFG, "rb") as f:
            sha_real = hashlib.sha256(f.read()).hexdigest()

        assert batch is not None
        assert batch["xml_sha256"] == sha_real, (
            "El xml_sha256 del batch debe coincidir con el hash real del XML"
        )

    def test_RNF08_4_solo_una_configuracion_activa_por_experimento(self, db_listo):
        """Solo debe haber una configuración activa (es_activa=1) por experimento."""
        from app import servicios as SERV
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "Solo una activa", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)

        NUC.crear_configuracion(conn, eid, "v2", CFG, version=2,
                                activar=True, db_path=db_listo, copiar_xml=True)
        NUC.crear_configuracion(conn, eid, "v3", CFG, version=3,
                                activar=True, db_path=db_listo, copiar_xml=True)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM configuraciones WHERE experiment_id=? AND es_activa=1", (eid,))
        activas = cur.fetchone()[0]
        conn.close()

        assert activas == 1, (
            f"Solo debe haber 1 configuración activa por experimento, hay {activas}"
        )


# ======================================================================
# RNF09 – Recuperabilidad: el sistema debe registrar errores y seguir
#          operando; los errores de réplica no deben bloquear el sistema.
# ======================================================================

class TestRecuperabilidad:
    """RNF09 – Manejo de errores sin bloqueo del sistema."""

    def test_RNF09_1_run_fallido_queda_registrado_en_db(self, db_listo):
        """Una réplica que falla debe quedar registrada como 'failed' con mensaje."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC
        from datetime import datetime

        res = SERV.crear_experimento(db_listo, "Fallo test", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)
        cfg_id = NUC.configuracion_activa(conn, eid)[0]

        run_id = SIM.registrar_run(conn, eid, 1, status="running",
                                   output_dir=tempfile.mkdtemp(),
                                   configuracion_id=cfg_id)
        SIM.actualizar_run(conn, run_id, "failed", end=True,
                           error_message="Simulación interrumpida por señal 11")
        conn.commit()

        runs = SIM.listar_runs(conn, eid)
        conn.close()

        assert len(runs) == 1
        run = runs[0]
        assert run[2] == "failed"
        assert run[6] is not None and "señal" in run[6].lower()

    def test_RNF09_2_experimento_sin_runs_no_afecta_otros(self, db_listo):
        """Experimentos sin runs no deben afectar la lista de otros experimentos."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res1 = SERV.crear_experimento(db_listo, "Con runs", "", "", CFG)
        res2 = SERV.crear_experimento(db_listo, "Sin runs", "", "", CFG)
        eid1, eid2 = res1["experiment_id"], res2["experiment_id"]

        conn = sqlite3.connect(db_listo)
        cfg_id = NUC.configuracion_activa(conn, eid1)[0]
        SIM.registrar_run(conn, eid1, 1, status="completed",
                          output_dir=tempfile.mkdtemp(), configuracion_id=cfg_id)
        conn.commit()

        lista = SERV.listar_experimentos_servicio(db_listo)
        conn.close()

        ids = [row[0] for row in lista]
        assert eid1 in ids and eid2 in ids, (
            "Ambos experimentos deben aparecer en la lista"
        )

    def test_RNF09_3_eliminar_experimento_limpia_runs_asociados(self, db_listo):
        """eliminar_experimento debe eliminar también los runs y escenarios asociados."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "Para eliminar", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)
        cfg_id = NUC.configuracion_activa(conn, eid)[0]
        SIM.registrar_run(conn, eid, 1, status="completed",
                          output_dir=tempfile.mkdtemp(), configuracion_id=cfg_id)
        SIM.crear_escenario(conn, eid, "esc1", CFG, "{}")
        conn.commit()
        conn.close()

        SERV.eliminar_experimento(db_listo, eid)

        conn = sqlite3.connect(db_listo)
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM runs WHERE experiment_id=?", (eid,))
        n_runs = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM escenarios WHERE experiment_id=?", (eid,))
        n_esc = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM experiments WHERE id=?", (eid,))
        n_exp = cur.fetchone()[0]
        conn.close()

        assert n_runs == 0, "Los runs del experimento eliminado deben borrarse"
        assert n_esc == 0, "Los escenarios del experimento eliminado deben borrarse"
        assert n_exp == 0, "El experimento eliminado debe borrarse"

    def test_RNF09_4_batch_en_estado_fallido_no_impide_nuevos_batches(self, db_listo):
        """Un batch en estado 'failed' no debe impedir crear nuevos batches."""
        from app import servicios as SERV
        from app import simulador as SIM
        from app import nucleo as NUC

        res = SERV.crear_experimento(db_listo, "Batch rec", "", "", CFG)
        eid = res["experiment_id"]
        conn = sqlite3.connect(db_listo)

        tmpdir = tempfile.mkdtemp()
        fake_exe = os.path.join(tmpdir, "project.exe")
        with open(fake_exe, "w") as f:
            f.write("fake")

        bid1 = SIM.crear_batch(conn, eid, CFG, fake_exe, n_replicas=1)
        SIM.actualizar_batch(conn, bid1, "failed", "Error simulado")
        conn.commit()

        bid2 = SIM.crear_batch(conn, eid, CFG, fake_exe, n_replicas=2)
        conn.commit()

        b2 = SIM.obtener_batch(conn, bid2)
        conn.close()

        assert b2 is not None
        assert b2["status"] == "running"
        assert b2["n_replicas"] == 2
