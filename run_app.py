#!/usr/bin/env python3
"""Punto de entrada de la aplicacion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from PyQt6.QtWidgets import QApplication
from app.interfaz_notion import NotionWindow, init_database


def main():
    init_database()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = NotionWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
