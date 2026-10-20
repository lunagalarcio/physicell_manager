#!/usr/bin/env python3
"""Temas QSS estilo Notion: claro, oscuro. Botones verde con hover amarillo."""

NOTION_FONT = "font-family: 'Segoe UI', 'Inter', sans-serif;"

LIGHT_QSS = f"""
QMainWindow {{ background-color: #f7f7f5; color: #37352f; }}
QWidget {{ {NOTION_FONT} font-size: 13px; }}
QFrame#CardExperiment {{ background-color: white; border: 1px solid #e9e9e7; border-radius: 10px; margin: 6px 0; padding: 4px; }}
QFrame#CardExperiment:hover {{ border-color: #22c55e; background-color: #fbfdfb; }}
QPushButton {{ background-color: #22c55e; border: 1px solid #16a34a; border-radius: 6px; padding: 6px 12px; color: white; font-weight: 600; }}
QPushButton:hover {{ background-color: #facc15; border-color: #eab308; color: #422006; }}
QPushButton:pressed {{ background-color: #16a34a; }}
QPushButton:disabled {{ background-color: #e7e7e4; border-color: #e7e7e4; color: #9b9b97; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{ border: 1px solid #e0e0de; border-radius: 6px; padding: 6px; background: white; color: #37352f; selection-background-color: #fef08a; }}
QProgressBar {{ border: 1px solid #e0e0de; border-radius: 6px; background: #f1f1ef; text-align: center; color: #37352f; height: 14px; }}
QProgressBar::chunk {{ background-color: #22c55e; border-radius: 5px; }}
QLabel {{ color: #37352f; }}
QCheckBox {{ color: #37352f; spacing: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: #fefce8; color: #422006; border: 1px solid #eab308; }}
"""

DARK_QSS = f"""
QMainWindow {{ background-color: #191919; color: #e8e8e6; }}
QWidget {{ {NOTION_FONT} font-size: 13px; }}
QFrame#CardExperiment {{ background-color: #202020; border: 1px solid #2e2e2c; border-radius: 10px; margin: 6px 0; padding: 4px; }}
QFrame#CardExperiment:hover {{ border-color: #22c55e; background-color: #232823; }}
QPushButton {{ background-color: #22c55e; border: 1px solid #16a34a; border-radius: 6px; padding: 6px 12px; color: #052e16; font-weight: 600; }}
QPushButton:hover {{ background-color: #facc15; border-color: #eab308; color: #422006; }}
QPushButton:pressed {{ background-color: #16a34a; color: white; }}
QPushButton:disabled {{ background-color: #2e2e2c; border-color: #2e2e2c; color: #6f6f6b; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{ border: 1px solid #2e2e2c; border-radius: 6px; padding: 6px; background: #202020; color: #e8e8e6; selection-background-color: #713f12; }}
QProgressBar {{ border: 1px solid #2e2e2c; border-radius: 6px; background: #202020; text-align: center; color: #e8e8e6; height: 14px; }}
QProgressBar::chunk {{ background-color: #22c55e; border-radius: 5px; }}
QLabel {{ color: #e8e8e6; }}
QCheckBox {{ color: #e8e8e6; spacing: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: #422006; color: #fefce8; border: 1px solid #eab308; }}
"""

# Verde Notion: base clara verdosa, acentos verde/amarillo más marcados
GREEN_QSS = f"""
QMainWindow {{ background-color: #f2fbf4; color: #14532d; }}
QWidget {{ {NOTION_FONT} font-size: 13px; }}
QFrame#CardExperiment {{ background-color: white; border: 1px solid #bbf7d0; border-radius: 10px; margin: 6px 0; padding: 4px; }}
QFrame#CardExperiment:hover {{ border-color: #22c55e; background-color: #f0fdf4; }}
QPushButton {{ background-color: #16a34a; border: 1px solid #15803d; border-radius: 6px; padding: 6px 12px; color: white; font-weight: 600; }}
QPushButton:hover {{ background-color: #facc15; border-color: #eab308; color: #422006; }}
QPushButton:pressed {{ background-color: #15803d; }}
QPushButton:disabled {{ background-color: #dcfce7; border-color: #dcfce7; color: #64748b; }}
QLineEdit, QSpinBox, QComboBox, QTextEdit, QPlainTextEdit {{ border: 1px solid #bbf7d0; border-radius: 6px; padding: 6px; background: white; color: #14532d; selection-background-color: #fef08a; }}
QProgressBar {{ border: 1px solid #bbf7d0; border-radius: 6px; background: #ecfdf5; text-align: center; color: #14532d; height: 14px; }}
QProgressBar::chunk {{ background-color: #22c55e; border-radius: 5px; }}
QLabel {{ color: #14532d; }}
QCheckBox {{ color: #14532d; spacing: 6px; }}
QScrollArea {{ border: none; background: transparent; }}
QToolTip {{ background: #fefce8; color: #422006; border: 1px solid #eab308; }}
"""

THEMES = {"claro": LIGHT_QSS, "oscuro": DARK_QSS, "verde": GREEN_QSS}


def detectar_tema_sistema():
    """Detecta claro/oscuro del SO via Qt cuando sea posible, sino claro."""
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            hints = app.styleHints()
            try:
                scheme = hints.colorScheme()
                if int(scheme) == 2:
                    return "oscuro"
                return "claro"
            except Exception:
                pass
    except Exception:
        pass
    return "claro"
