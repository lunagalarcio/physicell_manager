#!/usr/bin/env python3
"""Sistema visual PhysiCell Lab: oscuro carbón + lima. Sin verde-sobre-negro ilegible."""

FONDO = "#191919"
LATERAL = "#202020"
TARJETA = "#242424"
BORDE = "#343434"
TEXTO = "#F5F5F5"
TEXTO2 = "#A6A6A6"
LIMA = "#84CC16"
LIMA_HOVER = "#9BE315"
ROJO = "#E5484D"
AMARILLO = "#F5B83D"
VERDE_OK = "#46A758"

LAB_QSS = f"""
* {{ font-family: 'Segoe UI', 'Inter', sans-serif; font-size: 13px; }}
QMainWindow {{ background-color: {FONDO}; color: {TEXTO}; }}
QWidget#SideBar {{ background-color: {LATERAL}; border-right: 1px solid {BORDE}; }}
QWidget#SideBar QLabel#Brand {{ color: {TEXTO}; font-size: 17px; font-weight: 700; }}
QWidget#SideBar QLabel#BrandSub {{ color: {TEXTO2}; font-size: 11px; }}
QPushButton#NavBtn {{ background: transparent; border: none; border-radius: 6px; padding: 8px 10px; color: {TEXTO2}; text-align: left; font-weight: 600; }}
QPushButton#NavBtn:hover {{ background-color: #2a2a2a; color: {TEXTO}; }}
QPushButton#NavBtn:checked {{ background-color: #2c2c2c; color: {LIMA}; border: 1px solid {BORDE}; }}
QFrame#Card {{ background-color: {TARJETA}; border: 1px solid {BORDE}; border-radius: 10px; }}
QFrame#Card:hover {{ border-color: #4a4a48; }}
QLabel#H1 {{ color: {TEXTO}; font-size: 20px; font-weight: 700; }}
QLabel#H2 {{ color: {TEXTO}; font-size: 14px; font-weight: 700; }}
QLabel#Muted {{ color: {TEXTO2}; }}
QLabel#KpiNum {{ color: {TEXTO}; font-size: 22px; font-weight: 700; }}
QLabel#KpiLbl {{ color: {TEXTO2}; font-size: 11px; }}
QPushButton#Primary {{ background-color: {LIMA}; border: 1px solid {LIMA}; border-radius: 7px; padding: 7px 14px; color: #1a2e05; font-weight: 700; }}
QPushButton#Primary:hover {{ background-color: {LIMA_HOVER}; }}
QPushButton#Primary:disabled {{ background-color: #3a3a38; border-color: #3a3a38; color: #8a8a86; }}
QPushButton#Secondary {{ background-color: transparent; border: 1px solid {BORDE}; border-radius: 7px; padding: 6px 12px; color: {TEXTO}; }}
QPushButton#Secondary:hover {{ border-color: {LIMA}; color: {LIMA}; }}
QPushButton#Danger {{ background-color: transparent; border: 1px solid #5a2b2e; border-radius: 7px; padding: 6px 12px; color: {ROJO}; }}
QPushButton#Danger:hover {{ background-color: #2e1a1c; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{ background-color: #1f1f1f; border: 1px solid {BORDE}; border-radius: 7px; padding: 7px; color: {TEXTO}; selection-background-color: #3f6212; }}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {LIMA}; }}
QTabWidget::pane {{ border: 1px solid {BORDE}; border-radius: 8px; background: {TARJETA}; }}
QTabBar::tab {{ background: transparent; color: {TEXTO2}; padding: 8px 14px; border: none; font-weight: 600; }}
QTabBar::tab:selected {{ color: {LIMA}; border-bottom: 2px solid {LIMA}; }}
QProgressBar {{ background: #232323; border: 1px solid {BORDE}; border-radius: 6px; text-align: center; color: {TEXTO}; height: 14px; }}
QProgressBar::chunk {{ background-color: {LIMA}; border-radius: 5px; }}
QTableWidget {{ background-color: {TARJETA}; color: {TEXTO}; gridline-color: {BORDE}; border: 1px solid {BORDE}; border-radius: 8px; }}
QTableWidget::item {{ padding: 4px; }}
QHeaderView::section {{ background-color: #2a2a2a; color: {TEXTO2}; border: none; padding: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; }}
QScrollBar::handle:vertical {{ background: #3a3a38; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: #4a4a48; }}
QCheckBox {{ color: {TEXTO}; spacing: 6px; }}
QSlider::groove:horizontal {{ height: 6px; background: #2e2e2c; border-radius: 3px; }}
QSlider::handle:horizontal {{ background: {LIMA}; width: 14px; border-radius: 7px; margin: -4px 0; }}
QToolTip {{ background: #2a2a2a; color: {TEXTO}; border: 1px solid {BORDE}; }}
QMessageBox {{ background-color: {TARJETA}; }}
"""
