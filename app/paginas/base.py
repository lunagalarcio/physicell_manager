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
    VERDE_OK, AMARILLO,
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
    """Tarjeta de experimento con información resumida de estado y ejecuciones.

    Muestra título, descripción fragmentada, estado del XML, etiquetas,
    resumen de réplicas y fecha de última ejecución.
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
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

        # ---------- Título ----------
        t = QLabel(title or f"Experimento {eid}")
        t.setObjectName("CardTitulo")
        t.setWordWrap(True)
        t.setMaximumHeight(38)  # Máximo ~2 líneas
        self.layout_interno().addWidget(t)

        # ---------- Descripción (fragmento) ----------
        if desc and desc.strip():
            fragmento = desc.strip()
            if len(fragmento) > 110:
                fragmento = fragmento[:110].rstrip() + "..."
            d = QLabel(fragmento)
            d.setObjectName("CardDesc")
            d.setWordWrap(True)
            d.setMaximumHeight(44)  # ~2-3 líneas
            self.layout_interno().addWidget(d)

        # ---------- Separador ----------
        self.layout_interno().addWidget(Separador())

        # ---------- Fila de estado y XML ----------
        fila_estado = QHBoxLayout()
        fila_estado.setContentsMargins(0, 0, 0, 0)
        fila_estado.setSpacing(ESPACIO_S)
        b_estado = BadgeEstado(estado_general, estado_clave)
        fila_estado.addWidget(b_estado)
        b_xml = BadgeEstado(xml_label, xml_clave)
        fila_estado.addWidget(b_xml)
        fila_estado.addStretch()
        cont_estado = QWidget()
        cont_estado.setLayout(fila_estado)
        self.layout_interno().addWidget(cont_estado)

        # ---------- Etiquetas ----------
        if tags and tags.strip():
            lista_tags = [tg.strip() for tg in tags.split(",") if tg.strip()][:4]
            if lista_tags:
                fila_tags = QHBoxLayout()
                fila_tags.setContentsMargins(0, 0, 0, 0)
                fila_tags.setSpacing(ESPACIO_S)
                for tag in lista_tags:
                    bt = QLabel(tag)
                    bt.setObjectName("BadgeTag")
                    bt.setStyleSheet(
                        f"color: {LIMA}; font-weight: 600; font-size: {TAM_MENOR}px; "
                        f"padding: 2px 6px; border-radius: 4px; "
                        f"border: 1px solid #3a3a38;"
                    )
                    fila_tags.addWidget(bt)
                fila_tags.addStretch()
                cont_tags = QWidget()
                cont_tags.setLayout(fila_tags)
                self.layout_interno().addWidget(cont_tags)

        # ---------- Resumen de ejecuciones ----------
        if total_runs > 0:
            partes = []
            if completadas:
                partes.append(
                    f"<span style='color:{VERDE_OK}'>{completadas} completadas</span>"
                )
            if en_curso:
                partes.append(
                    f"<span style='color:{AMARILLO}'>{en_curso} en curso</span>"
                )
            if falladas:
                partes.append(
                    f"<span style='color:{ROJO}'>{falladas} fallidas</span>"
                )
            txt_ejec = " · ".join(partes) if partes else f"{total_runs} registro(s)"
            lbl_ejec = QLabel(txt_ejec)
            lbl_ejec.setObjectName("CardMeta")
            lbl_ejec.setWordWrap(True)
            self.layout_interno().addWidget(lbl_ejec)

            if ultima_fecha:
                fecha_corta = str(ultima_fecha)[:16]
                lbl_fecha = QLabel(f"Última ejecución: {fecha_corta}")
                lbl_fecha.setObjectName("CardMeta")
                self.layout_interno().addWidget(lbl_fecha)
        else:
            lbl_sin = QLabel("Sin ejecuciones")
            lbl_sin.setObjectName("CardMeta")
            self.layout_interno().addWidget(lbl_sin)

        self.layout_interno().addStretch()

        # ---------- Botones ----------
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(ESPACIO_S)
        b1 = QPushButton("Abrir")
        b1.setObjectName("Primary")
        b1.clicked.connect(lambda _: on_abrir(eid))
        b2 = QPushButton("⋯")
        b2.setObjectName("Fantasma")
        b2.setFixedWidth(40)
        b2.setToolTip("Editar / Eliminar")
        b2.clicked.connect(lambda _: on_acciones(eid))
        row.addWidget(b1)
        row.addWidget(b2)
        row.addStretch()
        contenedor = QWidget()
        contenedor.setLayout(row)
        self.layout_interno().addWidget(contenedor)
