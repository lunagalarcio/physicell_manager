"""Página global de Comparación: compara experimentos entre sí."""
from PyQt6.QtWidgets import QVBoxLayout, QPushButton, QComboBox, QCheckBox, QWidget, QLabel

from .base import (
    PaginaBase, Seccion, Tarjeta, ESPACIO_M,
)


class PaginaComparacion(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Comparación",
                "Compara experimentos entre sí: selecciona dos o más para ver "
                "métricas lado a lado.",
            )
        )

        self.exp_combo = QComboBox()
        self.exp_combo.setMinimumWidth(300)
        tarjeta = Tarjeta()
        tarjeta.add(self.exp_combo)

        btn = QPushButton("Agregar a comparación")
        btn.setObjectName("Secondary")
        btn.clicked.connect(self._agregar)
        tarjeta.add(btn)

        lay.addWidget(tarjeta)
        lay.addWidget(QLabel("Experimentos seleccionados para comparar:"))
        self.lista_sel = QWidget()
        self.lista_sel_lay = QVBoxLayout(self.lista_sel)
        self.lista_sel_lay.setContentsMargins(0, 0, 0, 0)
        self.lista_sel_lay.setSpacing(ESPACIO_M)
        lay.addWidget(self.lista_sel)

        btn_cmp = QPushButton("Generar comparación")
        btn_cmp.setObjectName("Primary")
        btn_cmp.clicked.connect(self._comparar)
        lay.addWidget(btn_cmp)

        lay.addStretch()

        self._cargar_exps()
        self.seleccionados = []
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

    def _agregar(self):
        eid = self.exp_combo.currentData()
        if eid is None:
            return
        if eid in self.seleccionados:
            return
        self.seleccionados.append(eid)
        self._refrescar_lista()

    def _refrescar_lista(self):
        while self.lista_sel_lay.count():
            item = self.lista_sel_lay.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        conn = self.conn()
        cur = conn.cursor()
        for eid in self.seleccionados:
            try:
                cur.execute("SELECT title FROM experiments WHERE id=?", (eid,))
                row = cur.fetchone()
                title = row[0] if row else f"Experimento {eid}"
            except Exception:
                title = f"Experimento {eid}"
            fila = QWidget()
            fl = QVBoxLayout(fila)
            fl.setContentsMargins(0, 0, 0, 0)
            fl.setSpacing(ESPACIO_M // 2)
            lbl = QLabel(f"#{eid} {title}")
            lbl.setObjectName("ActividadItem")
            fl.addWidget(lbl)
            btn_rm = QPushButton("Quitar")
            btn_rm.setObjectName("Danger")
            btn_rm.setFixedWidth(60)
            btn_rm.clicked.connect(lambda _=False, e=eid: self._quitar(e))
            fl.addWidget(btn_rm)
            self.lista_sel_lay.addWidget(fila)
        conn.close()

    def _quitar(self, eid):
        if eid in self.seleccionados:
            self.seleccionados.remove(eid)
        self._refrescar_lista()

    def _comparar(self):
        if len(self.seleccionados) < 2:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self.lw, "Comparación",
                "Selecciona al menos dos experimentos para comparar."
            )
            return
        self.lw.abrir_comparacion(self.seleccionados)
