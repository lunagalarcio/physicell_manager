#!/usr/bin/env python3
"""Sistema visual PhysiCell Lab: oscuro carbón + lima.

Diseño consistente: paleta unificada, espaciado estándar, componentes
reutilizables (tarjeta, sección, botón, entrada, tabla, badge, diálogo).
"""

# ---------- Paleta ----------
FONDO = "#191919"        # fondo principal de la ventana
LATERAL = "#202020"      # barra lateral
TARJETA = "#242424"      # tarjetas y paneles
TARJETA_ALTA = "#2a2a2a" # tarjeta activa / elevada
BORDE = "#343434"        # bordes suaves
BORDE_ENFOQUE = "#84CC16" # borde al enfocar (lima)
TEXTO = "#F5F5F5"        # texto principal
TEXTO2 = "#A6A6A6"       # texto secundario / muted
TEXTO_SUAVE = "#8a8a8a"  # texto deshabilitado
LIMA = "#84CC16"         # acento principal
LIMA_HOVER = "#9BE315"
LIMA_SUAVE = "#3f6212"   # para selección de texto
ROJO = "#E5484D"         # peligro / error
ROJO_SUAVE = "#2e1a1c"
AMARILLO = "#F5B83D"     # advertencia / en ejecución
VERDE_OK = "#46A758"     # éxito
GRIS_BORDE = "#4a4a48"

# ---------- Espaciado ----------
ESPACIO_XS = 4
ESPACIO_S = 8
ESPACIO_M = 12
ESPACIO_L = 16
ESPACIO_XL = 24

# ---------- Bordes y radio ----------
RADIO_S = 6
RADIO_M = 8
RADIO_L = 10
GROSOR_BORDE = 1

# ---------- Tipografía ----------
FUENTE_BASE = "'Segoe UI', 'Inter', sans-serif"
TAM_BASE = 13
TAM_H1 = 20
TAM_H2 = 14
TAM_TEXTO = 13
TAM_MENOR = 11
TAM_KPI = 22

LAB_QSS = f"""
* {{
    font-family: {FUENTE_BASE};
    font-size: {TAM_BASE}px;
}}
QMainWindow {{
    background-color: {FONDO};
    color: {TEXTO};
}}
QWidget#SideBar {{
    background-color: {LATERAL};
    border-right: {GROSOR_BORDE}px solid {BORDE};
}}
QWidget#SideBar QLabel#Brand {{
    color: {TEXTO};
    font-size: 17px;
    font-weight: 700;
}}
QWidget#SideBar QLabel#BrandSub {{
    color: {TEXTO2};
    font-size: 11px;
}}
QPushButton#NavBtn {{
    background: transparent;
    border: none;
    border-radius: {RADIO_S}px;
    padding: 9px 12px;
    color: {TEXTO2};
    text-align: left;
    font-weight: 600;
    font-size: {TAM_BASE}px;
}}
QPushButton#NavBtn:hover {{
    background-color: #2a2a2a;
    color: {TEXTO};
}}
QPushButton#NavBtn:checked {{
    background-color: #2c2c2c;
    color: {LIMA};
    border: {GROSOR_BORDE}px solid {BORDE};
}}

/* ---------- Tarjetas ---------- */
QFrame#Card {{
    background-color: {TARJETA};
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_M}px;
}}
QFrame#Card:hover {{
    border-color: {GRIS_BORDE};
}}
QFrame#CardElevada {{
    background-color: {TARJETA_ALTA};
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_M}px;
}}

/* ---------- Títulos y etiquetas ---------- */
QLabel#H1 {{
    color: {TEXTO};
    font-size: {TAM_H1}px;
    font-weight: 700;
}}
QLabel#H2 {{
    color: {TEXTO};
    font-size: {TAM_H2}px;
    font-weight: 700;
}}
QLabel#Muted {{
    color: {TEXTO2};
    font-size: {TAM_MENOR}px;
}}
QLabel#CardTitulo {{
    color: {TEXTO};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#CardDesc {{
    color: {TEXTO2};
    font-size: 11px;
}}
QLabel#CardMeta {{
    color: {TEXTO2};
    font-size: 10px;
}}

/* ---------- Tarjetas de experimento ---------- */
QLabel#CardTitulo {{
    color: {TEXTO};
    font-size: 15px;
    font-weight: 700;
}}
QLabel#CardDesc {{
    color: {TEXTO2};
    font-size: 11px;
}}
QLabel#CardMeta {{
    color: {TEXTO2};
    font-size: 10px;
}}
QLabel#CardMetricaValor {{
    color: {TEXTO};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#CardMetricaEtiqueta {{
    color: {TEXTO2};
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
}}
QLabel#CardXml {{
    color: {VERDE_OK};
    font-size: 10px;
    font-weight: 600;
}}
QLabel#CardEstado {{
    color: {TEXTO2};
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
}}
QLabel#CardEstadoValor {{
    font-size: 11px;
    font-weight: 600;
}}
QLabel#CardAccion {{
    color: #1a2e05;
    font-weight: 700;
    font-size: {TAM_BASE}px;
}}

QFrame#SeparadorSutil {{
    background-color: {BORDE};
    max-height: 1px;
    border: none;
    margin: 0;
}}

QProgressBar#ProgresoReplicas {{
    background: #232323;
    border: none;
    border-radius: 3px;
    text-align: center;
    color: {TEXTO2};
    height: 6px;
    font-size: 9px;
}}
QProgressBar#ProgresoReplicas::chunk {{
    background-color: {LIMA};
    border-radius: 3px;
}}
    color: {TEXTO};
    font-size: {TAM_KPI}px;
    font-weight: 700;
}}
QLabel#KpiLbl {{
    color: {TEXTO2};
    font-size: {TAM_MENOR}px;
}}

/* ---------- Botones ---------- */
QPushButton#Primary {{
    background-color: {LIMA};
    border: {GROSOR_BORDE}px solid {LIMA};
    border-radius: {RADIO_S}px;
    padding: 8px 16px;
    color: #1a2e05;
    font-weight: 700;
    font-size: {TAM_BASE}px;
}}
QPushButton#Primary:hover {{ background-color: {LIMA_HOVER}; }}
QPushButton#Primary:disabled {{
    background-color: #3a3a38;
    border-color: #3a3a38;
    color: #8a8a86;
}}
QPushButton#Secondary {{
    background-color: transparent;
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_S}px;
    padding: 7px 14px;
    color: {TEXTO};
    font-size: {TAM_BASE}px;
}}
QPushButton#Secondary:hover {{ border-color: {LIMA}; color: {LIMA}; }}
QPushButton#Danger {{
    background-color: transparent;
    border: {GROSOR_BORDE}px solid #5a2b2e;
    border-radius: {RADIO_S}px;
    padding: 7px 14px;
    color: {ROJO};
    font-size: {TAM_BASE}px;
}}
QPushButton#Danger:hover {{ background-color: {ROJO_SUAVE}; }}
QPushButton#Fantasma {{
    background: transparent;
    border: none;
    border-radius: {RADIO_S}px;
    padding: 6px 10px;
    color: {TEXTO2};
    font-size: {TAM_BASE}px;
}}
QPushButton#Fantasma:hover {{ background-color: #2a2a2a; color: {TEXTO}; }}

/* ---------- Entradas ---------- */
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{
    background-color: #1f1f1f;
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_S}px;
    padding: 8px;
    color: {TEXTO};
    selection-background-color: {LIMA_SUAVE};
    font-size: {TAM_BASE}px;
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus, QTextEdit:focus {{
    border-color: {BORDE_ENFOQUE};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    color: {TEXTO2};
    width: 12px;
    height: 12px;
}}

/* ---------- Tabs ---------- */
QTabWidget::pane {{
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_M}px;
    background: {TARJETA};
}}
QTabBar::tab {{
    background: transparent;
    color: {TEXTO2};
    padding: 10px 18px;
    border: none;
    font-weight: 600;
    font-size: {TAM_BASE}px;
}}
QTabBar::tab:selected {{
    color: {LIMA};
    border-bottom: 2px solid {LIMA};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXTO};
    background-color: #2a2a2a;
    border-radius: {RADIO_S}px;
}}

/* ---------- Progreso ---------- */
QProgressBar {{
    background: #232323;
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_S}px;
    text-align: center;
    color: {TEXTO};
    height: 14px;
    font-size: {TAM_MENOR}px;
}}
QProgressBar::chunk {{
    background-color: {LIMA};
    border-radius: {RADIO_S}px;
}}

/* ---------- Tablas ---------- */
QTableWidget {{
    background-color: {TARJETA};
    color: {TEXTO};
    gridline-color: {BORDE};
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_M}px;
    font-size: {TAM_BASE}px;
}}
QTableWidget::item {{
    padding: 8px 10px;
    border-bottom: {GROSOR_BORDE}px solid {BORDE};
}}
QTableWidget::item:selected {{
    background-color: {LIMA_SUAVE};
    color: {TEXTO};
}}
QHeaderView::section {{
    background-color: #2a2a2a;
    color: {TEXTO2};
    border: none;
    border-bottom: {GROSOR_BORDE}px solid {BORDE};
    padding: 10px;
    font-weight: 600;
    font-size: {TAM_MENOR}px;
}}

/* ---------- Áreas de desplazamiento ---------- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{
    background: transparent;
    width: 10px;
    margin: 0 0 0 0;
}}
QScrollBar::handle:vertical {{
    background: #3a3a38;
    border-radius: 5px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background: {GRIS_BORDE}; }}
QScrollBar:horizontal {{
    background: transparent;
    height: 10px;
}}
QScrollBar::handle:horizontal {{
    background: #3a3a38;
    border-radius: 5px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background: {GRIS_BORDE}; }}

/* ---------- Checkboxes y radios ---------- */
QCheckBox {{ color: {TEXTO}; spacing: 8px; font-size: {TAM_BASE}px; }}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: 4px;
    background: #1f1f1f;
}}
QCheckBox::indicator:checked {{
    background-color: {LIMA};
    border-color: {LIMA};
}}

/* ---------- Sliders ---------- */
QSlider::groove:horizontal {{
    height: 6px;
    background: #2e2e2c;
    border-radius: 3px;
}}
QSlider::handle:horizontal {{
    background: {LIMA};
    width: 14px;
    border-radius: 7px;
    margin: -4px 0;
}}
QSlider::sub-page:horizontal {{
    background: {LIMA};
    border-radius: 3px;
}}

/* ---------- Tooltips y mensajes ---------- */
QToolTip {{
    background: #2a2a2a;
    color: {TEXTO};
    border: {GROSOR_BORDE}px solid {BORDE};
    border-radius: {RADIO_S}px;
    padding: 6px;
    font-size: {TAM_MENOR}px;
}}
QMessageBox {{
    background-color: {TARJETA};
    color: {TEXTO};
}}
QMessageBox QPushButton {{
    min-width: 90px;
    padding: 6px 14px;
}}

/* ---------- Separador ---------- */
QFrame#Separador {{
    background-color: {BORDE};
    max-height: 1px;
    border: none;
}}
"""

# ---------- Estilos de estado (para badges / etiquetas) ----------
ESTILO_ESTADO = {
    "Sin configurar": TEXTO2, "Configurado": LIMA,
    "En ejecución": AMARILLO, "Completado": VERDE_OK, "Con errores": ROJO,
    "Sin XML": TEXTO2, "Válido": VERDE_OK, "Inválido": ROJO,
    "Inexistente": ROJO, "Sin motor": TEXTO2, "Listo": VERDE_OK,
    "registrado": TEXTO2,
}

# Estados internos del experimento (claves propias)
ESTADO_EXPERIMENTO = {
    "en_ejecucion": AMARILLO,
    "con_errores": ROJO,
    "completado": VERDE_OK,
    "configurado": LIMA,
    "sin_configurar": TEXTO2,
}

# ---------- Colores de prioridad / severidad ----------
COLOR_SEVERIDAD = {
    "info": "#38BDF8",
    "exito": VERDE_OK,
    "advertencia": AMARILLO,
    "error": ROJO,
}
