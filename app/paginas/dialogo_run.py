"""Diálogo con el detalle completo de una ejecución y la salida real de PhysiCell."""
import os
import sqlite3
import subprocess
import sys

from PyQt6.QtWidgets import (
    QLabel, QPlainTextEdit, QPushButton, QHBoxLayout, QMessageBox, QApplication,
)
from PyQt6.QtGui import QFont
from PyQt6.QtCore import Qt

from .. import simulador as SIM
from ..nucleo import get_db_path
from .base import DialogoBase, TEXTO2


def _hash_corto(valor, n=12):
    """Primeros caracteres de un SHA-256, o un guion si no hay huella."""
    valor = (valor or "").strip()
    return f"{valor[:n]}…" if len(valor) > n else (valor or "—")


class DialogoDetalleRun(DialogoBase):
    """Muestra el motivo del fallo y el registro íntegro del motor.

    ``datos`` admite las claves: experimento, replica, estado, inicio, fin,
    salida, motivo, log_path, pid y batch_id.
    """

    def __init__(self, datos, padre=None):
        super().__init__("Detalle de la ejecución", padre=padre, ancho=860, alto=660)
        self.datos = datos or {}
        self.log_path = self.datos.get("log_path") or ""
        self.salida = self.datos.get("salida") or ""
        self.batch = self._cargar_batch()

        estado = self.datos.get("estado") or "—"
        color = {
            "completed": "#3DDC84",
            "failed": "#FF6B6B",
            "cancelled": "#FFB020",
            "running": "#4DA3FF",
        }.get(estado, TEXTO2)
        motivo = (self.datos.get("motivo") or "").strip() or "Sin motivo registrado."
        pid = self.datos.get("pid")

        resumen = QLabel(
            f"<b>Experimento:</b> {self.datos.get('experimento') or '—'} &nbsp;&nbsp; "
            f"<b>Réplica:</b> {self.datos.get('replica') or '—'}<br>"
            f"<b>Estado:</b> <b style='color:{color}'>{estado}</b><br>"
            f"<b>Inicio:</b> {self.datos.get('inicio') or '—'} &nbsp;&nbsp; "
            f"<b>Fin:</b> {self.datos.get('fin') or '—'}<br>"
            f"<b>PID del proceso:</b> {pid if pid else '—'}<br>"
            f"<b>Carpeta de salida:</b> {self.salida or '—'}<br>"
            f"<b>Registro:</b> {self.log_path or '—'}"
        )
        resumen.setTextFormat(Qt.TextFormat.RichText)
        resumen.setWordWrap(True)
        self.add(resumen)

        self.add(self._etiqueta_lote())

        if self.batch and (self.batch.get("error_message") or "").strip():
            err_lote = QLabel(
                "<b>Error del lote:</b><br>" +
                (self.batch.get("error_message") or "").replace("\n", "<br>")[:2000]
            )
            err_lote.setWordWrap(True)
            err_lote.setTextFormat(Qt.TextFormat.RichText)
            err_lote.setStyleSheet(
                "background: #2A1416; padding: 8px; border-radius: 4px; color: #FFB4B4;"
            )
            self.add(err_lote)

        lbl_motivo = QLabel("<b>Motivo registrado</b>")
        self.add(lbl_motivo)
        txt_motivo = QLabel(motivo)
        txt_motivo.setWordWrap(True)
        txt_motivo.setStyleSheet("background: #14161A; padding: 8px; border-radius: 4px;")
        txt_motivo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.add(txt_motivo)

        cab = QLabel("<b>Salida de PhysiCell (registro del motor)</b>")
        self.add(cab)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setFont(QFont("Consolas", 9))
        self.log_view.setPlainText(self._contenido_log())
        self.add(self.log_view)

        fila = QHBoxLayout()
        b_carpeta = QPushButton("Abrir carpeta del registro")
        b_carpeta.setObjectName("Secondary")
        b_carpeta.clicked.connect(self._abrir_carpeta)
        b_copiar = QPushButton("Copiar salida")
        b_copiar.setObjectName("Secondary")
        b_copiar.clicked.connect(self._copiar)
        b_cerrar = QPushButton("Cerrar")
        b_cerrar.setObjectName("Primary")
        b_cerrar.clicked.connect(self.accept)
        fila.addWidget(b_carpeta)
        fila.addWidget(b_copiar)
        fila.addStretch(1)
        fila.addWidget(b_cerrar)
        self._lay.addLayout(fila)

    # ------------------------------------------------------------------
    def _cargar_batch(self):
        """Ficha del lote al que pertenece esta réplica (si existe)."""
        batch_id = self.datos.get("batch_id")
        if not batch_id:
            return None
        try:
            conn = sqlite3.connect(get_db_path())
            try:
                return SIM.obtener_batch(conn, batch_id)
            finally:
                conn.close()
        except Exception:
            return None

    def _etiqueta_lote(self):
        """Texto con la huella de ejecución: qué XML y qué motor se usaron."""
        lbl = QLabel()
        lbl.setTextFormat(Qt.TextFormat.RichText)
        lbl.setWordWrap(True)
        lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        batch_id = self.datos.get("batch_id")
        if not batch_id:
            lbl.setText(
                "<b>Lote:</b> sin lote registrado "
                "<span style='color:#A6A6A6'>(ejecución anterior a esta versión)</span>"
            )
            return lbl
        if not self.batch:
            lbl.setText(
                f"<b>Lote:</b> #{batch_id} "
                "<span style='color:#A6A6A6'>(no se pudo leer su ficha)</span>"
            )
            return lbl

        b = self.batch
        xml = os.path.basename(b.get("xml_path") or "") or "—"
        exe = os.path.basename(b.get("exe_path") or "") or "—"
        limite = (f"{b['timeout_min']} min por réplica"
                  if b.get("timeout_min") else "sin límite absoluto")
        inact = (f"cancela tras {b['inactividad_min']} min sin salida"
                 if b.get("inactividad_min") else "sin vigilancia de inactividad")
        estado_lote = b.get("status") or "—"
        color_lote = {
            "completed": "#3DDC84",
            "failed": "#FF6B6B",
            "cancelled": "#FFB020",
            "partial": "#FFB020",
            "running": "#4DA3FF",
        }.get(estado_lote, "#A6A6A6")
        lbl.setText(
            f"<b>Lote:</b> #{b.get('id')} &nbsp;·&nbsp; "
            f"<b>Estado del lote:</b> <b style='color:{color_lote}'>{estado_lote}</b> "
            f"&nbsp;·&nbsp; {b.get('n_replicas') or '—'} réplicas "
            f"&nbsp;·&nbsp; semilla base {b.get('seed_base') if b.get('seed_base') is not None else '—'}<br>"
            f"<b>XML:</b> {xml} "
            f"<span style='color:#A6A6A6'>SHA-256 {_hash_corto(b.get('xml_sha256'))}</span><br>"
            f"<b>Motor:</b> {exe} "
            f"<span style='color:#A6A6A6'>SHA-256 {_hash_corto(b.get('exe_sha256'))}</span><br>"
            f"<b>Límite:</b> {limite} &nbsp;·&nbsp; <b>Vigilancia:</b> {inact}<br>"
            f"<b>Creado:</b> {b.get('creado_en') or '—'} &nbsp;·&nbsp; "
            f"Python {b.get('python_version') or '—'} · {b.get('plataforma') or '—'}"
        )
        if b.get("notas"):
            lbl.setText(lbl.text() + f"<br><b>Notas:</b> {b['notas']}")
        return lbl

    def _contenido_log(self):
        if self.log_path:
            return SIM.leer_log(self.log_path)
        return SIM.leer_log("")

    def _abrir_carpeta(self):
        carpeta = os.path.dirname(self.log_path) if self.log_path else self.salida
        if not carpeta or not os.path.isdir(carpeta):
            QMessageBox.information(
                self, "Abrir carpeta",
                "Esta ejecución no tiene una carpeta de registro o salida disponible.",
            )
            return
        try:
            if sys.platform.startswith("win"):
                os.startfile(carpeta)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", carpeta])
            else:
                subprocess.Popen(["xdg-open", carpeta])
        except Exception as e:
            QMessageBox.warning(self, "Abrir carpeta", f"No se pudo abrir la carpeta:\n{e}")

    def _copiar(self):
        QApplication.clipboard().setText(self.log_view.toPlainText())
