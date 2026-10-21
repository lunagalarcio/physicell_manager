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
from PyQt6.QtGui import QFont

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
        self.setMinimumSize(1200, 800)
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
        sl.addSpacing(12)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns = {}
        self.stack = QStackedWidget()
        self._secciones = [
            "Resumen", "Experimentos", "Configuraciones", "Ejecuciones", "Visualización",
            "Resultados", "Comparación", "Reportes", "Ajustes",
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
            ("Ajustes", PaginaPreferencias),
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

    def abrir_comparacion(self, experiment_ids):
        """Abre un diálogo para comparar múltiples experimentos entre sí."""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QFrame
        from PyQt6.QtCore import Qt
        import sqlite3

        dlg = QDialog(self)
        dlg.setWindowTitle("Comparación de experimentos")
        dlg.setMinimumWidth(700)
        dlg.setMinimumHeight(400)
        lay = QVBoxLayout(dlg)
        lay.setContentsMargins(22, 20, 22, 20)
        lay.setSpacing(16)

        h = QLabel("Comparación entre experimentos")
        h.setObjectName("H1")
        lay.addWidget(h)

        sub = QLabel("Selecciona un experimento para abrir su detalle y ver los resultados.")
        sub.setObjectName("Muted")
        sub.setWordWrap(True)
        lay.addWidget(sub)

        from .nucleo import get_db_path
        conn = sqlite3.connect(get_db_path())
        cur = conn.cursor()

        for eid in experiment_ids:
            try:
                cur.execute("SELECT title, config_xml_path FROM experiments WHERE id=?", (eid,))
                row = cur.fetchone()
                title = row[0] if row else f"Experimento {eid}"
                cfg = row[1] if row else ""
            except Exception:
                title = f"Experimento {eid}"
                cfg = ""

            try:
                cur.execute(
                    "SELECT COUNT(*), SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END), "
                    "SUM(CASE WHEN status='running' THEN 1 ELSE 0 END), "
                    "SUM(CASE WHEN status IN ('failed','cancelled') THEN 1 ELSE 0 END) "
                    "FROM runs WHERE experiment_id=?",
                    (eid,),
                )
                stats = cur.fetchone()
                total = stats[0] or 0
                comp = stats[1] or 0
                run = stats[2] or 0
                fail = stats[3] or 0
            except Exception:
                total = comp = run = fail = 0

            fila = QFrame()
            fila.setObjectName("Card")
            fila_lay = QHBoxLayout(fila)
            fila_lay.setContentsMargins(16, 12, 16, 12)
            fila_lay.setSpacing(12)

            lbl_info = QLabel(
                f"<b>#{eid} {title}</b><br>"
                f"<span style='color:#A6A6A6'>Réplicas: {total} | "
                f"Completadas: {comp} | En curso: {run} | Fallidas: {fail}</span>"
            )
            lbl_info.setWordWrap(True)
            fila_lay.addWidget(lbl_info, 1)

            btn_abrir = QPushButton("Abrir detalle")
            btn_abrir.setObjectName("Primary")
            btn_abrir.clicked.connect(lambda _=False, e=eid: (dlg.accept(), self.abrir_detalle(e)))
            fila_lay.addWidget(btn_abrir)

            lay.addWidget(fila)

        conn.close()

        lay.addStretch()

        btn_cerrar = QPushButton("Cerrar")
        btn_cerrar.setObjectName("Secondary")
        btn_cerrar.clicked.connect(dlg.reject)
        lay.addWidget(btn_cerrar)

        dlg.exec()

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
