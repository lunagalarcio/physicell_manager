"""Página de Detalle de experimento: pestañas Resumen, Configuración, Ejecuciones,
Visualización 2D/3D, Resultados, Comparación y Reportes."""
import os
import sqlite3
from datetime import datetime

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit, QFileDialog,
    QMessageBox, QSpinBox, QTextEdit, QProgressBar, QStackedWidget, QButtonGroup,
    QComboBox, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QGridLayout, QDialog, QFormLayout, QDialogButtonBox, QSizePolicy, QFrame, QWidget
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt, QTimer

from .base import (
    PaginaBase, Seccion, Tarjeta, BadgeEstado, xml_estado, exe_estado,
    exp_estado, ESTILO_ESTADO, ESTADO_BOTON, CampoFormulario, DialogoBase,
    TablaBase, ESPACIO_M, ESPACIO_L, TAM_H2,
)
from .. import simulador as SIM
from ..xml_validator import validar_config, validar_texto
from ..motor_physicell import MotorPhysiCell
from ..visor_widget import VisorPhysiCell
from ..visor3d_vtk import abrir_vtk


class PaginaDetalle(PaginaBase):
    def __init__(self, lab_window):
        super().__init__(lab_window)
        self.current_experiment_id = None
        self.worker = None
        self.tabs_widget = None

    def build(self, eid):
        self.current_experiment_id = eid
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        # ---------- Encabezado del experimento ----------
        conn = self.conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT title, description, tags, config_xml_path, created_at, last_modified "
            "FROM experiments WHERE id=?", (eid,)
        )
        r = cur.fetchone() or ("", "", "", "", None, None)
        conn.close()
        title, desc, tags, cfg, creado, modif = r
        runs = self._runs_exp(eid)
        conn2 = self.conn()
        n_esc = len(SIM.listar_escenarios(conn2, eid))
        conn2.close()
        n_run = sum(1 for x in runs if x[2] == "running")
        n_fail = sum(1 for x in runs if x[2] in ("failed", "cancelled"))
        n_ok = sum(1 for x in runs if x[2] == "completed")
        xe, _ = xml_estado(cfg)
        estado = exp_estado(len(runs), n_run, n_fail, n_ok, xe == "Válido")
        col = ESTILO_ESTADO.get(estado, "#A6A6A6")

        head = QHBoxLayout()
        left = QVBoxLayout()
        h = QLabel(title or f"Experimento {eid}")
        h.setObjectName("H1")
        left.addWidget(h)
        st = QLabel(
            f"<b style='color:{col}'>● {estado}</b> &nbsp; "
            f"<span style='color:#A6A6A6'>{tags or 'sin etiquetas'} • {n_esc} escenarios • {len(runs)} runs</span>"
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
        tabs.addTab(self._tab_config(eid, cfg), "Configuración")
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

        info = QLabel(
            f"<h2>{title or f'Experimento {eid}'}</h2>"
            f"<p>{desc or 'Sin descripción'}</p>"
            f"<p>Estado: <b style='color:{col}'>{estado}</b><br>"
            f"Creado: {creado or '—'} &nbsp; Modificado: {modif or '—'}<br>"
            f"Etiquetas: {tags or '—'}</p>"
            f"<p>Escenarios: <b>{n_esc}</b> &nbsp; Ejecuciones: <b>{len(runs)}</b><br>"
            f"XML: {cfg or 'no asignado'}</p>"
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
    def _tab_config(self, eid, cfg):
        w = QFrame()
        w.setObjectName("Card")
        v = QVBoxLayout(w)
        v.setSpacing(ESPACIO_M)

        self.cfg_xml = QLineEdit(cfg or "")
        self.cfg_xml.setPlaceholderText(".../PhysiCell_settings.xml — plantilla de réplicas")
        v.addWidget(self._file_row("XML del experimento:", self.cfg_xml, self._browse_cfg_detalle))

        self.cfg_exe = QLineEdit(getattr(self.lw, "_last_exe", ""))
        self.cfg_exe.setPlaceholderText(".../project.exe — motor PhysiCell compilado")
        v.addWidget(self._file_row("Motor PhysiCell:", self.cfg_exe, self._browse_exe_detalle))

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

        self.cfg_estado = QLabel("")
        self.cfg_estado.setWordWrap(True)
        v.addWidget(self.cfg_estado)

        btns = QHBoxLayout()
        b1 = QPushButton("Validar archivos")
        b1.setObjectName("Secondary")
        b1.clicked.connect(self._validar_detalle)
        b2 = QPushButton("Guardar configuración")
        b2.setObjectName("Primary")
        b2.clicked.connect(self._guardar_cfg_detalle)
        b3 = QPushButton("Editar XML…")
        b3.setObjectName("Secondary")
        b3.clicked.connect(self._editar_xml_detalle)
        btns.addWidget(b1)
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
        v.addStretch()
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

    def _validar_detalle(self, silencioso=False):
        xe, _ = xml_estado(self.cfg_xml.text().strip())
        ee, _ = exe_estado(self.cfg_exe.text().strip())
        self.cfg_estado.setText(f"XML: {xe}   •   Motor: {ee}")
        if not silencioso:
            QMessageBox.information(self.lw, "Validación", f"XML: {xe}\nMotor: {ee}")

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
        conn = self.conn()
        cur = conn.cursor()
        cur.execute(
            "UPDATE experiments SET config_xml_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?",
            (p, self.current_experiment_id),
        )
        conn.commit()
        conn.close()
        self.lw._last_exe = self.cfg_exe.text().strip()
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
        v.addStretch()
        return w

    def _ejecutar(self):
        eid = self.current_experiment_id
        base = self.cfg_xml.text().strip() if hasattr(self, "cfg_xml") else ""
        if not base:
            QMessageBox.warning(self.lw, "Ejecución", "Asigna el XML en la pestaña Configuración.")
            return
        if not validar_config(base).get("ok"):
            QMessageBox.warning(self.lw, "Ejecución", "El XML del experimento no es válido.")
            return
        n = self.run_reps.value()
        exe = self.cfg_exe.text().strip() if hasattr(self, "cfg_exe") else ""
        self.lw._last_exe = exe
        if not exe or not os.path.isfile(exe):
            QMessageBox.warning(
                self.lw, "Ejecución",
                "Configura el Motor PhysiCell (project.exe) en la pestaña Configuración y guárdalo antes de ejecutar."
            )
            return
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.run_log.append(f"Iniciando {n} réplicas con PhysiCell...")
        from ..nucleo import ReplicaWorker, get_db_path
        self.worker = ReplicaWorker(eid, base, n, exe, get_db_path())
        self.worker.prog.connect(lambda v, t: (self.run_prog.setValue(v), self.run_log.append(t)))
        self.worker.done.connect(self._run_done)
        self.worker.fail.connect(self._run_fail)
        self.worker.start()

    def _run_done(self, info):
        self.run_prog.setValue(100)
        self.run_log.append(f"Completado: {info}")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.lw.refrescar_detalle()

    def _run_fail(self, msg):
        self.run_log.append(f"Detenido/error: {msg}")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

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
        cur = conn.cursor()
        cur.execute("SELECT title FROM experiments WHERE id=?", (self.current_experiment_id,))
        r = cur.fetchone()
        conn.close()
        abrir_vtk(self.lw, d or "", titulo=f"Tumor 3D — {(r[0] if r else '') or self.current_experiment_id}")

    def _salidas_replicas(self, eid):
        conn = self.conn()
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        outs = []
        import glob as _g
        for _id, rnum, st, _s, _e, od in rows:
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
        for i, (_id, rnum, st, s0, s1, od) in enumerate(runs):
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
        for _id, rnum, st, _s, _e, od in self._runs_exp(self.current_experiment_id):
            self.res_rep.addItem(f"Réplica {rnum} ({st})", od or "")
        self._res_verificar()

    def _res_rep_dir(self):
        d = self.res_rep.currentData() if hasattr(self, "res_rep") else ""
        return d or ""

    def _res_verificar(self):
        from ..visualizador import verificar_integridad, listar_archivos
        d = self._res_rep_dir()
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
        cur = conn.cursor()
        cur.execute("SELECT title, config_xml_path, created_at FROM experiments WHERE id=?", (eid,))
        t, cfg_path, creado = cur.fetchone() or ("", "", None)
        cur.execute("SELECT COUNT(*) FROM escenarios WHERE experiment_id=?", (eid,))
        n_esc = cur.fetchone()[0]
        cur.execute(
            "SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number",
            (eid,),
        )
        runs = cur.fetchall()
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
