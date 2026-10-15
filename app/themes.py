#!/usr/bin/env python3
"""Temas QSS: claro, oscuro, verde fosforescente."""

LIGHT_QSS = """
QMainWindow { background-color: #fafafa; color: #212121; }
QWidget { font-family: 'Segoe UI'; }
QFrame#CardExperiment { background-color: white; border: 1px solid #e0e0e0; border-radius: 8px; margin: 4px 0; }
QFrame#CardExperiment:hover { border-color: #1976d2; background-color: #f8f9fa; }
QPushButton { background-color: #f0f0f0; border: 1px solid #d0d0d0; border-radius: 4px; padding: 5px 10px; color: #212121; }
QPushButton:hover { background-color: #e0e0e0; }
QPushButton:disabled { color: #9e9e9e; }
QLineEdit, QSpinBox, QTextEdit, QPlainTextEdit { border: 1px solid #c0c0c0; border-radius: 4px; padding: 4px; background: white; color: #212121; }
QProgressBar { border: 1px solid #b0b0b0; border-radius: 4px; background: #f5f5f5; text-align: center; color: #212121; }
QProgressBar::chunk { background-color: #1976d2; }
QLabel { color: #212121; }
QScrollArea { border: none; }
"""

DARK_QSS = """
QMainWindow { background-color: #1a1a2e; color: #e9e9e9; }
QWidget { font-family: 'Segoe UI'; }
QFrame#CardExperiment { background-color: #2a3a50; border: 1px solid #0f3460; border-radius: 8px; margin: 4px 0; }
QFrame#CardExperiment:hover { border-color: #4fc3f7; background-color: #24344d; }
QPushButton { background-color: #0f3460; border: 1px solid #164078; border-radius: 4px; padding: 5px 10px; color: #e9e9e9; }
QPushButton:hover { background-color: #164078; }
QPushButton:disabled { color: #78909c; }
QLineEdit, QSpinBox, QTextEdit, QPlainTextEdit { border: 1px solid #0f3460; border-radius: 4px; padding: 4px; background: #1e2d45; color: #e9e9e9; }
QProgressBar { border: 1px solid #0f3460; border-radius: 4px; background: #1e2d45; text-align: center; color: #e9e9e9; }
QProgressBar::chunk { background-color: #4fc3f7; }
QLabel { color: #e9e9e9; }
QScrollArea { border: none; }
"""

GREEN_QSS = """
QMainWindow { background-color: #f0fdf4; color: #166534; }
QWidget { font-family: 'Segoe UI'; }
QFrame#CardExperiment { background-color: white; border: 2px solid #059669; border-radius: 8px; margin: 4px 0; }
QFrame#CardExperiment:hover { border-color: #00c853; background-color: #f0fdf4; }
QPushButton { background-color: #059669; border: 1px solid #059669; border-radius: 4px; padding: 5px 10px; color: white; font-weight: bold; }
QPushButton:hover { background-color: #00c853; border-color: #00c853; }
QPushButton:disabled { background-color: #a7f3d0; color: #4b5563; }
QLineEdit, QSpinBox, QTextEdit, QPlainTextEdit { border: 1px solid #059669; border-radius: 4px; padding: 4px; background: white; color: #166534; }
QProgressBar { border: 2px solid #059669; border-radius: 4px; background: #f0fdf4; text-align: center; color: #166534; }
QProgressBar::chunk { background-color: #00ff88; width: 10px; }
QLabel { color: #166534; }
QScrollArea { border: none; }
"""

THEMES = {"claro": LIGHT_QSS, "oscuro": DARK_QSS, "verde": GREEN_QSS}


def detectar_tema_sistema():
    """Detecta claro/oscuro del SO via Qt cuando sea posible, sino claro."""
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtCore import Qt
        app = QApplication.instance()
        if app:
            hints = app.styleHints()
            # Qt 6.5+: colorScheme
            try:
                scheme = hints.colorScheme()
                # 1=Light, 2=Dark segun Qt.ColorScheme
                if int(scheme) == 2:
                    return "oscuro"
                return "claro"
            except Exception:
                pass
    except Exception:
        pass
    return "claro"
