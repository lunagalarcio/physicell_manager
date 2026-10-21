"""Página global de Visualización: visor 2D/3D por experimento y réplica."""
import os
import glob as _g

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QComboBox, QWidget
)
from PyQt6.QtCore import Qt

from .base import (
    PaginaBase, Seccion, Tarjeta, ESPACIO_M,
)
from ..visor_widget import VisorPhysiCell
from .. import simulador as SIM


class PaginaVisualizacion(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Visualización",
                "Navega por los snapshots y resultados de las réplicas de un experimento.",
            )
        )

        # Barra de selección
        top = QHBoxLayout()
        self.exp_combo = QComboBox()
        self.rep_combo = QComboBox()
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Ambos", "2D", "3D"])
        btn_cargar = QPushButton("Cargar")
        btn_cargar.setObjectName("Primary")
        btn_cargar.clicked.connect(self._cargar)
        top.addWidget(QLabel("Experimento:"))
        top.addWidget(self.exp_combo, 1)
        top.addWidget(QLabel("Réplica:"))
        top.addWidget(self.rep_combo, 1)
        top.addWidget(QLabel("Vista:"))
        top.addWidget(self.mode_combo)
        top.addWidget(btn_cargar)
        bar = QWidget()
        bar.setLayout(top)
        lay.addWidget(bar)

        # Visor
        self.visor = VisorPhysiCell(output_dir="")
        tarjeta = Tarjeta()
        tarjeta.add(self.visor)
        lay.addWidget(tarjeta, 1)

        self.mode_combo.currentTextChanged.connect(self._modo)
        self.exp_combo.currentIndexChanged.connect(lambda _: self._cargar_reps())
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
        self._cargar_reps()

    def _cargar_reps(self):
        eid = self.exp_combo.currentData()
        self.rep_combo.clear()
        if eid is None:
            return
        for lbl, d in self._salidas_replicas_global(eid):
            self.rep_combo.addItem(lbl, d)

    def _salidas_replicas_global(self, eid):
        conn = self.conn()
        rows = SIM.listar_runs(conn, eid)
        conn.close()
        outs = []
        for _id, rnum, st, _s, _e, od in rows:
            if od and os.path.isdir(od):
                for d in (os.path.join(od, "output"), od):
                    if _g.glob(os.path.join(d, "snapshot*.svg")) or _g.glob(os.path.join(d, "*_cells.mat")):
                        outs.append((f"Réplica {rnum} ({st})", d))
                        break
        outs.append(("Salida global PhysiCell/output", ""))
        return outs

    def _cargar(self):
        d = self.rep_combo.currentData()
        if d:
            self.visor.set_output_dir(d)

    def _modo(self, modo):
        try:
            if modo == "2D":
                self.visor.ax2.set_visible(True)
                self.visor.ax3.set_visible(False)
            elif modo == "3D":
                self.visor.ax2.set_visible(False)
                self.visor.ax3.set_visible(True)
            else:
                self.visor.ax2.set_visible(True)
                self.visor.ax3.set_visible(True)
            self.visor.canvas.draw()
        except Exception:
            pass
