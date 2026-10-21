#!/usr/bin/env python3
"""PhysiCell Lab: shell oscuro con navegación por secciones. Reutiliza motor, DB y visor existentes."""
import os
import sys
import sqlite3
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QLineEdit, QFileDialog, QMessageBox, QSpinBox,
    QTextEdit, QProgressBar, QStackedWidget, QButtonGroup, QComboBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox,
    QGridLayout, QDialog, QFormLayout, QDialogButtonBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QPixmap
from .theme_lab import LAB_QSS
from .nucleo import get_db_path, init_database, ReplicaWorker
from . import simulador as SIM
from .xml_validator import validar_config
from .motor_physicell import MotorPhysiCell
from .visor_widget import VisorPhysiCell


def xml_estado(path):
    if not path or not str(path).strip():
        return ("Sin XML", "none")
    if not os.path.isfile(path):
        return ("Inexistente", "error")
    v = validar_config(path)
    if v.get("ok"):
        return ("Válido", "ok")
    return ("Inválido", "error")


def exe_estado(path):
    if not path or not str(path).strip():
        return ("Sin motor", "none")
    if os.path.isfile(path):
        return ("Listo", "ok")
    return ("Inexistente", "error")


def exp_estado(n_runs, n_running, n_failed, n_completed, xml_ok):
    if n_running > 0:
        return "En ejecución"
    if n_failed > 0:
        return "Error"
    if n_completed > 0:
        return "Completado"
    if n_runs > 0:
        return "Completado"
    if xml_ok:
        return "Listo para ejecutar"
    return "Sin configurar"


ESTILO_ESTADO = {
    "Sin configurar": "#A6A6A6", "Listo para ejecutar": "#84CC16",
    "En ejecución": "#F5B83D", "Completado": "#46A758", "Error": "#E5484D",
    "Sin XML": "#A6A6A6", "Válido": "#46A758", "Inválido": "#E5484D",
    "Inexistente": "#E5484D", "Sin motor": "#A6A6A6", "Listo": "#46A758",
}


class LabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhysiCell Lab")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(LAB_QSS)
        self.current_experiment_id = None
        self.worker = None
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        # ---- sidebar ----
        side = QWidget()
        side.setObjectName("SideBar")
        side.setFixedWidth(212)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 18, 14, 18)
        sl.setSpacing(6)
        brand = QLabel("PhysiCell Lab")
        brand.setObjectName("Brand")
        sl.addWidget(brand)
        sub = QLabel("Simulación celular")
        sub.setObjectName("BrandSub")
        sl.addWidget(sub)
        sl.addSpacing(10)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns = {}
        self.stack = QStackedWidget()
        self._secciones = ["Resumen", "Experimentos", "Configuraciones", "Ejecuciones", "Visualización",
                           "Resultados", "Comparación", "Reportes", "Preferencias"]
        for i, name in enumerate(self._secciones):
            b = QPushButton(name)
            b.setObjectName("NavBtn")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=name: self.ir(n))
            self.nav_group.addButton(b, i)
            sl.addWidget(b)
            self.nav_btns[name] = b
        sl.addStretch()
        root.addWidget(side)
        root.addWidget(self.stack, 1)
        # ---- páginas ----
        self.pg_resumen = QWidget()
        self.pg_exps = QWidget()
        self.pg_configs = QWidget()
        self.pg_ejec = QWidget()
        self.pg_vis = QWidget()
        self.pg_res = QWidget()
        self.pg_cmp = QWidget()
        self.pg_reportes = QWidget()
        self.pg_prefs = QWidget()
        self.pg_detalle = QWidget()
        for p in [self.pg_resumen, self.pg_exps, self.pg_configs, self.pg_ejec, self.pg_vis,
                  self.pg_res, self.pg_cmp, self.pg_reportes, self.pg_prefs, self.pg_detalle]:
            self.stack.addWidget(p)
        init_database()
        self._build_resumen()
        self._build_exps()
        self._build_configs()
        self._build_ejec()
        self._build_vis()
        self._build_res()
        self._build_cmp()
        self._build_reportes()
        self._build_prefs()
        self.ir("Resumen")

    # ---------- utilidades ----------
    def ir(self, name):
        idx = {"Resumen": 0, "Experimentos": 1, "Configuraciones": 2, "Ejecuciones": 3, "Visualización": 4,
               "Resultados": 5, "Comparación": 6, "Reportes": 7, "Preferencias": 8}[name]
        self.nav_btns[name].setChecked(True)
        if name == "Resumen":
            self.refrescar_resumen()
        elif name == "Experimentos":
            self.refrescar_exps()
        elif name == "Configuraciones":
            self.refrescar_configs()
        elif name == "Ejecuciones":
            self.refrescar_ejec()
        elif name == "Resultados":
            self.refrescar_res_page()
        elif name == "Comparación":
            self.refrescar_cmp_page()
        elif name == "Reportes":
            self.refrescar_reportes()
        self.stack.setCurrentIndex(idx)

    def abrir_detalle(self, eid):
        self.current_experiment_id = eid
        self._build_detalle()
        self.stack.setCurrentIndex(self.stack.indexOf(self.pg_detalle))
        for b in self.nav_btns.values():
            b.setChecked(False)
        self.nav_btns["Experimentos"].setChecked(True)

    def _kpis(self):
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT id, config_xml_path FROM experiments")
        exps = cur.fetchall()
        total = len(exps)
        cfg_ok = 0
        for _, c in exps:
            if c and os.path.isfile(c):
                try:
                    if validar_config(c).get("ok"):
                        cfg_ok += 1
                except Exception:
                    pass
        try:
            cur.execute("SELECT status, COUNT(*) FROM runs GROUP BY status")
            st = dict(cur.fetchall())
        except Exception:
            st = {}
        conn.close()
        comp = st.get("completed", 0)
        curso = st.get("running", 0)
        fallo = st.get("failed", 0) + st.get("cancelled", 0)
        return total, cfg_ok, comp, curso, fallo

    def _runs_exp(self, eid):
        conn = sqlite3.connect(get_db_path())
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        return rows

    # ---------- Resumen ----------
    def _build_resumen(self):
        lay = QVBoxLayout(self.pg_resumen)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(12)
        top = QHBoxLayout()
        t = QVBoxLayout()
        h = QLabel("Mis experimentos")
        h.setObjectName("H1")
        d = QLabel("Gestión y análisis de experimentos de simulación celular")
        d.setObjectName("Muted")
        t.addWidget(h)
        t.addWidget(d)
        top.addLayout(t, 1)
        self.res_search = QLineEdit()
        self.res_search.setPlaceholderText("Buscar experimentos...")
        self.res_search.setFixedWidth(260)
        self.res_search.textChanged.connect(lambda _: self.refrescar_resumen())
        top.addWidget(self.res_search)
        b = QPushButton("+ Nuevo experimento")
        b.setObjectName("Primary")
        b.clicked.connect(self._nuevo_desde_resumen)
        top.addWidget(b)
        lay.addLayout(top)
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(12)
        lay.addLayout(self.kpi_row)
        h2 = QLabel("Recientes")
        h2.setObjectName("H2")
        lay.addWidget(h2)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.res_recent = QWidget()
        self.res_grid = QGridLayout(self.res_recent)
        self.res_grid.setSpacing(12)
        scroll.setWidget(self.res_recent)
        lay.addWidget(scroll, 1)

    def _kpi_card(self, num, lbl):
        f = QFrame()
        f.setObjectName("Card")
        v = QVBoxLayout(f)
        n = QLabel(str(num))
        n.setObjectName("KpiNum")
        l = QLabel(lbl)
        l.setObjectName("KpiLbl")
        v.addWidget(n)
        v.addWidget(l)
        return f

    def refrescar_resumen(self):
        for i in reversed(range(self.kpi_row.count())):
            w = self.kpi_row.itemAt(i).widget()
            if w:
                w.deleteLater()
        total, cfg_ok, comp, curso, fallo = self._kpis()
        for n, l in [(total, "Total experimentos"), (cfg_ok, "Configurados"), (comp, "Ejecuciones completadas"), (f"{curso}/{fallo}", "En curso / fallidas")]:
            self.kpi_row.addWidget(self._kpi_card(n, l))
        for i in reversed(range(self.res_grid.count())):
            w = self.res_grid.itemAt(i).widget()
            if w:
                w.deleteLater()
        q = (self.res_search.text() or "").lower().strip() if hasattr(self, "res_search") else ""
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title, description, tags, config_xml_path, last_modified FROM experiments ORDER BY id DESC LIMIT 12")
            rows = cur.fetchall()
        except Exception:
            cur.execute("SELECT id, title, description FROM experiments ORDER BY id DESC LIMIT 12")
            rows = [(a, b, c, "", "", None) for a, b, c in cur.fetchall()]
        counts = {}
        try:
            cur.execute("SELECT experiment_id, COUNT(*) FROM runs GROUP BY experiment_id")
            counts = dict(cur.fetchall())
        except Exception:
            pass
        conn.close()
        col = row = 0
        mostrados = 0
        for r in rows:
            eid, title, desc = r[0], r[1], r[2]
            tags = r[3] if len(r) > 3 else ""
            cfg = r[4] if len(r) > 4 else ""
            modif = r[5] if len(r) > 5 else None
            if q and q not in f"{title} {desc} {tags}".lower():
                continue
            runs = counts.get(eid, 0)
            xe, _ = xml_estado(cfg)
            card = self._exp_card(eid, title, desc, tags, modif, xe, runs)
            self.res_grid.addWidget(card, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
            mostrados += 1
        if mostrados == 0:
            l = QLabel("Sin experimentos. Usa «+ Nuevo experimento» para empezar.")
            l.setObjectName("Muted")
            self.res_grid.addWidget(l, 0, 0)

    def _exp_card(self, eid, title, desc, tags, modif, xe, runs):
        f = QFrame()
        f.setObjectName("Card")
        f.setMinimumWidth(280)
        f.setMaximumWidth(360)
        v = QVBoxLayout(f)
        v.setSpacing(4)
        t = QLabel(title or f"Experimento {eid}")
        t.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t.setWordWrap(True)
        v.addWidget(t)
        d = QLabel((desc or "Sin descripción")[:140])
        d.setObjectName("Muted")
        d.setWordWrap(True)
        v.addWidget(d)
        m = QLabel(f"{tags or 'sin etiquetas'}  •  {runs} runs  •  XML: {xe}" + (f"  •  {modif}" if modif else ""))
        m.setObjectName("Muted")
        m.setWordWrap(True)
        v.addWidget(m)
        row = QHBoxLayout()
        b1 = QPushButton("Abrir")
        b1.setObjectName("Primary")
        b1.clicked.connect(lambda _=False, e=eid: self.abrir_detalle(e))
        b2 = QPushButton("⋯")
        b2.setObjectName("Secondary")
        b2.setFixedWidth(40)
        b2.setToolTip("Editar / Eliminar")
        b2.clicked.connect(lambda _=False, e=eid: self._acciones_exp(e))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch()
        w = QWidget()
        w.setLayout(row)
        v.addWidget(w)
        return f

    def _acciones_exp(self, eid):
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("Editar datos", lambda: self._editar_meta(eid))
        m.addAction("Eliminar", lambda: self._eliminar_exp(eid))
        m.exec(self.cursor().pos())

    def _editar_meta(self, eid):
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT title, description, tags FROM experiments WHERE id=?", (eid,))
        t, d, g = cur.fetchone() or ("", "", "")
        conn.close()
        dlg = QDialog(self)
        dlg.setWindowTitle("Editar experimento")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        e1, e2, e3 = QLineEdit(t), QLineEdit(d or ""), QLineEdit(g or "")
        form.addRow("Título:", e1)
        form.addRow("Descripción:", e2)
        form.addRow("Etiquetas:", e3)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            conn = sqlite3.connect(get_db_path())
            SIM.actualizar_experimento(conn, eid, e1.text().strip() or t, e2.text().strip(), e3.text().strip())
            conn.close()
            self.refrescar_resumen()
            self.refrescar_exps()

    def _eliminar_exp(self, eid):
        r = QMessageBox.question(self, "Eliminar", "Borra experimento, runs y escenarios. ¿Continuar?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        conn = sqlite3.connect(get_db_path())
        SIM.eliminar_experimento(conn, eid)
        conn.close()
        if self.current_experiment_id == eid:
            self.current_experiment_id = None
        self.refrescar_resumen()
        self.refrescar_exps()

    def _nuevo_desde_resumen(self):
        self.ir("Experimentos")
        self._nuevo_exp()

    # ---------- Experimentos ----------
    def _build_exps(self):
        lay = QVBoxLayout(self.pg_exps)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(10)
        top = QHBoxLayout()
        h = QLabel("Experimentos")
        h.setObjectName("H1")
        top.addWidget(h)
        top.addStretch()
        self.exp_search = QLineEdit()
        self.exp_search.setPlaceholderText("Buscar por título, descripción o etiquetas...")
        self.exp_search.setFixedWidth(300)
        self.exp_search.textChanged.connect(lambda _: self.refrescar_exps())
        top.addWidget(self.exp_search)
        b = QPushButton("+ Nuevo experimento")
        b.setObjectName("Primary")
        b.clicked.connect(self._nuevo_exp)
        top.addWidget(b)
        lay.addLayout(top)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.exps_wrap = QWidget()
        self.exps_grid = QGridLayout(self.exps_wrap)
        self.exps_grid.setSpacing(12)
        scroll.setWidget(self.exps_wrap)
        lay.addWidget(scroll, 1)

    def _nuevo_exp(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo experimento")
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        t1, t2, t3 = QLineEdit(), QLineEdit(), QLineEdit()
        t1.setPlaceholderText("Ej: Tumor + inmune, O2 bajo")
        t2.setPlaceholderText("Objetivo e hipótesis del ensayo")
        t3.setPlaceholderText("Ej: cancer, o2-bajo (coma)")
        form.addRow("Título:", t1)
        form.addRow("Descripción:", t2)
        form.addRow("Etiquetas:", t3)
        lay.addLayout(form)
        hint = QLabel("Podrás asignar el XML en la pestaña Configuración del detalle.")
        hint.setObjectName("Muted")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if not dlg.exec():
            return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM experiments")
        nid = ((cur.fetchone()[0] or 0) + 1)
        cur.execute("INSERT INTO experiments (id, title, description, tags, config_xml_path) VALUES (?,?,?,?,?)",
                    (nid, t1.text().strip() or f"Experimento {nid}", t2.text().strip(), t3.text().strip(), ""))
        conn.commit()
        conn.close()
        self.refrescar_exps()
        self.refrescar_resumen()
        self.abrir_detalle(nid)

    def refrescar_exps(self):
        for i in reversed(range(self.exps_grid.count())):
            w = self.exps_grid.itemAt(i).widget()
            if w:
                w.deleteLater()
        q = (self.exp_search.text() or "").lower().strip() if hasattr(self, "exp_search") else ""
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title, description, tags, config_xml_path FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        counts = {}
        try:
            cur.execute("SELECT experiment_id, COUNT(*) FROM runs GROUP BY experiment_id")
            counts = dict(cur.fetchall())
        except Exception:
            pass
        conn.close()
        col = row = 0
        for eid, title, desc, tags, cfg in rows:
            if q and q not in f"{title} {desc} {tags}".lower():
                continue
            xe, _ = xml_estado(cfg)
            self.exps_grid.addWidget(self._exp_card(eid, title, desc, tags, None, xe, counts.get(eid, 0)), row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

    # ---------- Detalle con pestañas ----------
    def _build_detalle(self):
        if self.pg_detalle.layout() is None:
            self.pg_detalle.setLayout(QVBoxLayout())
        lay = self.pg_detalle.layout()
        while lay.count():
            w = lay.takeAt(0).widget()
            if w:
                w.deleteLater()
        lay.setContentsMargins(22, 16, 22, 16)
        lay.setSpacing(8)
        eid = self.current_experiment_id
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT title, description, tags, config_xml_path, created_at, last_modified FROM experiments WHERE id=?", (eid,))
        r = cur.fetchone() or ("", "", "", "", None, None)
        conn.close()
        title, desc, tags, cfg, creado, modif = r
        runs = self._runs_exp(eid)
        conn2 = sqlite3.connect(get_db_path())
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
        st = QLabel(f"<b style='color:{col}'>● {estado}</b> &nbsp; <span style='color:#A6A6A6'>{tags or 'sin etiquetas'} • {n_esc} escenarios • {len(runs)} runs</span>")
        st.setTextFormat(Qt.TextFormat.RichText)
        left.addWidget(st)
        head.addLayout(left, 1)
        bback = QPushButton("← Volver")
        bback.setObjectName("Secondary")
        bback.clicked.connect(lambda: self.ir("Experimentos"))
        head.addWidget(bback)
        lay.addLayout(head)
        tabs = QTabWidget()
        lay.addWidget(tabs, 1)
        self.det_tabs = tabs
        tabs.addTab(self._tab_resumen(eid, title, desc, tags, cfg, creado, modif, runs, n_esc, estado, col), "Resumen")
        tabs.addTab(self._tab_config(eid, cfg), "Configuración")
        tabs.addTab(self._tab_ejecucion(eid, cfg), "Ejecuciones")
        tabs.addTab(self._tab_vis(eid), "Visualización 2D/3D")
        tabs.addTab(self._tab_resultados(eid), "Resultados")
        tabs.addTab(self._tab_comparacion(eid), "Comparación")
        tabs.addTab(self._tab_reportes(eid), "Reportes")
        self._res_cargar_reps()

    def _file_row(self, label, edit, browse_fn):
        w = QWidget()
        h = QHBoxLayout(w)
        h.setContentsMargins(0, 0, 0, 0)
        l = QLabel(label)
        l.setFixedWidth(170)
        h.addWidget(l)
        h.addWidget(edit, 1)
        b = QPushButton("...")
        b.setObjectName("Secondary")
        b.setFixedWidth(44)
        b.clicked.connect(browse_fn)
        h.addWidget(b)
        return w

    def _tab_config(self, eid, cfg):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)
        self.cfg_xml = QLineEdit(cfg or "")
        self.cfg_xml.setPlaceholderText(".../PhysiCell_settings.xml — plantilla de réplicas")
        v.addWidget(self._file_row("XML del experimento:", self.cfg_xml, self._browse_cfg_detalle))
        self.cfg_exe = QLineEdit(getattr(self, "_last_exe", ""))
        self.cfg_exe.setPlaceholderText(".../project.exe — motor PhysiCell compilado")
        v.addWidget(self._file_row("Motor PhysiCell:", self.cfg_exe, self._browse_exe_detalle))
        row = QHBoxLayout()
        row.addWidget(QLabel("Réplicas por ejecución:"))
        self.cfg_reps = QSpinBox()
        self.cfg_reps.setRange(1, 50)
        self.cfg_reps.setValue(3)
        row.addWidget(self.cfg_reps)
        row.addStretch()
        c = QWidget()
        c.setLayout(row)
        v.addWidget(c)
        self.cfg_out = QLabel(f"Salida: {os.path.join(os.path.dirname(get_db_path()), f'exp_{eid}')}")
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
        c2 = QWidget()
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
        cv = QWidget()
        cv.setLayout(vrow)
        v.addWidget(cv)
        v.addStretch()
        self._validar_detalle(silencioso=True)
        return w

    def _crear_variante(self, eid):
        from .simulador import crear_escenario
        from .xml_validator import validar_config as vc
        cfg = self.cfg_xml.text().strip() if hasattr(self, "cfg_xml") else ""
        if not vc(cfg).get("ok"):
            QMessageBox.warning(self, "Variante", "El XML del experimento no es válido.")
            return
        nom = self.var_nombre.text().strip() or "variante-1"
        conn = sqlite3.connect(get_db_path())
        crear_escenario(conn, eid, nom, cfg, "{}")
        conn.close()
        QMessageBox.information(self, "Variante", f"Escenario '{nom}' creado. Adminístralo en la pestaña Ejecuciones.")

    def _browse_cfg_detalle(self):
        f, _ = QFileDialog.getOpenFileName(self, "XML del experimento", "", "XML (*.xml)")
        if f:
            self.cfg_xml.setText(f)
            self._validar_detalle(silencioso=True)

    def _browse_exe_detalle(self):
        f, _ = QFileDialog.getOpenFileName(self, "Motor PhysiCell", "", "Ejecutable (*.exe);;Todos (*)")
        if f:
            self.cfg_exe.setText(f)
            self._last_exe = f
            self._validar_detalle(silencioso=True)

    def _validar_detalle(self, silencioso=False):
        xe, _ = xml_estado(self.cfg_xml.text().strip())
        ee, _ = exe_estado(self.cfg_exe.text().strip())
        self.cfg_estado.setText(f"XML: {xe}   •   Motor: {ee}")
        if not silencioso:
            QMessageBox.information(self, "Validación", f"XML: {xe}\nMotor: {ee}")

    def _guardar_cfg_detalle(self):
        from .xml_validator import validar_config as vc
        p = self.cfg_xml.text().strip()
        if p:
            v = vc(p)
            if not v.get("ok"):
                QMessageBox.warning(self, "Guardar", "XML inválido: " + "; ".join(v.get("errores", [])))
                return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("UPDATE experiments SET config_xml_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?", (p, self.current_experiment_id))
        conn.commit()
        conn.close()
        self._last_exe = self.cfg_exe.text().strip()
        QMessageBox.information(self, "Configuración", "Guardada en este experimento.")
        self._build_detalle()

    def _editar_xml_detalle(self):
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit, QDialogButtonBox
        from .config_manager import leer_texto, guardar_texto
        p = self.cfg_xml.text().strip()
        if not p or not os.path.isfile(p):
            QMessageBox.warning(self, "Editar", "Selecciona un XML existente primero.")
            return
        try:
            txt = leer_texto(p)
        except Exception as e:
            QMessageBox.warning(self, "Editar", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Editar XML")
        dlg.resize(720, 520)
        lay = QVBoxLayout(dlg)
        ed = QPlainTextEdit()
        ed.setPlainText(txt)
        lay.addWidget(ed)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            r = guardar_texto(p, ed.toPlainText())
            if r.get("ok"):
                QMessageBox.information(self, "Editar", "XML guardado.")
            else:
                QMessageBox.warning(self, "Editar", r.get("error", "Error"))

    def _tab_resumen(self, eid, title, desc, tags, cfg, creado, modif, runs, n_esc, estado, col):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(8)
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
        for lbl, idx in accesos:
            b = QPushButton(lbl)
            b.setObjectName("Secondary")
            b.clicked.connect(lambda _=False, i=idx: self.det_tabs.setCurrentIndex(i))
            grid.addWidget(b, 0, accesos.index((lbl, idx)))
        cw = QWidget()
        cw.setLayout(grid)
        v.addWidget(cw)
        v.addStretch()
        return w

    def _tab_ejecucion(self, eid, cfg):
        from .simulador import listar_escenarios, eliminar_escenario
        w = QWidget()
        v = QVBoxLayout(w)
        v.addWidget(QLabel("<b>Escenarios del experimento</b>"))
        conn_e = sqlite3.connect(get_db_path())
        escs = list(listar_escenarios(conn_e, eid))
        conn_e.close()
        if not escs:
            l = QLabel("Sin escenarios. Créalos como variantes en la pestaña Configuración.")
            l.setObjectName("Muted")
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
                conn = sqlite3.connect(get_db_path())
                eliminar_escenario(conn, s)
                conn.close()
                self._build_detalle()
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
        c = QWidget()
        c.setLayout(row)
        v.addWidget(c)
        self.run_prog = QProgressBar()
        self.run_prog.setRange(0, 100)
        v.addWidget(self.run_prog)
        self.run_log = QTextEdit()
        self.run_log.setReadOnly(True)
        self.run_log.setMaximumHeight(180)
        v.addWidget(self.run_log)
        v.addStretch()
        return w

    def _ejecutar(self):
        eid = self.current_experiment_id
        base = self.cfg_xml.text().strip() if hasattr(self, "cfg_xml") else ""
        if not base:
            QMessageBox.warning(self, "Ejecución", "Asigna el XML en la pestaña Configuración.")
            return
        from .xml_validator import validar_config as vc
        if not vc(base).get("ok"):
            QMessageBox.warning(self, "Ejecución", "El XML del experimento no es válido.")
            return
        n = self.run_reps.value()
        exe = self.cfg_exe.text().strip() if hasattr(self, "cfg_exe") else ""
        self._last_exe = exe
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.run_log.append(f"Iniciando {n} réplicas con PhysiCell...")
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
        self._build_detalle()

    def _run_fail(self, msg):
        self.run_log.append(f"Detenido/error: {msg}")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _detener(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            if hasattr(self, "run_log"):
                self.run_log.append("Solicitando detención del proceso PhysiCell...")

    def _tab_vis(self, eid):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(6)
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
        c = QWidget()
        c.setLayout(top)
        v.addWidget(c)
        self.visor = VisorPhysiCell(output_dir="")
        v.addWidget(self.visor, 1)
        self.vis_mode.currentTextChanged.connect(self._vis_modo)
        self._vis_cargar()
        return w

    def _abrir_vtk_detalle(self):
        from .visor3d_vtk import abrir_vtk
        d = ""
        try:
            outs = self.vis_rep.property("outs") or []
            i = self.vis_rep.currentIndex()
            if 0 <= i < len(outs):
                d = outs[i]
        except Exception:
            pass
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT title FROM experiments WHERE id=?", (self.current_experiment_id,))
        r = cur.fetchone()
        conn.close()
        abrir_vtk(self, d or "", titulo=f"Tumor 3D — {(r[0] if r else '') or self.current_experiment_id}")

    def _salidas_replicas(self, eid):
        conn = sqlite3.connect(get_db_path())
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        outs = []
        for _id, rnum, st, _s, _e, od in rows:
            if od and os.path.isdir(od):
                import glob as _g
                cands = [os.path.join(od, "output"), od]
                for d in cands:
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
                self.visor.ax2.set_visible(True)
                self.visor.ax3.set_visible(False)
            elif modo == "3D":
                self.visor.ax2.set_visible(False)
                self.visor.ax3.set_visible(True)
            else:
                self.visor.ax2.set_visible(True)
                self.visor.ax3.set_visible(True)
            self.visor.canvas.draw()
        except Exception:
            pass

    def _tab_resultados(self, eid):
        from .visualizador import resumen_resultados
        w = QWidget()
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
        t.setMaximumHeight(180)
        v.addWidget(t)
        # explorador por réplica con integridad
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
        ec = QWidget()
        ec.setLayout(erow)
        v.addWidget(ec)
        self.res_files = QTableWidget()
        self.res_files.setColumnCount(2)
        self.res_files.setHorizontalHeaderLabels(["Archivo", "Tamaño"])
        self.res_files.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.res_files.setMaximumHeight(150)
        v.addWidget(self.res_files)
        self.res_temp_img = QLabel("Sin gráfica temporal.")
        self.res_temp_img.setObjectName("Muted")
        self.res_temp_img.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.addWidget(self.res_temp_img)
        self.res_log = QTextEdit()
        self.res_log.setReadOnly(True)
        self.res_log.setMaximumHeight(110)
        v.addWidget(self.res_log)
        row = QHBoxLayout()
        for lbl, fn in [("Resumen", self._res_resumen), ("CSV", self._res_csv), ("JSON", self._res_json), ("Temporal", self._res_temporal), ("Consolidar", self._res_consolidar), ("Limpiar", self._res_limpiar)]:
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
        c = QWidget()
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
        from .visualizador import verificar_integridad, listar_archivos
        d = self._res_rep_dir()
        # tabla de archivos
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
            self.res_log.append(f"Integridad OK en {d}: svg={v['n_svg']} xml={v['n_xml']} mats={v['n_cells_mat']} grafos={v['n_grafos']}")
        else:
            self.res_log.append(f"Integridad INCOMPLETA en {d}: falta {', '.join(v['faltan'])} (svg={v['n_svg']} xml={v['n_xml']} mats={v['n_cells_mat']} grafos={v['n_grafos']})")

    def _res_abrir_vis(self):
        d = self._res_rep_dir()
        if not d or not os.path.isdir(d):
            QMessageBox.warning(self, "Resultados", "La réplica no tiene carpeta de salida.")
            return
        self.det_tabs.setCurrentIndex(3)
        try:
            self.visor.set_output_dir(d if os.path.isfile(os.path.join(d, "initial.xml")) else os.path.join(d, "output"))
        except Exception as e:
            self.res_log.append(f"No se pudo abrir en visor: {e}")

    def _exp_dir(self):
        import os as _o
        return _o.path.join(_o.path.dirname(get_db_path()), f"exp_{self.current_experiment_id}")

    def _res_resumen(self):
        from .visualizador import resumen_resultados
        r = resumen_resultados(self._exp_dir())
        self.res_log.append(f"SVG:{r.get('n_svg', 0)} XML:{r.get('n_xml', 0)} MAT:{r.get('n_mat', 0)}")

    def _res_csv(self):
        from .reportes import exportar_runs_csv
        r = exportar_runs_csv(self.current_experiment_id, get_db_path(), self._exp_dir() + "/runs.csv")
        self.res_log.append(f"CSV: {r}")

    def _res_json(self):
        from .reportes import exportar_runs_json
        r = exportar_runs_json(self.current_experiment_id, get_db_path(), self._exp_dir() + "/runs.json")
        self.res_log.append(f"JSON: {r}")

    def _res_informe(self):
        from .reportes import generar_reporte_html
        r = generar_reporte_html(self.current_experiment_id, get_db_path(), self._exp_dir() + "/reporte.html")
        self.res_log.append(f"Informe: {r}")
        if r.get("ok"):
            QMessageBox.information(self, "Informe", f"Generado: {r['path']}")

    def _res_pdf(self):
        from .reportes import generar_reporte_html, exportar_reporte_pdf
        import os as _o
        html = _o.path.join(self._exp_dir(), "reporte.html")
        generar_reporte_html(self.current_experiment_id, get_db_path(), html)
        pdf = _o.path.join(self._exp_dir(), "reporte.pdf")
        r = exportar_reporte_pdf(html, pdf)
        self.res_log.append(f"PDF: {r}")
        if r.get("ok"):
            QMessageBox.information(self, "PDF", f"Generado: {r['path']}")
        else:
            QMessageBox.warning(self, "PDF", r.get("error", "Error"))

    def _res_temporal(self):
        from .comparacion import generar_grafica_temporal
        import os as _o
        d = self._res_rep_dir()
        out = _o.path.join(self._exp_dir(), "temporal.png")
        r = generar_grafica_temporal(d, out)
        self.res_log.append(f"Temporal: {r}")
        if r.get("ok"):
            self.res_temp_img.setPixmap(QPixmap(out).scaledToWidth(620, Qt.TransformationMode.SmoothTransformation))
        else:
            QMessageBox.warning(self, "Temporal", r.get("error", "Error"))

    def _res_limpiar(self):
        import os as _o
        runs = self._runs_exp(self.current_experiment_id)
        marcados = 0
        conn = sqlite3.connect(get_db_path())
        for _id, _rn, st, _s, _e, od in runs:
            if st in ("running", "pending", "registered") and (not od or not _o.path.isdir(od)):
                SIM.actualizar_run(conn, _id, "failed", end=True)
                marcados += 1
        conn.close()
        self.res_log.append(f"Limpieza: {marcados} runs sin salida marcados como failed")
        self._build_detalle()

    def _res_consolidar(self):
        from .agregador import agregar_experimento
        from PyQt6.QtWidgets import QProgressDialog
        from PyQt6.QtCore import Qt
        dlg = QProgressDialog("Consolidando réplicas...", "Cancelar", 0, 100, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        dlg.setValue(10)
        QApplication.processEvents()
        try:
            r = agregar_experimento(get_db_path(), self.current_experiment_id, self._exp_dir())
        finally:
            dlg.setValue(100)
            dlg.close()
        self.res_log.append(f"Consolidado: {r}")
        if r.get("ok"):
            QMessageBox.information(self, "Consolidar",
                                    f"Réplicas con datos: {r['replicas']}\n{r['frames_csv']}\n{r['celulas_todas.csv']}")
        else:
            QMessageBox.warning(self, "Consolidar", r.get("error", "Error"))

    def _tab_comparacion(self, eid):
        from .visor_widget import VisorPhysiCell
        w = QWidget()
        v = QVBoxLayout(w)
        info = QLabel("Compara réplicas del experimento: vistas paralelas con navegación sincronizada y métricas. Si difieren en frames, se informa en lugar de forzar la comparación.")
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
        c = QWidget()
        c.setLayout(row)
        v.addWidget(c)
        self.cmp_warn = QLabel("")
        self.cmp_warn.setObjectName("Muted")
        self.cmp_warn.setWordWrap(True)
        v.addWidget(self.cmp_warn)
        par = QHBoxLayout()
        self.cmp_va = VisorPhysiCell()
        self.cmp_vb = VisorPhysiCell()
        self.cmp_va.setMinimumHeight(320)
        self.cmp_vb.setMinimumHeight(320)
        par.addWidget(self.cmp_va, 1)
        par.addWidget(self.cmp_vb, 1)
        cp = QWidget()
        cp.setLayout(par)
        v.addWidget(cp, 1)
        self.cmp_a.currentIndexChanged.connect(lambda _: self._cmp_cargar())
        self.cmp_b.currentIndexChanged.connect(lambda _: self._cmp_cargar())
        self.cmp_va.slider.valueChanged.connect(lambda _: self._cmp_sync_de_a())
        self.cmp_vb.slider.valueChanged.connect(lambda _: self._cmp_sync_de_b())
        self.cmp_log = QTextEdit()
        self.cmp_log.setReadOnly(True)
        self.cmp_log.setMaximumHeight(110)
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
            self.cmp_warn.setText(f"Aviso: réplicas con distinto número de frames (A={na}, B={nb}). La sincronización se limita al total de cada una.")
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
        from .comparacion import generar_grafica_comparacion
        out = self._exp_dir() + "/comparacion.png"
        r = generar_grafica_comparacion(get_db_path(), self.current_experiment_id, out)
        self.cmp_log.append(f"Gráfica: {r['path']} runs={len(r['filas'])} sin_datos={r['sin_datos']}")
        for f in r["filas"]:
            self.cmp_log.append(f"run {f['run']}: {f['status']} n_final={f['n_final']}")
        if os.path.isfile(out):
            self.cmp_img.setPixmap(QPixmap(out).scaledToWidth(640, Qt.TransformationMode.SmoothTransformation))

    def _tab_reportes(self, eid):
        from .reportes import generar_reporte_html, exportar_reporte_pdf, exportar_runs_csv, exportar_runs_json
        w = QWidget()
        v = QVBoxLayout(w)
        info = QLabel("Trazabilidad: qué configuración produjo cada ejecución y qué resultados pertenecen a ella.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        v.addWidget(info)
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT title, config_xml_path, created_at FROM experiments WHERE id=?", (eid,))
        t, cfg, creado = cur.fetchone() or ("", "", None)
        cur.execute("SELECT COUNT(*) FROM escenarios WHERE experiment_id=?", (eid,))
        n_esc = cur.fetchone()[0]
        cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (eid,))
        runs = cur.fetchall()
        conn.close()
        traza = QLabel(f"<b>{t}</b> (#{eid})<br>Config: {cfg or '—'}<br>Creado: {creado or '—'}<br>"
                       f"Escenarios: {n_esc} &nbsp; Ejecuciones: {len(runs)}")
        traza.setWordWrap(True)
        v.addWidget(traza)
        t2 = QTableWidget()
        t2.setColumnCount(4)
        t2.setHorizontalHeaderLabels(["Run", "Estado", "Periodo", "Salida"])
        t2.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        t2.setRowCount(len(runs))
        for i, (rn, st, s0, s1, od) in enumerate(runs):
            t2.setItem(i, 0, QTableWidgetItem(str(rn)))
            t2.setItem(i, 1, QTableWidgetItem(st))
            t2.setItem(i, 2, QTableWidgetItem(f"{s0 or ''} → {s1 or ''}"))
            t2.setItem(i, 3, QTableWidgetItem(od or ""))
        t2.setMaximumHeight(200)
        v.addWidget(t2)
        self.rep_log = QTextEdit()
        self.rep_log.setReadOnly(True)
        self.rep_log.setMaximumHeight(110)
        v.addWidget(self.rep_log)
        row = QHBoxLayout()
        for lbl in ("Informe HTML", "PDF", "CSV", "JSON"):
            b = QPushButton(lbl)
            b.setObjectName("Primary" if lbl == "Informe HTML" else "Secondary")
            b.clicked.connect(lambda _=False, k=lbl: self._rep_exportar(k))
            row.addWidget(b)
        row.addStretch()
        c = QWidget()
        c.setLayout(row)
        v.addWidget(c)
        v.addStretch()
        return w

    def _rep_exportar(self, kind):
        from .reportes import generar_reporte_html, exportar_reporte_pdf, exportar_runs_csv, exportar_runs_json
        import os as _o
        base = self._exp_dir()
        if kind == "Informe HTML":
            r = generar_reporte_html(self.current_experiment_id, get_db_path(), _o.path.join(base, "reporte.html"))
        elif kind == "PDF":
            html = _o.path.join(base, "reporte.html")
            generar_reporte_html(self.current_experiment_id, get_db_path(), html)
            r = exportar_reporte_pdf(html, _o.path.join(base, "reporte.pdf"))
        elif kind == "CSV":
            r = exportar_runs_csv(self.current_experiment_id, get_db_path(), _o.path.join(base, "runs.csv"))
        else:
            r = exportar_runs_json(self.current_experiment_id, get_db_path(), _o.path.join(base, "runs.json"))
        self.rep_log.append(f"{kind}: {r}")
        if r.get("ok"):
            QMessageBox.information(self, "Reportes", f"Generado: {r.get('path')}")
        else:
            QMessageBox.warning(self, "Reportes", r.get("error", "Error"))

    # ---------- Ejecuciones ----------
    def _build_ejec(self):
        lay = QVBoxLayout(self.pg_ejec)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("Ejecuciones")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel("Historial de réplicas de todos los experimentos, con estado y salida.")
        d.setObjectName("Muted")
        lay.addWidget(d)
        self.ejec_table = QTableWidget()
        self.ejec_table.setColumnCount(6)
        self.ejec_table.setHorizontalHeaderLabels(["Experimento", "Run", "Estado", "Inicio", "Fin", "Salida"])
        self.ejec_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.ejec_table, 1)

    def refrescar_ejec(self):
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT e.title, r.run_number, r.status, r.start_time, r.end_time, r.output_dir FROM runs r JOIN experiments e ON e.id=r.experiment_id ORDER BY r.start_time DESC LIMIT 200")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.ejec_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate([str(x or "") for x in r]):
                self.ejec_table.setItem(i, j, QTableWidgetItem(val))

    # ---------- Visualización global ----------
    def _build_vis(self):
        lay = QVBoxLayout(self.pg_vis)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)
        h = QLabel("Visualización")
        h.setObjectName("H1")
        lay.addWidget(h)
        top = QHBoxLayout()
        self.g_exp = QComboBox()
        self.g_rep = QComboBox()
        self.g_mode = QComboBox()
        self.g_mode.addItems(["Ambos", "2D", "3D"])
        b = QPushButton("Cargar")
        b.setObjectName("Primary")
        b.clicked.connect(self._g_cargar)
        top.addWidget(QLabel("Experimento:"))
        top.addWidget(self.g_exp, 1)
        top.addWidget(QLabel("Réplica:"))
        top.addWidget(self.g_rep, 1)
        top.addWidget(QLabel("Vista:"))
        top.addWidget(self.g_mode)
        top.addWidget(b)
        c = QWidget()
        c.setLayout(top)
        lay.addWidget(c)
        self.g_visor = VisorPhysiCell(output_dir="")
        lay.addWidget(self.g_visor, 1)
        self.g_mode.currentTextChanged.connect(self._g_modo)
        self.g_exp.currentIndexChanged.connect(lambda _: self._g_reps())
        self._g_exps()

    def _g_exps(self):
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.g_exp.clear()
        for eid, t in rows:
            self.g_exp.addItem(f"#{eid} {t}", eid)
        self._g_reps()

    def _g_reps(self):
        eid = self.g_exp.currentData()
        self.g_rep.clear()
        if eid is None:
            return
        for lbl, d in self._salidas_replicas_global(eid):
            self.g_rep.addItem(lbl, d)

    def _salidas_replicas(self, eid):
        return self._salidas_replicas_global(eid)

    def _salidas_replicas_global(self, eid):
        conn = sqlite3.connect(get_db_path())
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        outs = []
        for _id, rnum, st, _s, _e, od in rows:
            if od and os.path.isdir(od):
                import glob as _g
                for d in (os.path.join(od, "output"), od):
                    if _g.glob(os.path.join(d, "snapshot*.svg")) or _g.glob(os.path.join(d, "*_cells.mat")):
                        outs.append((f"Réplica {rnum} ({st})", d))
                        break
        outs.append(("Salida global PhysiCell/output", ""))
        return outs

    def _g_cargar(self):
        d = self.g_rep.currentData()
        if d:
            self.g_visor.set_output_dir(d)

    def _g_modo(self, modo):
        try:
            if modo == "2D":
                self.g_visor.ax2.set_visible(True)
                self.g_visor.ax3.set_visible(False)
            elif modo == "3D":
                self.g_visor.ax2.set_visible(False)
                self.g_visor.ax3.set_visible(True)
            else:
                self.g_visor.ax2.set_visible(True)
                self.g_visor.ax3.set_visible(True)
            self.g_visor.canvas.draw()
        except Exception:
            pass

    # ---------- Resultados global ----------
    def _build_res(self):
        lay = QVBoxLayout(self.pg_res)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("Resultados")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel("Selecciona un experimento para ver métricas, archivos y exportaciones. El detalle por experimento está en Experimentos → Abrir → Resultados.")
        d.setObjectName("Muted")
        d.setWordWrap(True)
        lay.addWidget(d)
        self.res_exp = QComboBox()
        lay.addWidget(self.res_exp)
        b = QPushButton("Abrir resultados del experimento")
        b.setObjectName("Primary")
        b.clicked.connect(lambda: self.abrir_detalle(self.res_exp.currentData()) if self.res_exp.currentData() else None)
        lay.addWidget(b)
        lay.addStretch()
        self.refrescar_res_page()

    def refrescar_res_page(self):
        if not hasattr(self, "res_exp"):
            return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.res_exp.clear()
        for eid, t in rows:
            self.res_exp.addItem(f"#{eid} {t}", eid)

    # ---------- Comparación global ----------
    def _build_cmp(self):
        lay = QVBoxLayout(self.pg_cmp)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("Comparación")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel("Compara réplicas dentro de un experimento. Abre el detalle para la gráfica dedicada.")
        d.setObjectName("Muted")
        lay.addWidget(d)
        self.cmp_exp = QComboBox()
        lay.addWidget(self.cmp_exp)
        b = QPushButton("Abrir comparación del experimento")
        b.setObjectName("Primary")
        b.clicked.connect(lambda: self.abrir_detalle(self.cmp_exp.currentData()) if self.cmp_exp.currentData() else None)
        lay.addWidget(b)
        lay.addStretch()
        self.refrescar_cmp_page()

    def refrescar_cmp_page(self):
        if not hasattr(self, "cmp_exp"):
            return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.cmp_exp.clear()
        for eid, t in rows:
            self.cmp_exp.addItem(f"#{eid} {t}", eid)

    # ---------- Configuración ----------
    # ---------- Configuraciones (biblioteca XML) ----------
    def _build_configs(self):
        lay = QVBoxLayout(self.pg_configs)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)
        h = QLabel("Configuraciones")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel("Biblioteca de XML de PhysiCell: importa, edita y valida sin listas rígidas de parámetros. Asocia un XML a un experimento o escenario.")
        d.setObjectName("Muted")
        d.setWordWrap(True)
        lay.addWidget(d)
        row = QHBoxLayout()
        b_imp = QPushButton("Importar XML…")
        b_imp.setObjectName("Primary")
        b_imp.clicked.connect(self._cfg_importar)
        b_new = QPushButton("Nuevo desde plantilla")
        b_new.setObjectName("Secondary")
        b_new.clicked.connect(self._cfg_nuevo)
        b_ref = QPushButton("Actualizar")
        b_ref.setObjectName("Secondary")
        b_ref.clicked.connect(self.refrescar_configs)
        row.addWidget(b_imp)
        row.addWidget(b_new)
        row.addWidget(b_ref)
        row.addStretch()
        c = QWidget()
        c.setLayout(row)
        lay.addWidget(c)
        self.cfg_table = QTableWidget()
        self.cfg_table.setColumnCount(3)
        self.cfg_table.setHorizontalHeaderLabels(["Archivo", "Estado", "Tamaño"])
        self.cfg_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.cfg_table, 1)
        row2 = QHBoxLayout()
        b_ed = QPushButton("Editar…")
        b_ed.setObjectName("Secondary")
        b_ed.clicked.connect(self._cfg_editar)
        b_val = QPushButton("Validar")
        b_val.setObjectName("Secondary")
        b_val.clicked.connect(self._cfg_validar)
        b_as = QPushButton("Asociar a experimento…")
        b_as.setObjectName("Secondary")
        b_as.clicked.connect(self._cfg_asociar)
        row2.addWidget(b_ed)
        row2.addWidget(b_val)
        row2.addWidget(b_as)
        row2.addStretch()
        c2 = QWidget()
        c2.setLayout(row2)
        lay.addWidget(c2)

    def _cfg_dir(self):
        import os as _o
        d = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "..", "config")
        _o.makedirs(d, exist_ok=True)
        return _o.path.abspath(d)

    def _cfg_sel(self):
        r = self.cfg_table.currentRow()
        if r < 0:
            return ""
        it = self.cfg_table.item(r, 0)
        return it.text() if it else ""

    def refrescar_configs(self):
        import glob as _g
        import os as _o
        files = sorted(_g.glob(_o.path.join(self._cfg_dir(), "*.xml")))
        self.cfg_table.setRowCount(len(files))
        for i, p in enumerate(files):
            xe, _ = xml_estado(p)
            try:
                sz = str(_o.path.getsize(p))
            except Exception:
                sz = "?"
            self.cfg_table.setItem(i, 0, QTableWidgetItem(p))
            self.cfg_table.setItem(i, 1, QTableWidgetItem(xe))
            self.cfg_table.setItem(i, 2, QTableWidgetItem(sz))

    def _cfg_importar(self):
        from .config_manager import importar_config
        src, _ = QFileDialog.getOpenFileName(self, "Importar XML", "", "XML (*.xml)")
        if not src:
            return
        r = importar_config(src, self._cfg_dir())
        if r.get("ok"):
            QMessageBox.information(self, "Configuraciones", f"Importado: {r['path']}")
        else:
            QMessageBox.warning(self, "Configuraciones", r.get("error", "Error"))
        self.refrescar_configs()

    def _cfg_nuevo(self):
        import shutil as _s
        import os as _o
        base = _o.path.join(r"C:\Users\PC\Downloads\gestor_physicell\gestor_physicell\PhysiCell", "config", "PhysiCell_settings.xml")
        dst = _o.path.join(self._cfg_dir(), "nueva_config.xml")
        n = 1
        while _o.path.isfile(dst):
            n += 1
            dst = _o.path.join(self._cfg_dir(), f"nueva_config_{n}.xml")
        try:
            _s.copyfile(base, dst)
        except Exception as e:
            QMessageBox.warning(self, "Configuraciones", f"No se pudo crear desde plantilla: {e}")
            return
        self.refrescar_configs()
        QMessageBox.information(self, "Configuraciones", f"Creada: {dst}")

    def _cfg_editar(self):
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit, QDialogButtonBox
        from .config_manager import leer_texto, guardar_texto
        p = self._cfg_sel()
        if not p:
            QMessageBox.warning(self, "Configuraciones", "Selecciona un archivo de la tabla.")
            return
        try:
            txt = leer_texto(p)
        except Exception as e:
            QMessageBox.warning(self, "Configuraciones", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Editar {p}")
        dlg.resize(720, 520)
        lay = QVBoxLayout(dlg)
        ed = QPlainTextEdit()
        ed.setPlainText(txt)
        lay.addWidget(ed)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            r = guardar_texto(p, ed.toPlainText())
            if not r.get("ok"):
                QMessageBox.warning(self, "Configuraciones", r.get("error", "Error"))
            self.refrescar_configs()

    def _cfg_validar(self):
        p = self._cfg_sel()
        if not p:
            QMessageBox.warning(self, "Configuraciones", "Selecciona un archivo de la tabla.")
            return
        from .xml_validator import validar_config as vc
        v = vc(p)
        if v.get("ok"):
            msg = "Válido." + (f" Avisos: {'; '.join(v.get('warnings', []))}" if v.get("warnings") else "")
            QMessageBox.information(self, "Configuraciones", msg)
        else:
            QMessageBox.warning(self, "Configuraciones", "; ".join(v.get("errores", [])))
        self.refrescar_configs()

    def _cfg_asociar(self):
        p = self._cfg_sel()
        if not p:
            QMessageBox.warning(self, "Configuraciones", "Selecciona un archivo de la tabla.")
            return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        if not rows:
            QMessageBox.warning(self, "Configuraciones", "No hay experimentos. Crea uno primero.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Asociar XML")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Asociar:\n{p}"))
        cb = QComboBox()
        for eid, t in rows:
            cb.addItem(f"#{eid} {t}", eid)
        lay.addWidget(cb)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            eid = cb.currentData()
            conn = sqlite3.connect(get_db_path())
            cur = conn.cursor()
            cur.execute("UPDATE experiments SET config_xml_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?", (p, eid))
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Configuraciones", f"Asociado al experimento #{eid}.")

    # ---------- Reportes ----------
    def _build_reportes(self):
        lay = QVBoxLayout(self.pg_reportes)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)
        h = QLabel("Reportes")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel("Informes HTML generados por experimento, con trazabilidad de configuración, réplicas y resultados.")
        d.setObjectName("Muted")
        d.setWordWrap(True)
        lay.addWidget(d)
        row = QHBoxLayout()
        self.rep_exp = QComboBox()
        b_gen = QPushButton("Generar informe")
        b_gen.setObjectName("Primary")
        b_gen.clicked.connect(self._rep_generar)
        b_open = QPushButton("Abrir carpeta")
        b_open.setObjectName("Secondary")
        b_open.clicked.connect(self._rep_abrir)
        row.addWidget(self.rep_exp, 1)
        row.addWidget(b_gen)
        row.addWidget(b_open)
        c = QWidget()
        c.setLayout(row)
        lay.addWidget(c)
        self.rep_table = QTableWidget()
        self.rep_table.setColumnCount(3)
        self.rep_table.setHorizontalHeaderLabels(["Experimento", "Informe", "Gráfica"])
        self.rep_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.rep_table, 1)
        self._rep_cargar_exps()
        self.refrescar_reportes()

    def _rep_cargar_exps(self):
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.rep_exp.clear()
        for eid, t in rows:
            self.rep_exp.addItem(f"#{eid} {t}", eid)

    def refrescar_reportes(self):
        import glob as _g
        import os as _o
        base = _o.path.dirname(get_db_path())
        reps = sorted(_g.glob(_o.path.join(base, "exp_*", "reporte.html")))
        self.rep_table.setRowCount(len(reps))
        for i, p in enumerate(reps):
            exp = _o.path.basename(_o.path.dirname(p))
            gra = _o.path.join(_o.path.dirname(p), "comparacion.png")
            self.rep_table.setItem(i, 0, QTableWidgetItem(exp))
            self.rep_table.setItem(i, 1, QTableWidgetItem(p))
            self.rep_table.setItem(i, 2, QTableWidgetItem(gra if _o.path.isfile(gra) else "—"))
        self._rep_cargar_exps()

    def _rep_generar(self):
        from .reportes import generar_reporte_html
        import os as _o
        eid = self.rep_exp.currentData()
        if not eid:
            return
        out = _o.path.join(_o.path.dirname(get_db_path()), f"exp_{eid}", "reporte.html")
        r = generar_reporte_html(eid, get_db_path(), out)
        if r.get("ok"):
            QMessageBox.information(self, "Reportes", f"Generado: {r['path']}")
        else:
            QMessageBox.warning(self, "Reportes", r.get("error", "Error"))
        self.refrescar_reportes()

    def _rep_abrir(self):
        import os as _o
        import subprocess as _sp
        base = _o.path.dirname(get_db_path())
        try:
            _sp.Popen(["explorer", base])
        except Exception as e:
            QMessageBox.warning(self, "Reportes", str(e))

    # ---------- Preferencias ----------
    def _build_prefs(self):
        lay = QVBoxLayout(self.pg_prefs)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)
        h = QLabel("Preferencias")
        h.setObjectName("H1")
        lay.addWidget(h)
        self.cfg_root = QLineEdit(r"C:\Users\PC\Downloads\gestor_physicell\gestor_physicell\PhysiCell")
        self.cfg_root.setPlaceholderText("Carpeta raíz de PhysiCell (motor externo)")
        lay.addWidget(QLabel("Raíz de PhysiCell (motor, no se modifica):"))
        lay.addWidget(self.cfg_root)
        self.cfg_bin = QLineEdit(getattr(self, "_last_exe", "") or "")
        self.cfg_bin.setPlaceholderText(".../project.exe por defecto para nuevas ejecuciones")
        lay.addWidget(QLabel("Binario por defecto:"))
        lay.addWidget(self.cfg_bin)
        info = QLabel(f"Datos por usuario: {get_db_path()}\nTema: oscuro PhysiCell Lab, coherente en tablas, formularios y gráficos.\nEl motor PhysiCell es externo. La app solo genera XML, lanza el binario y organiza salidas.")
        info.setObjectName("Muted")
        info.setWordWrap(True)
        lay.addWidget(info)
        b = QPushButton("Detectar binario en la raíz")
        b.setObjectName("Secondary")
        b.clicked.connect(self._detectar_bin)
        lay.addWidget(b)
        lay.addWidget(QLabel("Calidad:"))
        self.test_log = QTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(160)
        lay.addWidget(self.test_log)
        bt = QPushButton("Ejecutar pruebas de regresión")
        bt.setObjectName("Secondary")
        bt.setToolTip("Corre tests/test_regresion.py con datos reales y muestra el resultado")
        bt.clicked.connect(self._ejecutar_tests)
        lay.addWidget(bt)
        lay.addStretch()

    def _detectar_bin(self):
        m = MotorPhysiCell(self.cfg_root.text().strip())
        b = m.resolver_binario()
        if b:
            self.cfg_bin.setText(b)
            self._last_exe = b
            QMessageBox.information(self, "Configuración", f"Binario: {b}")
        else:
            QMessageBox.warning(self, "Configuración", "No se encontró project.exe en la raíz indicada.")

    def _ejecutar_tests(self):
        import subprocess as _sp
        import os as _o
        t = _o.path.join(_o.path.dirname(_o.path.abspath(__file__)), "..", "tests", "test_regresion.py")
        try:
            p = _sp.run([sys.executable, t], capture_output=True, text=True, timeout=300)
            out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
            self.test_log.setPlainText(out[-3000:])
            if p.returncode == 0:
                QMessageBox.information(self, "Pruebas", "Regresión OK. Ver detalle en el panel.")
            else:
                QMessageBox.warning(self, "Pruebas", "Hay fallos. Ver detalle en el panel.")
        except Exception as e:
            QMessageBox.warning(self, "Pruebas", str(e))
