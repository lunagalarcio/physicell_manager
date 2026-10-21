"""Página de Experimentos: lista, creación y acceso al detalle."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QGridLayout, QFrame, QDialog,
    QFormLayout, QDialogButtonBox, QMessageBox, QMenu
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from .base import PaginaBase, xml_estado
from .. import simulador as SIM


class PaginaExperimentos(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(10)

        top = QHBoxLayout()
        h = QLabel("Experimentos")
        h.setObjectName("H1")
        top.addWidget(h)
        top.addStretch()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar por título, descripción o etiquetas...")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(lambda _: self.refrescar())
        top.addWidget(self.search)
        b = QPushButton("+ Nuevo experimento")
        b.setObjectName("Primary")
        b.clicked.connect(self._nuevo)
        top.addWidget(b)
        lay.addLayout(top)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.wrap = QWidget()
        self.grid = QGridLayout(self.wrap)
        self.grid.setSpacing(12)
        scroll.setWidget(self.wrap)
        lay.addWidget(scroll, 1)

        self.refrescar()
        return self

    def refrescar(self):
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.deleteLater()

        q = (self.search.text() or "").lower().strip()
        conn = self.conn()
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
            card = self._exp_card(eid, title, desc, tags, None, xe, counts.get(eid, 0))
            self.grid.addWidget(card, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1

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
        m = QLabel(
            f"{tags or 'sin etiquetas'}  •  {runs} runs  •  XML: {xe}"
        )
        m.setObjectName("Muted")
        m.setWordWrap(True)
        v.addWidget(m)
        row = QHBoxLayout()
        b1 = QPushButton("Abrir")
        b1.setObjectName("Primary")
        b1.clicked.connect(lambda _=False, e=eid: self.lw.abrir_detalle(e))
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
