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
    QHeaderView, QSizePolicy, QSpacerItem, QProgressBar
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ..nucleo import get_db_path
from ..xml_validator import validar_config
from ..theme_lab import (
    FONDO, LATERAL, TARJETA, BORDE, TEXTO, TEXTO2, LIMA, ROJO,
    VERDE_OK, AMARILLO,
    ESPACIO_S, ESPACIO_XS, ESPACIO_M, ESPACIO_L, ESPACIO_XL,
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


def estadisticas_experimento(conn, eid):
    """Devuelve estadísticas de runs para un experimento desde la DB."""
    cur = conn.cursor()
    cur.execute(
        """SELECT COUNT(r.id),
                  SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN r.status = 'running' THEN 1 ELSE 0 END),
                  SUM(CASE WHEN r.status IN ('failed', 'cancelled') THEN 1 ELSE 0 END),
                  MAX(r.start_time)
           FROM runs r WHERE r.experiment_id = ?""",
        (eid,),
    )
    row = cur.fetchone()
    return {
        "total": row[0] or 0,
        "completadas": row[1] or 0,
        "en_curso": row[2] or 0,
        "falladas": row[3] or 0,
        "ultima_fecha": row[4],
    }


def estado_general_experimento(n_runs, n_running, n_failed, n_completed, xml_ok):
    """Determina el estado general del experimento y su clave de color.

    Prioridad:
    1. Hay réplicas en curso → En ejecución
    2. Hay réplicas fallidas/canceladas → Con errores
    3. Hay réplicas completadas y al menos una run → Completado
    4. Tiene XML válido pero sin runs → Configurado
    5. Sin XML → Sin configurar
    """
    if n_running > 0:
        return "En ejecución", "en_ejecucion"
    if n_failed > 0:
        return "Con errores", "con_errores"
    if n_completed > 0 and n_runs > 0:
        return "Completado", "completado"
    if xml_ok:
        return "Configurado", "configurado"
    return "Sin configurar", "sin_configurar"


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


class ExperimentoCard(Tarjeta):
    """Tarjeta de experimento con el diseño visual solicitado.

    Orden:
      1. Encabezado: título + descripción + menú ⋯ (esquina superior derecha)
      2. Etiquetas + indicador XML
      3. Separador sutil
      4. Métricas en dos columnas: RÉPLICAS | ÚLTIMA EJECUCIÓN
      5. Información inferior: CONFIGURACIÓN + ESTADO
      6. Progreso (solo si hay réplicas)
      7. Botón final: Abrir experimento
    """

    def __init__(
        self,
        eid,
        title,
        desc,
        tags,
        xml_label,
        xml_clave,
        total_runs,
        completadas,
        en_curso,
        falladas,
        ultima_fecha,
        estado_general,
        estado_clave,
        on_abrir,
        on_acciones,
        padre=None,
    ):
        super().__init__(padre=padre)
        self.eid = eid
        self.setMinimumWidth(300)
        self.setMaximumWidth(420)

        lay = self.layout_interno()
        lay.setContentsMargins(ESPACIO_L, ESPACIO_L, ESPACIO_L, ESPACIO_L)
        lay.setSpacing(ESPACIO_M)

        # ================================================================
        # 1. ENCABEZADO: título + descripción + menú ⋯ (esquina superior derecha)
        # ================================================================
        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(ESPACIO_S)

        t = QLabel(title or f"Experimento {eid}")
        t.setObjectName("CardTitulo")
        t.setWordWrap(True)
        t.setMaximumHeight(38)
        header.addWidget(t, 1)

        b_menu = QPushButton("⋯")
        b_menu.setObjectName("Fantasma")
        b_menu.setFixedWidth(36)
        b_menu.setToolTip("Editar / Eliminar")
        b_menu.clicked.connect(lambda _: on_acciones(eid))
        header.addWidget(b_menu)

        lay.addLayout(header)

        if desc and desc.strip():
            fragmento = desc.strip()
            if len(fragmento) > 110:
                fragmento = fragmento[:110].rstrip() + "..."
            d = QLabel(fragmento)
            d.setObjectName("CardDesc")
            d.setWordWrap(True)
            d.setMaximumHeight(44)
            lay.addWidget(d)

        # ================================================================
        # 2. ETIQUETAS + indicador XML
        # ================================================================
        fila_tags = QHBoxLayout()
        fila_tags.setContentsMargins(0, 0, 0, 0)
        fila_tags.setSpacing(ESPACIO_S)

        if tags and tags.strip():
            lista_tags = [tg.strip() for tg in tags.split(",") if tg.strip()][:4]
            for tag in lista_tags:
                bt = QLabel(tag)
                bt.setObjectName("BadgeTag")
                bt.setStyleSheet(
                    f"color: {LIMA}; font-weight: 600; font-size: {TAM_MENOR}px; "
                    f"padding: 2px 6px; border-radius: 4px; "
                    f"border: 1px solid #3a3a38;"
                )
                fila_tags.addWidget(bt)

        # Indicador XML (discreto, al final de la fila de etiquetas)
        if xml_label and xml_label != "Sin XML" and xml_label != "Inexistente":
            xml_ind = QLabel(xml_label)
            xml_ind.setObjectName("CardXml")
            xml_ind.setStyleSheet(
                f"color: {VERDE_OK}; font-weight: 600; font-size: {TAM_MENOR}px; "
                f"padding: 2px 6px; border-radius: 4px; "
                f"border: 1px solid {VERDE_OK};"
            )
        else:
            xml_ind = QLabel(xml_label or "Sin XML")
            xml_ind.setObjectName("CardXml")
            xml_ind.setStyleSheet(
                f"color: {TEXTO2}; font-weight: 600; font-size: {TAM_MENOR}px; "
                f"padding: 2px 6px; border-radius: 4px; "
                f"border: 1px solid #3a3a38;"
            )
        fila_tags.addWidget(xml_ind)
        fila_tags.addStretch()

        cont_tags = QWidget()
        cont_tags.setLayout(fila_tags)
        lay.addWidget(cont_tags)

        # ================================================================
        # 3. SEPARADOR sutil
        # ================================================================
        sep = QFrame()
        sep.setObjectName("SeparadorSutil")
        lay.addWidget(sep)

        # ================================================================
        # 4. MÉTRICAS EN DOS COLUMNAS: RÉPLICAS | ÚLTIMA EJECUCIÓN
        # ================================================================
        metricas = QHBoxLayout()
        metricas.setContentsMargins(0, 0, 0, 0)
        metricas.setSpacing(ESPACIO_L)

        # Columna izquierda: RÉPLICAS
        col_rep = QVBoxLayout()
        col_rep.setContentsMargins(0, 0, 0, 0)
        col_rep.setSpacing(ESPACIO_XS)
        lbl_rep_t = QLabel("RÉPLICAS")
        lbl_rep_t.setObjectName("CardMetricaEtiqueta")
        col_rep.addWidget(lbl_rep_t)

        if total_runs and total_runs > 0:
            txt_rep = f"{completadas} / {total_runs}"
        else:
            txt_rep = "0 / 0"
        lbl_rep_v = QLabel(txt_rep)
        lbl_rep_v.setObjectName("CardMetricaValor")
        col_rep.addWidget(lbl_rep_v)

        lbl_rep_s = QLabel(
            f"{completadas} completadas"
            + (f" · {en_curso} en curso" if en_curso else "")
            + (f" · {falladas} fallidas" if falladas else "")
        )
        lbl_rep_s.setObjectName("CardMetricaEtiqueta")
        col_rep.addWidget(lbl_rep_s)

        met_izq = QWidget()
        met_izq.setLayout(col_rep)
        metricas.addWidget(met_izq, 1)

        # Columna derecha: ÚLTIMA EJECUCIÓN
        col_ult = QVBoxLayout()
        col_ult.setContentsMargins(0, 0, 0, 0)
        col_ult.setSpacing(ESPACIO_XS)
        lbl_ult_t = QLabel("ÚLTIMA EJECUCIÓN")
        lbl_ult_t.setObjectName("CardMetricaEtiqueta")
        col_ult.addWidget(lbl_ult_t)

        if ultima_fecha:
            try:
                from datetime import datetime
                fecha_dt = datetime.fromisoformat(str(ultima_fecha))
                ahora = datetime.now()
                diff = ahora - fecha_dt
                if diff.days > 0:
                    txt_ult = f"Hace {diff.days} d"
                elif diff.seconds >= 3600:
                    txt_ult = f"Hace {diff.seconds // 3600} h"
                elif diff.seconds >= 60:
                    txt_ult = f"Hace {diff.seconds // 60} min"
                else:
                    txt_ult = "Hace menos de 1 min"
                fecha_real = fecha_dt.strftime("%d/%m/%Y %H:%M")
            except Exception:
                txt_ult = "—"
                fecha_real = str(ultima_fecha)[:16]
        else:
            txt_ult = "—"
            fecha_real = None

        lbl_ult_v = QLabel(txt_ult)
        lbl_ult_v.setObjectName("CardMetricaValor")
        col_ult.addWidget(lbl_ult_v)

        if fecha_real:
            lbl_ult_s = QLabel(fecha_real)
            lbl_ult_s.setObjectName("CardMetricaEtiqueta")
            col_ult.addWidget(lbl_ult_s)

        met_der = QWidget()
        met_der.setLayout(col_ult)
        metricas.addWidget(met_der, 1)

        lay.addLayout(metricas)

        # ================================================================
        # 5. INFORMACIÓN INFERIOR: CONFIGURACIÓN + ESTADO
        # ================================================================
        info = QHBoxLayout()
        info.setContentsMargins(0, 0, 0, 0)
        info.setSpacing(ESPACIO_L)

        # CONFIGURACIÓN
        col_cfg = QVBoxLayout()
        col_cfg.setContentsMargins(0, 0, 0, 0)
        col_cfg.setSpacing(ESPACIO_XS)
        lbl_cfg_t = QLabel("CONFIGURACIÓN")
        lbl_cfg_t.setObjectName("CardMetricaEtiqueta")
        col_cfg.addWidget(lbl_cfg_t)

        xml_nombre = ""
        if xml_label and xml_label not in ("Sin XML", "Inexistente"):
            try:
                xml_nombre = os.path.basename(xml_label)
            except Exception:
                xml_nombre = xml_label
        lbl_cfg_v = QLabel(xml_nombre or "Sin XML asignado")
        lbl_cfg_v.setObjectName("CardMeta")
        lbl_cfg_v.setWordWrap(True)
        col_cfg.addWidget(lbl_cfg_v)

        cfg_w = QWidget()
        cfg_w.setLayout(col_cfg)
        info.addWidget(cfg_w, 1)

        # ESTADO
        col_est = QVBoxLayout()
        col_est.setContentsMargins(0, 0, 0, 0)
        col_est.setSpacing(ESPACIO_XS)
        lbl_est_t = QLabel("ESTADO")
        lbl_est_t.setObjectName("CardMetricaEtiqueta")
        col_est.addWidget(lbl_est_t)

        color_estado = {
            "en_ejecucion": AMARILLO,
            "con_errores": ROJO,
            "completado": VERDE_OK,
            "configurado": LIMA,
            "sin_configurar": TEXTO2,
        }.get(estado_clave, TEXTO2)

        lbl_est_v = QLabel(estado_general)
        lbl_est_v.setObjectName("CardEstadoValor")
        lbl_est_v.setStyleSheet(f"color: {color_estado};")
        col_est.addWidget(lbl_est_v)

        est_w = QWidget()
        est_w.setLayout(col_est)
        info.addWidget(est_w, 1)

        lay.addLayout(info)

        # ================================================================
        # 6. PROGRESO (solo si hay réplicas válidas)
        # ================================================================
        if total_runs and total_runs > 0:
            porcentaje = int((completadas / total_runs) * 100)
            lbl_prog = QLabel(f"{porcentaje}% completado")
            lbl_prog.setObjectName("CardMeta")
            lay.addWidget(lbl_prog)

            pb = QProgressBar()
            pb.setObjectName("ProgresoReplicas")
            pb.setRange(0, 100)
            pb.setValue(porcentaje)
            pb.setTextVisible(False)
            lay.addWidget(pb)

        # ================================================================
        # 7. ACCIÓN FINAL: botón Abrir experimento
        # ================================================================
        b_abrir = QPushButton("Abrir experimento")
        b_abrir.setObjectName("CardAccion")
        b_abrir.setCursor(Qt.CursorShape.PointingHandCursor)
        b_abrir.clicked.connect(lambda _: on_abrir(eid))
        lay.addWidget(b_abrir)

