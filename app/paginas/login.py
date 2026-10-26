"""Página de autenticación integrada en la ventana principal de PhysiCell Lab.

Se muestra dentro del mismo QStackedWidget de LabWindow, sin crear
segunda ventana ni diálogo independiente.
"""
from PyQt6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QWidget, QFrame, QMessageBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from .base import (
    PaginaBase, Seccion, Tarjeta, DialogoBase, ESPACIO_M, ESPACIO_L,
    TAM_H2,
)
from .. import servicios as SERV


class PaginaLogin(PaginaBase):
    """Pantalla de inicio de sesión integrada en la ventana principal."""

    def __init__(self, lab_window):
        super().__init__(lab_window)
        self.auth_service = None

    def build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(ESPACIO_L, ESPACIO_L, ESPACIO_L, ESPACIO_L)
        lay.setSpacing(ESPACIO_M)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.auth_service = SERV.AuthService(self.db_path())

        # Tarjeta central con el formulario de login
        tarjeta = Tarjeta(elevado=True)
        tarjeta.setFixedWidth(420)
        tarjeta.setFixedHeight(520)

        tlay = tarjeta.layout_interno()
        tlay.setContentsMargins(ESPACIO_L, ESPACIO_L, ESPACIO_L, ESPACIO_L)
        tlay.setSpacing(ESPACIO_M)

        # Título
        titulo = QLabel("PhysiCell Lab")
        titulo.setObjectName("H1")
        titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tlay.addWidget(titulo)

        subtitulo = QLabel("Iniciar sesión")
        subtitulo.setObjectName("H2")
        subtitulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tlay.addWidget(subtitulo)

        tlay.addSpacing(ESPACIO_M)

        # Campo de usuario
        self.edit_user = QLineEdit()
        self.edit_user.setPlaceholderText("Usuario")
        self.edit_user.setFixedHeight(36)
        tlay.addWidget(self.edit_user)

        # Campo de contraseña
        self.edit_pass = QLineEdit()
        self.edit_pass.setPlaceholderText("Contraseña")
        self.edit_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit_pass.setFixedHeight(36)
        self.edit_pass.returnPressed.connect(self._intentar_login)
        tlay.addWidget(self.edit_pass)

        # Mensaje de error (oculto por defecto)
        self.lbl_error = QLabel("")
        self.lbl_error.setObjectName("Muted")
        self.lbl_error.setStyleSheet("color: #E5484D; font-weight: 600;")
        self.lbl_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_error.setVisible(False)
        self.lbl_error.setWordWrap(True)
        tlay.addWidget(self.lbl_error)

        tlay.addSpacing(ESPACIO_M)

        # Botón entrar
        btn_entrar = QPushButton("Entrar")
        btn_entrar.setObjectName("Primary")
        btn_entrar.setFixedHeight(38)
        btn_entrar.clicked.connect(self._intentar_login)
        tlay.addWidget(btn_entrar)

        # Botón registrar (solo si no hay usuarios)
        btn_reg = QPushButton("Crear cuenta")
        btn_reg.setObjectName("Secondary")
        btn_reg.setFixedHeight(34)
        btn_reg.clicked.connect(self._mostrar_registro)
        tlay.addWidget(btn_reg)

        tlay.addStretch()

        # Centrar la tarjeta en la página
        cont = QWidget()
        cl = QVBoxLayout(cont)
        cl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cl.addWidget(tarjeta)
        lay.addWidget(cont)

        return self

    def _intentar_login(self):
        usuario = self.edit_user.text().strip()
        password = self.edit_pass.text()

        if not usuario or not password:
            self._mostrar_error("Ingresa usuario y contraseña.")
            return

        resultado = self.auth_service.login(usuario, password)
        if resultado.get("ok"):
            self.lbl_error.setVisible(False)
            self.lw._autenticado(resultado["usuario"])
        else:
            self._mostrar_error(resultado.get("error", "Error de autenticación"))

    def _mostrar_error(self, mensaje):
        self.lbl_error.setText(mensaje)
        self.lbl_error.setVisible(True)

    def _mostrar_registro(self):
        usuario, ok1 = self._pedir_texto("Nuevo usuario", "Nombre de usuario:")
        if not ok1 or not usuario:
            return
        email, ok2 = self._pedir_texto("Correo electrónico", "Email:")
        if not ok2 or not email:
            return
        password, ok3 = self._pedir_texto("Contraseña", "Contraseña:", modo_password=True)
        if not ok3 or not password:
            return

        resultado = self.auth_service.registrar(usuario, email, password)
        if resultado.get("ok"):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(self.lw, "Registro", "Cuenta creada. Ahora puedes iniciar sesión.")
        else:
            self._mostrar_error(resultado.get("error", "Error al crear cuenta"))

    def _pedir_texto(self, titulo, etiqueta, modo_password=False):
        from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFormLayout, QLineEdit
        dlg = QDialog(self.lw)
        dlg.setWindowTitle(titulo)
        dlg.setMinimumWidth(350)
        lay = QVBoxLayout(dlg)
        form = QFormLayout()
        edit = QLineEdit()
        if modo_password:
            edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setPlaceholderText(etiqueta)
        form.addRow(etiqueta, edit)
        lay.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("Aceptar")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        lay.addWidget(btns)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        if dlg.exec():
            return edit.text().strip(), True
        return "", False
