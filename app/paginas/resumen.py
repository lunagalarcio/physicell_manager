"""Página de Resumen: KPIs y tarjetas de experimentos recientes."""
import os

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QScrollArea, QWidget, QGridLayout, QFrame, QMenu
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .base import (
    PaginaBase, Seccion, Tarjeta, BadgeEstado, xml_estado, ESTILO_ESTADO,
    exp_estado, ESPACIO_M, ESPACIO_L, TAM_H2,
)
from .. import simulador as SIM
from ..theme_lab import LIMA
from ..xml_validator import validar_config


def _validar_ok(path):
    if not path:
        return False
    v = validar_config(path)
    return bool(v.get("ok"))


class KpiCard(Tarjeta):
    """Tarjeta de indicador clave con número grande y etiqueta."""

    def __init__(self, numero, etiqueta, padre=None):
        super().__init__(padre=padre)
        self.setFixedWidth(200)
        self.setFixedHeight(90)
        num = QLabel(str(numero))
        num.setObjectName("KpiNum")
        lbl = QLabel(etiqueta)
        lbl.setObjectName("KpiLbl")
        self.layout_interno().addWidget(num)
        self.layout_interno().addWidget(lbl)


class ExperimentoCard(Tarjeta):
    """Tarjeta de experimento con título, descripción, metadatos y botones."""

    def __init__(self, eid, title, desc, tags, modif, xe, runs, on_abrir, on_acciones, padre=None):
        super().__init__(padre=padre)
        self.eid = eid
        self.setMinimumWidth(260)
        self.setMaximumWidth(360)

        t = QLabel(title or f"Experimento {eid}")
        t.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t.setWordWrap(True)
        self.layout_interno().addWidget(t)

        d = QLabel((desc or "Sin descripción")[:140])
        d.setObjectName("Muted")
        d.setWordWrap(True)
        self.layout_interno().addWidget(d)

        meta = QLabel(
            f"{tags or 'sin etiquetas'}  •  {runs} runs  •  XML: {xe}"
            + (f"  •  {modif}" if modif else "")
        )
        meta.setObjectName("Muted")
        meta.setWordWrap(True)
        self.layout_interno().addWidget(meta)

        row = QHBoxLayout()
        b1 = QPushButton("Abrir")
        b1.setObjectName("Primary")
        b1.clicked.connect(lambda _: on_abrir(eid))
        b2 = QPushButton("⋯")
        b2.setObjectName("Fantasma")
        b2.setFixedWidth(40)
        b2.setToolTip("Editar / Eliminar")
        b2.clicked.connect(lambda _: on_acciones(eid))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch()
        contenedor = QWidget()
        contenedor.setLayout(row)
        self.layout_interno().addWidget(contenedor)


class PaginaResumen(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        # Encabezado con búsqueda y botón nuevo
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar experimentos...")
        self.search.setFixedWidth(280)
        self.search.textChanged.connect(lambda _: self.refrescar())

        b_nuevo = QPushButton("+ Nuevo experimento")
        b_nuevo.setObjectName("Primary")
        b_nuevo.clicked.connect(self._nuevo)

        lay.addWidget(
            Seccion(
                "Mis experimentos",
                "Gestión y análisis de experimentos de simulación celular",
                acciones=[self.search, b_nuevo],
            )
        )

        # KPIs
        self.kpi_row = QHBoxLayout()
        self.kpi_row.setSpacing(ESPACIO_M)
        lay.addLayout(self.kpi_row)

        # Lista reciente
        h2 = QLabel("Recientes")
        h2.setObjectName("H2")
        lay.addWidget(h2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.recent = QWidget()
        self.grid = QGridLayout(self.recent)
        self.grid.setSpacing(ESPACIO_M)
        scroll.setWidget(self.recent)
        lay.addWidget(scroll, 1)

        self.refrescar()
        return self

    def refrescar(self):
        self._kpis()
        self._tarjetas()

    def _kpis(self):
        # Limpiar KPIs previos
        while self.kpi_row.count():
            item = self.kpi_row.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        total, cfg_ok, comp, curso, fallo = self._contar()
        datos = [
            (total, "Total experimentos"),
            (cfg_ok, "Configurados"),
            (comp, "Ejecuciones completadas"),
            (f"{curso}/{fallo}", "En curso / fallidas"),
        ]
        for numero, etiqueta in datos:
            self.kpi_row.addWidget(KpiCard(numero, etiqueta))
        self.kpi_row.addStretch()

    def _contar(self):
        conn = self.conn()
        cur = conn.cursor()
        cur.execute("SELECT id, config_xml_path FROM experiments")
        exps = cur.fetchall()
        total = len(exps)
        cfg_ok = 0
        for _, c in exps:
            if c and os.path.isfile(c) and _validar_ok(c):
                cfg_ok += 1
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

    def _tarjetas(self):
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
                "SELECT id, title, description, tags, config_xml_path, last_modified "
                "FROM experiments ORDER BY id DESC LIMIT 12"
            )
            filas = cur.fetchall()
        except Exception:
            cur.execute("SELECT id, title, description FROM experiments ORDER BY id DESC LIMIT 12")
            filas = [(a, b, c, "", "", None) for a, b, c in cur.fetchall()]
        counts = {}
        try:
            cur.execute("SELECT experiment_id, COUNT(*) FROM runs GROUP BY experiment_id")
            counts = dict(cur.fetchall())
        except Exception:
            pass
        conn.close()

        col = fila = 0
        mostrados = 0
        for r in filas:
            eid, title, desc = r[0], r[1], r[2]
            tags = r[3] if len(r) > 3 else ""
            cfg = r[4] if len(r) > 4 else ""
            modif = r[5] if len(r) > 5 else None
            if q and q not in f"{title} {desc} {tags}".lower():
                continue
            runs = counts.get(eid, 0)
            xe, _ = xml_estado(cfg)
            card = ExperimentoCard(
                eid, title, desc, tags, modif, xe, runs,
                on_abrir=self.lw.abrir_detalle,
                on_acciones=self._acciones_exp,
            )
            self.grid.addWidget(card, fila, col)
            col += 1
            if col > 2:
                col = 0
                fila += 1
            mostrados += 1
        if mostrados == 0:
            vazio = QLabel("Sin experimentos. Usa «+ Nuevo experimento» para empezar.")
            vazio.setObjectName("Muted")
            self.grid.addWidget(vazio, 0, 0)

    def _acciones_exp(self, eid):
        m = QMenu(self.lw)
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
