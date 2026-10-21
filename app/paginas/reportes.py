"""Página de Reportes: generación de informes HTML/PDF/CSV/JSON por experimento."""
import os
import sys
import glob as _g

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QTextEdit, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt

from .base import (
    PaginaBase, Seccion, Tarjeta, TablaBase, ESPACIO_M,
)
from ..reportes import (
    generar_reporte_html, exportar_reporte_pdf, exportar_runs_csv, exportar_runs_json
)
import subprocess as _sp


class PaginaReportes(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Reportes",
                "Informes HTML generados por experimento, con trazabilidad de configuración, "
                "réplicas y resultados.",
            )
        )

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

        self.table = TablaBase(["Experimento", "Informe", "Gráfica"])
        tarjeta = Tarjeta()
        tarjeta.add(self.table)
        lay.addWidget(tarjeta, 1)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(100)
        self.log.setObjectName("Muted")
        lay.addWidget(self.log)

        self._cargar_exps()
        self.refrescar()
        return self

    def refrescar(self):
        self._cargar_exps()
        base = os.path.dirname(self.db_path())
        reps = sorted(_g.glob(os.path.join(base, "exp_*", "reporte.html")))
        filas = []
        for p in reps:
            exp = os.path.basename(os.path.dirname(p))
            gra = os.path.join(os.path.dirname(p), "comparacion.png")
            filas.append([exp, p, gra if os.path.isfile(gra) else "—"])
        self.table.cargar(filas)

    def _cargar_exps(self):
        conn = self.conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            filas = cur.fetchall()
        except Exception:
            filas = []
        conn.close()
        self.exp_combo.clear()
        for eid, t in filas:
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
            if sys.platform.startswith("win"):
                os.startfile(base)
            elif sys.platform.startswith("darwin"):
                _sp.Popen(["open", base])
            else:
                _sp.Popen(["xdg-open", base])
        except Exception as e:
            QMessageBox.warning(self, "Reportes", str(e))
