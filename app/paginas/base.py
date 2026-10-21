"""Utilidades compartidas entre páginas de PhysiCell Lab."""
import os
import sqlite3
import logging

from PyQt6.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..nucleo import get_db_path
from ..xml_validator import validar_config

logger = logging.getLogger(__name__)


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


ESTILO_ESTADO = {
    "Sin configurar": "#A6A6A6", "Listo para ejecutar": "#84CC16",
    "En ejecución": "#F5B83D", "Completado": "#46A758", "Error": "#E5484D",
    "Sin XML": "#A6A6A6", "Válido": "#46A758", "Inválido": "#E5484D",
    "Inexistente": "#E5484D", "Sin motor": "#A6A6A6", "Listo": "#46A758",
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


class PaginaBase(QWidget):
    """Clase base para páginas de PhysiCell Lab.

    Proporciona acceso al LabWindow padre, la base de datos y utilidades
    comunes. Cada página construye su propio QWidget y expone métodos
    de refrescar que son llamados por LabWindow al navegar.
    """

    def __init__(self, lab_window):
        super().__init__()
        self.lw = lab_window  # referencia a LabWindow

    def db_path(self):
        return get_db_path()

    def conn(self):
        return sqlite3.connect(self.db_path())

    def refrescar(self):
        """Método llamado por LabWindow al entrar a la página. Sobreescribir si es necesario."""
        pass
