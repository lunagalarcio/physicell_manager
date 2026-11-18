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
        b_gen_html = QPushButton("Generar informe (HTML)")
        b_gen_html.setObjectName("Primary")
        b_gen_html.clicked.connect(self._generar_html)
        b_gen_pdf = QPushButton("Generar informe (PDF)")
        b_gen_pdf.setObjectName("Secondary")
        b_gen_pdf.clicked.connect(self._generar_pdf)
        b_open = QPushButton("Abrir carpeta")
        b_open.setObjectName("Secondary")
        b_open.clicked.connect(self._abrir_carpeta)
        row.addWidget(self.exp_combo, 1)
        row.addWidget(b_gen_html)
        row.addWidget(b_gen_pdf)
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
        reps_pdf = sorted(_g.glob(os.path.join(base, "exp_*", "reporte.pdf")))
        filas = []
        for p in sorted(set(reps + reps_pdf)):
            exp = os.path.basename(os.path.dirname(p))
            gra = os.path.join(os.path.dirname(p), "comparacion.png")
            filas.append([exp, p, gra if os.path.isfile(gra) else "—"])
        self.table.cargar(filas)

    def _cargar_exps(self):
        from .. import servicios as SERV
        uid = self.lw.usuario_actual["id"] if self.lw.usuario_actual else None
        filas = SERV.listar_experimentos_servicio(self.db_path(), usuario_id=uid)
        self.exp_combo.clear()
        for fila in filas:
            eid, t = fila[0], fila[1]
            self.exp_combo.addItem(f"#{eid} {t}", eid)

    def _generar_html(self):
        """Genera el informe del experimento en formato HTML."""
        eid = self.exp_combo.currentData()
        if not eid:
            return
        base = os.path.dirname(self.db_path())
        exp_dir = os.path.join(base, f"exp_{eid}")
        r = generar_reporte_html(eid, self.db_path(), os.path.join(exp_dir, "reporte.html"))
        if r.get("ok"):
            QMessageBox.information(self, "Reportes", f"Generado: {r.get('path', r)}")
        else:
            QMessageBox.warning(self, "Reportes", r.get("error", "Error"))
        self.refreshar()

    def _generar_pdf(self):
        """Genera el informe del experimento en formato PDF a partir del HTML."""
        eid = self.exp_combo.currentData()
        if not eid:
            return
        base = os.path.dirname(self.db_path())
        exp_dir = os.path.join(base, f"exp_{eid}")
        html = os.path.join(exp_dir, "reporte.html")
        r = generar_reporte_html(eid, self.db_path(), html)
        if not r.get("ok"):
            QMessageBox.warning(self, "Reportes", r.get("error", "Error"))
            return
        pdf = os.path.join(exp_dir, "reporte.pdf")
        r2 = exportar_reporte_pdf(html, pdf)
        if r2.get("ok"):
            QMessageBox.information(self, "Reportes", f"Generado: {r2.get('path', r2)}")
        else:
            QMessageBox.warning(self, "Reportes", r2.get("error", "Error"))
        self.refreshar()

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
