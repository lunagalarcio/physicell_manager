#!/usr/bin/env python3
"""Tumor 3D científico con PyVista + VTK: membranas, núcleos, estados y corte.

Datos reales de PhysiCell (snapshot SVG + *_cells.mat + grafos + microambiente):
- Membrana: esfera con radio del SVG (como Studio) o derivado del volumen.
- Núcleo: esfera interior con nuclear_radius real (fila 38 del .mat);
  si no hay .mat, aproximación visual al 55% claramente etiquetada.
- Colores por estado vital real (viva/apoptótica/necrótica), por tipo celular
  o por variable (presión/volumen) con escala. Nada inventado.
- Corte con plano, selección con propiedades, frames con play/velocidad.
- Rendimiento: una malla glyph compartida por grupo (3 actores de membrana
  + 3 de núcleo como máximo), sin reconstruir la escena al mover la cámara.
"""
import os
import glob

try:
    import pyvista as pv
    from pyvistaqt import QtInteractor
    PYVISTA_OK = True
    PYVISTA_ERROR = ""
except Exception as e:
    pv = None
    QtInteractor = None
    PYVISTA_OK = False
    PYVISTA_ERROR = str(e)

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QMessageBox, QSlider, QComboBox, QTextEdit, QColorDialog,
)
from PyQt6.QtCore import Qt, QTimer

COLORES_ESTADO = {
    "viva": "#4ADE80",
    "apoptotica": "#FACC15",
    "necrotica": "#EF4444",
}
NOMBRES_ESTADO = {"viva": "Vivas", "apoptotica": "Apoptóticas", "necrotica": "Necróticas"}
PALETA_TIPOS = ["#38BDF8", "#F472B6", "#FBBF24", "#A78BFA", "#34D399",
                "#FB923C", "#22D3EE", "#E879F9", "#A3E635", "#F87171"]


def _oscurecer(hexcolor, f=0.45):
    try:
        h = hexcolor.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return "#{:02x}{:02x}{:02x}".format(int(r * f), int(g * f), int(b * f))
    except Exception:
        return "#3F3F46"


def _snapshots(output_dir):
    if not output_dir or not os.path.isdir(output_dir):
        return []
    return sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))


def _mats(output_dir):
    if not output_dir or not os.path.isdir(output_dir):
        return []
    return sorted(glob.glob(os.path.join(output_dir, "output*_cells.mat")))


def leer_estado_celular(output_dir, frame_idx):
    """Cruza SVG (posición, radio, tipo, color) con cells.mat (estado, núcleo...)."""
    import numpy as _np
    from .visor_widget import parse_snapshot_svg, leer_bounds, detectar_fila_nrad
    snaps = _snapshots(output_dir)
    if not snaps:
        return {"ok": False, "error": "Sin snapshot*.svg en " + str(output_dir)}
    idx = max(0, min(len(snaps) - 1, frame_idx))
    bounds = leer_bounds(output_dir)
    r = parse_snapshot_svg(snaps[idx], bounds)
    if not r.get("ok"):
        return {"ok": False, "error": r.get("error", "?")}
    n = len(r["x"])
    tipos = [str(t) if t else "" for t in list(r.get("types", []))]
    estados = ["desconocido"] * n
    vols = [None] * n
    pres = [None] * n
    ctype = [None] * n
    nuc = [None] * n
    ids = list(range(n))
    ciclo = [None] * n
    fase = [None] * n
    mig = [None] * n
    dano = [None] * n
    adh = [None] * n
    contactobm = [None] * n
    nuc_real = False
    mats = _mats(output_dir)
    if mats:
        mi = idx
        if len(mats) != len(snaps):
            mi = round(idx * (len(mats) - 1) / max(1, len(snaps) - 1))
        try:
            import scipy.io as _sio
            m = _sio.loadmat(mats[mi])["cells"]
            ncols = m.shape[1]
            dead = m[26].ravel() if m.shape[0] > 26 else _np.zeros(ncols)
            dmod = m[27].ravel() if m.shape[0] > 27 else _np.zeros(ncols)
            vols = (m[4].ravel().tolist() if m.shape[0] > 4 else [None] * ncols)
            pres = (m[20].ravel().tolist() if m.shape[0] > 20 else [None] * ncols)
            ctype = (m[5].ravel().tolist() if m.shape[0] > 5 else [None] * ncols)
            nrad = detectar_fila_nrad(m, ncols) if m.shape[0] > 0 else [None] * ncols
            try:
                ids = [int(v) for v in m[0].ravel().tolist()] if m.shape[0] > 0 else list(range(ncols))
            except Exception:
                ids = list(range(ncols))
            cyc = (m[6].ravel().tolist() if m.shape[0] > 6 else [None] * ncols)
            pha = (m[7].ravel().tolist() if m.shape[0] > 7 else [None] * ncols)
            migv = (m[52].ravel().tolist() if m.shape[0] > 52 else [None] * ncols)
            dan = (m[83].ravel().tolist() if m.shape[0] > 83 else [None] * ncols)
            adh = (m[40].ravel().tolist() if m.shape[0] > 40 else [None] * ncols)
            cbm = (m[23].ravel().tolist() if m.shape[0] > 23 else [None] * ncols)
            k = min(n, ncols)
            if any(v is not None and float(v) > 0 for v in nrad[:k]):
                nuc_real = True
            for i in range(k):
                nuc[i] = nrad[i]
                ciclo[i] = cyc[i]
                fase[i] = pha[i]
                mig[i] = migv[i]
                dano[i] = dan[i]
                adh[i] = adh[i]
                contactobm[i] = cbm[i]
                try:
                    is_dead = float(dead[i]) != 0.0
                except Exception:
                    is_dead = False
                if not is_dead:
                    estados[i] = "viva"
                else:
                    try:
                        code = int(float(dmod[i]))
                    except Exception:
                        code = -1
                    estados[i] = "apoptotica" if code == 100 else "necrotica"
        except Exception:
            pass
    return {"ok": True, "idx": idx, "n_snaps": len(snaps), "path": snaps[idx],
            "x": r["x"], "y": r["y"], "r": r["r"], "rgba": r["rgba"],
            "tipos": tipos, "estados": estados, "vols": vols, "pres": pres,
            "ctype": ctype, "nuc": nuc, "nuc_real": nuc_real,
            "ids": ids, "ciclo": ciclo, "fase": fase, "mig": mig,
            "dano": dano, "adh": adh, "contactobm": contactobm,
            "time": r.get("time", ""), "n": r.get("n", n)}


def leer_sustrato_3d(output_dir, frame_idx):
    from .visor_widget import cargar_substrato, leer_sustratos
    sub = cargar_substrato(output_dir, frame_idx)
    if sub is None:
        return None
    xg, yg, val = sub
    names = leer_sustratos(output_dir) or ["substrato"]
    return {"x": xg, "y": yg, "v": val, "nombre": names[0]}


class DialogoVTK(QDialog):
    def __init__(self, parent, output_dir, titulo="Tumor 3D"):
        super().__init__(parent)
        self.output_dir = output_dir
        self.titulo = titulo
        self.colores = dict(COLORES_ESTADO)
        self.modo = "estado"
        self.setWindowTitle("PhysiCell Lab — Tumor 3D (PyVista/VTK)")
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint | Qt.WindowMinimizeButtonHint)
        self.setMinimumSize(900, 600)
        self.resize(1280, 780)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        # ---- panel lateral ----
        side = QWidget()
        side.setFixedWidth(330)
        sl = QVBoxLayout(side)
        sl.setSpacing(6)
        t = QLabel(titulo)
        t.setWordWrap(True)
        t.setStyleSheet("font-weight: bold; font-size: 14px;")
        sl.addWidget(t)
        self.lbl_frame = QLabel("")
        self.lbl_frame.setWordWrap(True)
        sl.addWidget(self.lbl_frame)
        sl.addWidget(QLabel("<b>Colorear por</b>"))
        self.cmb_modo = QComboBox()
        self.cmb_modo.addItems(["estado", "tipo", "presión", "volumen"])
        self.cmb_modo.currentTextChanged.connect(self._modo)
        sl.addWidget(self.cmb_modo)
        self.cmb_var = QComboBox()
        self.cmb_var.addItems(["presión", "volumen"])
        self.cmb_var.setVisible(False)
        self.cmb_var.currentTextChanged.connect(lambda _: self.refrescar())
        sl.addWidget(self.cmb_var)
        sl.addWidget(QLabel("<b>Leyenda</b>"))
        self.lbl_leyenda = QLabel("")
        self.lbl_leyenda.setWordWrap(True)
        sl.addWidget(self.lbl_leyenda)
        row_c = QHBoxLayout()
        for clave in ("viva", "apoptotica", "necrotica"):
            b = QPushButton(NOMBRES_ESTADO[clave])
            b.setToolTip(f"Color de células {NOMBRES_ESTADO[clave].lower()} (clic para cambiar)")
            b.clicked.connect(lambda _=False, k=clave: self._color(k))
            setattr(self, f"btn_{clave}", b)
            row_c.addWidget(b)
        cc = QWidget()
        cc.setLayout(row_c)
        sl.addWidget(cc)
        sl.addWidget(QLabel("<b>Capas</b>"))
        self.chk_nuc = QCheckBox("Núcleos")
        self.chk_nuc.setChecked(True)
        self.chk_nuc.setToolTip("Esfera interior con radio nuclear real de PhysiCell (o aproximación si no hay .mat)")
        self.chk_vec = QCheckBox("Vecindad (contacto)")
        self.chk_vec.setChecked(True)
        self.chk_att = QCheckBox("Uniones (attached/spring)")
        self.chk_att.setChecked(True)
        self.chk_sub = QCheckBox("Sustrato (si existe)")
        self.chk_sub.setChecked(False)
        self.chk_org = QCheckBox("Variación orgánica ±3% (visual)")
        self.chk_org.setChecked(False)
        self.chk_org.setToolTip("Jitter determinista del radio solo visual. No altera los datos.")
        for c in (self.chk_nuc, self.chk_vec, self.chk_att, self.chk_sub, self.chk_org):
            c.stateChanged.connect(lambda _: self.refrescar())
            sl.addWidget(c)
        sl.addWidget(QLabel("<b>Corte</b>"))
        self.chk_corte = QCheckBox("Plano de corte")
        self.chk_corte.setToolTip("Explora el interior del tumor desplazando el plano")
        self.chk_corte.stateChanged.connect(lambda _: self.refrescar())
        sl.addWidget(self.chk_corte)
        self.cmb_eje = QComboBox()
        self.cmb_eje.addItems(["X", "Y", "Z"])
        self.cmb_eje.setToolTip("Eje perpendicular al plano de corte")
        self.cmb_eje.currentTextChanged.connect(lambda _: self._corte())
        sl.addWidget(self.cmb_eje)
        self.sld_corte = QSlider(Qt.Orientation.Horizontal)
        self.sld_corte.setRange(0, 100)
        self.sld_corte.setValue(50)
        self.sld_corte.valueChanged.connect(lambda _: self._corte())
        sl.addWidget(self.sld_corte)
        sl.addWidget(QLabel("<b>Célula seleccionada</b>"))
        self.info = QTextEdit()
        self.info.setReadOnly(True)
        self.info.setMinimumHeight(340)
        self.info.setStyleSheet("""
            font-family: Consolas, monospace;
            font-size: 12px;
            background-color: #1a1a1a;
            border: 1px solid #353535;
            border-radius: 6px;
            padding: 6px;
        """)
        self.info.setPlaceholderText("Haz clic en una célula para consultar su información.")
        sl.addWidget(self.info)
        row_sel = QHBoxLayout()
        self.btn_centrar = QPushButton("Centrar cámara")
        self.btn_centrar.setToolTip("Centra la cámara en la célula seleccionada")
        self.btn_centrar.clicked.connect(self._centrar)
        self.btn_limpiar = QPushButton("Limpiar")
        self.btn_limpiar.setToolTip("Limpia la selección actual")
        self.btn_limpiar.clicked.connect(lambda: self._limpiar_sel(mensaje=True))
        row_sel.addWidget(self.btn_centrar)
        row_sel.addWidget(self.btn_limpiar)
        cs = QWidget()
        cs.setLayout(row_sel)
        sl.addWidget(cs)
        sl.addStretch()
        lay.addWidget(side)
        # ---- área 3D + temporal ----
        center = QWidget()
        cl = QVBoxLayout(center)
        cl.setContentsMargins(0, 0, 0, 0)
        self.plotter = QtInteractor(self)
        cl.addWidget(self.plotter, 1)
        bot = QHBoxLayout()
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(lambda: self._mover(-1))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(lambda _: self.refrescar())
        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(lambda: self._mover(1))
        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(60)
        self.btn_play.clicked.connect(self._play)
        self.cmb_vel = QComboBox()
        self.cmb_vel.addItems(["0.5x", "1x", "2x", "4x"])
        self.cmb_vel.setCurrentText("1x")
        self.cmb_vel.currentTextChanged.connect(self._vel)
        b_reset = QPushButton("Restablecer vista")
        b_reset.clicked.connect(self._reset)
        bot.addWidget(self.btn_prev)
        bot.addWidget(self.slider, 1)
        bot.addWidget(self.btn_next)
        bot.addWidget(self.btn_play)
        bot.addWidget(self.cmb_vel)
        bot.addWidget(b_reset)
        cb = QWidget()
        cb.setLayout(bot)
        cl.addWidget(cb)
        lay.addWidget(center, 1)
        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._avanzar)
        self._atajos()
        try:
            self.plotter.render_window.SetMultiSamples(8)
        except Exception:
            pass
        self._cam_init = False
        self._sel_id = None
        self._press_xy = None
        try:
            _vtk_iren = self.plotter.iren.interactor
            _vtk_iren.AddObserver("LeftButtonPressEvent", self._on_press)
            _vtk_iren.AddObserver("LeftButtonReleaseEvent", self._on_release)
        except Exception:
            pass
        try:
            self.plotter.enable_point_picking(callback=self._on_punto, left_clicking=True,
                                              picker="cell", show_message=False,
                                              show_point=False, use_picker=True)
        except Exception:
            pass
        self._actores_corte = []
        self._pintar_colores()
        self._cargar_frames()
        self._luces()
        self.refrescar()

    # ---- datos y controles ----
    def _cargar_frames(self):
        import glob as _g
        self.snaps = sorted(_g.glob(os.path.join(self.output_dir, "snapshot*.svg"))) if os.path.isdir(self.output_dir) else []
        self.slider.blockSignals(True)
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, len(self.snaps) - 1))
        self.slider.setValue(0)
        self.slider.blockSignals(False)

    def _mover(self, d):
        if self.snaps:
            self.slider.setValue(max(0, min(len(self.snaps) - 1, self.slider.value() + d)))

    def _play(self):
        if self._timer.isActive():
            self._timer.stop()
            self.btn_play.setText("Play")
        elif self.snaps:
            self._timer.start()
            self.btn_play.setText("Pausa")

    def _vel(self, txt):
        self._timer.setInterval({"0.5x": 1600, "1x": 800, "2x": 400, "4x": 200}.get(txt, 800))

    def _avanzar(self):
        if not self.snaps:
            return
        v = self.slider.value() + 1
        self.slider.setValue(0 if v >= len(self.snaps) else v)

    def _reset(self):
        self._cam_init = False
        self._encuadrar()

    def _res_esferas(self, n):
        """Resolución adaptativa: detalle alto con pocas células, ligera con miles."""
        if n > 2000:
            return 10
        if n > 500:
            return 12
        return 20

    def _encuadrar(self):
        """Centra el conjunto celular y aprovecha el espacio sin deformar proporciones."""
        try:
            import numpy as _np
            d = getattr(self, "_datos", None)
            if not d or not d.get("ok") or not len(d["x"]):
                self.plotter.reset_camera()
                return
            x = _np.asarray(d["x"], float)
            y = _np.asarray(d["y"], float)
            cx, cy = float(x.mean()), float(y.mean())
            span = float(max(x.max() - x.min(), y.max() - y.min(), 1.0))
            dist = span * 1.35 + 50.0
            cam = self.plotter.camera
            cam.SetFocalPoint(cx, cy, 0.0)
            cam.SetPosition(cx + dist * 0.55, cy - dist * 0.75, dist * 0.65)
            cam.SetViewUp(0, 0, 1)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
            self._cam_init = True
        except Exception:
            try:
                self.plotter.reset_camera()
            except Exception:
                pass

    def _modo(self, txt):
        self.modo = {"estado": "estado", "tipo": "tipo"}.get(txt, "variable")
        self.cmb_var.setVisible(self.modo == "variable")
        if txt in ("presión", "volumen"):
            self.cmb_var.setCurrentText(txt)
        self.refrescar()

    def _color(self, clave):
        from PyQt6.QtGui import QColor as _QC
        c = QColorDialog.getColor(_QC(self.colores[clave]), self, f"Color {NOMBRES_ESTADO[clave]}")
        if c.isValid():
            self.colores[clave] = c.name()
            self._pintar_colores()
            self.refrescar()

    def _pintar_colores(self):
        for clave in ("viva", "apoptotica", "necrotica"):
            getattr(self, f"btn_{clave}").setStyleSheet(
                f"background-color: {self.colores[clave]}; border-radius: 4px; padding: 4px;")

    def _luces(self):
        try:
            import vtk
            for lgt in getattr(self, "_mis_luces", []):
                try:
                    self.plotter.renderer.RemoveLight(lgt)
                except Exception:
                    pass
            key = vtk.vtkLight()
            key.SetPosition(1.0, 1.0, 2.0)
            key.SetIntensity(0.85)
            key.SetLightTypeToSceneLight()
            fill = vtk.vtkLight()
            fill.SetPosition(-1.5, -0.5, 0.5)
            fill.SetIntensity(0.3)
            fill.SetLightTypeToSceneLight()
            rim = vtk.vtkLight()
            rim.SetPosition(0.0, -1.0, -1.5)
            rim.SetIntensity(0.45)
            rim.SetLightTypeToSceneLight()
            self._mis_luces = [key, fill, rim]
            for lgt in self._mis_luces:
                self.plotter.renderer.AddLight(lgt)
        except Exception:
            pass

    def _jitter(self, n):
        import numpy as _np
        i = _np.arange(n, dtype=float)
        return 1.0 + 0.03 * _np.sin(i * 12.9898) * _np.cos(i * 78.233)

    # ---- render ----
    def refrescar(self):
        import numpy as _np
        self.plotter.clear()
        self.plotter.set_background("#141414")
        self._luces()
        self._actores_corte = []
        if not self.snaps:
            self.lbl_frame.setText("Sin snapshot*.svg. Ejecuta PhysiCell primero.")
            return
        idx = self.slider.value()
        d = leer_estado_celular(self.output_dir, idx)
        if not d.get("ok"):
            self.lbl_frame.setText(f"Error: {d.get('error')}")
            return
        x, y = _np.asarray(d["x"], float), _np.asarray(d["y"], float)
        n = len(x)
        z = _np.zeros(n)
        try:
            rv = _np.asarray(d["r"], float)
        except Exception:
            rv = _np.full(n, 8.0)
        rv = _np.where(rv > 0, rv, 8.0)
        est = d["estados"]
        tipos = d["tipos"]
        vols = d["vols"]
        nuc = d["nuc"]
        modo = self.modo
        var = self.cmb_var.currentText() if modo == "variable" else ""
        # --- variación orgánica por estado (solo visual, no altera datos) ---
        jitter_estado = {"viva": 0.0, "apoptotica": 0.05, "necrotica": 0.12}
        jit = _np.array([1.0 + jitter_estado.get(e, 0.0) *
                         _np.sin(i * 12.9898) * _np.cos(i * 78.233)
                         for i, e in enumerate(est)])
        if self.chk_org.isChecked():
            rv = rv * jit
        # --- membranas por grupo con geometría compartida ---
        grupos = []  # (nombre, ids, color)
        if modo == "tipo":
            tset = sorted(set(str(t) for t in tipos if t), key=str)
            if not tset:
                tset = ["default"]
            for k, t in enumerate(tset):
                ids = [i for i in range(n) if str(tipos[i] if i < len(tipos) else "") == t]
                if ids:
                    grupos.append((f"tipo:{t}", ids, PALETA_TIPOS[k % len(PALETA_TIPOS)]))
        elif modo == "variable":
            grupo_ids = list(range(n))
            grupos.append(("var", grupo_ids, None))
        else:
            for clave in ("viva", "apoptotica", "necrotica"):
                ids = [i for i in range(n) if est[i] == clave]
                if ids:
                    grupos.append((clave, ids, self.colores[clave]))
            ids = [i for i in range(n) if est[i] == "desconocido"]
            if ids:
                grupos.append(("desconocido", ids, "#9AA0A6"))
        import numpy as _n2
        res = self._res_esferas(n)
        # rango real de la variable para la leyenda
        vals_range = None
        if modo == "variable" and n:
            try:
                if var == "presión":
                    vs = [float(d["pres"][i]) for i in range(min(n, len(d["pres"])))
                          if d["pres"][i] is not None]
                else:
                    vs = [float(vols[i]) for i in range(min(n, len(vols)))
                          if vols[i] is not None]
                if vs:
                    vals_range = (min(vs), max(vs))
            except Exception:
                vals_range = None
        # diferenciación del núcleo por tipo (solo geometría visual)
        res_nuc_por_tipo = {}
        if modo == "tipo" and tipos:
            uniq = sorted(set(str(t) for t in tipos if t))
            for k in range(max(1, len(uniq))):
                res_nuc_por_tipo[uniq[k % len(uniq)] if uniq else "default"] = \
                    max(6, (res - 4) if n < 500 else max(6, res - 6))
        for nombre, ids, color in grupos:
            pts = _n2.column_stack([x[ids], y[ids], z[ids]])
            cloud = pv.PolyData(pts)
            cloud["radius"] = _n2.asarray([float(rv[i]) for i in ids], float)
            esfera = pv.Sphere(radius=1.0, theta_resolution=res, phi_resolution=res)
            glyph = cloud.glyph(geom=esfera, scale="radius", orient=False)
            if modo == "variable":
                vals = []
                for i in ids:
                    if var == "presión":
                        v = d["pres"][i] if i < len(d["pres"]) else None
                    else:
                        v = vols[i] if i < len(vols) else None
                    vals.append(0.0 if v is None else float(v))
                glyph["valor"] = _n2.repeat(_n2.asarray(vals, float), esfera.n_points)
                actor = self.plotter.add_mesh(glyph, scalars="valor", cmap="viridis",
                                             smooth_shading=True, ambient=0.25, diffuse=0.85,
                                             specular=0.4, specular_power=30,
                                             scalar_bar_args={"title": var}, name=nombre)
            else:
                actor = self.plotter.add_mesh(glyph, color=color, smooth_shading=True,
                                             ambient=0.25, diffuse=0.85,
                                             specular=0.4, specular_power=30, name=nombre)
            self._actores_corte.append(actor)
            # --- núcleo interior: radio nuclear real o aproximación etiquetada ---
            if self.chk_nuc.isChecked():
                nrad = []
                res_n = res_nuc_por_tipo.get(str(tipos[ids[0]] if ids[0] < len(tipos) else ""),
                                              max(6, res - 4))
                for i in ids:
                    try:
                        nr = float(nuc[i]) if i < len(nuc) and nuc[i] is not None else 0.0
                    except Exception:
                        nr = 0.0
                    nrad.append(nr if nr > 0 else float(rv[i]) * 0.55)
                cloud_n = pv.PolyData(pts)
                cloud_n["radius"] = _n2.asarray(nrad, float)
                gly_n = cloud_n.glyph(geom=pv.Sphere(radius=1.0, theta_resolution=res_n, phi_resolution=res_n),
                                      scale="radius", orient=False)
                ncol = _oscurecer(color) if color else "#3F3F46"
                a2 = self.plotter.add_mesh(gly_n, color=ncol, smooth_shading=True,
                                          ambient=0.3, diffuse=0.9,
                                          specular=0.12, specular_power=10, name=nombre + ":nucleo")
                self._actores_corte.append(a2)
        # --- interacciones ---
        from .visor_widget import leer_grafo
        pos = {i: (float(x[i]), float(y[i]), 0.0) for i in range(n)}
        if self.chk_vec.isChecked():
            for i, j in leer_grafo(self.output_dir, idx, "neighbor"):
                if i in pos and j in pos:
                    self.plotter.add_mesh(pv.Line(pos[i], pos[j]), color="gray", line_width=2)
        if self.chk_att.isChecked():
            for i, j in leer_grafo(self.output_dir, idx, "attached") | leer_grafo(self.output_dir, idx, "spring"):
                if i in pos and j in pos:
                    self.plotter.add_mesh(pv.Line(pos[i], pos[j]), color="red", line_width=3)
        # --- sustrato: difusión difusa + puntos de alta concentración ---
        if self.chk_sub.isChecked():
            try:
                from .visor_widget import cargar_substrato, leer_sustratos
                sub = cargar_substrato(self.output_dir, idx)
                if sub is not None:
                    xg, yg, val = sub
                    import numpy as _n2
                    vmax = float(val.max())
                    vmin = float(val.min())
                    if vmax - vmin < 1e-12:
                        # sin gradiente real: no dibujar campo uniforme
                        self.lbl_frame.setText(
                            f"{d.get('time','')} — frame {idx+1}/{len(self.snaps)} — {n} células"
                            " — Sustrato: sin gradiente (valor constante). "
                            "Configura initial_condition y uptake/secretion en el XML.")
                    else:
                        try:
                            from scipy.ndimage import gaussian_filter as _gf
                            vblur = _n2.asarray(_gf(_n2.asarray(val, float), sigma=1.8))
                        except Exception:
                            vblur = _n2.asarray(val, float)
                        xga, yga = _n2.asarray(xg), _n2.asarray(yg)
                        names = leer_sustratos(self.output_dir) or ["substrato"]
                        # plano base difuso en z=-8 con plasma (mejor contraste)
                        zga = _n2.full_like(xga, -8.0, dtype=float)
                        grid = pv.StructuredGrid(xga, yga, zga)
                        grid["sustrato"] = vblur.ravel(order="F")
                        self.plotter.add_mesh(grid, scalars="sustrato", cmap="plasma",
                                             opacity=0.55, smooth_shading=True,
                                             scalar_bar_args={"title": f"{names[0]} ({vmin:.3g}…{vmax:.3g})",
                                                              "color": "#F5F5F5",
                                                              "title_font_size": 10,
                                                              "label_font_size": 9})
                        # capa de difusión translúcida cerca de las células
                        zga2 = _n2.full_like(xga, -2.0, dtype=float)
                        grid2 = pv.StructuredGrid(xga, yga, zga2)
                        grid2["sustrato"] = vblur.ravel(order="F")
                        self.plotter.add_mesh(grid2, scalars="sustrato", cmap="hot",
                                             opacity=0.22, smooth_shading=True,
                                             show_scalar_bar=False)
                        # contornos isotérmicos para resaltar gradientes de concentración
                        try:
                            import numpy as _n3
                            levels = _n3.linspace(vmin, vmax, 8)
                            cont = grid.contour(isosurfaces=8, scalars="sustrato")
                            self.plotter.add_mesh(cont.contour, scalars="sustrato", cmap="inferno",
                                                 line_width=2.0, opacity=0.8,
                                                 show_scalar_bar=False)
                        except Exception:
                            pass
                else:
                    self.chk_sub.setChecked(False)
            except Exception:
                pass
        # --- leyenda ---
        from collections import Counter as _C
        if modo == "tipo":
            ct = _C(str(t) for t in tipos if t)
            leg = "Tipos: " + ", ".join(f"{k} ({v})" for k, v in sorted(ct.items(), key=str))
        elif modo == "variable":
            if vals_range:
                vmin, vmax = vals_range
                leg = f"Variable: {var} (viridis {vmin:.4g} … {vmax:.4g})"
            else:
                leg = f"Variable: {var} (escala viridis)"
        else:
            c = _C(est)
            leg = " | ".join(f"{NOMBRES_ESTADO.get(k, k)}: {v}" for k, v in sorted(c.items()) if k != "desconocido")
            if c.get("desconocido"):
                leg += f" | Sin .mat: {c['desconocido']}"
        nuc_txt = "radio nuclear real" if d.get("nuc_real") else "núcleo aproximado (visual)"
        self.lbl_leyenda.setText(leg + f"\nNúcleos: {nuc_txt}.")
        self.lbl_frame.setText(f"{d.get('time','')} — frame {idx+1}/{len(self.snaps)} — {n} células")
        self._datos = d
        if self._sel_id is not None:
            try:
                list(d.get("ids", list(range(n)))).index(self._sel_id)
                self._resaltar()
                self._mostrar_info()
            except Exception:
                self._sel_id = None
                try:
                    self.plotter.remove_actor("seleccion", reset_camera=False)
                except Exception:
                    pass
                self.info.setPlainText("La célula seleccionada ya no está presente en este frame.")
        self._corte()
        if not getattr(self, "_cam_init", False):
            self._encuadrar()
        else:
            try:
                self.plotter.render()
            except Exception:
                pass

    def _corte(self):
        if not self.chk_corte.isChecked():
            try:
                for a in self._actores_corte:
                    a.mapper.SetClippingPlanes(None)
            except Exception:
                pass
            return
        try:
            import vtk
            import numpy as _np
            bounds = []
            for a in self._actores_corte:
                try:
                    b = a.GetBounds()
                    if b:
                        bounds.append(b)
                except Exception:
                    pass
            eje = self.cmb_eje.currentText() if hasattr(self, "cmb_eje") else "X"
            k = {"X": 0, "Y": 1, "Z": 2}.get(eje, 0)
            if bounds:
                lo = min(b[2 * k] for b in bounds)
                hi = max(b[2 * k + 1] for b in bounds)
            else:
                lo, hi = (-500.0, 500.0) if k < 2 else (-10.0, 10.0)
            v0 = lo + (hi - lo) * self.sld_corte.value() / 100.0
            normal = [0, 0, 0]
            normal[k] = 1
            origin = [0, 0, 0]
            origin[k] = v0
            plane = vtk.vtkPlane()
            plane.SetNormal(*normal)
            plane.SetOrigin(*origin)
            planes = vtk.vtkPlanes()
            planes.SetPlanes(plane)
            for a in self._actores_corte:
                try:
                    a.mapper.SetClippingPlanes(planes)
                except Exception:
                    pass
            try:
                self.plotter.render()
            except Exception:
                pass
        except Exception:
            pass

    # ---- selección por ID estable ----
    def _atajos(self):
        """Atajos de teclado: espacio=play, flechas=frames, +/-=zoom."""
        try:
            iren = self.plotter.iren.interactor

            def on_key(obj, ev):
                try:
                    k = iren.GetKeySym() if hasattr(iren, 'GetKeySym') else ''
                    if not k:
                        return
                    k = k.lower()
                    if k == 'space':
                        self._play()
                    elif k == 'right':
                        self._mover(1)
                    elif k == 'left':
                        self._mover(-1)
                    elif k in ('plus', 'equal'):
                        self._zoom(0.85)
                    elif k in ('minus', 'underscore'):
                        self._zoom(1.18)
                except Exception:
                    pass
            iren.AddObserver("KeyPressEvent", on_key)
        except Exception:
            pass

    def _zoom(self, factor):
        try:
            cam = self.plotter.camera
            px, py, pz = cam.GetPosition()
            fx, fy, fz = cam.GetFocalPoint()
            nx = fx + (px - fx) * factor
            ny = fy + (py - fy) * factor
            nz = fz + (pz - fz) * factor
            cam.SetPosition(nx, ny, nz)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
        except Exception:
            pass
        try:
            self._press_xy = obj.GetEventPosition()
        except Exception:
            self._press_xy = None

    def _on_release(self, obj, event):
        try:
            if self._press_xy is None:
                return
            pos = obj.GetEventPosition()
            dx = pos[0] - self._press_xy[0]
            dy = pos[1] - self._press_xy[1]
            self._press_xy = None
            if dx * dx + dy * dy > 36:
                return  # era arrastre (rotación), no clic
            self._pick_xy(pos[0], pos[1])
        except Exception:
            pass

    def _on_punto(self, punto, picker=None):
        try:
            import numpy as _np
            d = getattr(self, "_datos", None)
            if not d or not d.get("ok"):
                return
            arr = _np.asarray(punto, dtype=float).ravel()
            if arr.size != 3:
                return
            x, y = _np.asarray(d["x"], float), _np.asarray(d["y"], float)
            dist2 = (x - arr[0]) ** 2 + (y - arr[1]) ** 2
            i = int(_np.argmin(dist2))
            try:
                tol = (float(d["r"][i]) * 1.6) ** 2 + 25.0
            except Exception:
                tol = 400.0
            if dist2[i] <= tol:
                self._seleccionar_por_indice(i)
        except Exception:
            pass

    def _pick_legacy(self, *args):
        try:
            d = getattr(self, "_datos", None)
            if not d or not d.get("ok"):
                return
            import numpy as _np
            x, y = _np.asarray(d["x"], float), _np.asarray(d["y"], float)
            for a in args:
                try:
                    arr = _np.asarray(a, dtype=float).ravel()
                    if arr.size == 3:
                        i = int(_np.argmin((x - arr[0]) ** 2 + (y - arr[1]) ** 2))
                        self._seleccionar_por_indice(i)
                        return
                except Exception:
                    continue
        except Exception:
            pass

    def _pick_xy(self, px, py):
        try:
            import vtk
            d = getattr(self, "_datos", None)
            if not d or not d.get("ok"):
                return
            picker = vtk.vtkCellPicker()
            picker.SetTolerance(0.005)
            if picker.Pick(px, py, 0, self.plotter.renderer) == 0 or picker.GetCellId() < 0:
                self._limpiar_sel(mensaje=False)
                self.info.setPlaceholderText("Haz clic en una célula para consultar su información.")
                return
            import numpy as _np
            pp = picker.GetPickPosition()
            x, y = _np.asarray(d["x"], float), _np.asarray(d["y"], float)
            dist2 = (x - pp[0]) ** 2 + (y - pp[1]) ** 2
            i = int(_np.argmin(dist2))
            try:
                tol = (float(d["r"][i]) * 1.6) ** 2 + 25.0
            except Exception:
                tol = 400.0
            if dist2[i] > tol:
                self._limpiar_sel(mensaje=False)
                return
            self._seleccionar_por_indice(i)
        except Exception:
            pass

    def _seleccionar_por_indice(self, i):
        d = getattr(self, "_datos", None)
        try:
            ids = d.get("ids", list(range(len(d["x"]))))
            self._sel_id = ids[i] if i < len(ids) else i
        except Exception:
            self._sel_id = i
        self._resaltar()
        self._mostrar_info()

    def _limpiar_sel(self, mensaje=False):
        self._sel_id = None
        try:
            self.plotter.remove_actor("seleccion", reset_camera=False)
        except Exception:
            pass
        if mensaje:
            self.info.clear()
        try:
            self.plotter.render()
        except Exception:
            pass

    def _resaltar(self):
        try:
            self.plotter.remove_actor("seleccion", reset_camera=False)
        except Exception:
            pass
        d = getattr(self, "_datos", None)
        if d is None or self._sel_id is None:
            return
        try:
            ids = d.get("ids", list(range(len(d["x"]))))
            i = list(ids).index(self._sel_id)
        except Exception:
            return
        try:
            import numpy as _np
            r = float(d["r"][i]) * 1.18 + 1.0
            sph = pv.Sphere(radius=r, center=(float(d["x"][i]), float(d["y"][i]), 0.0),
                            theta_resolution=20, phi_resolution=20)
            self.plotter.add_mesh(sph, color="#84CC16", style="wireframe", line_width=2.5,
                                 name="seleccion")
            self.plotter.render()
        except Exception:
            pass

    def _centrar(self):
        d = getattr(self, "_datos", None)
        if d is None or self._sel_id is None:
            return
        try:
            import numpy as _np
            ids = d.get("ids", list(range(len(d["x"]))))
            i = list(ids).index(self._sel_id)
            x, y = float(d["x"][i]), float(d["y"][i])
            cam = self.plotter.camera
            px, py, pz = cam.GetPosition()
            dist = float(_np.sqrt((px - x) ** 2 + (py - y) ** 2 + pz ** 2)) or 300.0
            cam.SetFocalPoint(x, y, 0.0)
            cam.SetPosition(x + dist * 0.45, y - dist * 0.55, dist * 0.55)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
        except Exception:
            pass

    def _oxigeno_local(self, x, y):
        try:
            from .visor_widget import cargar_substrato, leer_sustratos
            sub = cargar_substrato(self.output_dir, self.slider.value())
            if sub is None:
                return None, None
            xg, yg, val = sub
            import numpy as _np
            ix = int(_np.argmin(abs(_np.asarray(xg[0, :], float) - x)))
            iy = int(_np.argmin(abs(_np.asarray(yg[:, 0], float) - y)))
            names = leer_sustratos(self.output_dir) or ["substrato"]
            return names[0], float(val[iy, ix])
        except Exception:
            return None, None

    def _mostrar_info(self):
        from collections import Counter as _C
        d = getattr(self, "_datos", None)
        if d is None or self._sel_id is None:
            return
        try:
            ids = list(d.get("ids", list(range(len(d["x"])))))
            i = ids.index(self._sel_id)
        except Exception:
            self.info.setPlainText("La célula seleccionada ya no está presente en este frame.")
            return
        import numpy as _np
        x, y = _np.asarray(d["x"], float), _np.asarray(d["y"], float)
        tip = d["tipos"][i] if i < len(d["tipos"]) else ""
        est = d["estados"][i] if i < len(d["estados"]) else "?"
        vol = d["vols"][i] if i < len(d["vols"]) else None
        pre = d["pres"][i] if i < len(d["pres"]) else None
        cty = d["ctype"][i] if i < len(d["ctype"]) else None
        nr = d["nuc"][i] if i < len(d["nuc"]) else None
        cic = d["ciclo"][i] if i < len(d.get("ciclo", [])) else None
        fas = d["fase"][i] if i < len(d.get("fase", [])) else None
        mig = d["mig"][i] if i < len(d.get("mig", [])) else None
        dan = d["dano"][i] if i < len(d.get("dano", [])) else None
        adh = d["adh"][i] if i < len(d.get("adh", [])) else None
        cbm = d["contactobm"][i] if i < len(d.get("contactobm", [])) else None
        nvec = sum(1 for a, b in self._vec_frame() if a == i or b == i)
        nom_ox, val_ox = self._oxigeno_local(float(x[i]), float(y[i]))
        L = []
        L.append("— General —")
        L.append(f"ID: {self._sel_id}")
        L.append(f"Tipo: {tip or cty if (tip or cty) not in (None, '') else 'No disponible'}")
        L.append(f"Estado: {est}")
        L.append(f"Frame: {d.get('idx', 0)+1}/{d.get('n_snaps', '?')} — {d.get('time', '')}")
        L.append(f"Posición: ({x[i]:.1f}, {y[i]:.1f}, 0.0) µm")
        L.append("— Geometría —")
        L.append(f"Radio: {d['r'][i] if i < len(d['r']) else 'No disponible'} µm")
        if nr:
            L.append(f"Radio nuclear: {nr} µm (real)")
        else:
            L.append("Radio nuclear: aproximado (visual)")
        L.append(f"Volumen: {vol if vol is not None else 'No disponible'}")
        L.append("— Biología —")
        if nom_ox is not None:
            L.append(f"{nom_ox} local: {val_ox:.3f}")
        else:
            L.append("Oxígeno local: No disponible")
        L.append(f"Daño: {dan if dan is not None else 'No disponible'}")
        L.append(f"Presión: {pre if pre is not None else 'No disponible'}")
        L.append(f"Contactos: {nvec}")
        L.append(f"Ciclo: {cic if cic is not None else 'No disponible'} / fase {fas if fas is not None else '—'}")
        L.append(f"Migración: {mig if mig is not None else 'No disponible'}")
        L.append(f"Adhesión: {adh if adh is not None else 'No disponible'} / BM: {cbm if cbm is not None else 'No disponible'}")
        self.info.setPlainText("\n".join(str(t) for t in L))

    def _vec_frame(self):
        try:
            from .visor_widget import leer_grafo
            return leer_grafo(self.output_dir, self.slider.value(), "neighbor")
        except Exception:
            return set()

    def _pick(self, *args):
        self._pick_legacy(*args)


def abrir_vtk(parent, output_dir, titulo="Tumor 3D"):
    if not PYVISTA_OK:
        QMessageBox.warning(parent, "3D VTK",
                            "PyVista/VTK no disponible. Instala con:\npython -m pip install pyvista pyvistaqt vtk\n\n"
                            f"Detalle: {PYVISTA_ERROR}")
        return None
    dlg = DialogoVTK(parent, output_dir, titulo)
    dlg.show()
    return dlg
