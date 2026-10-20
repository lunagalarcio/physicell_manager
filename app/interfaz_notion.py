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
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from .nucleo import ReplicaWorker, get_user_data_dir, get_db_path, init_database


class CardExperiment(QFrame):
    def __init__(self, experiment_id, title="Nuevo Experimento", description="", tags="", config_ok=False, n_runs=0, parent=None, on_click=None):
        super().__init__(parent)
        self.experiment_id = experiment_id
        self.on_click = on_click
        self.setObjectName("CardExperiment")
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setMinimumSize(260, 150)
        self.setMaximumHeight(190)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Clic para abrir. Título, descripción y etiquetas ayudan a organizar.")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(5)
        self.title_label = QLabel(title)
        self.title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.title_label.setWordWrap(True)
        layout.addWidget(self.title_label)
        self.desc_label = QLabel(description or "Sin descripción. Clic para añadir contexto del ensayo.")
        self.desc_label.setWordWrap(True)
        layout.addWidget(self.desc_label)
        tag_txt = tags.strip() if tags else "sin etiquetas"
        estado = "● config lista" if config_ok else "○ falta XML"
        self.meta_label = QLabel(f"{tag_txt}  •  {n_runs} runs  •  {estado}")
        self.meta_label.setWordWrap(True)
        layout.addWidget(self.meta_label)
        layout.addStretch()

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click(self.experiment_id)
        super().mousePressEvent(event)


class NewExperimentCard(QFrame):
    def __init__(self, parent=None, on_click=None):
        super().__init__(parent)
        self.on_click = on_click
        self.setObjectName("CardExperiment")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumSize(260, 150)
        self.setMaximumHeight(190)
        self.setToolTip("Crear un nuevo experimento")
        layout = QVBoxLayout(self)
        layout.addStretch()
        lbl = QLabel("+  Nuevo experimento")
        lbl.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(lbl)
        hint = QLabel("Título, descripción y etiquetas")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(hint)
        layout.addStretch()

    def mousePressEvent(self, event):
        if self.on_click:
            self.on_click()
        super().mousePressEvent(event)


class NotionWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.current_experiment_id = None
        self.worker = None
        self.current_theme = "claro"
        self.setWindowTitle("PhysiCell Experiment Manager")
        self.setMinimumSize(1020, 680)
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
        self.sidebar.setFixedWidth(260)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(16, 20, 16, 20)
        sidebar_layout.setSpacing(8)
        title = QLabel("PhysiCell Manager")
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        sidebar_layout.addWidget(title)
        sub = QLabel("Gestión de experimentos PhysiCell")
        sub.setWordWrap(True)
        sidebar_layout.addWidget(sub)
        guide = QLabel(
            "Cómo empezar:\n"
            "1) Elige tu PhysiCell_settings.xml\n"
            "2) Elige project.exe compilado\n"
            "3) Crea experimento y lanza réplicas"
        )
        guide.setWordWrap(True)
        sidebar_layout.addWidget(guide)
        lbl_theme = QLabel("Tema: claro / oscuro / verde")
        sidebar_layout.addWidget(lbl_theme)
        self.combo_theme = QComboBox()
        self.combo_theme.addItems(["claro", "oscuro", "verde"])
        self.combo_theme.currentTextChanged.connect(self._apply_theme)
        sidebar_layout.addWidget(self.combo_theme)
        self.btn_auto_theme = QPushButton("Auto (sistema)")
        self.btn_auto_theme.clicked.connect(self._auto_theme)
        sidebar_layout.addWidget(self.btn_auto_theme)
        lbl_cfg = QLabel("Archivo 1 - Config PhysiCell (.xml): Sirve como plantilla de réplicas.")
        lbl_cfg.setWordWrap(True)
        sidebar_layout.addWidget(lbl_cfg)
        self.config_path = QLineEdit()
        self.config_path.setPlaceholderText("Ej: .../PhysiCell_settings.xml")
        self.config_path.setToolTip("XML de PhysiCell. Debe incluir domain, overall, microenvironment y cell_definitions.")
        sidebar_layout.addWidget(self.config_path)
        self.btn_browse = QPushButton("1) Examinar XML...")
        self.btn_browse.setToolTip("Selecciona tu archivo PhysiCell_settings.xml")
        self.btn_browse.clicked.connect(self._browse_config)
        sidebar_layout.addWidget(self.btn_browse)
        self.btn_import = QPushButton("Importar a config/")
        self.btn_import.setToolTip("Copia el XML a la carpeta config del proyecto")
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
        self.main_title.setText("Experimentos")
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        intro = QLabel(
            "<h2>Gestión de experimentos PhysiCell</h2>"
            "<p>Crea tarjetas con título, descripción y etiquetas. Abre una tarjeta para configurar réplicas, ejecutar PhysiCell, visualizar estados y generar reportes.</p>"
            "<p><b>Archivos que debes ingresar:</b><br>"
            "1) <b>PhysiCell_settings.xml</b> en la barra lateral: plantilla base de la simulación.<br>"
            "2) <b>project.exe</b> compilado de PhysiCell en el detalle del experimento: motor que ejecuta.<br>"
            "Sin project.exe solo se generan configs y el estado queda como <i>registered</i>.</p>"
        )
        intro.setWordWrap(True)
        self.content_layout.addWidget(intro)
        self._refresh_list(mostrar_bienvenida=False)

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

    def _on_new_experiment(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Nuevo experimento")
        dlg.resize(420, 260)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        t_title = QLineEdit()
        t_title.setPlaceholderText("Ej: Tumor + inmune, dosis O2 baja")
        t_desc = QLineEdit()
        t_desc.setPlaceholderText("Ej: Probar 5 réplicas con seed distinto")
        t_tags = QLineEdit()
        t_tags.setPlaceholderText("Ej: cancer, o2-bajo, lote-1 (separadas por coma)")
        form.addRow("Título:", t_title)
        form.addRow("Descripción:", t_desc)
        form.addRow("Etiquetas:", t_tags)
        lay.addLayout(form)
        hint = QLabel("El XML actual de la barra lateral se guardará como plantilla del experimento.")
        hint.setWordWrap(True)
        lay.addWidget(hint)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if not dlg.exec():
            return
        title = t_title.text().strip() or "Experimento sin título"
        desc = t_desc.text().strip()
        tags = t_tags.text().strip()
        cfg = self.config_path.text().strip()
        if cfg:
            from .xml_validator import validar_config as _vc2
            _v = _vc2(cfg)
            if not _v.get("ok"):
                r = QMessageBox.warning(self, "XML base inválido",
                    "El XML de la barra lateral es inválido:\n" + "; ".join(_v.get("errores", [])) +
                    "\n\nSe creará igual y podrás corregirlo en el detalle del experimento. ¿Continuar?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                if r != QMessageBox.StandardButton.Yes:
                    return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM experiments")
        row = cur.fetchone()
        new_id = (row[0] or 0) + 1
        cur.execute(
            "INSERT INTO experiments (id, title, description, config_xml_path, tags) VALUES (?, ?, ?, ?, ?)",
            (new_id, title, desc, cfg, tags),
        )
        conn.commit()
        conn.close()
        self._refresh_list()
        self._show_experiment_detail(new_id)

    def _refresh_list(self, mostrar_bienvenida=True):
        from PyQt6.QtWidgets import QGridLayout
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        if mostrar_bienvenida:
            intro = QLabel("Tus experimentos. Usa la tarjeta + para crear uno nuevo con título, descripción y etiquetas.")
            intro.setWordWrap(True)
            self.content_layout.addWidget(intro)
        brow = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Buscar por título, descripción o etiquetas...")
        self.search_edit.setText(getattr(self, "_filtro", ""))
        self.search_edit.textChanged.connect(self._filtrar_lista)
        brow.addWidget(self.search_edit, 1)
        bw = QWidget()
        bw.setLayout(brow)
        self.content_layout.addWidget(bw)
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title, description, tags, config_xml_path FROM experiments ORDER BY id DESC")
        except Exception:
            cur.execute("SELECT id, title, description FROM experiments ORDER BY id DESC")
            rows = [(a, b, c, "", "") for a, b, c in cur.fetchall()]
            conn.close()
            self._pintar_grid(rows)
            return
        rows = cur.fetchall()
        # runs por experimento
        counts = {}
        try:
            cur.execute("SELECT experiment_id, COUNT(*) FROM runs GROUP BY experiment_id")
            counts = dict(cur.fetchall())
        except Exception:
            pass
        conn.close()
        data = []
        for r in rows:
            eid, title, desc, tags, cfg = (list(r) + ["", ""])[:5]
            data.append((eid, title, desc, tags, bool(cfg and str(cfg).strip()), counts.get(eid, 0)))
        self._pintar_grid(data)

    def _filtrar_lista(self, txt):
        self._filtro = txt
        self._refresh_list(mostrar_bienvenida=False)
        try:
            self.search_edit.setFocus()
            self.search_edit.setCursorPosition(len(txt))
        except Exception:
            pass

    def _pintar_grid(self, data):
        from PyQt6.QtWidgets import QGridLayout
        f = (getattr(self, "_filtro", "") or "").lower().strip()
        if f:
            data = [d for d in data if f in f"{d[1]} {d[2] if len(d) > 2 else ''} {d[3] if len(d) > 3 else ''}".lower()]
        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setSpacing(12)
        grid.addWidget(NewExperimentCard(on_click=self._on_new_experiment), 0, 0)
        col = 1
        fila = 0
        for item in data:
            if len(item) == 6:
                eid, title, desc, tags, ok, n = item
            else:
                eid, title, desc = item[:3]
                tags, ok, n = "", False, 0
            card = CardExperiment(eid, title=title, description=desc or "", tags=tags or "", config_ok=ok, n_runs=n, on_click=self._show_experiment_detail)
            grid.addWidget(card, fila, col)
            col += 1
            if col > 1:
                col = 0
                fila += 1
        self.content_layout.addWidget(grid_w)
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
        self.main_title.setText(f"Experimento {experiment_id}: {title}")
        while self.content_layout.count():
            item = self.content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        info = QLabel(
            f"<h2>{title}</h2>"
            f"<p>{desc or 'Añade contexto: objetivo, hipótesis, lote.'}</p>"
        )
        info.setWordWrap(True)
        self.content_layout.addWidget(info)
        brow = QHBoxLayout()
        btn_back = QPushButton("← Volver a experimentos")
        btn_back.setToolTip("Regresa a la cuadrícula de tarjetas")
        btn_back.clicked.connect(self._refresh_list)
        btn_edit_meta = QPushButton("Editar datos")
        btn_edit_meta.setToolTip("Editar título, descripción y etiquetas")
        btn_edit_meta.clicked.connect(self._editar_metadatos)
        btn_del = QPushButton("Eliminar")
        btn_del.setToolTip("Borra experimento, runs y escenarios")
        btn_del.clicked.connect(self._eliminar_experimento)
        brow.addWidget(btn_back)
        brow.addWidget(btn_edit_meta)
        brow.addWidget(btn_del)
        brow.addStretch()
        bw = QWidget()
        bw.setLayout(brow)
        self.content_layout.addWidget(bw)
        # escenarios del experimento
        from .simulador import listar_escenarios
        conn2 = sqlite3.connect(get_db_path())
        escs = listar_escenarios(conn2, experiment_id)
        conn2.close()
        sbox = QFrame()
        sbox.setObjectName("CardExperiment")
        sl = QVBoxLayout(sbox)
        sl.addWidget(QLabel("<b>Escenarios</b> (variantes de config dentro del experimento):"))
        erow = QHBoxLayout()
        self.esc_nombre = QLineEdit()
        self.esc_nombre.setPlaceholderText("Nombre escenario, ej: o2-bajo")
        btn_esc = QPushButton("Crear escenario desde XML actual")
        btn_esc.clicked.connect(self._crear_escenario)
        erow.addWidget(self.esc_nombre, 1)
        erow.addWidget(btn_esc)
        sl.addLayout(erow)
        if escs:
            for sid, nom, cpath in escs:
                r2 = QHBoxLayout()
                l2 = QLabel(f"#{sid} {nom} - {cpath}")
                l2.setWordWrap(True)
                b2 = QPushButton("Borrar")
                b2.setFixedWidth(70)
                b2.clicked.connect(lambda _=False, _s=sid: self._borrar_escenario(_s))
                r2.addWidget(l2, 1)
                r2.addWidget(b2)
                cw = QWidget()
                cw.setLayout(r2)
                sl.addWidget(cw)
        else:
            sl.addWidget(QLabel("Sin escenarios. Crea uno para comparar variantes."))
        self.content_layout.addWidget(sbox)
        # XML propio del experimento con validación
        from .xml_validator import validar_config as _vc
        v0 = _vc(cfg) if cfg else {"ok": False, "errores": ["Sin XML asignado"], "warnings": []}
        estado = "✓ válido" if v0.get("ok") else "✗ inválido"
        box = QFrame()
        box.setObjectName("CardExperiment")
        bl = QVBoxLayout(box)
        bl.addWidget(QLabel("<b>Archivo 1 - XML de este experimento</b> (plantilla de sus réplicas):"))
        rowx = QHBoxLayout()
        self.exp_config = QLineEdit(cfg or "")
        self.exp_config.setPlaceholderText("Ej: .../PhysiCell_settings.xml")
        self.exp_config.setToolTip("Cada experimento guarda su propio XML. No depende del campo global.")
        btn_cx = QPushButton("...")
        btn_cx.setFixedWidth(40)
        btn_cx.clicked.connect(self._browse_exp_config)
        btn_vx = QPushButton("Validar")
        btn_vx.clicked.connect(self._validar_exp_config)
        btn_sx = QPushButton("Guardar XML")
        btn_sx.clicked.connect(self._guardar_exp_config)
        rowx.addWidget(self.exp_config, 1)
        rowx.addWidget(btn_cx)
        rowx.addWidget(btn_vx)
        rowx.addWidget(btn_sx)
        bl.addLayout(rowx)
        self.lbl_exp_valid = QLabel(f"Estado: {estado}" + (f" - {'; '.join(v0.get('errores', []))}" if not v0.get("ok") else ""))
        self.lbl_exp_valid.setWordWrap(True)
        bl.addWidget(self.lbl_exp_valid)
        bl.addWidget(QLabel("<b>Archivo 2 - Motor PhysiCell:</b> selecciona abajo tu project.exe compilado. Sin él solo se generan réplicas."))
        self.content_layout.addWidget(box)
        # controles replicas
        row_h = QHBoxLayout()
        lbl = QLabel("Réplicas:")
        lbl.setToolTip("Cuántas copias con distinto random_seed se generarán")
        self.spin_replicas = QSpinBox()
        self.spin_replicas.setMinimum(1)
        self.spin_replicas.setMaximum(50)
        self.spin_replicas.setValue(3)
        self.spin_replicas.setToolTip("1 a 50 réplicas por ejecución")
        self.exe_path = QLineEdit()
        self.exe_path.setPlaceholderText("Archivo 2: .../project.exe (motor PhysiCell compilado)")
        self.exe_path.setToolTip("Binario compilado con make. Obligatorio para simular, opcional para solo generar configs.")
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
        # visor 2D/3D integrado (sin PNG externos)
        from .visor_widget import VisorPhysiCell
        lbl_vis = QLabel("<b>Visualización 2D y 3D integrada:</b> usa la carpeta output de PhysiCell y el slider para navegar estados temporales.")
        lbl_vis.setWordWrap(True)
        self.content_layout.addWidget(lbl_vis)
        self.visor = VisorPhysiCell(output_dir=r"C:\Users\PC\Downloads\gestor_physicell\gestor_physicell\PhysiCell\output")
        self.visor.setMinimumHeight(380)
        self.content_layout.addWidget(self.visor)
        self.content_layout.addStretch()

    def _editar_metadatos(self):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        from .simulador import actualizar_experimento
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("SELECT title, description, tags FROM experiments WHERE id=?", (self.current_experiment_id,))
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
            actualizar_experimento(conn, self.current_experiment_id, e1.text().strip() or t, e2.text().strip(), e3.text().strip())
            conn.close()
            self._show_experiment_detail(self.current_experiment_id)

    def _eliminar_experimento(self):
        from .simulador import eliminar_experimento
        r = QMessageBox.question(self, "Eliminar", "Borra experimento, runs y escenarios. ¿Continuar?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r != QMessageBox.StandardButton.Yes:
            return
        conn = sqlite3.connect(get_db_path())
        eliminar_experimento(conn, self.current_experiment_id)
        conn.close()
        self.current_experiment_id = None
        self._refresh_list()

    def _crear_escenario(self):
        from .simulador import crear_escenario
        from .xml_validator import validar_config
        nom = self.esc_nombre.text().strip() or "escenario-1"
        cfg = self.exp_config.text().strip()
        v = validar_config(cfg)
        if not v.get("ok"):
            QMessageBox.warning(self, "Escenario", "XML inválido: " + "; ".join(v.get("errores", [])))
            return
        conn = sqlite3.connect(get_db_path())
        crear_escenario(conn, self.current_experiment_id, nom, cfg, "{}")
        conn.close()
        self._show_experiment_detail(self.current_experiment_id)

    def _borrar_escenario(self, sid):
        from .simulador import eliminar_escenario
        conn = sqlite3.connect(get_db_path())
        eliminar_escenario(conn, sid)
        conn.close()
        self._show_experiment_detail(self.current_experiment_id)

    def _browse_exe(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Binario PhysiCell", "", "Ejecutable (*.exe);;Todos (*)")
        if fname:
            self.exe_path.setText(fname)

    def _browse_exp_config(self):
        fname, _ = QFileDialog.getOpenFileName(self, "XML de este experimento", "", "XML (*.xml);;Todos (*)")
        if fname:
            self.exp_config.setText(fname)
            self._validar_exp_config(silencioso=True)

    def _validar_exp_config(self, silencioso=False):
        from .xml_validator import validar_config
        res = validar_config(self.exp_config.text().strip())
        if res.get("ok"):
            msg = "Estado: ✓ válido" + (f" - warnings: {'; '.join(res.get('warnings', []))}" if res.get("warnings") else "")
            self.lbl_exp_valid.setText(msg)
            if not silencioso:
                QMessageBox.information(self, "Validación", "XML válido para este experimento.")
        else:
            self.lbl_exp_valid.setText(f"Estado: ✗ inválido - {'; '.join(res.get('errores', []))}")
            if not silencioso:
                QMessageBox.warning(self, "Validación", "\n".join(res.get("errores", [])))
        return res

    def _guardar_exp_config(self):
        path = self.exp_config.text().strip()
        from .xml_validator import validar_config
        v = validar_config(path)
        if not v.get("ok"):
            QMessageBox.warning(self, "Guardar", "No se guarda: " + "; ".join(v.get("errores", [])))
            return
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()
        cur.execute("UPDATE experiments SET config_xml_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?", (path, self.current_experiment_id))
        conn.commit()
        conn.close()
        self.lbl_exp_valid.setText("Estado: ✓ válido - guardado en este experimento")
        self.log.append(f"XML guardado en experimento {self.current_experiment_id}: {path}")

    def _ejecutar_replicas(self):
        if self.current_experiment_id is None:
            return
        base_xml = self.exp_config.text().strip() if hasattr(self, "exp_config") else self.config_path.text().strip()
        if not base_xml:
            QMessageBox.warning(self, "Falta config", "Asigna el XML de este experimento arriba.")
            return
        from .xml_validator import validar_config
        v = validar_config(base_xml)
        if not v["ok"]:
            QMessageBox.warning(self, "XML invalido en este experimento", "\n".join(v["errores"]))
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
        from .comparacion import generar_grafica_comparacion
        d = self._output_dir_actual()
        xmls = sorted(glob.glob(os.path.join(d, "replica_*", "replica_*.xml"))) or sorted(glob.glob(os.path.join(d, "replica_*.xml")))
        if xmls:
            filas = comparar_replicas(xmls)
            self.log.append("Seeds por réplica:")
            for f in filas:
                self.log.append(f"{os.path.basename(os.path.dirname(f['path']))}/{os.path.basename(f['path'])} | seed={f['seed']}")
        out_png = os.path.join(d, "comparacion.png")
        r = generar_grafica_comparacion(get_db_path(), self.current_experiment_id, out_png)
        self.log.append(f"Gráfica: {r['path']} runs={len(r['filas'])} sin_datos={r['sin_datos']}")
        for f in r["filas"]:
            self.log.append(f"run {f['run']}: {f['status']} n_final={f['n_final']}")

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
