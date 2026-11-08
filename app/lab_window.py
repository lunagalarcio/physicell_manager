#!/usr/bin/env python3
"""PhysiCell Lab: shell oscuro con navegación por secciones.

Contenedor ligero: delega cada página a un módulo en app/paginas/.
No modifica el motor PhysiCell; solo genera XML, lanza el binario y organiza salidas.

Incluye autenticación local integrada en la misma ventana principal:
si no hay sesión activa, se muestra la pantalla de login dentro del
mismo QStackedWidget (sin segunda ventana ni diálogo independiente).
"""
import os
import sys

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QButtonGroup, QStackedWidget, QSizePolicy
)
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtCore import Qt

from .theme_lab import LAB_QSS
from .nucleo import init_database, get_db_path
from .paginas.base import PaginaBase
from .paginas.resumen import PaginaResumen
from .paginas.experimentos import PaginaExperimentos
from .paginas.configuraciones import PaginaConfiguraciones
from .paginas.ejecuciones import PaginaEjecuciones
from .paginas.resultados_global import PaginaResultados
from .paginas.comparacion_global import PaginaComparacion
from .paginas.reportes import PaginaReportes
from .paginas.preferencias import PaginaPreferencias
from .paginas.detalle import PaginaDetalle
from .paginas.login import PaginaLogin
from . import servicios as SERV


class LabWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PhysiCell Manager")
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "assets", "physicell_lab.png")))
        self.setMinimumSize(1200, 800)
        self.setStyleSheet(LAB_QSS)
        self.current_experiment_id = None
        self.worker = None
        self._last_exe = ""
        self.usuario_actual = None
        self.auth_service = SERV.AuthService(get_db_path())

        central = QWidget()
        central.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---- QStackedWidget principal: Login vs Aplicación ----
        self.stack_principal = QStackedWidget()
        self.stack_principal.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self.stack_principal)

        # =====================================================
        # PÁGINA 0: Login (misma ventana, sin segunda ventana)
        # =====================================================
        self.pagina_login = PaginaLogin(self)
        self.pagina_login.build()
        self.stack_principal.addWidget(self.pagina_login)

        # =====================================================
        # PÁGINA 1: Aplicación principal (sidebar + páginas)
        # =====================================================
        self.app_contenedor = QWidget()
        self.app_contenedor.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        app_lay = QHBoxLayout(self.app_contenedor)
        app_lay.setContentsMargins(0, 0, 0, 0)
        app_lay.setSpacing(0)

        # ---- sidebar ----
        self.side = QWidget()
        self.side.setObjectName("SideBar")
        self.side.setFixedWidth(212)
        self.side.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        sl = QVBoxLayout(self.side)
        sl.setContentsMargins(14, 18, 14, 18)
        sl.setSpacing(6)
        brand = QLabel("PhysiCell Manager")
        brand.setObjectName("Brand")
        sl.addWidget(brand)
        sub = QLabel("Simulación celular")
        sub.setObjectName("BrandSub")
        sl.addWidget(sub)
        sl.addSpacing(12)
        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_btns = {}
        self._secciones = [
            "Resumen", "Experimentos", "Configuraciones", "Ejecuciones",
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
        self.btn_logout = QPushButton("Cerrar sesión")
        self.btn_logout.setObjectName("Secondary")
        self.btn_logout.setFixedHeight(32)
        self.btn_logout.clicked.connect(self.cerrar_sesion)
        sl.addWidget(self.btn_logout)
        self.btn_logout.setVisible(False)

        app_lay.addWidget(self.side)

        # ---- stack de páginas internas ----
        self.stack = QStackedWidget()
        self.stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        app_lay.addWidget(self.stack, 1)

        self.stack_principal.addWidget(self.app_contenedor)

        # ---- páginas internas ----
        self.paginas = {}
        self._seccion_widget = {}
        for nombre, cls in [
            ("Resumen", PaginaResumen),
            ("Experimentos", PaginaExperimentos),
            ("Configuraciones", PaginaConfiguraciones),
            ("Ejecuciones", PaginaEjecuciones),
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
        # Siempre inicia mostrando el login
        self._mostrar_login()

    # ---------- autenticación ----------

    def _mostrar_login(self):
        """Muestra la pantalla de login en la misma ventana."""
        self.usuario_actual = None
        self.auth_service._usuario_actual = None
        self.stack_principal.setCurrentWidget(self.pagina_login)

    def _autenticado(self, usuario):
        """Transiciona a la interfaz principal tras un login exitoso."""
        self.usuario_actual = usuario
        self.auth_service._usuario_actual = usuario
        self.btn_logout.setVisible(True)
        self.stack_principal.setCurrentWidget(self.app_contenedor)
        self.ir("Resumen")

    def cerrar_sesion(self):
        """Cierra la sesión y regresa a la pantalla de login en la misma ventana."""
        self.auth_service.logout()
        self.usuario_actual = None
        self.current_experiment_id = None
        self.btn_logout.setVisible(False)
        self.stack_principal.setCurrentWidget(self.pagina_login)
        # Limpiar campos del login
        self.pagina_login.edit_user.clear()
        self.pagina_login.edit_pass.clear()
        self.pagina_login.lbl_error.setVisible(False)

    # ---------- navegación interna ----

    def ir(self, name):
        if name not in self._secciones:
            return
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

        from .. import simulador as SIM
        from .nucleo import get_db_path
        conn = sqlite3.connect(get_db_path())

        for eid in experiment_ids:
            try:
                row = SIM.obtener_experimento(conn, eid)
                title = row[1] if row else f"Experimento {eid}"
                cfg = row[4] if row else ""
            except Exception:
                title = f"Experimento {eid}"
                cfg = ""

            try:
                stats = SIM.estadisticas_experimento(conn, eid)
                total = stats["total"]
                comp = stats["completadas"]
                run = stats["en_curso"]
                fail = stats["falladas"]
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

        conn.close()
        dlg.exec()

    def refrescar_detalle(self):
        if self.current_experiment_id is not None:
            self.pagina_detalle.build(self.current_experiment_id)

    # ---------- delegados (compatibilidad con código externo) ----------
    def refrescar_resumen(self):
        self.paginas["Resumen"].refrescar()

    def refrescar_exps(self):
        self.paginas["Experimentos"].refrescar()

    def refrescar_cmp_page(self):
        self.paginas["Comparación"].refrescar()

    def refrescar_reportes(self):
        self.paginas["Reportes"].refrescar()
