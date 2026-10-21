"""Página global de Ejecuciones: historial de réplicas de todos los experimentos."""
from PyQt6.QtWidgets import QVBoxLayout, QTableWidgetItem

from .base import (
    PaginaBase, Seccion, Tarjeta, TablaBase, ESPACIO_M,
)
from .. import simulador as SIM


class PaginaEjecuciones(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Ejecuciones",
                "Historial de réplicas de todos los experimentos, con estado y salida.",
            )
        )

        self.table = TablaBase(
            ["Experimento", "Run", "Estado", "Inicio", "Fin", "Salida"]
        )
        tarjeta = Tarjeta()
        tarjeta.add(self.table)
        lay.addWidget(tarjeta, 1)

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
            filas = cur.fetchall()
        except Exception:
            filas = []
        conn.close()
        self.table.cargar(filas)
