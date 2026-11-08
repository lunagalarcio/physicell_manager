"""Página global de Ejecuciones: historial de réplicas de todos los experimentos."""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHeaderView, QLabel,
)
from PyQt6.QtGui import QColor

from .base import (
    PaginaBase, Seccion, Tarjeta, TablaBase, ESPACIO_M, resumen_texto,
)
from .dialogo_run import DialogoDetalleRun

# Estado -> color del texto en la columna Estado
_COLOR_ESTADO = {
    "completed": "#3DDC84",
    "failed": "#FF6B6B",
    "cancelled": "#FFB020",
    "running": "#4DA3FF",
    "registered": "#A6A6A6",
    "pending": "#A6A6A6",
}

COL_MOTIVO = 5
COL_REGISTRO = 6
COL_SALIDA = 7


class PaginaEjecuciones(PaginaBase):
    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_M, ESPACIO_M, ESPACIO_M, ESPACIO_M)
        lay.setSpacing(ESPACIO_M)

        lay.addWidget(
            Seccion(
                "Ejecuciones",
                "Historial de réplicas con estado, motivo del fallo y registro del motor.",
            )
        )

        self.table = TablaBase(
            ["Experimento", "Run", "Estado", "Inicio", "Fin",
             "Motivo del error", "Registro", "Salida"]
        )
        cab = self.table.horizontalHeader()
        cab.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(COL_MOTIVO, QHeaderView.ResizeMode.Stretch)
        cab.setSectionResizeMode(COL_REGISTRO, QHeaderView.ResizeMode.ResizeToContents)
        cab.setSectionResizeMode(COL_SALIDA, QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(COL_SALIDA, 320)
        self.table.itemDoubleClicked.connect(self._ver_detalle)

        tarjeta = Tarjeta()
        tarjeta.add(self.table)
        lay.addWidget(tarjeta, 1)

        pista = QLabel(
            "Doble clic en una fila para ver el motivo completo y la salida real de PhysiCell."
        )
        pista.setObjectName("Muted")
        lay.addWidget(pista)

        self.refrescar()
        return self

    def refrescar(self):
        from .. import simulador as SIM
        conn = self.conn()
        try:
            crudas = SIM.listar_todos_los_runs(conn)
        except Exception:
            crudas = []
        conn.close()
        filas = []
        self._filas = []
        for r in crudas:
            motivo = r[6] or ""
            if not motivo and r[2] in ("failed", "cancelled"):
                motivo = "Sin detalle registrado (ejecución anterior a esta versión)"
            log_path = r[7] if len(r) > 7 else ""
            pid = r[8] if len(r) > 8 else None
            batch_id = r[9] if len(r) > 9 else None
            self._filas.append({
                "experimento": r[0],
                "replica": r[1],
                "estado": r[2],
                "inicio": r[3] or "",
                "fin": r[4] or "",
                "motivo": motivo,
                "salida": r[5] or "",
                "log_path": log_path or "",
                "pid": pid,
                "batch_id": batch_id,
            })
            filas.append((
                r[0], r[1], r[2], r[3] or "", r[4] or "",
                resumen_texto(motivo),
                "Ver salida" if log_path else "sin registro",
                r[5] or "",
            ))
        self.table.cargar(filas)
        for i, datos in enumerate(self._filas):
            it = self.table.item(i, COL_MOTIVO)
            if it is not None:
                it.setToolTip(datos["motivo"])
            it_log = self.table.item(i, COL_REGISTRO)
            if it_log is not None:
                it_log.setToolTip(
                    datos["log_path"] or
                    "Esta ejecución no tiene registro del motor guardado."
                )
                if not datos["log_path"]:
                    it_log.setForeground(QColor("#7A7A7A"))
        self._colorear_estados()

    def _colorear_estados(self):
        for i in range(self.table.rowCount()):
            item = self.table.item(i, 2)
            if item is None:
                continue
            color = _COLOR_ESTADO.get(item.text(), "#A6A6A6")
            item.setForeground(QColor(color))

    def _ver_detalle(self, item):
        fila = item.row()
        datos = (self._filas[fila] if getattr(self, "_filas", None)
                 and fila < len(self._filas) else {})
        DialogoDetalleRun(datos, padre=self).exec()
