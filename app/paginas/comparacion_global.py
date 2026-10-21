"""Página global de Comparación: selector de experimento para abrir su detalle."""
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QComboBox

from .base import (
    PaginaBase, Seccion, Tarjeta, ESPACIO_M,
)


class PaginaComparacion(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Comparación",
                "Compara réplicas dentro de un experimento. "
                "Abre el detalle para la gráfica dedicada.",
            )
        )

        self.exp_combo = QComboBox()
        tarjeta = Tarjeta()
        tarjeta.add(self.exp_combo)

        btn = QPushButton("Abrir comparación del experimento")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._abrir)
        tarjeta.add(btn)

        lay.addWidget(tarjeta)
        lay.addStretch()

        self._cargar_exps()
        return self

    def refrescar(self):
        self._cargar_exps()

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
        for eid, title in filas:
            self.exp_combo.addItem(f"#{eid} {title}", eid)

    def _abrir(self):
        eid = self.exp_combo.currentData()
        if eid:
            self.lw.abrir_detalle(eid)
