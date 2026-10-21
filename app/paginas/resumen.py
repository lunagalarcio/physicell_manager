"""Página de Resumen: KPIs y tarjetas de experimentos recientes."""
import os
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QGridLayout, QFrame
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from .base import PaginaBase, xml_estado, ESTILO_ESTADO, exp_estado
from .. import simulador as SIM


class PaginaResumen(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
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

        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar experimentos...")
        self.search.setFixedWidth(260)
        self.search.textChanged.connect(lambda _: self.refrescar())
        top.addWidget(self.search)

        b_nuevo = QPushButton("+ Nuevo experimento")
        b_nuevo.setObjectName("Primary")
        b_nuevo.clicked.connect(self._nuevo)
        top.addWidget(b_nuevo)
        lay.addLayout(top)

        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(12)
        lay.addLayout(self.kpi_row)

        h2 = QLabel("Recientes")
        h2.setObjectName("H2")
        lay.addWidget(h2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.recent = QWidget()
        self.grid = QGridLayout(self.recent)
        self.grid.setSpacing(12)
        scroll.setWidget(self.recent)
        lay.addWidget(scroll, 1)

        self.refrescar()
        return self

    def refrescar(self):
        self._kpis()
        self._tarjetas()

    # ---------- KPIs ----------
    def _kpis(self):
        for i in reversed(range(self.kpi_row.count())):
            w = self.kpi_row.itemAt(i).widget()
            if w:
                w.deleteLater()
        total, cfg_ok, comp, curso, fallo = self._contar()
        for n, lbl in [
            (total, "Total experimentos"),
            (cfg_ok, "Configurados"),
            (comp, "Ejecuciones completadas"),
            (f"{curso}/{fallo}", "En curso / fallidas"),
        ]:
            self.kpi_row.addWidget(self._kpi_card(n, lbl))

    def _contar(self):
        conn = self.conn()
        cur = conn.cursor()
        cur.execute("SELECT id, config_xml_path FROM experiments")
        exps = cur.fetchall()
        total = len(exps)
        cfg_ok = 0
        for _, c in exps:
            if c and os.path.isfile(c):
                try:
                    if validar_config_ok(c):
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

    # ---------- tarjetas recientes ----------
    def _tarjetas(self):
        for i in reversed(range(self.grid.count())):
            w = self.grid.itemAt(i).widget()
            if w:
                w.deleteLater()

        q = (self.search.text() or "").lower().strip()
        conn = self.conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT id, title, description, tags, config_xml_path, last_modified "
                "FROM experiments ORDER BY id DESC LIMIT 12"
            )
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
            self.grid.addWidget(card, row, col)
            col += 1
            if col > 2:
                col = 0
                row += 1
            mostrados += 1
        if mostrados == 0:
            l = QLabel("Sin experimentos. Usa «+ Nuevo experimento» para empezar.")
            l.setObjectName("Muted")
            self.grid.addWidget(l, 0, 0)

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
            + (f"  •  {modif}" if modif else "")
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
        from PyQt6.QtWidgets import QMenu
        m = QMenu(self)
        m.addAction("Editar datos", lambda: self._editar_meta(eid))
        m.addAction("Eliminar", lambda: self._eliminar_exp(eid))
        m.exec(self.lw.cursor().pos())

    def _editar_meta(self, eid):
        from PyQt6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
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
            self.lw.refrescar_exps()

    def _eliminar_exp(self, eid):
        from PyQt6.QtWidgets import QMessageBox
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
        self.lw.refrescar_exps()

    def _nuevo(self):
        self.lw.ir("Experimentos")
        self.lw.paginas["experimentos"]._nuevo()


def validar_config_ok(path):
    from ..xml_validator import validar_config
    v = validar_config(path)
    return bool(v.get("ok"))
