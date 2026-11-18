"""Página global de Comparación: compara experimentos entre sí."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QPushButton, QComboBox, QCheckBox, QWidget, QLabel,
    QHBoxLayout, QMessageBox,
)

from .base import (
    PaginaBase, Seccion, Tarjeta, ESPACIO_M,
)
from .. import simulador as SIM


class PaginaComparacion(PaginaBase):
    def build(self):
        # Inicializar estado antes de cualquier llamada que lo use
        self.seleccionados = []

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
        btn.setMinimumHeight(34)
        btn.setMaximumWidth(220)
        btn.clicked.connect(self._agregar)
        btn_row = QHBoxLayout()
        btn_row.addWidget(btn)
        btn_row.addStretch(1)
        btn_cont = QWidget()
        btn_cont.setLayout(btn_row)
        tarjeta.add(btn_cont)

        lay.addWidget(tarjeta)
        lay.addWidget(QLabel("Experimentos seleccionados para comparar:"))
        self.lista_sel = QWidget()
        self.lista_sel_lay = QVBoxLayout(self.lista_sel)
        self.lista_sel_lay.setContentsMargins(0, 0, 0, 0)
        self.lista_sel_lay.setSpacing(ESPACIO_M)
        lay.addWidget(self.lista_sel)

        btn_cmp = QPushButton("Generar comparación")
        btn_cmp.setObjectName("Primary")
        btn_cmp.setMinimumHeight(36)
        btn_cmp.setMaximumWidth(220)
        btn_cmp.clicked.connect(self._comparar)
        row_cmp = QHBoxLayout()
        row_cmp.addWidget(btn_cmp)
        row_cmp.addStretch(1)
        cmp_cont = QWidget()
        cmp_cont.setLayout(row_cmp)
        lay.addWidget(cmp_cont)

        lay.addStretch()

        self._cargar_exps()
        return self

    def refrescar(self):
        self._cargar_exps()

    def _cargar_exps(self):
        from .. import servicios as SERV
        try:
            uid = self.lw.usuario_actual["id"] if self.lw.usuario_actual else None
            filas = SERV.listar_experimentos_servicio(self.db_path(), usuario_id=uid) or []
        except Exception:
            filas = []
        self.exp_combo.clear()
        for fila in filas:
            eid, title = fila[0], fila[1]
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
        uid = self.lw.usuario_actual["id"] if self.lw.usuario_actual else None
        try:
            conn = self.conn()
            for eid in list(self.seleccionados):
                try:
                    row = SIM.obtener_experimento_por_usuario(conn, eid, uid) if uid else None
                    title = row[1] if row else f"Experimento {eid}"
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
        except Exception as ex:
            lbl_err = QLabel(f"Error al cargar lista: {ex}")
            lbl_err.setObjectName("Muted")
            self.lista_sel_lay.addWidget(lbl_err)

    def _quitar(self, eid):
        if eid in self.seleccionados:
            self.seleccionados.remove(eid)
        self._refrescar_lista()

    def _comparar(self):
        if len(self.seleccionados) < 2:
            QMessageBox.information(
                self.lw, "Comparación",
                "Selecciona al menos dos experimentos para comparar."
            )
            return
        self.lw.abrir_comparacion(self.seleccionados)
