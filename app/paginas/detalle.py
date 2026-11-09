"""Página de Detalle de experimento: pestañas Resumen, Configuración, Ejecuciones,
Visualización 2D/3D, Resultados, Comparación y Reportes."""
import os
import sqlite3
from datetime import datetime
from html import escape as _escape

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QSpinBox, QTextEdit, QProgressBar, QStackedWidget, QButtonGroup,
    QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QGridLayout, QDialog, QFormLayout, QDialogButtonBox, QSizePolicy, QFrame, QWidget,
    QApplication, QInputDialog
)
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal

from .base import (
    PaginaBase, Seccion, Tarjeta, BadgeEstado, xml_estado, exe_estado,
    exp_estado, ESTILO_ESTADO, ESTADO_BOTON, CampoFormulario, DialogoBase,
    TablaBase, ESPACIO_M, ESPACIO_L, TAM_H2, resumen_texto,
)
from .. import simulador as SIM
from ..xml_validator import validar_config, validar_texto
from ..motor_physicell import MotorPhysiCell
from ..visor_widget import VisorPhysiCell
from ..visor3d_vtk import abrir_vtk
from ..exportacion import generar_video_2d, generar_video_3d_vtk
from .dialogo_run import DialogoDetalleRun


# Estado de una réplica -> color del texto en las tablas
_COLOR_ESTADO_RUN = {
    "completed": "#3DDC84",
    "failed": "#FF6B6B",
    "cancelled": "#FFB020",
    "running": "#4DA3FF",
    "registered": "#A6A6A6",
    "pending": "#A6A6A6",
}


class _DiagWorker(QThread):
    """Ejecuta el autodiagnóstico del motor sin congelar la interfaz."""

    done = pyqtSignal(dict)

    def __init__(self, exe, xml, log_path, padre=None):
        super().__init__(padre)
        self.exe = exe
        self.xml = xml
        self.log_path = log_path

    def run(self):
        try:
            from ..motor_physicell import MotorPhysiCell
            r = MotorPhysiCell().autodiagnostico(
                self.exe, self.xml, log_path=self.log_path
            )
        except Exception as e:
            r = {
                "ok": False,
                "problemas": [f"Error inesperado del diagnóstico: {e}"],
                "avisos": [],
                "log_path": self.log_path,
                "duracion": 0.0,
            }
        self.done.emit(r)


class PaginaDetalle(PaginaBase):
    def __init__(self, lab_window):
        super().__init__(lab_window)
        self.current_experiment_id = None
        self.worker = None
        self.tabs_widget = None

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())

    def build(self, eid):
        self.current_experiment_id = eid

        # Si ya tiene layout (build llamado más de una vez), limpiarlo antes de reconstruir
        layout = self.layout()
        if layout is None:
            layout = QVBoxLayout(self)
            layout.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
            layout.setSpacing(ESPACIO_M)
        else:
            while layout.count():
                item = layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
                elif item.layout():
                    self._clear_layout(item.layout())

        lay = layout

        # ---------- Encabezado del experimento ----------
        from .. import servicios as SERV
        info = SERV.obtener_experimento_completo(self.db_path(), eid)
        if not info.get("ok"):
            title, desc, tags, cfg, binp, cpp, h, creado, modif = ("",) * 8
            runs = []
            n_esc = 0
        else:
            exp = info["experimento"]
            title = exp["title"] or ""
            desc = exp["description"] or ""
            tags = exp["tags"] or ""
            cfg = exp["config_xml_path"] or ""
            binp = exp["binary_path"] or ""
            cpp = exp["custom_cpp_path"] or ""
            h = exp["custom_h_path"] or ""
            creado = exp["created_at"]
            modif = exp["last_modified"]
            runs = self._runs_exp(eid)
            n_esc = len(info["escenarios"])
        n_run = sum(1 for x in runs if x[2] == "running")
        n_fail = sum(1 for x in runs if x[2] in ("failed", "cancelled"))
        n_ok = sum(1 for x in runs if x[2] == "completed")
        tanda = SIM.tanda_de_estados([(x[0], x[1], x[2]) for x in runs])
        xe, _ = xml_estado(cfg)
        estado = exp_estado(len(runs), n_run, n_fail, n_ok, xe == "Válido", tanda)
        col = ESTILO_ESTADO.get(estado, "#A6A6A6")

        # Si la última tanda falló, mostrar el motivo junto al estado
        detalle_error = ""
        if estado == "Con errores" and runs:
            ultima = max(runs, key=lambda x: x[0] or 0)
            motivo = (ultima[6] or "").strip() if len(ultima) > 6 else ""
            if motivo:
                detalle_error = " · " + _escape(" ".join(motivo.split())[:120])

        head = QHBoxLayout()
        left = QVBoxLayout()
        h = QLabel(title or f"Experimento {eid}")
        h.setObjectName("H1")
        left.addWidget(h)
        st = QLabel(
            f"<b style='color:{col}'>● {estado}</b> &nbsp; "
            f"<span style='color:#A6A6A6'>{tags or 'sin etiquetas'} • {n_esc} escenarios • {len(runs)} runs{detalle_error}</span>"
        )
        st.setTextFormat(Qt.TextFormat.RichText)
        left.addWidget(st)
        head.addLayout(left, 1)
        bback = QPushButton("← Volver")
        bback.setObjectName("Secondary")
        bback.clicked.connect(lambda: self.lw.ir("Experimentos"))
        head.addWidget(bback)
        lay.addLayout(head)

        # ---------- Pestañas ----------
        tabs = QTabWidget()
        self.tabs_widget = tabs
        lay.addWidget(tabs, 1)
        tabs.addTab(self._tab_resumen(eid, title, desc, tags, cfg, creado, modif, runs, n_esc, estado, col), "Resumen")
        tabs.addTab(self._tab_config(eid, cfg, binp, cpp, h), "Configuración")
        tabs.addTab(self._tab_ejecucion(eid, cfg), "Ejecuciones")
        tabs.addTab(self._tab_vis(eid), "Visualización 2D/3D")
        tabs.addTab(self._tab_resultados(eid), "Resultados")
        tabs.addTab(self._tab_comparacion(eid), "Comparación")
        tabs.addTab(self._tab_reportes(eid), "Reportes")
        self._res_cargar_reps()
        return self

    # ---------- Utilidades ----------
    def _file_row(self, label, edit, browse_fn):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        l = QLabel(label)
        l.setFixedWidth(150)
        h.addWidget(l)
        h.addWidget(edit, 1)
        b = QPushButton("…")
        b.setObjectName("Secondary")
        b.setFixedWidth(40)
        b.clicked.connect(browse_fn)
        h.addWidget(b)
        return w

    def _runs_exp(self, eid):
        conn = self.conn()
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        return rows

    def _exp_dir(self):
        return os.path.join(os.path.dirname(self.db_path()), f"exp_{self.current_experiment_id}")

    # =====================================================================
    # Pestaña: Resumen
    # =====================================================================
    def _tab_resumen(self, eid, title, desc, tags, cfg, creado, modif, runs, n_esc, estado, col):
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        v.setSpacing(ESPACIO_M)

        tanda = SIM.tanda_de_estados([(x[0], x[1], x[2]) for x in runs])
        linea_tanda = ""
        if tanda:
            ok = sum(1 for e in tanda if e == "completed")
            linea_tanda = (
                f"Última ejecución: <b>{ok}/{len(tanda)}</b> completadas · {estado}<br>"
            )

        info = QLabel(
            f"<h2>{title or f'Experimento {eid}'}</h2>"
            f"<p>{desc or 'Sin descripción'}</p>"
            f"<p>Estado: <b style='color:{col}'>{estado}</b><br>"
            f"Creado: {creado or '—'} &nbsp; Modificado: {modif or '—'}<br>"
            f"Etiquetas: {tags or '—'}</p>"
            f"<p>Escenarios: <b>{n_esc}</b> &nbsp; Ejecuciones: <b>{len(runs)}</b><br>"
            f"{linea_tanda}XML: {cfg or 'no asignado'}</p>"
        )
        info.setWordWrap(True)
        v.addWidget(info)

        grid = QGridLayout()
        accesos = [("Configuración", 0), ("Ejecuciones", 2), ("Visualización 2D/3D", 3), ("Resultados", 4)]
        for i, (lbl, idx) in enumerate(accesos):
            b = QPushButton(lbl)
            b.setObjectName("Secondary")
            b.clicked.connect(lambda _=False, i=idx: self.tabs_widget.setCurrentIndex(i))
            grid.addWidget(b, 0, i)
        cw = QFrame()
        cw.setLayout(grid)
        v.addWidget(cw)
        v.addStretch()
        return w

    # =====================================================================
    # Pestaña: Configuración
    # =====================================================================
    def _tab_config(self, eid, cfg, binp="", cpp="", h=""):
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        v.setSpacing(ESPACIO_M)

        self.cfg_xml = QLineEdit(cfg or "")
        self.cfg_xml.setPlaceholderText(".../PhysiCell_settings.xml — plantilla de réplicas")
        v.addWidget(self._file_row("XML del experimento:", self.cfg_xml, self._browse_cfg_detalle))

        self.cfg_exe = QLineEdit(binp or getattr(self.lw, "_last_exe", ""))
        self.cfg_exe.setPlaceholderText(".../project.exe — motor PhysiCell compilado")
        v.addWidget(self._file_row("Motor PhysiCell:", self.cfg_exe, self._browse_exe_detalle))

        self.cfg_cpp = QLineEdit(cpp or "")
        self.cfg_cpp.setPlaceholderText(".../custom.cpp — reglas propias del motor (opcional)")
        v.addWidget(self._file_row("custom.cpp del motor:", self.cfg_cpp, self._browse_cpp_detalle))

        self.cfg_h = QLineEdit(h or "")
        self.cfg_h.setPlaceholderText(".../custom.h — encabezado del motor (opcional)")
        v.addWidget(self._file_row("custom.h del motor:", self.cfg_h, self._browse_h_detalle))

        row = QHBoxLayout()
        row.addWidget(QLabel("Réplicas por ejecución:"))
        self.cfg_reps = QSpinBox()
        self.cfg_reps.setRange(1, 50)
        self.cfg_reps.setValue(3)
        row.addWidget(self.cfg_reps)
        row.addStretch()
        c = QFrame()
        c.setLayout(row)
        v.addWidget(c)

        self.cfg_out = QLabel(f"Salida: {os.path.join(os.path.dirname(self.db_path()), f'exp_{eid}')}")
        self.cfg_out.setObjectName("Muted")
        self.cfg_out.setWordWrap(True)
        v.addWidget(self.cfg_out)

        self.cfg_salidas = QLabel("")
        self.cfg_salidas.setObjectName("Muted")
        self.cfg_salidas.setWordWrap(True)
        v.addWidget(self.cfg_salidas)

        self.cfg_estado = QLabel("")
        self.cfg_estado.setWordWrap(True)
        v.addWidget(self.cfg_estado)

        btns = QHBoxLayout()
        b1 = QPushButton("Validar archivos")
        b1.setObjectName("Secondary")
        b1.clicked.connect(self._validar_detalle)
        self.btn_probar = QPushButton("Probar motor")
        self.btn_probar.setObjectName("Secondary")
        self.btn_probar.setToolTip(
            "Ejecuta PhysiCell con un XML reducido para comprobar que arranca, "
            "termina y guarda resultados. Detecta DLLs incompatibles en segundos."
        )
        self.btn_probar.clicked.connect(self._probar_motor)
        b2 = QPushButton("Guardar configuración")
        b2.setObjectName("Primary")
        b2.clicked.connect(self._guardar_cfg_detalle)
        b3 = QPushButton("Editar XML…")
        b3.setObjectName("Secondary")
        b3.clicked.connect(self._editar_xml_detalle)
        btns.addWidget(b1)
        btns.addWidget(self.btn_probar)
        btns.addWidget(b3)
        btns.addStretch()
        btns.addWidget(b2)
        c2 = QFrame()
        c2.setLayout(btns)
        v.addWidget(c2)

        v.addWidget(QLabel("<b>Variantes (escenarios)</b>: crea una variante del XML actual sin tocar el original."))
        vrow = QHBoxLayout()
        self.var_nombre = QLineEdit()
        self.var_nombre.setPlaceholderText("Nombre de la variante, ej: o2-bajo")
        bvar = QPushButton("Crear variante")
        bvar.setObjectName("Secondary")
        bvar.clicked.connect(lambda: self._crear_variante(eid))
        vrow.addWidget(self.var_nombre, 1)
        vrow.addWidget(bvar)
        cv = QFrame()
        cv.setLayout(vrow)
        v.addWidget(cv)

        # ---------- Versiones de configuración ----------
        v.addWidget(QLabel("<b>Versiones de configuración</b>: historial de versiones del XML del experimento."))
        vrow2 = QHBoxLayout()
        b_nueva_ver = QPushButton("Registrar nueva versión…")
        b_nueva_ver.setObjectName("Secondary")
        b_nueva_ver.clicked.connect(self._registrar_version)
        b_activar = QPushButton("Activar versión seleccionada")
        b_activar.setObjectName("Secondary")
        b_activar.clicked.connect(self._activar_version)
        b_ref = QPushButton("Actualizar")
        b_ref.setObjectName("Secondary")
        b_ref.clicked.connect(self._cargar_versiones)
        vrow2.addWidget(b_nueva_ver)
        vrow2.addWidget(b_activar)
        vrow2.addWidget(b_ref)
        vrow2.addStretch()
        c2v = QFrame()
        c2v.setLayout(vrow2)
        v.addWidget(c2v)

        self.tab_versiones = QTableWidget()
        self.tab_versiones.setColumnCount(5)
        self.tab_versiones.setHorizontalHeaderLabels(["Versión", "Nombre", "Archivo XML", "Estado", "Creado"])
        cab = self.tab_versiones.horizontalHeader()
        cab.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        cab.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        cab.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tab_versiones.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        v.addWidget(self.tab_versiones, 1)
        v.addStretch()
        self._cargar_versiones()
        self._validar_detalle(silencioso=True)
        return w

    def _crear_variante(self, eid):
        cfg = self.cfg_xml.text().strip() if hasattr(self, "cfg_xml") else ""
        if not validar_config(cfg).get("ok"):
            QMessageBox.warning(self.lw, "Variante", "El XML del experimento no es válido.")
            return
        nom = self.var_nombre.text().strip() or "variante-1"
        conn = self.conn()
        SIM.crear_escenario(conn, eid, nom, cfg, "{}")
        conn.close()
        QMessageBox.information(self.lw, "Variante", f"Escenario '{nom}' creado. Adminístralo en la pestaña Ejecuciones.")

    # ---------- Versiones de configuración (historial) ----------

    def _cargar_versiones(self):
        """Pinta el historial de versiones de configuración del experimento."""
        from .. import servicios as SERV
        from PyQt6.QtWidgets import QTableWidgetItem
        self.tab_versiones.setRowCount(0)
        info = None
        try:
            info = SERV.obtener_experimento_completo(self.db_path(), self.current_experiment_id)
        except Exception:
            info = None
        cfgs = []
        if isinstance(info, dict):
            cfgs = info.get("configuraciones") or []
        filas = sorted(cfgs, key=lambda c: int(c.get("version") or 0)) if cfgs else []
        self._versiones_cache = filas
        for c in filas:
            r = self.tab_versiones.rowCount()
            self.tab_versiones.insertRow(r)
            self.tab_versiones.setItem(r, 0, QTableWidgetItem(str(c.get("version") or "")))
            self.tab_versiones.setItem(r, 1, QTableWidgetItem(str(c.get("nombre") or "")))
            xmlp = c.get("xml_path") or ""
            self.tab_versiones.setItem(r, 2, QTableWidgetItem(os.path.basename(xmlp) if xmlp else "—"))
            self.tab_versiones.setItem(r, 3, QTableWidgetItem("Activa" if c.get("es_activa") else "Inactiva"))
            self.tab_versiones.setItem(r, 4, QTableWidgetItem(str(c.get("creado_en") or "")))
        if not filas:
            r = self.tab_versiones.rowCount()
            self.tab_versiones.insertRow(r)
            for j, txt in enumerate(["Sin versiones registradas", "", "", "", ""]):
                self.tab_versiones.setItem(r, j, QTableWidgetItem(txt))

    def _registrar_version(self):
        """Registra una nueva versión de configuración (con copia resguardo) para el experimento."""
        from PyQt6.QtWidgets import QFileDialog, QInputDialog, QMessageBox
        from .. import servicios as SERV
        xml_path, _filtro = QFileDialog.getOpenFileName(
            self.lw, "Registrar versión — XML de PhysiCell", "",
            "XML (*.xml)")
        if not xml_path:
            return
        nombre, ok = QInputDialog.getText(self.lw, "Registrar versión", "Nombre de la versión:", text="v")
        if not ok or not (nombre or "").strip():
            return
        r = SERV.registrar_nueva_configuracion(
            self.db_path(), self.current_experiment_id, nombre.strip(), xml_path, activar=True)
        if r.get("ok"):
            QMessageBox.information(self.lw, "Versiones", f"Versión registrada correctamente.")
            if hasattr(self, "cfg_xml"):
                self.cfg_xml.setText(xml_path)
            self._cargar_versiones()
            self.lw.refrescar_detalle()
        else:
            QMessageBox.warning(self.lw, "Versiones", r.get("error", "Error al registrar la versión."))

    def _activar_version(self):
        """Activa (restaura) una versión del historial para el experimento."""
        from PyQt6.QtWidgets import QMessageBox
        from .. import servicios as SERV
        fila = self.tab_versiones.currentRow()
        if fila < 0:
            QMessageBox.warning(self.lw, "Versiones", "Selecciona una versión del historial.")
            return
        cache = getattr(self, "_versiones_cache", None) or []
        if fila >= len(cache):
            return
        c = cache[fila]
        if c.get("es_activa"):
            return
        ok = SERV.activar_configuracion_servicio(self.db_path(), c.get("id"))
        if ok.get("ok"):
            QMessageBox.information(self.lw, "Versiones", f"Versión {c.get('version')} ({c.get('nombre')}) activada.")
            if c.get("xml_path"):
                self.cfg_xml.setText(c.get("xml_path") or "")
                self._validar_detalle(silencioso=True)
            self._cargar_versiones()
            self.lw.refrescar_detalle()
        else:
            QMessageBox.warning(self.lw, "Versiones", ok.get("error", "No se pudo activar la versión."))

    def _browse_cfg_detalle(self):
        f, _ = QFileDialog.getOpenFileName(self.lw, "XML del experimento", "", "XML (*.xml)")
        if f:
            self.cfg_xml.setText(f)
            self._validar_detalle(silencioso=True)

    def _browse_exe_detalle(self):
        f, _ = QFileDialog.getOpenFileName(self.lw, "Motor PhysiCell", "", "Ejecutable (*.exe);;Todos (*)")
        if f:
            self.cfg_exe.setText(f)
            self.lw._last_exe = f
            self._validar_detalle(silencioso=True)

    def _browse_cpp_detalle(self):
        f, _ = QFileDialog.getOpenFileName(self.lw, "custom.cpp del motor", "", "C++ (*.cpp *.h);;Todos (*)")
        if f:
            self.cfg_cpp.setText(f)
            self._validar_detalle(silencioso=True)

    def _browse_h_detalle(self):
        f, _ = QFileDialog.getOpenFileName(self.lw, "custom.h del motor", "", "C/C++ (*.h *.hpp);;Todos (*)")
        if f:
            self.cfg_h.setText(f)
            self._validar_detalle(silencioso=True)

    def _validar_detalle(self, silencioso=False):
        xe, _ = xml_estado(self.cfg_xml.text().strip())
        exe = self.cfg_exe.text().strip()
        ee, _ = exe_estado(exe)
        from ..motor_physicell import verificar_binario, intervalos_guardado
        problemas = verificar_binario(exe) if exe else []

        iv = intervalos_guardado(self.cfg_xml.text().strip())
        salidas = []
        if iv["svg"] > 0:
            salidas.append(f"SVG cada {iv['svg']:g} min")
        if iv["full_data"] > 0:
            salidas.append(f"datos completos cada {iv['full_data']:g} min")
        texto_salidas = ("Salidas del XML: " + " · ".join(salidas)) if salidas else (
            "Salidas del XML: el XML no guarda resultados "
            "(revisa <save><full_data> y <save><SVG>)."
        )
        if hasattr(self, "cfg_salidas"):
            self.cfg_salidas.setText(texto_salidas)

        self.cfg_estado.setText(f"XML: {xe}   •   Motor: {ee}")
        self.cfg_estado.setToolTip(
            "\n".join(f"- {p}" for p in problemas) if problemas else "Motor listo para ejecutar."
        )
        if not silencioso:
            detalle = ""
            if problemas:
                detalle = "\n\nProblemas del motor:\n- " + "\n- ".join(problemas)
            QMessageBox.information(
                self.lw, "Validación",
                f"XML: {xe}\nMotor: {ee}\n{texto_salidas}{detalle}",
            )

    def _probar_motor(self):
        """Lanza PhysiCell con un XML reducido para comprobar que funciona."""
        exe = self.cfg_exe.text().strip()
        xml = self.cfg_xml.text().strip()
        if not xml or not os.path.isfile(xml):
            QMessageBox.warning(self.lw, "Probar motor",
                                "Selecciona primero un XML que exista.")
            return
        if not exe or not os.path.isfile(exe):
            QMessageBox.warning(self.lw, "Probar motor",
                                "Selecciona el ejecutable de PhysiCell (project.exe).")
            return
        log = os.path.join(os.path.dirname(self.db_path()), "diagnostico_motor.log")
        self.btn_probar.setEnabled(False)
        self.btn_probar.setText("Probando…")
        self._diag = _DiagWorker(exe, xml, log, self)
        self._diag.done.connect(self._diag_listo)
        self._diag.start()

    def _diag_listo(self, r):
        self.btn_probar.setEnabled(True)
        self.btn_probar.setText("Probar motor")
        lineas = []
        if r.get("ok"):
            lineas.append(
                f"Motor OK: arrancó y guardó {r.get('n_svg', 0)} SVG, "
                f"{r.get('n_xml', 0)} XML y {r.get('n_mat', 0)} .mat "
                f"en {r.get('duracion', 0):.1f} s."
            )
        else:
            lineas.append("El motor NO superó la prueba:")
            lineas += [f"- {p}" for p in (r.get("problemas") or ["sin detalle"])]
        for a in r.get("avisos") or []:
            lineas.append(f"Aviso: {a}")
        if r.get("log_path"):
            lineas.append(f"\nRegistro: {r['log_path']}")
        texto = "\n".join(lineas)
        if hasattr(self, "run_log"):
            self.run_log.append(texto)
        icono = QMessageBox.Icon.Information if r.get("ok") else QMessageBox.Icon.Warning
        QMessageBox(icono, "Probar motor", texto[:4000], parent=self.lw).exec()

    def _guardar_cfg_detalle(self):
        p = self.cfg_xml.text().strip()
        if p:
            v = validar_config(p)
            if not v.get("ok"):
                QMessageBox.warning(
                    self.lw, "Guardar",
                    "XML inválido: " + "; ".join(v.get("errores", []))
                )
                return
        from .. import servicios as SERV
        r = SERV.actualizar_rutas_experimento(
            self.db_path(), self.current_experiment_id,
            config_xml_path=p,
            binary_path=self.cfg_exe.text().strip() if hasattr(self, "cfg_exe") else "",
            custom_cpp_path=self.cfg_cpp.text().strip() if hasattr(self, "cfg_cpp") else "",
            custom_h_path=self.cfg_h.text().strip() if hasattr(self, "cfg_h") else "",
        )
        if not r.get("ok"):
            QMessageBox.warning(self.lw, "Configuración", r.get("error", "Error al guardar"))
            return
        self.lw._last_exe = self.cfg_exe.text().strip() if hasattr(self, "cfg_exe") else ""
        QMessageBox.information(self.lw, "Configuración", "Guardada en este experimento.")
        self.lw.refrescar_exps()
        self.lw.refrescar_resumen()

    def _editar_xml_detalle(self):
        from PyQt6.QtWidgets import QPlainTextEdit
        from ..config_manager import leer_texto, guardar_texto
        p = self.cfg_xml.text().strip() if hasattr(self, "cfg_xml") else ""
        if not p or not os.path.isfile(p):
            QMessageBox.warning(self.lw, "Editar", "Selecciona un XML existente primero.")
            return
        try:
            txt = leer_texto(p)
        except Exception as e:
            QMessageBox.warning(self.lw, "Editar", str(e))
            return
        dlg = QDialog(self.lw)
        dlg.setWindowTitle("Editar XML")
        dlg.resize(900, 600)
        lay = QVBoxLayout(dlg)

        ed = QPlainTextEdit()
        ed.setPlainText(txt)
        ed.setFont(QFont("Consolas", 10))
        lay.addWidget(ed)

        lbl_val = QLabel("")
        lbl_val.setObjectName("Muted")
        lbl_val.setWordWrap(True)
        lbl_val.setMaximumHeight(40)
        lay.addWidget(lbl_val)

        timer = QTimer(dlg)
        timer.setSingleShot(True)

        def _validar_tiempo_real():
            texto = ed.toPlainText()
            v = validar_texto(texto)
            if v.get("ok"):
                avisos = v.get("warnings", [])
                if avisos:
                    lbl_val.setText("Válido · " + "; ".join(avisos[:3]))
                    lbl_val.setStyleSheet("color: #F5B83D;")
                else:
                    lbl_val.setText("Válido")
                    lbl_val.setStyleSheet("color: #4CAF69;")
            else:
                lbl_val.setText("Error: " + "; ".join(v.get("errores", [])[:3]))
                lbl_val.setStyleSheet("color: #E5484D;")

        def _programar_validacion():
            timer.stop()
            timer.start(400)

        ed.textChanged.connect(_programar_validacion)
        timer.timeout.connect(_validar_tiempo_real)
        _validar_tiempo_real()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("Secondary")
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            r = guardar_texto(p, ed.toPlainText())
            if r.get("ok"):
                QMessageBox.information(self.lw, "Editar", "XML guardado.")
            else:
                QMessageBox.warning(self.lw, "Editar", r.get("error", "Error"))

    # =====================================================================
    # Pestaña: Ejecuciones
    # =====================================================================
    def _tab_ejecucion(self, eid, cfg):
        from ..simulador import listar_escenarios, eliminar_escenario
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<b>Escenarios del experimento</b>"))
        conn_e = self.conn()
        escs = list(listar_escenarios(conn_e, eid))
        conn_e.close()
        if not escs:
            l = QLabel("Sin escenarios. Créalos como variantes en la pestaña Configuración.")
            l.setObjectName("Muted")
            l.setWordWrap(True)
            v.addWidget(l)
        for sid, nom, cpath in escs:
            f = QFrame()
            f.setObjectName("Card")
            h = QHBoxLayout(f)
            l = QLabel(f"#{sid} {nom}\n{cpath}")
            l.setWordWrap(True)
            h.addWidget(l, 1)
            bb = QPushButton("Borrar")
            bb.setFixedWidth(70)
            bb.setObjectName("Danger")
            def _borrar(_=False, s=sid):
                conn = self.conn()
                eliminar_escenario(conn, s)
                conn.close()
                self.lw.refrescar_detalle()
            bb.clicked.connect(_borrar)
            h.addWidget(bb)
            v.addWidget(f)

        # Selector de escenario (variante) para las réplicas a lanzar
        row_esc = QHBoxLayout()
        row_esc.addWidget(QLabel("Escenario (variante):"))
        self.run_escenario = QComboBox()
        self.run_escenario.addItem("Sin escenario (configuración activa del experimento)", None)
        self._escenarios_ejecucion = []
        for s in escs:
            self.run_escenario.addItem(f"#{s[0]} {s[1]}", s[0])
            self._escenarios_ejecucion.append(tuple(s))
        row_esc.addWidget(self.run_escenario)
        cesc = QFrame()
        cesc.setLayout(row_esc)
        v.addWidget(cesc)

        info = QLabel("Lanza réplicas en segundo plano. El progreso usa el tiempo simulado real de PhysiCell.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        v.addWidget(info)

        row = QHBoxLayout()
        row.addWidget(QLabel("Réplicas:"))
        self.run_reps = QSpinBox()
        self.run_reps.setRange(1, 50)
        self.run_reps.setValue(getattr(self, "cfg_reps", QSpinBox()).value() if hasattr(self, "cfg_reps") else 3)
        row.addWidget(self.run_reps)
        row.addWidget(QLabel("Límite por réplica (min):"))
        self.run_timeout = QSpinBox()
        self.run_timeout.setRange(0, 10080)  # hasta 7 dias; 0 = sin limite
        self.run_timeout.setValue(0)
        self.run_timeout.setToolTip(
            "0 = sin límite absoluto (recomendado).\n"
            "Si el motor deja de escribir 10 min seguidos, se cancela y se explica."
        )
        row.addWidget(self.run_timeout)
        self.btn_run = QPushButton("Ejecutar")
        self.btn_run.setObjectName("Primary")
        self.btn_run.clicked.connect(self._ejecutar)
        self.btn_stop = QPushButton("Detener")
        self.btn_stop.setObjectName("Secondary")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._detener)
        row.addWidget(self.btn_run)
        row.addWidget(self.btn_stop)
        row.addStretch()
        c = QFrame()
        c.setLayout(row)
        v.addWidget(c)

        self.run_prog = QProgressBar()
        self.run_prog.setRange(0, 100)
        v.addWidget(self.run_prog)
        self.run_log = QTextEdit()
        self.run_log.setReadOnly(True)
        self.run_log.setMaximumHeight(160)
        v.addWidget(self.run_log)

        v.addWidget(QLabel("<b>Réplicas de este experimento</b>"))
        self.runs_table = TablaBase(
            ["Run", "Estado", "Inicio", "Fin", "Motivo del error", "Registro"]
        )
        cab = self.runs_table.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.runs_table.itemDoubleClicked.connect(self._ver_detalle_run)
        self._cargar_runs_tabla(eid)
        v.addWidget(self.runs_table, 1)
        return w

    def _cargar_runs_tabla(self, eid=None):
        """Vuelca las réplicas con estado, motivo del fallo y registro del motor."""
        eid = self.current_experiment_id if eid is None else eid
        if not eid or not hasattr(self, "runs_table"):
            return
        filas = []
        self._filas_runs = []
        for r in self._runs_exp(eid):
            motivo = r[6] or ""
            if not motivo and r[2] in ("failed", "cancelled"):
                motivo = "Sin detalle registrado (ejecución anterior a esta versión)"
            log_path = r[7] if len(r) > 7 else ""
            pid = r[8] if len(r) > 8 else None
            batch_id = r[9] if len(r) > 9 else None
            self._filas_runs.append({
                "experimento": self.current_experiment_id,
                "replica": r[1],
                "estado": r[2],
                "inicio": r[3] or "",
                "fin": r[4] or "",
                "motivo": motivo,
                "salida": r[5] or "",
                "log_path": log_path or "",
                "pid": pid,
                "batch_id": batch_id,
            })
            filas.append((
                r[1], r[2], r[3] or "", r[4] or "", resumen_texto(motivo),
                "Ver salida" if log_path else "sin registro",
            ))
        self.runs_table.cargar(filas)
        for i, datos in enumerate(self._filas_runs):
            it = self.runs_table.item(i, 4)
            if it is not None:
                it.setToolTip(datos["motivo"])
            it_log = self.runs_table.item(i, 5)
            if it_log is not None:
                it_log.setToolTip(
                    datos["log_path"] or
                    "Esta ejecución no tiene registro del motor guardado."
                )
                if not datos["log_path"]:
                    it_log.setForeground(QColor("#7A7A7A"))
        for i in range(self.runs_table.rowCount()):
            it = self.runs_table.item(i, 1)
            if it is not None:
                it.setForeground(QColor(_COLOR_ESTADO_RUN.get(it.text(), "#A6A6A6")))

    def _ver_detalle_run(self, item):
        fila = item.row()
        datos = (self._filas_runs[fila] if getattr(self, "_filas_runs", None)
                 and fila < len(self._filas_runs) else {})
        DialogoDetalleRun(datos, padre=self).exec()

    def _ejecutar(self):
        try:
            self._ejecutar_interno()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.run_log.append(f"ERROR CRÍTICO: {e}")
            QMessageBox.critical(
                self.lw,
                "Error durante la ejecución",
                f"Ocurrió un error inesperado al intentar iniciar la simulación:\n\n{e}\n\n"
                f"Detalles técnicos:\n{tb[-1500:]}",
            )

    def _ejecutar_interno(self):
        eid = self.current_experiment_id
        # RF05: escenario (variante) seleccionado -> define la config y vincula la réplica
        esc_id = self.run_escenario.currentData() if hasattr(self, "run_escenario") else None
        esc_sid = int(esc_id) if esc_id is not None else None
        base = self.cfg_xml.text().strip() if hasattr(self, "cfg_xml") else ""
        cfg_id = None
        if esc_sid is not None:
            base = next(
                (str(s[2] or "") for s in (getattr(self, "_escenarios_ejecucion", None) or [])
                 if int(s[0]) == esc_sid),
                "",
            )
            conn_e = self.conn()
            try:
                row_e = conn_e.execute(
                    "SELECT configuracion_id FROM escenarios WHERE id=?", (esc_sid,)
                ).fetchone()
            finally:
                conn_e.close()
            cfg_id = row_e[0] if row_e else None
        else:
            from ..nucleo import configuracion_activa
            conn_e = self.conn()
            try:
                ca = configuracion_activa(conn_e, eid)
            finally:
                conn_e.close()
            cfg_id = ca[0] if ca else None
        if not (base or "").strip():
            QMessageBox.warning(self.lw, "Ejecución", "Asigna el XML en la pestaña Configuración.")
            return
        v = validar_config(base)
        if not v.get("ok"):
            motivos = "; ".join(v.get("errores", [])) or "sin detalle del validador"
            self.run_log.append(f"XML inválido: {motivos}")
            QMessageBox.warning(
                self.lw, "Ejecución",
                f"El XML del experimento no es válido:\n\n{motivos}\n\n{v.get('path', base)}",
            )
            return
        n = self.run_reps.value()
        exe = self.cfg_exe.text().strip() if hasattr(self, "cfg_exe") else ""
        cpp = self.cfg_cpp.text().strip() if hasattr(self, "cfg_cpp") else ""
        hh = self.cfg_h.text().strip() if hasattr(self, "cfg_h") else ""

        # Persistencia automática: guarda el motor y custom.cpp/h en la BD aunque no se cierre la pestaña
        from .. import servicios as SERV
        if esc_sid is None:
            SERV.actualizar_rutas_experimento(
                self.db_path(), eid,
                config_xml_path=base,
                binary_path=exe,
                custom_cpp_path=cpp,
                custom_h_path=hh,
            )
        self.lw._last_exe = exe

        if not exe:
            QMessageBox.warning(
                self.lw, "Ejecución",
                "Configura la ruta del Motor PhysiCell (project.exe) en la pestaña Configuración."
            )
            return
        from ..motor_physicell import verificar_binario
        problemas = verificar_binario(exe)
        if problemas:
            detalle = "\n- " + "\n- ".join(problemas)
            self.run_log.append(f"Motor no usable:{detalle}")
            QMessageBox.warning(
                self.lw, "Ejecución",
                "No se puede iniciar PhysiCell porque el motor configurado no es usable:"
                f"{detalle}\n\nRuta: {exe}"
            )
            return
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        timeout_min = self.run_timeout.value() if hasattr(self, "run_timeout") else 0
        limite_txt = (f"{timeout_min} min por réplica" if timeout_min
                      else "sin límite absoluto (watchdog de inactividad 10 min)")
        self.run_log.append(f"Iniciando {n} réplicas con PhysiCell — {limite_txt}...")
        try:
            from ..nucleo import ReplicaWorker, get_db_path
            self.worker = ReplicaWorker(eid, base, n, exe, get_db_path(),
                                        configuracion_id=cfg_id, escenario_id=esc_sid,
                                        timeout_min=timeout_min)
            self.worker.prog.connect(lambda v, t: (self.run_prog.setValue(v), self.run_log.append(t)))
            self.worker.done.connect(self._run_done)
            self.worker.fail.connect(self._run_fail)
            self.worker.start()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            self.btn_run.setEnabled(True)
            self.btn_stop.setEnabled(False)
            self.run_log.append(f"ERROR al iniciar worker: {e}")
            QMessageBox.critical(
                self.lw,
                "Error al iniciar simulación",
                f"No se pudo iniciar el worker de réplicas:\n\n{e}\n\n"
                f"Detalles técnicos:\n{tb[-2000:]}",
            )

    def _run_done(self, info):
        self.run_prog.setValue(100)
        fallos = (info.get("fallos") or []) if isinstance(info, dict) else []
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if fallos:
            self.run_log.append(f"Terminó con {len(fallos)} réplica(s) fallida(s):")
            for f in fallos:
                self.run_log.append(f"  • {f}")
            QMessageBox.warning(
                self.lw,
                "Ejecución con errores",
                f"{len(fallos)} de {info.get('replicas', '?')} réplicas fallaron.\n\n"
                + "\n\n".join(fallos[:5])[:3000]
                + "\n\nEl motivo y la salida completa del motor están en la tabla "
                  "de abajo (columna Registro, doble clic) y en la página Ejecuciones.",
            )
        else:
            self.run_log.append(
                f"Completado: {info.get('replicas', '?')} réplica(s) sin errores. "
                "El registro de cada una está en la tabla de abajo (columna Registro)."
            )
        self.lw.refrescar_detalle()

    def _run_fail(self, msg):
        self.run_log.append(f"Detenido/error: {msg}")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        # También imprimir a consola para debugging
        print(f"[ERROR WORKER] {msg}")
        QMessageBox.warning(
            self.lw,
            "Error de ejecución",
            f"La simulación se detuvo con un error:\n\n{msg}",
        )

    def _detener(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.run_log.append("Solicitando detención del proceso PhysiCell...")

    # =====================================================================
    # Pestaña: Visualización
    # =====================================================================
    def _tab_vis(self, eid):
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        v.setSpacing(ESPACIO_M)

        top = QHBoxLayout()
        self.vis_rep = QComboBox()
        self.vis_rep.setToolTip("Réplica / salida a visualizar")
        self.vis_mode = QComboBox()
        self.vis_mode.addItems(["Ambos", "2D", "3D"])
        self.vis_mode.setToolTip("Vista 2D, 3D o comparada")
        b_ref = QPushButton("Actualizar")
        b_ref.setObjectName("Secondary")
        b_ref.clicked.connect(self._vis_cargar)
        b_rst = QPushButton("Restablecer vista")
        b_rst.setObjectName("Secondary")
        b_rst.clicked.connect(lambda: self.visor._recargar() if hasattr(self, "visor") else None)
        b_vtk = QPushButton("Tumor 3D (PyVista/VTK)")
        b_vtk.setObjectName("Primary")
        b_vtk.setToolTip("Abrir esferas 3D interactivas: rotar, zoom, seleccionar células y ver oxígeno")
        b_vtk.clicked.connect(self._abrir_vtk_detalle)
        top.addWidget(QLabel("Réplica:"))
        top.addWidget(self.vis_rep, 1)
        top.addWidget(QLabel("Vista:"))
        top.addWidget(self.vis_mode)
        top.addWidget(b_ref)
        top.addWidget(b_rst)
        top.addWidget(b_vtk)
        b_vid2 = QPushButton("Video 2D")
        b_vid2.setObjectName("Secondary")
        b_vid2.setToolTip("Generar video MP4 2D de los frames de la réplica seleccionada (requiere ffmpeg)")
        b_vid2.clicked.connect(lambda: self._generar_video("2d"))
        b_vid3 = QPushButton("Video 3D (VTK)")
        b_vid3.setObjectName("Secondary")
        b_vid3.setToolTip("Generar video MP4 3D con PyVista/VTK de los frames de la réplica seleccionada (requiere ffmpeg)")
        b_vid3.clicked.connect(lambda: self._generar_video("3d"))
        top.addWidget(b_vid2)
        top.addWidget(b_vid3)
        bar = QFrame()
        bar.setLayout(top)
        v.addWidget(bar)

        self.visor = VisorPhysiCell(output_dir="")
        v.addWidget(self.visor, 1)
        self.vis_mode.currentTextChanged.connect(self._vis_modo)
        self._vis_cargar()
        return w

    def _abrir_vtk_detalle(self):
        d = ""
        try:
            outs = self.vis_rep.property("outs") or []
            i = self.vis_rep.currentIndex()
            if 0 <= i < len(outs):
                d = outs[i]
        except Exception:
            pass
        conn = self.conn()
        r = SIM.obtener_experimento(conn, self.current_experiment_id)
        conn.close()
        titulo = r[1] if r else ""
        abrir_vtk(self.lw, d or "", titulo=f"Tumor 3D — {titulo or self.current_experiment_id}")

    def _generar_video(self, tipo: str):
        eid = self.current_experiment_id
        outs = self._salidas_replicas(eid)
        i = self.vis_rep.currentIndex()
        if not outs or i < 0 or i >= len(outs):
            QMessageBox.warning(self.lw, "Video", "Selecciona una réplica con salida válida.")
            return
        lbl, output_dir = outs[i]
        if not output_dir or not os.path.isdir(output_dir):
            QMessageBox.warning(self.lw, "Video", "La réplica seleccionada no tiene carpeta de salida.")
            return

        from PyQt6.QtWidgets import QInputDialog, QFileDialog
        fps, ok = QInputDialog.getInt(
            self.lw, "FPS del video", "Frames por segundo:", 1, 1, 60, 1
        )
        if not ok:
            return
        salida, _ = QFileDialog.getSaveFileName(
            self.lw, f"Guardar video {tipo.upper()}", f"video_{tipo}_{lbl.replace(' ', '_')}.mp4",
            "MP4 (*.mp4)"
        )
        if not salida:
            return

        self.run_log.append(f"Generando video {tipo.upper()} con {fps} FPS...")
        QApplication.processEvents()

        if tipo == "2d":
            r = generar_video_2d(output_dir, salida, fps=fps)
        else:
            r = generar_video_3d_vtk(output_dir, salida, fps=fps)

        if r.get("ok"):
            conn = self.conn()
            run_num = SIM.obtener_run_por_output_dir(conn, eid, output_dir)
            conn.close()
            from ..nucleo import registrar_video, get_db_path
            conn2 = sqlite3.connect(get_db_path())
            registrar_video(conn2, eid, run_num, tipo=tipo, ruta_archivo=salida, fps=fps, frames=r.get("frames", 0))
            conn2.close()
            self.run_log.append(f"Video {tipo.upper()} generado: {salida} ({r.get('frames', 0)} frames)")
            QMessageBox.information(self.lw, "Video", f"Video {tipo.upper()} generado:\n{salida}")
        else:
            self.run_log.append(f"Error video {tipo.upper()}: {r.get('error')}")
            QMessageBox.warning(self.lw, "Video", r.get("error", "Error desconocido"))

    def _salidas_replicas(self, eid):
        conn = self.conn()
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        outs = []
        import glob as _g
        for fila in rows:
            _id, rnum, st, _s, _e, od = fila[:6]
            if od and os.path.isdir(od):
                for d in (os.path.join(od, "output"), od):
                    if _g.glob(os.path.join(d, "snapshot*.svg")) or _g.glob(os.path.join(d, "*_cells.mat")):
                        outs.append((f"Réplica {rnum} ({st})", d))
                        break
        outs.append(("Salida global PhysiCell/output", ""))
        return outs

    def _vis_cargar(self):
        outs = self._salidas_replicas(self.current_experiment_id)
        self.vis_rep.clear()
        for lbl, _d in outs:
            self.vis_rep.addItem(lbl)
        self.vis_rep.setProperty("outs", [d for _, d in outs])
        self.vis_rep.currentIndexChanged.connect(lambda _: self._vis_sel())
        self._vis_sel()

    def _vis_sel(self):
        outs = self.vis_rep.property("outs") or []
        i = self.vis_rep.currentIndex()
        if 0 <= i < len(outs):
            self.visor.set_output_dir(outs[i])

    def _vis_modo(self, modo):
        try:
            if modo == "2D":
                self.visor.tabs_vis.setCurrentIndex(0)
            elif modo == "3D":
                self.visor.tabs_vis.setCurrentIndex(1)
            else:
                self.visor.tabs_vis.setCurrentIndex(0)
            self.visor.canvas2.draw()
            self.visor.canvas3.draw()
        except Exception:
            pass

    # =====================================================================
    # Pestaña: Resultados
    # =====================================================================
    def _tab_resultados(self, eid):
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        runs = self._runs_exp(eid)
        info = QLabel(f"{len(runs)} réplicas registradas. Cada resultado indica experimento, réplica y carpeta de salida.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        v.addWidget(info)

        t = QTableWidget()
        t.setColumnCount(5)
        t.setHorizontalHeaderLabels(["Run", "Estado", "Inicio", "Fin", "Salida"])
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t.setRowCount(len(runs))
        for i, fila in enumerate(runs):
            _id, rnum, st, s0, s1, od = fila[:6]
            for j, val in enumerate([str(rnum), st, s0 or "", s1 or "", od or ""]):
                t.setItem(i, j, QTableWidgetItem(val))
        t.setMaximumHeight(160)
        v.addWidget(t)

        erow = QHBoxLayout()
        self.res_rep = QComboBox()
        self.res_rep.setToolTip("Réplica cuya carpeta se inspecciona")
        self.res_rep.currentIndexChanged.connect(lambda _: self._res_verificar())
        b_ver = QPushButton("Verificar integridad")
        b_ver.setObjectName("Secondary")
        b_ver.clicked.connect(self._res_verificar)
        b_abrir = QPushButton("Abrir en visualización")
        b_abrir.setObjectName("Secondary")
        b_abrir.clicked.connect(self._res_abrir_vis)
        erow.addWidget(QLabel("Réplica:"))
        erow.addWidget(self.res_rep, 1)
        erow.addWidget(b_ver)
        erow.addWidget(b_abrir)
        ec = QFrame()
        ec.setLayout(erow)
        v.addWidget(ec)

        self.res_files = QTableWidget()
        self.res_files.setColumnCount(2)
        self.res_files.setHorizontalHeaderLabels(["Archivo", "Tamaño"])
        self.res_files.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.res_files.setMaximumHeight(130)
        v.addWidget(self.res_files)

        self.res_temp_img = QLabel("Sin gráfica temporal.")
        self.res_temp_img.setObjectName("Muted")
        self.res_temp_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.res_temp_img)

        self.res_log = QTextEdit()
        self.res_log.setReadOnly(True)
        self.res_log.setMaximumHeight(100)
        v.addWidget(self.res_log)

        row = QHBoxLayout()
        for lbl, fn in [
            ("Resumen", self._res_resumen),
            ("CSV", self._res_csv),
            ("JSON", self._res_json),
            ("Temporal", self._res_temporal),
            ("Consolidar", self._res_consolidar),
            ("Limpiar", self._res_limpiar),
        ]:
            b = QPushButton(lbl)
            b.setObjectName("Secondary")
            if lbl == "Temporal":
                b.setToolTip("Gráfica de células por frame de la réplica seleccionada")
            elif lbl == "Consolidar":
                b.setToolTip("Genera frames_todas.csv y celulas_todas.csv con todas las réplicas para análisis")
            elif lbl == "Limpiar":
                b.setToolTip("Marca como fallidos los runs sin carpeta de salida")
            b.clicked.connect(fn)
            row.addWidget(b)
        row.addStretch()
        c = QFrame()
        c.setLayout(row)
        v.addWidget(c)
        v.addStretch()
        return w

    def _res_cargar_reps(self):
        self.res_rep.clear()
        for fila in self._runs_exp(self.current_experiment_id):
            _id, rnum, st, _s, _e, od = fila[:6]
            self.res_rep.addItem(f"Réplica {rnum} ({st})", od or "")
        self._res_verificar()

    def _res_rep_dir(self):
        d = self.res_rep.currentData() if hasattr(self, "res_rep") else ""
        return d or ""

    def _res_verificar(self):
        from ..visualizador import verificar_integridad, listar_archivos
        d = self._res_rep_dir()
        if not d:
            return
        try:
            filas = listar_archivos(d)
        except Exception:
            filas = []
        self.res_files.setRowCount(len(filas))
        for i, (p, sz) in enumerate(filas):
            self.res_files.setItem(i, 0, QTableWidgetItem(p))
            self.res_files.setItem(i, 1, QTableWidgetItem(str(sz)))
        try:
            v = verificar_integridad(d)
        except Exception as e:
            self.res_log.append(f"Integridad: error {e}")
            return
        if v.get("ok"):
            self.res_log.append(
                f"Integridad OK en {d}: svg={v['n_svg']} xml={v['n_xml']} "
                f"mats={v['n_cells_mat']} grafos={v['n_grafos']}"
            )
        else:
            self.res_log.append(
                f"Integridad INCOMPLETA en {d}: falta {', '.join(v['faltan'])} "
                f"(svg={v['n_svg']} xml={v['n_xml']} mats={v['n_cells_mat']} grafos={v['n_grafos']})"
            )

    def _res_abrir_vis(self):
        d = self._res_rep_dir()
        if not d or not os.path.isdir(d):
            QMessageBox.warning(self.lw, "Resultados", "La réplica no tiene carpeta de salida.")
            return
        self.tabs_widget.setCurrentIndex(3)
        try:
            self.visor.set_output_dir(d if os.path.isfile(os.path.join(d, "initial.xml")) else os.path.join(d, "output"))
        except Exception as e:
            self.res_log.append(f"No se pudo abrir en visor: {e}")

    def _res_resumen(self):
        from ..visualizador import resumen_resultados
        r = resumen_resultados(self._exp_dir())
        self.res_log.append(f"SVG:{r.get('n_svg', 0)} XML:{r.get('n_xml', 0)} MAT:{r.get('n_mat', 0)}")

    def _res_csv(self):
        from ..reportes import exportar_runs_csv
        r = exportar_runs_csv(self.current_experiment_id, self.db_path(), self._exp_dir() + "/runs.csv")
        self.res_log.append(f"CSV: {r}")

    def _res_json(self):
        from ..reportes import exportar_runs_json
        r = exportar_runs_json(self.current_experiment_id, self.db_path(), self._exp_dir() + "/runs.json")
        self.res_log.append(f"JSON: {r}")

    def _res_informe(self):
        from ..reportes import generar_reporte_html
        r = generar_reporte_html(self.current_experiment_id, self.db_path(), self._exp_dir() + "/reporte.html")
        self.res_log.append(f"Informe: {r}")
        if r.get("ok"):
            QMessageBox.information(self.lw, "Informe", f"Generado: {r['path']}")

    def _res_pdf(self):
        from ..reportes import generar_reporte_html, exportar_reporte_pdf
        import os as _o
        html = _o.path.join(self._exp_dir(), "reporte.html")
        generar_reporte_html(self.current_experiment_id, self.db_path(), html)
        pdf = _o.path.join(self._exp_dir(), "reporte.pdf")
        r = exportar_reporte_pdf(html, pdf)
        self.res_log.append(f"PDF: {r}")
        if r.get("ok"):
            QMessageBox.information(self.lw, "PDF", f"Generado: {r['path']}")
        else:
            QMessageBox.warning(self.lw, "PDF", r.get("error", "Error"))

    def _res_temporal(self):
        from ..comparacion import generar_grafica_temporal
        import os as _o
        d = self._res_rep_dir()
        out = _o.path.join(self._exp_dir(), "temporal.png")
        r = generar_grafica_temporal(d, out)
        self.res_log.append(f"Temporal: {r}")
        if r.get("ok"):
            self.res_temp_img.setPixmap(__import__("PyQt6.QtGui", fromlist=["QPixmap"]).QPixmap(out).scaledToWidth(
                620, Qt.TransformationMode.SmoothTransformation
            ))
        else:
            QMessageBox.warning(self.lw, "Temporal", r.get("error", "Error"))

    def _res_limpiar(self):
        import os as _o
        runs = self._runs_exp(self.current_experiment_id)
        marcados = 0
        conn = self.conn()
        for _id, _rn, st, _s, _e, od in runs:
            if st in ("running", "pending", "registered") and (not od or not _o.path.isdir(od)):
                SIM.actualizar_run(conn, _id, "failed", end=True)
                marcados += 1
        conn.close()
        self.res_log.append(f"Limpieza: {marcados} runs sin salida marcados como failed")
        self.lw.refrescar_detalle()

    def _res_consolidar(self):
        from ..agregador import agregar_experimento
        from PyQt6.QtWidgets import QProgressDialog
        dlg = QProgressDialog("Consolidando réplicas...", "Cancelar", 0, 100, self.lw)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(10)
        __import__("PyQt6.QtWidgets", fromlist=["QApplication"]).QApplication.processEvents()
        try:
            r = agregar_experimento(self.db_path(), self.current_experiment_id, self._exp_dir())
        finally:
            dlg.setValue(100)
            dlg.close()
        self.res_log.append(f"Consolidado: {r}")
        if r.get("ok"):
            QMessageBox.information(
                self.lw, "Consolidar",
                f"Réplicas con datos: {r['replicas']}\n{r['frames_csv']}\n{r['celulas_csv']}"
            )
        else:
            QMessageBox.warning(self.lw, "Consolidar", r.get("error", "Error"))

    # =====================================================================
    # Pestaña: Comparación
    # =====================================================================
    def _tab_comparacion(self, eid):
        from ..visor_widget import VisorPhysiCell
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        info = QLabel(
            "Compara réplicas del experimento: vistas paralelas con navegación sincronizada y métricas. "
            "Si difieren en frames, se informa en lugar de forzar la comparación."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        v.addWidget(info)

        # ---------- Comparación estadística entre experimentos (t de Student) ----------
        from .. import servicios as SERV
        from .. import estadistica as EST

        v.addWidget(QLabel("<b>Comparación estadística entre experimentos</b>: prueba t de Student sobre métricas de réplicas (n.º de células finales)."))
        row_stats = QHBoxLayout()
        self.cmp_exp_a = QComboBox()
        self.cmp_exp_b = QComboBox()
        exps = SERV.listar_experimentos_servicio(self.db_path()) or []
        for r in exps:
            self.cmp_exp_a.addItem(f"#{r[0]} {r[1] or ''}", r[0])
            self.cmp_exp_b.addItem(f"#{r[0]} {r[1] or ''}", r[0])
        if self.cmp_exp_b.count() > 1:
            self.cmp_exp_b.setCurrentIndex(1)
        row_stats.addWidget(QLabel("Del experimento:"))
        row_stats.addWidget(self.cmp_exp_a, 2)
        row_stats.addWidget(QLabel("Con el de:"))
        row_stats.addWidget(self.cmp_exp_b, 2)
        b_cmp_stats = QPushButton("Ejecutar comparación (t de Student)")
        b_cmp_stats.setObjectName("Primary")
        b_cmp_stats.clicked.connect(self._cmp_stats)
        b_cmp_stats_csv = QPushButton("Exportar CSV")
        b_cmp_stats_csv.setObjectName("Secondary")
        b_cmp_stats_csv.clicked.connect(self._cmp_stats_csv)
        row_stats.addWidget(b_cmp_stats)
        row_stats.addWidget(b_cmp_stats_csv)
        sstats = QFrame()
        sstats.setLayout(row_stats)
        v.addWidget(sstats)

        self.cmp_stats_out = QTextEdit()
        self.cmp_stats_out.setReadOnly(True)
        self.cmp_stats_out.setMaximumHeight(140)
        v.addWidget(self.cmp_stats_out)

        outs = self._salidas_replicas(eid)
        row = QHBoxLayout()
        self.cmp_a = QComboBox()
        self.cmp_b = QComboBox()
        for lbl, _d in outs:
            self.cmp_a.addItem(lbl)
            self.cmp_b.addItem(lbl)
        if self.cmp_b.count() > 1:
            self.cmp_b.setCurrentIndex(1)
        self.cmp_sync = QCheckBox("Sincronizar frames")
        self.cmp_sync.setChecked(True)
        self.cmp_sync.setToolTip("Mover un slider mueve el otro, limitado al total de cada réplica")
        row.addWidget(QLabel("A:"))
        row.addWidget(self.cmp_a, 1)
        row.addWidget(QLabel("B:"))
        row.addWidget(self.cmp_b, 1)
        row.addWidget(self.cmp_sync)
        bar = QFrame()
        bar.setLayout(row)
        v.addWidget(bar)

        self.cmp_warn = QLabel("")
        self.cmp_warn.setObjectName("Muted")
        self.cmp_warn.setWordWrap(True)
        v.addWidget(self.cmp_warn)

        par = QHBoxLayout()
        self.cmp_va = VisorPhysiCell()
        self.cmp_vb = VisorPhysiCell()
        self.cmp_va.setMinimumHeight(300)
        self.cmp_vb.setMinimumHeight(300)
        par.addWidget(self.cmp_va, 1)
        par.addWidget(self.cmp_vb, 1)
        cp = QFrame()
        cp.setLayout(par)
        v.addWidget(cp, 1)

        self.cmp_a.currentIndexChanged.connect(lambda _: self._cmp_cargar())
        self.cmp_b.currentIndexChanged.connect(lambda _: self._cmp_cargar())
        self.cmp_va.slider.valueChanged.connect(lambda _: self._cmp_sync_de_a())
        self.cmp_vb.slider.valueChanged.connect(lambda _: self._cmp_sync_de_b())

        self.cmp_log = QTextEdit()
        self.cmp_log.setReadOnly(True)
        self.cmp_log.setMaximumHeight(100)
        v.addWidget(self.cmp_log)

        self.cmp_img = QLabel("Sin gráfica generada.")
        self.cmp_img.setObjectName("Muted")
        self.cmp_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.cmp_img)

        b = QPushButton("Generar métricas y gráfica")
        b.setObjectName("Primary")
        b.clicked.connect(self._gen_cmp)
        v.addWidget(b)

        self._cmp_outs = outs
        self._cmp_cargar()
        return w

    def _cmp_dirs(self):
        a = self.cmp_a.currentIndex() if hasattr(self, "cmp_a") else 0
        b = self.cmp_b.currentIndex() if hasattr(self, "cmp_b") else 0
        da = self._cmp_outs[a][1] if 0 <= a < len(self._cmp_outs) else ""
        db = self._cmp_outs[b][1] if 0 <= b < len(self._cmp_outs) else ""
        return da, db

    def _cmp_cargar(self):
        if not hasattr(self, "cmp_va"):
            return
        da, db = self._cmp_dirs()
        self.cmp_va.slider.blockSignals(True)
        self.cmp_vb.slider.blockSignals(True)
        self.cmp_va.set_output_dir(da)
        self.cmp_vb.set_output_dir(db)
        self.cmp_va.slider.blockSignals(False)
        self.cmp_vb.slider.blockSignals(False)
        na, nb = len(self.cmp_va.snaps), len(self.cmp_vb.snaps)
        if na != nb:
            self.cmp_warn.setText(
                f"Aviso: réplicas con distinto número de frames (A={na}, B={nb}). "
                f"La sincronización se limita al total de cada una."
            )
        else:
            self.cmp_warn.setText(f"Ambas réplicas con {na} frames. Tiempos comparables si comparten intervalos.")

    def _cmp_sync_de_a(self):
        if hasattr(self, "cmp_sync") and self.cmp_sync.isChecked() and hasattr(self, "cmp_vb"):
            self.cmp_vb.slider.blockSignals(True)
            self.cmp_vb.slider.setValue(min(self.cmp_va.slider.value(), self.cmp_vb.slider.maximum()))
            self.cmp_vb.slider.blockSignals(False)

    def _cmp_sync_de_b(self):
        if hasattr(self, "cmp_sync") and self.cmp_sync.isChecked() and hasattr(self, "cmp_va"):
            self.cmp_va.slider.blockSignals(True)
            self.cmp_va.slider.setValue(min(self.cmp_vb.slider.value(), self.cmp_va.slider.maximum()))
            self.cmp_va.slider.blockSignals(False)

    def _gen_cmp(self):
        from ..comparacion import generar_grafica_comparacion
        out = self._exp_dir() + "/comparacion.png"
        r = generar_grafica_comparacion(self.db_path(), self.current_experiment_id, out)
        self.cmp_log.append(f"Gráfica: {r['path']} runs={len(r['filas'])} sin_datos={r['sin_datos']}")
        for f in r["filas"]:
            self.cmp_log.append(f"run {f['run']}: {f['status']} n_final={f['n_final']}")
        if os.path.isfile(out):
            self.cmp_img.setPixmap(__import__("PyQt6.QtGui", fromlist=["QPixmap"]).QPixmap(out).scaledToWidth(
                640, Qt.TransformationMode.SmoothTransformation
            ))

    def _cmp_stats(self):
        """Ejecuta la comparación estadística (t de Student) entre dos experimentos."""
        from PyQt6.QtWidgets import QMessageBox
        from .. import estadistica as EST
        if self.cmp_exp_a.count() < 1 or self.cmp_exp_b.count() < 1:
            QMessageBox.warning(self.lw, "Comparación", "No hay experimentos registrados.")
            return
        id_a = self.cmp_exp_a.currentData()
        id_b = self.cmp_exp_b.currentData()
        if id_a is None or id_b is None or int(id_a) == int(id_b):
            QMessageBox.warning(self.lw, "Comparación", "Selecciona dos experimentos distintos.")
            return
        try:
            r = EST.comparar_experimentos(self.db_path(), [int(id_a), int(id_b)])
        except Exception as e:
            QMessageBox.critical(self.lw, "Comparación", f"Error al comparar: {e}")
            return
        comps = r.get("comparaciones") or {}
        clave = f"{int(id_a)}_vs_{int(id_b)}"
        c = comps.get(clave)
        if not c:
            self.cmp_stats_out.setText(
                f"Experimento {id_a} vs {id_b}\n"
                "Sin datos comparables: se requieren al menos 2 réplicas válidas por experimento "
                "para la prueba t de Student."
            )
            return
        sig = "SÍ" if c.get("significativo") else "NO"
        texto = (
            f"Experimento {id_a} vs {id_b}\n"
            f"  n células finales: media={c.get('media1'):.2f} (n={c.get('n1')}, std={c.get('std1'):.2f}) "
            f"vs {c.get('media2'):.2f} (n={c.get('n2')}, std={c.get('std2'):.2f})\n"
            f"  t = {c.get('t'):.3f}, p = {c.get('p'):.4f} -> Diferencia significativa: {sig}"
        )
        self.cmp_stats_out.setText(texto)
        self.cmp_stats_out.setReadOnly(True)

    def _cmp_stats_csv(self):
        """Exporta los datos de réplica (n.º células finales) de la comparación a CSV."""
        from PyQt6.QtWidgets import QMessageBox
        from .. import estadistica as EST
        if self.cmp_exp_a.count() < 1 or self.cmp_exp_b.count() < 1:
            QMessageBox.warning(self.lw, "Comparación", "No hay experimentos registrados.")
            return
        id_a = self.cmp_exp_a.currentData()
        id_b = self.cmp_exp_b.currentData()
        if id_a is None or id_b is None or int(id_a) == int(id_b):
            QMessageBox.warning(self.lw, "Comparación", "Selecciona dos experimentos distintos.")
            return
        try:
            r = EST.comparar_experimentos(self.db_path(), [int(id_a), int(id_b)])
        except Exception as e:
            QMessageBox.critical(self.lw, "Comparación", f"Error al exportar: {e}")
            return
        if not (r.get("comparaciones") or {}):
            QMessageBox.warning(self.lw, "Comparación", "Sin datos para exportar.")
            return
        salida = os.path.join(self._exp_dir(), "comparacion_estadistica.csv")
        p = EST.exportar_comparacion_csv(r, salida)
        QMessageBox.information(self.lw, "Comparación", f"CSV exportado:\n{p}")

    # =====================================================================
    # Pestaña: Reportes
    # =====================================================================
    def _tab_reportes(self, eid):
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        info = QLabel("Trazabilidad: qué configuración produjo cada ejecución y qué resultados pertenecen a ella.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        v.addWidget(info)

        conn = self.conn()
        exp_row = SIM.obtener_experimento(conn, eid)
        t = exp_row[1] if exp_row else ""
        cfg_path = exp_row[4] if exp_row else ""
        creado = exp_row[8] if exp_row else None
        n_esc = len(SIM.listar_escenarios(conn, eid))
        runs = SIM.listar_runs(conn, eid)
        conn.close()
        traza = QLabel(
            f"<b>{t}</b> (#{eid})<br>Config: {cfg_path or '—'}<br>Creado: {creado or '—'}<br>"
        )
        traza.setWordWrap(True)
        v.addWidget(traza)

        self.rep_log = QTextEdit()
        self.rep_log.setReadOnly(True)
        self.rep_log.setMaximumHeight(100)
        v.addWidget(self.rep_log)

        row = QHBoxLayout()
        for lbl in ("Informe HTML", "PDF", "CSV", "JSON"):
            b = QPushButton(lbl)
            b.setObjectName("Primary" if lbl == "Informe HTML" else "Secondary")
            b.clicked.connect(lambda _=False, k=lbl: self._rep_exportar(k))
            row.addWidget(b)
        row.addStretch()
        c = QFrame()
        c.setLayout(row)
        v.addWidget(c)
        v.addStretch()
        return w

    def _rep_exportar(self, kind):
        from ..reportes import generar_reporte_html, exportar_reporte_pdf, exportar_runs_csv, exportar_runs_json
        import os as _o
        base = self._exp_dir()
        if kind == "Informe HTML":
            r = generar_reporte_html(self.current_experiment_id, self.db_path(), _o.path.join(base, "reporte.html"))
        elif kind == "PDF":
            html = _o.path.join(base, "reporte.html")
            generar_reporte_html(self.current_experiment_id, self.db_path(), html)
            r = exportar_reporte_pdf(html, _o.path.join(base, "reporte.pdf"))
        elif kind == "CSV":
            r = exportar_runs_csv(self.current_experiment_id, self.db_path(), _o.path.join(base, "runs.csv"))
        else:
            r = exportar_runs_json(self.current_experiment_id, self.db_path(), _o.path.join(base, "runs.json"))
        self.rep_log.append(f"{kind}: {r}")
        if r.get("ok"):
            QMessageBox.information(self.lw, "Reportes", f"Generado: {r.get('path')}")
        else:
            QMessageBox.warning(self.lw, "Reportes", r.get("error", "Error"))
