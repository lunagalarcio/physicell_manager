"""Utilidades compartidas entre páginas de PhysiCell Lab.

Proporciona componentes de UI consistentes (sección, tarjeta, badge, diálogo,
formulario, tabla) para que todas las pantallas tengan el mismo aspecto y
espaciado.
"""
import os
import sqlite3
import logging

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame, QPushButton,
    QDialog, QDialogButtonBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy, QSpacerItem
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..nucleo import get_db_path
from ..xml_validator import validar_config
from ..theme_lab import (
    FONDO, LATERAL, TARJETA, BORDE, TEXTO, TEXTO2, LIMA, ROJO,
    ESPACIO_S, ESPACIO_M, ESPACIO_L, ESPACIO_XL,
    RADIO_S, RADIO_M, RADIO_L, TAM_BASE, TAM_H1, TAM_H2, TAM_MENOR,
    ESTILO_ESTADO, COLOR_SEVERIDAD,
)

logger = logging.getLogger(__name__)


# ---------- Utilidades de datos ----------

def xml_estado(path):
    if not path or not str(path).strip():
        return ("Sin XML", "none")
    if not os.path.isfile(path):
        return ("Inexistente", "error")
    v = validar_config(path)
    if v.get("ok"):
        return ("Válido", "ok")
    return ("Inválido", "error")


def exe_estado(path):
    if not path or not str(path).strip():
        return ("Sin motor", "none")
    if os.path.isfile(path):
        return ("Listo", "ok")
    return ("Inexistente", "error")


ESTADO_BOTON = {
    "En ejecución": "Primary",
    "Completado": "Secondary",
    "Error": "Danger",
    "Sin configurar": "Secondary",
    "Listo para ejecutar": "Secondary",
}


def exp_estado(n_runs, n_running, n_failed, n_completed, xml_ok):
    if n_running > 0:
        return "En ejecución"
    if n_failed > 0:
        return "Error"
    if n_completed > 0:
        return "Completado"
    if n_runs > 0:
        return "Completado"
    if xml_ok:
        return "Listo para ejecutar"
    return "Sin configurar"


# ---------- Componentes de UI ----------

class PaginaBase(QWidget):
    """Clase base para páginas de PhysiCell Lab."""

    def __init__(self, lab_window):
        super().__init__()
        self.lw = lab_window
        self.setObjectName("PaginaBase")

    def db_path(self):
        return get_db_path()

    def conn(self):
        return sqlite3.connect(self.db_path())

    def refrescar(self):
        """Método llamado por LabWindow al entrar a la página."""
        pass


class Seccion(QWidget):
    """Encabezado consistente de una sección: título, descripción y barra de acciones."""

    def __init__(self, titulo, subtitulo="", acciones=None, padre=None):
        super().__init__(padre)
        self.setObjectName("Seccion")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(ESPACIO_S)

        if titulo:
            h = QLabel(titulo)
            h.setObjectName("H1")
            lay.addWidget(h)
        if subtitulo:
            d = QLabel(subtitulo)
            d.setObjectName("Muted")
            d.setWordWrap(True)
            lay.addWidget(d)

        if acciones:
            bar = QHBoxLayout()
            for accion in acciones:
                bar.addWidget(accion)
            bar.addStretch()
            contenedor = QWidget()
            contenedor.setLayout(bar)
            lay.addWidget(contenedor)

        lay.addSpacing(ESPACIO_M)


class Tarjeta(QFrame):
    """Tarjeta consistente con borde, radio y padding estándar."""

    def __init__(self, elevado=False, padre=None):
        super().__init__(padre)
        self.setObjectName("CardElevada" if elevado else "Card")
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(ESPACIO_L, ESPACIO_L, ESPACIO_L, ESPACIO_L)
        self._lay.setSpacing(ESPACIO_M)

    def add(self, widget):
        self._lay.addWidget(widget)

    def addStretch(self):
        self._lay.addStretch()

    def layout_interno(self):
        return self._lay


class BadgeEstado(QLabel):
    """Etiqueta de estado con color consistente."""

    def __init__(self, texto, clave="none", padre=None):
        super().__init__(texto, padre)
        color = ESTILO_ESTADO.get(clave, TEXTO2)
        self.setStyleSheet(
            f"color: {color}; font-weight: 700; font-size: {TAM_MENOR}px; "
            f"padding: 3px 8px; border-radius: 4px;"
        )


class DialogoBase(QDialog):
    """Diálogo modal consistente con encabezado, cuerpo y botones estándar."""

    def __init__(self, titulo, padre=None, ancho=620, alto=420):
        super().__init__(padre)
        self.setWindowTitle(titulo)
        self.setMinimumSize(ancho, alto)
        self.setModal(True)
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(ESPACIO_L, ESPACIO_L, ESPACIO_L, ESPACIO_L)
        self._lay.setSpacing(ESPACIO_M)

    def add(self, widget):
        self._lay.addWidget(widget)

    def addStretch(self):
        self._lay.addStretch()

    def botones_estandar(self, aceptar="Aceptar", cancelar="Cancelar"):
        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText(aceptar)
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText(cancelar)
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("Secondary")
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        self._lay.addWidget(btns)
        return btns


class CampoFormulario(QWidget):
    """Etiqueta + campo de entrada con estilo consistente."""

    def __init__(self, etiqueta, widget, padre=None):
        super().__init__(padre)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(ESPACIO_S)
        lbl = QLabel(etiqueta)
        lbl.setFixedWidth(150)
        lbl.setObjectName("Muted")
        lay.addWidget(lbl)
        lay.addWidget(widget, 1)


class TablaBase(QTableWidget):
    """Tabla con estilo oscuro consistente, encabezados y selección unificados."""

    def __init__(self, columnas, padre=None):
        super().__init__(padre)
        self.setColumnCount(len(columnas))
        self.setHorizontalHeaderLabels(columnas)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().hide()
        self.setAlternatingRowColors(False)
        self.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)

    def cargar(self, filas):
        """Carga filas (lista de listas/tuplas) en la tabla."""
        self.setRowCount(len(filas))
        for i, fila in enumerate(filas):
            for j, valor in enumerate(fila):
                item = QTableWidgetItem(str(valor or ""))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.setItem(i, j, item)

    def vaciar(self):
        self.setRowCount(0)


class Separador(QFrame):
    """Línea divisoria sutil entre secciones."""

    def __init__(self, padre=None):
        super().__init__(padre)
        self.setObjectName("Separador")
        self.setFixedHeight(1)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
