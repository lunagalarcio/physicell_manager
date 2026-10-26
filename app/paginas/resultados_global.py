"""Página global de Resultados: selector de experimento para abrir su detalle."""
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QComboBox

from .base import (
    PaginaBase, Seccion, Tarjeta, ESPACIO_M,
)


class PaginaResultados(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Resultados",
                "Selecciona un experimento para ver métricas, archivos y exportaciones. "
                "El detalle por experimento está en Experimentos → Abrir → Resultados.",
            )
        )

        self.exp_combo = QComboBox()
        tarjeta = Tarjeta()
        tarjeta.add(self.exp_combo)

        btn = QPushButton("Abrir resultados del experimento")
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
        from .. import servicios as SERV
        uid = self.lw.usuario_actual["id"] if self.lw.usuario_actual else None
        filas = SERV.listar_experimentos_servicio(self.db_path(), usuario_id=uid)
        self.exp_combo.clear()
        for eid, title in filas:
            self.exp_combo.addItem(f"#{eid} {title}", eid)

    def _abrir(self):
        eid = self.exp_combo.currentData()
        if eid:
            self.lw.abrir_detalle(eid)
