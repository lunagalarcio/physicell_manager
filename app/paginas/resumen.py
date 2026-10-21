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
    exp_estado, ESPACIO_M, ESPACIO_L, ESPACIO_XS, TAM_H2,
    ExperimentoCard, estadisticas_experimento, estado_general_experimento,
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
        self.setFixedWidth(210)
        self.setFixedHeight(115)

        fila = QHBoxLayout()
        fila.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        fila.setSpacing(ESPACIO_M)

        num = QLabel(str(numero))
        num.setObjectName("KpiNum")
        lbl = QLabel(etiqueta)
        lbl.setObjectName("KpiLbl")

        col = QVBoxLayout()
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(ESPACIO_XS)
        col.addWidget(num)
        col.addWidget(lbl)

        fila.addLayout(col, 1)
        self.layout_interno().addLayout(fila)


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
                """SELECT e.id, e.title, e.description, e.tags, e.config_xml_path,
                          e.last_modified,
                          COUNT(r.id) as total_runs,
                          SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN r.status IN ('failed', 'cancelled')
                                   THEN 1 ELSE 0 END),
                          MAX(r.start_time)
                   FROM experiments e
                   LEFT JOIN runs r ON e.id = r.experiment_id
                   GROUP BY e.id
                   ORDER BY e.id DESC
                   LIMIT 12"""
            )
            filas = cur.fetchall()
        except Exception:
            cur.execute(
                "SELECT id, title, description, tags, config_xml_path, last_modified "
                "FROM experiments ORDER BY id DESC LIMIT 12"
            )
            filas = [
                (a, b, c, d, e, f, 0, 0, 0, 0, None)
                for a, b, c, d, e, f in cur.fetchall()
            ]
        conn.close()

        col = fila = 0
        mostrados = 0
        for r in filas:
            eid = r[0]
            title = r[1]
            desc = r[2]
            tags = r[3] if len(r) > 3 else ""
            cfg = r[4] if len(r) > 4 else ""
            modif = r[5] if len(r) > 5 else None

            if q and q not in f"{title} {desc} {tags}".lower():
                continue

            # Estadísticas de ejecuciones
            total_runs = r[6] if len(r) > 6 else 0
            completadas = r[7] if len(r) > 7 else 0
            en_curso = r[8] if len(r) > 8 else 0
            falladas = r[9] if len(r) > 9 else 0
            ultima_fecha = r[10] if len(r) > 10 else None

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
