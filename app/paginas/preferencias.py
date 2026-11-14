"""Página de Ajustes: rutas del motor PhysiCell y suite de regresión."""
import os
import subprocess as _sp
import sys

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTextEdit, QMessageBox, QWidget
)
from PyQt6.QtCore import Qt

from .base import (
    PaginaBase, Seccion, Tarjeta, get_db_path, ESPACIO_M,
)
from ..nucleo import (
    cargar_preferencias, guardar_preferencias,
)
from ..motor_physicell import MotorPhysiCell
from ..theme_lab import LIMA


class PaginaPreferencias(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(Seccion("Ajustes", "Rutas del motor PhysiCell y utilidades de calidad."))

        prefs = cargar_preferencias()
        motor_prefs = prefs.get("motor") if isinstance(prefs.get("motor"), dict) else {}
        self.root_edit = QLineEdit(motor_prefs.get("raiz") or "")
        self.root_edit.setPlaceholderText("Carpeta raíz de PhysiCell (motor externo)")
        tarjeta = Tarjeta()
        tarjeta.add(QLabel("Raíz de PhysiCell (motor, no se modifica):"))
        tarjeta.add(self.root_edit)

        self.bin_edit = QLineEdit(motor_prefs.get("binario") or getattr(self.lw, "_last_exe", "") or "")
        self.bin_edit.setPlaceholderText(".../project.exe por defecto para nuevas ejecuciones")
        tarjeta.add(QLabel("Binario por defecto:"))
        tarjeta.add(self.bin_edit)

        b_det = QPushButton("Detectar binario en la raíz")
        b_det.setObjectName("Secondary")
        b_det.clicked.connect(self._detectar_bin)
        b_guardar = QPushButton("Guardar preferencias")
        b_guardar.setObjectName("Primary")
        b_guardar.clicked.connect(self._guardar)
        row_b = QHBoxLayout()
        row_b.addWidget(b_det)
        row_b.addWidget(b_guardar)
        row_b.addStretch()
        c = QWidget()
        c.setLayout(row_b)
        tarjeta.add(c)

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
            # Persistir de inmediato la preferencia detectada
            prefs = cargar_preferencias()
            motor = prefs.get("motor") if isinstance(prefs.get("motor"), dict) else {}
            motor["raiz"] = self.root_edit.text().strip()
            motor["binario"] = b
            prefs["motor"] = motor
            try:
                guardar_preferencias(prefs)
            except Exception as e:
                QMessageBox.warning(self, "Configuración", f"No se pudo guardar la preferencia: {e}")
            QMessageBox.information(self, "Configuración", f"Binario: {b}")
        else:
            QMessageBox.warning(self, "Configuración", "No se encontró project.exe en la raíz indicada.")

    def _guardar(self):
        """Guarda las preferencias de motor (raíz y binario) en el archivo de datos."""
        prefs = cargar_preferencias()
        motor = prefs.get("motor") if isinstance(prefs.get("motor"), dict) else {}
        motor["raiz"] = self.root_edit.text().strip()
        motor["binario"] = self.bin_edit.text().strip()
        prefs["motor"] = motor
        try:
            guardar_preferencias(prefs)
        except Exception as e:
            QMessageBox.warning(self, "Ajustes", f"No se pudo guardar las preferencias:\n{e}")
            return
        if self.bin_edit.text().strip():
            self.lw._last_exe = self.bin_edit.text().strip()
        QMessageBox.information(self, "Ajustes", "Preferencias guardadas correctamente.")

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
