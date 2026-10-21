"""Página de Experimentos: lista, creación y acceso al detalle."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QGridLayout, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QMenu
)

from .base import (
    PaginaBase, Seccion, Tarjeta, xml_estado, ESPACIO_M,
    ExperimentoCard, estadisticas_experimento, estado_general_experimento,
)
from .. import simulador as SIM
from ..theme_lab import LIMA


class PaginaExperimentos(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por título, descripción o etiquetas...")
        self.search.setFixedWidth(320)
        self.search.textChanged.connect(lambda _: self.refrescar())

        b = QPushButton("+ Nuevo experimento")
        b.setObjectName("Primary")
        b.clicked.connect(self._nuevo)

        lay.addWidget(
            Seccion(
                "Experimentos",
                "Lista de experimentos creados. Abre uno para asignar XML, ejecutar réplicas y ver resultados.",
                acciones=[self.search, b],
            )
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.wrap = QWidget()
        self.grid = QGridLayout(self.wrap)
        self.grid.setSpacing(ESPACIO_M)
        scroll.setWidget(self.wrap)
        lay.addWidget(scroll, 1)

        self.refrescar()
        return self

    def refrescar(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        q = (self.search.text() or "").lower().strip()
        conn = self.conn()
        cur = conn.cursor()
        try:
            cur.execute(
                """SELECT e.id, e.title, e.description, e.tags, e.config_xml_path,
                          e.binary_path, e.custom_cpp_path, e.last_modified,
                          COUNT(r.id) as total_runs,
                          SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN r.status IN ('failed', 'cancelled')
                                   THEN 1 ELSE 0 END),
                          MAX(r.start_time)
                   FROM experiments e
                   LEFT JOIN runs r ON e.id = r.experiment_id
                   GROUP BY e.id
                   ORDER BY e.id DESC"""
            )
            filas = cur.fetchall()
        except Exception:
            cur.execute(
                "SELECT id, title, description, tags, config_xml_path, binary_path, custom_cpp_path, last_modified "
                "FROM experiments ORDER BY id DESC"
            )
            filas = [
                (a, b, c, d, e, f, g, h, 0, 0, 0, 0, None)
                for a, b, c, d, e, f, g, h in cur.fetchall()
            ]
        conn.close()

        col = fila = 0
        for r in filas:
            eid = r[0]
            title = r[1]
            desc = r[2]
            tags = r[3] if len(r) > 3 else ""
            cfg = r[4] if len(r) > 4 else ""
            binp = r[5] if len(r) > 5 else ""
            cpp = r[6] if len(r) > 6 else ""
            modif = r[7] if len(r) > 7 else None

            if q and q not in f"{title} {desc} {tags}".lower():
                continue

            # Estadísticas de ejecuciones
            total_runs = r[8] if len(r) > 8 else 0
            completadas = r[9] if len(r) > 9 else 0
            en_curso = r[10] if len(r) > 10 else 0
            falladas = r[11] if len(r) > 11 else 0
            ultima_fecha = r[12] if len(r) > 12 else None

            # Estado del XML
            xe_label, xe_clave = xml_estado(cfg)

            # Estado general del experimento
            n_failed = falladas
            n_completed = completadas
            n_running = en_curso
            xml_ok = xe_label == "Válido"
            estado_general, estado_clave = estado_general_experimento(
                total_runs, n_running, n_failed, n_completed, xml_ok
            )

            card = ExperimentoCard(
                eid=eid,
                title=title,
                desc=desc or "",
                tags=tags or "",
                xml_label=xe_label,
                xml_clave=xe_clave,
                total_runs=total_runs,
                completadas=completadas,
                en_curso=en_curso,
                falladas=falladas,
                ultima_fecha=ultima_fecha,
                estado_general=estado_general,
                estado_clave=estado_clave,
                on_abrir=self.lw.abrir_detalle,
                on_acciones=self._acciones_exp,
            )
            self.grid.addWidget(card, fila, col)
            col += 1
            if col > 2:
                col = 0
                fila += 1

    def _acciones_exp(self, eid):
        m = QMenu(self.lw)
        m.addAction("Editar datos", lambda: self._editar_meta(eid))
        m.addAction("Eliminar", lambda: self._eliminar_exp(eid))
        m.exec(self.lw.cursor().pos())

    def _editar_meta(self, eid):
        from PyQt6.QtWidgets import QLineEdit
        conn = self.conn()
        cur = conn.cursor()
        cur.execute("SELECT title, description, tags, binary_path, custom_cpp_path FROM experiments WHERE id=?", (eid,))
        t, d, g, bp, cpp = cur.fetchone() or ("", "", "", "", "")
        conn.close()

        dlg = QDialog(self.lw)
        dlg.setWindowTitle("Editar experimento")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        e1, e2, e3, e4, e5 = QLineEdit(t), QLineEdit(d or ""), QLineEdit(g or ""), QLineEdit(bp or ""), QLineEdit(cpp or "")
        e4.setPlaceholderText(".../project.exe — motor PhysiCell (opcional)")
        e5.setPlaceholderText(".../custom.cpp — reglas propias del motor (opcional)")
        form.addRow("Título:", e1)
        form.addRow("Descripción:", e2)
        form.addRow("Etiquetas:", e3)
        form.addRow("Motor PhysiCell:", e4)
        form.addRow("custom.cpp del motor:", e5)
        lay.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("Secondary")
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            conn = self.conn()
            SIM.actualizar_experimento(
                conn, eid, e1.text().strip() or t, e2.text().strip(), e3.text().strip(), e4.text().strip(), e5.text().strip()
            )
            conn.close()
            self.refrescar()
            self.lw.refrescar_resumen()

    def _eliminar_exp(self, eid):
        r = QMessageBox.question(
            self.lw, "Eliminar",
            "Borra experimento, runs y escenarios. ¿Continuar?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        conn = self.conn()
        SIM.eliminar_experimento(conn, eid)
        conn.close()
        if self.lw.current_experiment_id == eid:
            self.lw.current_experiment_id = None
        self.refrescar()
        self.lw.refrescar_resumen()

    def _nuevo(self):
        from PyQt6.QtWidgets import QLineEdit
        dlg = QDialog(self.lw)
        dlg.setWindowTitle("Nuevo experimento")
        dlg.setMinimumWidth(450)
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

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Crear")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("Secondary")
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if not dlg.exec():
            return

        conn = self.conn()
        cur = conn.cursor()
        cur.execute("SELECT MAX(id) FROM experiments")
        nid = ((cur.fetchone()[0] or 0) + 1)
        cur.execute(
            "INSERT INTO experiments (id, title, description, tags, config_xml_path, binary_path, custom_cpp_path) VALUES (?,?,?,?,?,?,?)",
            (nid, t1.text().strip() or f"Experimento {nid}", t2.text().strip(), t3.text().strip(), "", "", ""),
        )
        conn.commit()
        conn.close()
        self.refrescar()
        self.lw.refrescar_resumen()
        self.lw.abrir_detalle(nid)
