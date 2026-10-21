"""Página de Reportes: generación de informes HTML/PDF/CSV/JSON por experimento."""
import os
import glob as _g

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt

from .base import PaginaBase
from ..reportes import (
    generar_reporte_html, exportar_reporte_pdf, exportar_runs_csv, exportar_runs_json
)
import subprocess as _sp


class PaginaReportes(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(8)
        h = QLabel("Reportes")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel(
            "Informes HTML generados por experimento, con trazabilidad de configuración, "
            "réplicas y resultados."
        )
        d.setObjectName("Muted")
        d.setWordWrap(True)
        lay.addWidget(d)

        row = QHBoxLayout()
        self.exp_combo = QComboBox()
        b_gen = QPushButton("Generar informe")
        b_gen.setObjectName("Primary")
        b_gen.clicked.connect(self._generar)
        b_open = QPushButton("Abrir carpeta")
        b_open.setObjectName("Secondary")
        b_open.clicked.connect(self._abrir_carpeta)
        row.addWidget(self.exp_combo, 1)
        row.addWidget(b_gen)
        row.addWidget(b_open)
        bar = QWidget()
        bar.setLayout(row)
        lay.addWidget(bar)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Experimento", "Informe", "Gráfica"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(110)
        lay.addWidget(self.log)

        self._cargar_exps()
        self.refrescar()
        return self

    def refrescar(self):
        self._cargar_exps()
        base = os.path.dirname(self.db_path())
        reps = sorted(_g.glob(os.path.join(base, "exp_*", "reporte.html")))
        self.table.setRowCount(len(reps))
        for i, p in enumerate(reps):
            exp = os.path.basename(os.path.dirname(p))
            gra = os.path.join(os.path.dirname(p), "comparacion.png")
            self.table.setItem(i, 0, QTableWidgetItem(exp))
            self.table.setItem(i, 1, QTableWidgetItem(p))
            self.table.setItem(i, 2, QTableWidgetItem(gra if os.path.isfile(gra) else "—"))

    def _cargar_exps(self):
        conn = self.conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.exp_combo.clear()
        for eid, t in rows:
            self.exp_combo.addItem(f"#{eid} {t}", eid)

    def _generar(self):
        eid = self.exp_combo.currentData()
        if not eid:
            return
        base = os.path.dirname(self.db_path())
        out = os.path.join(base, f"exp_{eid}", "reporte.html")
        r = generar_reporte_html(eid, self.db_path(), out)
        if r.get("ok"):
            QMessageBox.information(self, "Reportes", f"Generado: {r['path']}")
        else:
            QMessageBox.warning(self, "Reportes", r.get("error", "Error"))
        self.refrescar()

    def _abrir_carpeta(self):
        base = os.path.dirname(self.db_path())
        try:
            _sp.Popen(["explorer", base])
        except Exception as e:
            QMessageBox.warning(self, "Reportes", str(e))
