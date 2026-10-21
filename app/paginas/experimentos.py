"""Página de Experimentos: lista, creación y acceso al detalle."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QGridLayout, QFrame, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QMenu
)
from PyQt6.QtGui import QFont

from .base import (
    PaginaBase, Seccion, Tarjeta, BadgeEstado, xml_estado, ESPACIO_M,
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
                "SELECT id, title, description, tags, config_xml_path FROM experiments ORDER BY id DESC"
            )
            filas = cur.fetchall()
        except Exception:
            filas = []
        counts = {}
        try:
            cur.execute("SELECT experiment_id, COUNT(*) FROM runs GROUP BY experiment_id")
            counts = dict(cur.fetchall())
        except Exception:
            pass
        conn.close()

        col = fila = 0
        for eid, title, desc, tags, cfg in filas:
            if q and q not in f"{title} {desc} {tags}".lower():
                continue
            xe, _ = xml_estado(cfg)
            card = self._tarjeta_experimento(
                eid, title, desc, tags, None, xe, counts.get(eid, 0)
            )
            self.grid.addWidget(card, fila, col)
            col += 1
            if col > 2:
                col = 0
                fila += 1

    def _tarjeta_experimento(self, eid, title, desc, tags, modif, xe, runs):
        from .resumen import ExperimentoCard
        return ExperimentoCard(
            eid, title, desc, tags, modif, xe, runs,
            on_abrir=self.lw.abrir_detalle,
            on_acciones=self._acciones_exp,
        )

    def _acciones_exp(self, eid):
        m = QMenu(self.lw)
        m.addAction("Editar datos", lambda: self._editar_meta(eid))
        m.addAction("Eliminar", lambda: self._eliminar_exp(eid))
        m.exec(self.lw.cursor().pos())

    def _editar_meta(self, eid):
        from PyQt6.QtWidgets import QLineEdit
        conn = self.conn()
        cur = conn.cursor()
        cur.execute("SELECT title, description, tags FROM experiments WHERE id=?", (eid,))
        t, d, g = cur.fetchone() or ("", "", "")
        conn.close()

        dlg = QDialog(self.lw)
        dlg.setWindowTitle("Editar experimento")
        dlg.setMinimumWidth(420)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        e1, e2, e3 = QLineEdit(t), QLineEdit(d or ""), QLineEdit(g or "")
        form.addRow("Título:", e1)
        form.addRow("Descripción:", e2)
        form.addRow("Etiquetas:", e3)
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
                conn, eid, e1.text().strip() or t, e2.text().strip(), e3.text().strip()
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
            "INSERT INTO experiments (id, title, description, tags, config_xml_path) VALUES (?,?,?,?,?)",
            (nid, t1.text().strip() or f"Experimento {nid}", t2.text().strip(), t3.text().strip(), ""),
        )
        conn.commit()
        conn.close()
        self.refrescar()
        self.lw.refrescar_resumen()
        self.lw.abrir_detalle(nid)
