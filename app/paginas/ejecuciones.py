"""Página global de Ejecuciones: historial de réplicas de todos los experimentos."""
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QTableWidget, QTableWidgetItem, QHeaderView
from PyQt6.QtCore import Qt

from .base import PaginaBase
from .. import simulador as SIM


class PaginaEjecuciones(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("Ejecuciones")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel("Historial de réplicas de todos los experimentos, con estado y salida.")
        d.setObjectName("Muted")
        lay.addWidget(d)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels(["Experimento", "Run", "Estado", "Inicio", "Fin", "Salida"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        lay.addWidget(self.table, 1)
        self.refrescar()
        return self

    def refrescar(self):
        conn = self.conn()
        cur = conn.cursor()
        try:
            cur.execute(
                "SELECT e.title, r.run_number, r.status, r.start_time, r.end_time, r.output_dir "
                "FROM runs r JOIN experiments e ON e.id=r.experiment_id ORDER BY r.start_time DESC LIMIT 200"
            )
            rows = cur.fetchall()
        except Exception:
            rows = []
        conn.close()
        self.table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate([str(x or "") for x in r]):
                self.table.setItem(i, j, QTableWidgetItem(val))
