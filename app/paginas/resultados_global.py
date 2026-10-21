"""Página global de Resultados: selector de experimento para abrir su detalle."""
from PyQt6.QtWidgets import QVBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import Qt

from .base import PaginaBase


class PaginaResultados(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 20, 22, 20)
        h = QLabel("Resultados")
        h.setObjectName("H1")
        lay.addWidget(h)
        d = QLabel(
            "Selecciona un experimento para ver métricas, archivos y exportaciones. "
            "El detalle por experimento está en Experimentos → Abrir → Resultados."
        )
        d.setObjectName("Muted")
        d.setWordWrap(True)
        lay.addWidget(d)
        self.exp_combo = QComboBox()
        lay.addWidget(self.exp_combo)
        btn = QPushButton("Abrir resultados del experimento")
        btn.setObjectName("Primary")
        btn.clicked.connect(self._abrir)
        lay.addWidget(btn)
        lay.addStretch()
        self.refrescar()
        return self

    def refrescar(self):
        self._cargar_exps()

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
        for eid, title in rows:
            self.exp_combo.addItem(f"#{eid} {title}", eid)

    def _abrir(self):
        eid = self.exp_combo.currentData()
        if eid:
            self.lw.abrir_detalle(eid)
