#!/usr/bin/env python3
"""Punto de entrada de la aplicacion."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from PyQt6.QtWidgets import QApplication
from app.lab_window import LabWindow
from app.nucleo import init_database


def instalar_registro_errores():
    """Guarda cualquier excepcion no controlada con traza completa y la muestra."""
    import traceback
    from datetime import datetime

    def _hook(tipo, valor, tb):
        traza = "".join(traceback.format_exception(tipo, valor, tb))
        ruta = None
        try:
            from app.nucleo import get_user_data_dir
            ruta = Path(get_user_data_dir()) / "error.log"
            with open(ruta, "a", encoding="utf-8") as f:
                f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n{traza}\n")
        except Exception:
            ruta = None
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "Error inesperado",
                f"{tipo.__name__}: {valor}\n\n"
                f"Detalle tecnico guardado en:\n{ruta or '(no se pudo escribir)'}\n\n"
                f"{traza[-1500:]}",
            )
        except Exception:
            pass

    sys.excepthook = _hook


def main():
    instalar_registro_errores()
    init_database()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    window = LabWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
