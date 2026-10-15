#!/usr/bin/env python3
"""Ventana principal tipo Notion - Fase 1 MVP con DB por usuario."""

import os
import sys
import sqlite3
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QScrollArea, QFrame, QSpacerItem, QSizePolicy,
    QLineEdit, QFileDialog, QMessageBox, QSpinBox, QTextEdit, QProgressBar
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
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
            for i in range(1, self.n_replicas + 1):
                if self._stop:
                    self.fail.emit("Cancelado por usuario")
                    return
                self.prog.emit(int((i - 1) * 100 / self.n_replicas), f"Replica {i}/{self.n_replicas} preparando")
                out_xml = os.path.join(base_dir, f"replica_{i}.xml")
                generar_replica_config(self.base_xml, out_xml, seed=1000 + i)
                run_id = registrar_run(conn, self.experiment_id, i, status="running", output_dir=base_dir)
                if self.exe_path and os.path.isfile(self.exe_path):
                    r = motor.ejecutar(self.exe_path, out_xml, cwd=os.path.dirname(self.exe_path), timeout_ms=300000)
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
    conn.commit()
    conn.close()
    print(f"DB inicializada: {db_path}")
    return db_path


class CardExperiment(QFrame):
    def __init__(self, experiment_id, title="Nuevo Experimento", description="", parent=None, on_click=None):
        super().__init__(parent)
        self.experiment_id = experiment_id
        self.on_click = on_click
        self.setObjectName("CardExperiment")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumHeight(110)
        self.setMaximumHeight(150)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.desc_label = QLabel(description)
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        layout.addWidget(self.desc_label)
        layout.addStretch()

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.experiment_id)
        super().mousePressEvent(event)


class NotionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_experiment_id = None
        self.worker = None
        self.current_theme = "claro"
        self.setWindowTitle("PhysiCell Experiment Manager - MVP")
        self.setMinimumSize(900, 600)
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        self._setup_sidebar(main_layout)
        self._setup_main_area(main_layout)
        init_database()
        self._load_theme()
        self._show_welcome()

    def _setup_sidebar(self, main_layout):
        from PyQt6.QtWidgets import QComboBox
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 24)
        sidebar_layout.setSpacing(10)
        title = QLabel("PhysiCell")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        sidebar_layout.addWidget(title)
        sub = QLabel("Experiments")
        sidebar_layout.addWidget(sub)
        lbl_theme = QLabel("Tema:")
        sidebar_layout.addWidget(lbl_theme)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["claro", "oscuro", "verde"])
        self.combo_theme.currentTextChanged.connect(self._apply_theme)
        sidebar_layout.addWidget(self.combo_theme)
        self.btn_auto_theme = QPushButton("Auto (sistema)")
        self.btn_auto_theme.clicked.connect(self._auto_theme)
        sidebar_layout.addWidget(self.btn_auto_theme)
        lbl_cfg = QLabel("Config XML:")
        lbl_cfg.setStyleSheet("color: #666666; font-size: 11px;")
        sidebar_layout.addWidget(lbl_cfg)
        self.config_path = QLineEdit()
        self.config_path.setPlaceholderText("Seleccionar PhysiCell_settings.xml")
        sidebar_layout.addWidget(self.config_path)
        self.btn_browse = QPushButton("Examinar...")
        self.btn_browse.clicked.connect(self._browse_config)
        sidebar_layout.addWidget(self.btn_browse)
        self.btn_validate = QPushButton("Validar XML")
        self.btn_validate.clicked.connect(self._validate_current_config)
        sidebar_layout.addWidget(self.btn_validate)
        self.btn_import = QPushButton("Importar XML")
        self.btn_import.clicked.connect(self._importar_config)
        sidebar_layout.addWidget(self.btn_import)
        sidebar_layout.addSpacerItem(
            QSpacerItem(20, 40, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        )
        self.btn_new_exp = QPushButton("+ New Experiment")
        self.btn_new_exp.setFixedHeight(36)
        self.btn_new_exp.clicked.connect(self._on_new_experiment)
        sidebar_layout.addWidget(self.btn_new_exp)
        main_layout.addWidget(self.sidebar, 0)

    def _setup_main_area(self, main_layout):
        self.main_container = QWidget()
        main_layout.addWidget(self.main_container, 1)
        container_layout = QVBoxLayout(self.main_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        header = QFrame()
        header_layout = QHBoxLayout(header)
        self.main_title = QLabel("Bienvenido a PhysiCell Experiments")
        self.main_title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        header_layout.addWidget(self.main_title)
        header_layout.addStretch()
        container_layout.addWidget(header)
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(20, 20, 20, 20)
        self.content_layout.setSpacing(12)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.content_widget)
        container_layout.addWidget(self.scroll)

    def _theme_file(self):
        import os
        return os.path.join(get_user_data_dir(), "theme_preference.txt")

    def _apply_theme(self, name):
        from .themes import THEMES
        if name not in THEMES:
            return
        self.current_theme = name
        self.setStyleSheet(THEMES[name])
        try:
            if self.combo_theme.currentText() != name:
                self.combo_theme.setCurrentText(name)
        except Exception:
            pass
        try:
            with open(self._theme_file(), "w", encoding="utf-8") as f:
                f.write(name)
        except Exception:
            pass

    def _load_theme(self):
        import os
        try:
            if os.path.isfile(self._theme_file()):
                with open(self._theme_file(), "r", encoding="utf-8") as f:
                    name = f.read().strip()
                    if name:
                        self._apply_theme(name)
                        return
        except Exception:
            pass
        self._auto_theme()

    def _auto_theme(self):
        from .themes import detectar_tema_sistema
        self._apply_theme(detectar_tema_sistema())

    def _show_welcome(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        welcome = QLabel(
            "<h3>PhysiCell Experiment Manager</h3>"
            "<p>MVP: gestion basica de experimentos</p>"
            "<p>Click <b>+ New Experiment</b> para crear</p>"
        )
        welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_layout.addWidget(welcome)
        self.content_layout.addStretch()

    def _browse_config(self):
        fname, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar config PhysiCell", "", "XML (*.xml);;Todos (*)"
        )
        if fname:
            self.config_path.setText(fname)

    def _importar_config(self):
        from .config_manager import importar_config
        import os
        src = self.config_path.text().strip()
        if not src:
            src, _ = QFileDialog.getOpenFileName(self, "Importar XML", "", "XML (*.xml)")
            if not src:
                return
        dst_dir = os.path.join(os.path.dirname(__file__), "..", "config")
        r = importar_config(src, dst_dir)
        if r.get("ok"):
            self.config_path.setText(r["path"])
            QMessageBox.information(self, "Importar", f"Importado: {r['path']}")
        else:
            QMessageBox.warning(self, "Importar", r.get("error", "Error"))

    def _validate_current_config(self):
        from .xml_validator import validar_config
        res = validar_config(self.config_path.text().strip())
        if res["ok"]:
            msg = "XML valido."
            if res["warnings"]:
                msg += "\nWarnings: " + "; ".join(res["warnings"])
            QMessageBox.information(self, "Validacion", msg)
        else:
            QMessageBox.warning(self, "Validacion", "\n".join(res["errores"]))

    def _on_new_experiment(self):
        cfg = self.config_path.text().strip()
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM experiments")
        row = cur.fetchone()
        new_id = (row[0] or 0) + 1
        cur.execute(
            "INSERT INTO experiments (id, title, description, config_xml_path) VALUES (?, ?, ?, ?)",
            (new_id, f"Experiment {new_id}", "Configure simulation parameters", cfg),
        )
        conn.commit()
        conn.close()
        self._refresh_list()
        self._show_experiment_detail(new_id)

    def _refresh_list(self):
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT id, title, description FROM experiments ORDER BY id DESC")
        rows = cur.fetchall()
        conn.close()
        if not rows:
            self._show_welcome()
            return
        for eid, title, desc in rows:
            card = CardExperiment(eid, title=title, description=desc or "", on_click=self._show_experiment_detail)
            self.content_layout.addWidget(card)
        self.content_layout.addStretch()

    def _show_experiment_detail(self, experiment_id):
        self.current_experiment_id = experiment_id
        from .simulador import listar_runs
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT title, description, config_xml_path FROM experiments WHERE id=?", (experiment_id,))
        row = cur.fetchone()
        runs = listar_runs(conn, experiment_id)
        conn.close()
        if not row:
            return
        title, desc, cfg = row
        if cfg and not self.config_path.text().strip():
            self.config_path.setText(cfg)
        self.main_title.setText(f"Experimento {experiment_id}: {title}")
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        info = QLabel(f"<b>{title}</b><br>{desc or ''}<br><i>Config: {cfg or self.config_path.text()}</i>")
        info.setWordWrap(True)
        self.content_layout.addWidget(info)
        btn_back = QPushButton("Volver a lista")
        btn_back.clicked.connect(self._refresh_list)
        self.content_layout.addWidget(btn_back)
        # controles replicas
        row_h = QHBoxLayout()
        lbl = QLabel("Replicas:")
        self.spin_replicas = QSpinBox()
        self.spin_replicas.setMinimum(1)
        self.spin_replicas.setMaximum(50)
        self.spin_replicas.setValue(3)
        self.exe_path = QLineEdit()
        self.exe_path.setPlaceholderText("Binario PhysiCell opcional (project.exe)")
        btn_exe = QPushButton("...")
        btn_exe.setFixedWidth(40)
        btn_exe.clicked.connect(self._browse_exe)
        self.btn_run = QPushButton("Ejecutar replicas")
        self.btn_run.clicked.connect(self._ejecutar_replicas)
        self.btn_stop = QPushButton("Detener")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._detener_worker)
        row_h.addWidget(lbl)
        row_h.addWidget(self.spin_replicas)
        row_h.addWidget(self.exe_path, 1)
        row_h.addWidget(btn_exe)
        row_h.addWidget(self.btn_run)
        row_h.addWidget(self.btn_stop)
        cont = QWidget()
        cont.setLayout(row_h)
        self.content_layout.addWidget(cont)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.content_layout.addWidget(self.progress)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(160)
        self.content_layout.addWidget(self.log)
        txt = "<b>Runs registrados:</b><br>" if runs else "Sin runs registrados."
        for rid, rnum, st, s0, s1, od in runs:
            txt += f"#{rnum} id={rid} {st} {s0 or ''} -&gt; {s1 or ''}<br>"
        lbl_runs = QLabel(txt)
        lbl_runs.setWordWrap(True)
        self.content_layout.addWidget(lbl_runs)
        # resultados y reportes
        row2 = QHBoxLayout()
        self.btn_resumen = QPushButton("Resumen resultados")
        self.btn_resumen.clicked.connect(self._ver_resumen)
        self.btn_csv = QPushButton("Export CSV")
        self.btn_csv.clicked.connect(self._export_csv)
        self.btn_json = QPushButton("Export JSON")
        self.btn_json.clicked.connect(self._export_json)
        self.btn_rep = QPushButton("Generar reporte")
        self.btn_rep.clicked.connect(self._generar_reporte)
        row2.addWidget(self.btn_resumen)
        row2.addWidget(self.btn_csv)
        row2.addWidget(self.btn_json)
        row2.addWidget(self.btn_rep)
        self.btn_edit = QPushButton("Editar XML")
        self.btn_edit.clicked.connect(self._editar_xml)
        self.btn_cmp = QPushButton("Comparar replicas")
        self.btn_cmp.clicked.connect(self._comparar_replicas)
        row2.addWidget(self.btn_edit)
        row2.addWidget(self.btn_cmp)
        cont2 = QWidget()
        cont2.setLayout(row2)
        self.content_layout.addWidget(cont2)
        # navegacion temporal
        row3 = QHBoxLayout()
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(lambda: self._mover_frame(-1))
        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(lambda: self._mover_frame(1))
        self.lbl_frame = QLabel("Frame 0")
        self.frame_idx = 0
        row3.addWidget(QLabel("Estados temporales:"))
        row3.addWidget(self.btn_prev)
        row3.addWidget(self.lbl_frame)
        row3.addWidget(self.btn_next)
        row3.addStretch()
        cont3 = QWidget()
        cont3.setLayout(row3)
        self.content_layout.addWidget(cont3)
        self.content_layout.addStretch()

    def _browse_exe(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Binario PhysiCell", "", "Ejecutable (*.exe);;Todos (*)")
        if fname:
            self.exe_path.setText(fname)

    def _ejecutar_replicas(self):
        if self.current_experiment_id is None:
            return
        base_xml = self.config_path.text().strip()
        if not base_xml:
            QMessageBox.warning(self, "Falta config", "Seleccione config XML en sidebar.")
            return
        from .xml_validator import validar_config
        v = validar_config(base_xml)
        if not v["ok"]:
            QMessageBox.warning(self, "XML invalido", "\n".join(v["errores"]))
            return
        n = self.spin_replicas.value()
        self.btn_run.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log.append(f"Iniciando {n} replicas...")
        self.worker = ReplicaWorker(self.current_experiment_id, base_xml, n, self.exe_path.text().strip(), get_db_path())
        self.worker.prog.connect(self._on_worker_prog)
        self.worker.done.connect(self._on_worker_done)
        self.worker.fail.connect(self._on_worker_fail)
        self.worker.start()

    def _on_worker_prog(self, val, txt):
        self.progress.setValue(val)
        self.log.append(txt)

    def _on_worker_done(self, info):
        self.progress.setValue(100)
        self.log.append(f"Completado: {info}")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self._show_experiment_detail(self.current_experiment_id)

    def _on_worker_fail(self, msg):
        self.log.append(f"Error/detencion: {msg}")
        self.btn_run.setEnabled(True)
        self.btn_stop.setEnabled(False)

    def _output_dir_actual(self):
        import os
        return os.path.join(os.path.dirname(get_db_path()), f"exp_{self.current_experiment_id}")

    def _ver_resumen(self):
        from .visualizador import resumen_resultados
        r = resumen_resultados(self._output_dir_actual())
        self.log.append(f"SVG:{r.get('n_svg',0)} XML:{r.get('n_xml',0)} MAT:{r.get('n_mat',0)}")
        if "ultimo_svg" in r:
            self.log.append(str(r["ultimo_svg"]))
        if "ultimo_xml" in r:
            self.log.append(str(r["ultimo_xml"]))

    def _export_csv(self):
        from .reportes import exportar_runs_csv
        import os
        out = os.path.join(os.path.dirname(get_db_path()), f"exp_{self.current_experiment_id}", "runs.csv")
        r = exportar_runs_csv(self.current_experiment_id, get_db_path(), out)
        self.log.append(f"CSV: {r}")

    def _export_json(self):
        from .reportes import exportar_runs_json
        import os
        out = os.path.join(os.path.dirname(get_db_path()), f"exp_{self.current_experiment_id}", "runs.json")
        r = exportar_runs_json(self.current_experiment_id, get_db_path(), out)
        self.log.append(f"JSON: {r}")

    def _generar_reporte(self):
        from .reportes import generar_reporte_html
        import os
        out = os.path.join(os.path.dirname(get_db_path()), f"exp_{self.current_experiment_id}", "reporte.html")
        r = generar_reporte_html(self.current_experiment_id, get_db_path(), out)
        self.log.append(f"Reporte: {r}")
        if r.get("ok"):
            QMessageBox.information(self, "Reporte", f"Generado: {r['path']}")

    def _mover_frame(self, delta):
        from .visualizador import listar_frames, leer_svg_info
        fr = listar_frames(self._output_dir_actual())
        svgs = fr["svg"]
        if not svgs:
            self.lbl_frame.setText("Sin frames PhysiCell")
            return
        self.frame_idx = max(0, min(len(svgs) - 1, self.frame_idx + delta))
        info = leer_svg_info(svgs[self.frame_idx])
        self.lbl_frame.setText(f"Frame {self.frame_idx+1}/{len(svgs)} n={info.get('n_agentes','?')}")
        self.log.append(f"{svgs[self.frame_idx]} -> {info}")

    def _editar_xml(self):
        from PyQt6.QtWidgets import QDialog, QPlainTextEdit, QDialogButtonBox
        from .config_manager import leer_texto, guardar_texto
        path = self.config_path.text().strip()
        if not path:
            QMessageBox.warning(self, "Editar", "Seleccione config XML.")
            return
        try:
            txt = leer_texto(path)
        except Exception as e:
            QMessageBox.warning(self, "Editar", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Editar {path}")
        dlg.resize(700, 500)
        lay = QVBoxLayout(dlg)
        edit = QPlainTextEdit()
        edit.setPlainText(txt)
        lay.addWidget(edit)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            r = guardar_texto(path, edit.toPlainText())
            if r.get("ok"):
                self.log.append(f"Guardado: {path}")
            else:
                QMessageBox.warning(self, "Guardar", r.get("error", "Error"))

    def _comparar_replicas(self):
        import glob, os
        from .config_manager import comparar_replicas
        d = self._output_dir_actual()
        xmls = sorted(glob.glob(os.path.join(d, "replica_*.xml")))
        if not xmls:
            self.log.append("Sin replicas para comparar.")
            return
        filas = comparar_replicas(xmls)
        self.log.append("Comparacion replicas (path | seed | bytes):")
        for f in filas:
            self.log.append(f"{os.path.basename(f['path'])} | seed={f['seed']} | {f['bytes']}")

    def _detener_worker(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.log.append("Solicitando detencion...")


if __name__ == "__main__":
    init_database()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = NotionWindow()
    window.show()
    sys.exit(app.exec())
