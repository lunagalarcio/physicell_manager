"""Página de Configuraciones: biblioteca de XML de PhysiCell."""
import os
import glob as _g

from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QFileDialog, QMessageBox, QDialog,
    QPlainTextEdit, QDialogButtonBox, QWidget, QComboBox
)
from PyQt6.QtCore import Qt

from .base import (
    PaginaBase, Seccion, Tarjeta, TablaBase, xml_estado, DialogoBase,
    ESPACIO_M, ESPACIO_L,
)
from ..config_manager import importar_config, leer_texto, guardar_texto
from ..xml_validator import validar_config as vc


class PaginaConfiguraciones(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Configuraciones",
                "Biblioteca de XML de PhysiCell: importa, edita y valida sin listas "
                "rígidas de parámetros. Asocia un XML a un experimento o escenario.",
            )
        )

        # Barra de acciones
        row = QHBoxLayout()
        b_imp = QPushButton("Importar XML…")
        b_imp.setObjectName("Primary")
        b_imp.clicked.connect(self._importar)
        b_new = QPushButton("Nuevo desde plantilla")
        b_new.setObjectName("Secondary")
        b_new.clicked.connect(self._nuevo)
        b_ref = QPushButton("Actualizar")
        b_ref.setObjectName("Secondary")
        b_ref.clicked.connect(self.refrescar)
        row.addWidget(b_imp)
        row.addWidget(b_new)
        row.addWidget(b_ref)
        row.addStretch()
        bar = QWidget()
        bar.setLayout(row)
        lay.addWidget(bar)

        # Tabla de archivos
        self.table = TablaBase(["Archivo", "Estado", "Tamaño"])
        tarjeta = Tarjeta()
        tarjeta.add(self.table)
        lay.addWidget(tarjeta, 1)

        # Botones secundarios
        row2 = QHBoxLayout()
        b_ed = QPushButton("Editar…")
        b_ed.setObjectName("Secondary")
        b_ed.clicked.connect(self._editar)
        b_val = QPushButton("Validar")
        b_val.setObjectName("Secondary")
        b_val.clicked.connect(self._validar)
        b_as = QPushButton("Asociar a experimento…")
        b_as.setObjectName("Secondary")
        b_as.clicked.connect(self._asociar)
        row2.addWidget(b_ed)
        row2.addWidget(b_val)
        row2.addWidget(b_as)
        row2.addStretch()
        bar2 = QWidget()
        bar2.setLayout(row2)
        lay.addWidget(bar2)

        self.refrescar()
        return self

    def _dir(self):
        d = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config")
        os.makedirs(d, exist_ok=True)
        return os.path.abspath(d)

    def _sel(self):
        r = self.table.currentRow()
        if r < 0:
            return ""
        it = self.table.item(r, 0)
        return it.text() if it else ""

    def refrescar(self):
        files = sorted(_g.glob(os.path.join(self._dir(), "*.xml")))
        self.table.cargar([
            [p, xml_estado(p)[0], str(os.path.getsize(p)) if os.path.isfile(p) else "?"]
            for p in files
        ])

    def _importar(self):
        src, _ = QFileDialog.getOpenFileName(self, "Importar XML", "", "XML (*.xml)")
        if not src:
            return
        r = importar_config(src, self._dir())
        if r.get("ok"):
            QMessageBox.information(self, "Configuraciones", f"Importado: {r['path']}")
        else:
            QMessageBox.warning(self, "Configuraciones", r.get("error", "Error"))
        self.refrescar()

    def _nuevo(self):
        import shutil as _s
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "config", "PhysiCell_settings.xml")
        dst = os.path.join(self._dir(), "nueva_config.xml")
        n = 1
        while os.path.isfile(dst):
            n += 1
            dst = os.path.join(self._dir(), f"nueva_config_{n}.xml")
        try:
            _s.copyfile(base, dst)
        except Exception as e:
            QMessageBox.warning(self, "Configuraciones", f"No se pudo crear desde plantilla: {e}")
            return
        self.refrescar()
        QMessageBox.information(self, "Configuraciones", f"Creada: {dst}")

    def _editar(self):
        p = self._sel()
        if not p:
            QMessageBox.warning(self, "Configuraciones", "Selecciona un archivo de la tabla.")
            return
        try:
            txt = leer_texto(p)
        except Exception as e:
            QMessageBox.warning(self, "Configuraciones", str(e))
            return
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Editar {p}")
        dlg.resize(720, 520)
        lay = QVBoxLayout(dlg)
        ed = QPlainTextEdit()
        ed.setPlainText(txt)
        lay.addWidget(ed)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Save).setObjectName("Primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("Secondary")
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            r = guardar_texto(p, ed.toPlainText())
            if not r.get("ok"):
                QMessageBox.warning(self, "Configuraciones", r.get("error", "Error"))
            self.refrescar()

    def _validar(self):
        p = self._sel()
        if not p:
            QMessageBox.warning(self, "Configuraciones", "Selecciona un archivo de la tabla.")
            return
        v = vc(p)
        if v.get("ok"):
            msg = "Válido." + (
                f" Avisos: {'; '.join(v.get('warnings', []))}" if v.get("warnings") else ""
            )
            QMessageBox.information(self, "Configuraciones", msg)
        else:
            QMessageBox.warning(self, "Configuraciones", "; ".join(v.get("errores", [])))
        self.refrescar()

    def _asociar(self):
        p = self._sel()
        if not p:
            QMessageBox.warning(self, "Configuraciones", "Selecciona un archivo de la tabla.")
            return
        conn = self.conn()
        cur = conn.cursor()
        try:
            cur.execute("SELECT id, title FROM experiments ORDER BY id DESC")
            filas = cur.fetchall()
        except Exception:
            filas = []
        conn.close()
        if not filas:
            QMessageBox.warning(self, "Configuraciones", "No hay experimentos. Crea uno primero.")
            return
        dlg = QDialog(self)
        dlg.setWindowTitle("Asociar XML")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(f"Asociar:\n{p}"))
        cb = QComboBox()
        for eid, t in filas:
            cb.addItem(f"#{eid} {t}", eid)
        lay.addWidget(cb)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setObjectName("Primary")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setObjectName("Secondary")
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            eid = cb.currentData()
            conn = self.conn()
            cur = conn.cursor()
            cur.execute(
                "UPDATE experiments SET config_xml_path=?, last_modified=CURRENT_TIMESTAMP WHERE id=?",
                (p, eid),
            )
            conn.commit()
            conn.close()
            QMessageBox.information(self, "Configuraciones", f"Asociado al experimento #{eid}.")
