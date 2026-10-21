#!/usr/bin/env python3
"""PhysiCell Lab: shell oscuro con navegación por secciones.

Contenedor ligero: delega cada página a un módulo en app/paginas/.
No modifica el motor PhysiCell; solo genera XML, lanza el binario y organiza salidas.
"""
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QStackedWidget
)
from .theme_lab import LAB_QSS
from .nucleo import init_database
from .paginas.base import PaginaBase
from .paginas.resumen import PaginaResumen
from .paginas.experimentos import PaginaExperimentos
from .paginas.configuraciones import PaginaConfiguraciones
from .paginas.ejecuciones import PaginaEjecuciones
from .paginas.visualizacion_global import PaginaVisualizacion
from .paginas.resultados_global import PaginaResultados
from .paginas.comparacion_global import PaginaComparacion
from .paginas.reportes import PaginaReportes
from .paginas.preferencias import PaginaPreferencias
from .paginas.detalle import PaginaDetalle


class LabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhysiCell Lab")
        self.setMinimumSize(1180, 760)
        self.setStyleSheet(LAB_QSS)
        self.current_experiment_id = None
        self.worker = None
        self._last_exe = ""

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- sidebar ----
        side = QWidget()
        side.setObjectName("SideBar")
        side.setFixedWidth(212)
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 18, 14, 18)
        sl.setSpacing(6)
        brand = QLabel("PhysiCell Lab")
        brand.setObjectName("Brand")
        sl.addWidget(brand)
        sub = QLabel("Simulación celular")
        sub.setObjectName("BrandSub")
        sl.addWidget(sub)
        sl.addSpacing(10)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns = {}
        self.stack = QStackedWidget()
        self._secciones = [
            "Resumen", "Experimentos", "Configuraciones", "Ejecuciones", "Visualización",
            "Resultados", "Comparación", "Reportes", "Preferencias",
        ]
        for i, name in enumerate(self._secciones):
            b = QPushButton(name)
            b.setObjectName("NavBtn")
            b.setCheckable(True)
            b.clicked.connect(lambda _=False, n=name: self.ir(n))
            self.nav_group.addButton(b, i)
            sl.addWidget(b)
            self.nav_btns[name] = b
        sl.addStretch()
        root.addWidget(side)
        root.addWidget(self.stack, 1)

        # ---- páginas ----
        self.paginas = {}
        self._seccion_widget = {}
        for nombre, cls in [
            ("Resumen", PaginaResumen),
            ("Experimentos", PaginaExperimentos),
            ("Configuraciones", PaginaConfiguraciones),
            ("Ejecuciones", PaginaEjecuciones),
            ("Visualización", PaginaVisualizacion),
            ("Resultados", PaginaResultados),
            ("Comparación", PaginaComparacion),
            ("Reportes", PaginaReportes),
            ("Preferencias", PaginaPreferencias),
        ]:
            pagina = cls(self)
            pagina.build()
            self.paginas[nombre] = pagina
            idx = self.stack.addWidget(pagina)
            self._seccion_widget[nombre] = idx

        # detalle (se construye bajo demanda con el experimento actual)
        self.pagina_detalle = PaginaDetalle(self)
        self.pg_detalle_idx = self.stack.addWidget(self.pagina_detalle)

        init_database()
        self.ir("Resumen")

    # ---------- navegación ----------
    def ir(self, name):
        idx = {n: i for i, n in enumerate(self._secciones)}[name]
        self.nav_btns[name].setChecked(True)
        pagina = self.paginas.get(name)
        if pagina and hasattr(pagina, "refrescar"):
            pagina.refrescar()
        self.stack.setCurrentIndex(idx)

    def abrir_detalle(self, eid):
        self.current_experiment_id = eid
        self.pagina_detalle.build(eid)
        self.stack.setCurrentIndex(self.pg_detalle_idx)
        for b in self.nav_btns.values():
            b.setChecked(False)
        self.nav_btns["Experimentos"].setChecked(True)

    def refrescar_detalle(self):
        if self.current_experiment_id is not None:
            self.pagina_detalle.build(self.current_experiment_id)

    # ---------- delegados (compatibilidad con código externo) ----------
    def refrescar_resumen(self):
        self.paginas["Resumen"].refrescar()

    def refrescar_exps(self):
        self.paginas["Experimentos"].refrescar()

    def refrescar_configs(self):
        self.paginas["Configuraciones"].refrescar()

    def refrescar_ejec(self):
        self.paginas["Ejecuciones"].refrescar()

    def refrescar_res_page(self):
        self.paginas["Resultados"].refrescar()

    def refrescar_cmp_page(self):
        self.paginas["Comparación"].refrescar()

    def refrescar_reportes(self):
        self.paginas["Reportes"].refrescar()
