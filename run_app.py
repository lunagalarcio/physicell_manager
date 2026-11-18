#!/usr/bin/env python3
"""Punto de entrada de la aplicacion."""
import sys
import os
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.resolve()))

from PyQt6.QtWidgets import QApplication
from app.lab_window import LabWindow
from app.nucleo import init_database


def _ruta_log():
    try:
        from app.nucleo import get_user_data_dir
        p = Path(get_user_data_dir()) / "error.log"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p
    except Exception:
        return Path(os.path.expanduser("~")) / "physicell_error.log"


def _escribir_log(texto):
    try:
        from datetime import datetime
        ruta = _ruta_log()
        with open(ruta, "a", encoding="utf-8") as f:
            f.write(f"\n[{datetime.now().isoformat(timespec='seconds')}]\n{texto}\n")
        return ruta
    except Exception:
        return None


def instalar_registro_errores():
    """Intercepta CUALQUIER excepción no controlada en el hilo principal o en threads.

    Sin esto, una excepción en un QThread o en código de fondo mata el proceso
    silenciosamente sin mostrar ningún mensaje.
    """

    def _hook_principal(tipo, valor, tb):
        """Excepción no controlada en el hilo principal de Qt."""
        traza = "".join(traceback.format_exception(tipo, valor, tb))
        ruta = _escribir_log(traza)
        try:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "Error inesperado",
                f"{tipo.__name__}: {valor}\n\n"
                f"Log guardado en:\n{ruta or '(no disponible)'}\n\n"
                f"{traza[-2000:]}",
            )
        except Exception:
            print(f"[CRASH] {traza}", file=sys.stderr)

    sys.excepthook = _hook_principal

    # ── Excepción en un hilo secundario (threading.Thread, QThread.run) ──
    # En Python ≥ 3.8 existe threading.excepthook para capturar esto.
    # Sin él, una excepción en un QThread/Thread cierra el proceso sin aviso.
    try:
        import threading

        def _hook_thread(args):
            if args.exc_type is SystemExit:
                return  # salida limpia, no es un crash
            traza = "".join(traceback.format_exception(
                args.exc_type, args.exc_value, args.exc_traceback
            ))
            hilo = getattr(args.thread, "name", "desconocido")
            mensaje = f"[Hilo: {hilo}]\n{traza}"
            ruta = _escribir_log(mensaje)
            # Mostrar el error en el hilo principal a través de la cola de Qt
            try:
                from PyQt6.QtCore import QMetaObject, Qt
                from PyQt6.QtWidgets import QApplication, QMessageBox

                def _mostrar():
                    QMessageBox.critical(
                        None,
                        f"Error en hilo secundario ({hilo})",
                        f"Se produjo un error inesperado en un proceso de fondo:\n\n"
                        f"{args.exc_type.__name__}: {args.exc_value}\n\n"
                        f"Log guardado en:\n{ruta or '(no disponible)'}\n\n"
                        f"{traza[-1500:]}",
                    )

                app = QApplication.instance()
                if app:
                    # invokeMethod garantiza ejecución en el hilo de Qt
                    QMetaObject.invokeMethod(
                        app, "_mostrar_error_hilo",
                        Qt.ConnectionType.QueuedConnection,
                    )
                    # Fallback: guardar para mostrarlo en el próximo ciclo de eventos
                    if not hasattr(app, "_errores_hilo"):
                        app._errores_hilo = []
                    app._errores_hilo.append(
                        (f"Error en hilo secundario ({hilo})",
                         f"{args.exc_type.__name__}: {args.exc_value}\n\n{traza[-1500:]}")
                    )
            except Exception:
                print(f"[CRASH HILO] {mensaje}", file=sys.stderr)

        threading.excepthook = _hook_thread
    except AttributeError:
        # Python < 3.8: threading.excepthook no existe
        pass

    # ── Capturar errores pendientes de hilos en el bucle de eventos ──
    try:
        from PyQt6.QtCore import QTimer

        def _vaciar_errores_hilo():
            app = QApplication.instance()
            if not app:
                return
            pendientes = getattr(app, "_errores_hilo", [])
            if pendientes:
                app._errores_hilo = []
                from PyQt6.QtWidgets import QMessageBox
                for titulo, msg in pendientes:
                    QMessageBox.critical(None, titulo, msg)

        # Se instala tras arrancar la app; aquí solo se define la función
        instalar_registro_errores._vaciar = _vaciar_errores_hilo
    except Exception:
        pass


def main():
    instalar_registro_errores()
    init_database()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Vaciar errores de hilos cada 500 ms mientras la app está abierta
    try:
        from PyQt6.QtCore import QTimer
        vaciar = getattr(instalar_registro_errores, "_vaciar", None)
        if vaciar:
            timer = QTimer()
            timer.setInterval(500)
            timer.timeout.connect(vaciar)
            timer.start()
            app._timer_errores = timer  # evitar recolección de basura
    except Exception:
        pass

    window = LabWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
