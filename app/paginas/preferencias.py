"""Página de Preferencias: rutas del motor PhysiCell y suite de regresión."""
import os
import subprocess as _sp
import sys

from PyQt6.QtWidgets import (
    QVBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox
)
from PyQt6.QtCore import Qt

from .base import (
    PaginaBase, Seccion, Tarjeta, get_db_path, ESPACIO_M,
)
from ..motor_physicell import MotorPhysiCell
from ..theme_lab import LIMA


class PaginaPreferencias(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(Seccion("Preferencias", "Rutas del motor PhysiCell y utilidades de calidad."))

        self.root_edit = QLineEdit("")
        self.root_edit.setPlaceholderText("Carpeta raíz de PhysiCell (motor externo)")
        tarjeta = Tarjeta()
        tarjeta.add(QLabel("Raíz de PhysiCell (motor, no se modifica):"))
        tarjeta.add(self.root_edit)

        self.bin_edit = QLineEdit(getattr(self.lw, "_last_exe", "") or "")
        self.bin_edit.setPlaceholderText(".../project.exe por defecto para nuevas ejecuciones")
        tarjeta.add(QLabel("Binario por defecto:"))
        tarjeta.add(self.bin_edit)

        b_det = QPushButton("Detectar binario en la raíz")
        b_det.setObjectName("Secondary")
        b_det.clicked.connect(self._detectar_bin)
        tarjeta.add(b_det)

        lay.addWidget(tarjeta)

        info = QLabel(
            f"Datos por usuario: {get_db_path()}\n"
            "Tema: oscuro PhysiCell Lab, coherente en tablas, formularios y gráficos.\n"
            "El motor PhysiCell es externo. La app solo genera XML, lanza el binario y organiza salidas."
        )
        info.setObjectName("Muted")
        info.setWordWrap(True)
        lay.addWidget(info)

        lay.addWidget(QLabel("Calidad:"))
        self.test_log = QTextEdit()
        self.test_log.setReadOnly(True)
        self.test_log.setMaximumHeight(140)
        lay.addWidget(self.test_log)

        b_tests = QPushButton("Ejecutar pruebas de regresión")
        b_tests.setObjectName("Secondary")
        b_tests.setToolTip("Corre tests/test_regresion.py y muestra el resultado")
        b_tests.clicked.connect(self._ejecutar_tests)
        lay.addWidget(b_tests)

        lay.addStretch()
        return self

    def _detectar_bin(self):
        m = MotorPhysiCell(self.root_edit.text().strip())
        b = m.resolver_binario()
        if b:
            self.bin_edit.setText(b)
            self.lw._last_exe = b
            QMessageBox.information(self, "Configuración", f"Binario: {b}")
        else:
            QMessageBox.warning(self, "Configuración", "No se encontró project.exe en la raíz indicada.")

    def _ejecutar_tests(self):
        t = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "tests", "test_regresion.py",
        )
        try:
            p = _sp.run([sys.executable, t], capture_output=True, text=True, timeout=300)
            out = (p.stdout or "") + ("\n" + p.stderr if p.stderr else "")
            self.test_log.setPlainText(out[-3000:])
            if p.returncode == 0:
                QMessageBox.information(self, "Pruebas", "Regresión OK. Ver detalle en el panel.")
            else:
                QMessageBox.warning(self, "Pruebas", "Hay fallos. Ver detalle en el panel.")
        except Exception as e:
            QMessageBox.warning(self, "Pruebas", str(e))
