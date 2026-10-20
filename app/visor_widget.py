#!/usr/bin/env python3
"""Visor estilo PhysiCell Studio: SVG con colores/radios reales + substrato + 3D.

Replica vis_tab.py de Studio: tissue>cells>g>circle, fill rgb/rgba,
mapeo x += output_xmin, PatchCollection en escala de datos,
titulo 'X days, Y hrs, Z mins (N agents)'.
"""
import os
import glob
import xml.etree.ElementTree as ET
from collections import deque
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QLineEdit, QFileDialog, QCheckBox
from PyQt6.QtCore import Qt
import matplotlib
matplotlib.use("QtAgg")
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from matplotlib.patches import Circle
from matplotlib.collections import PatchCollection
import matplotlib.colors as mplc
import numpy as np


def listar_snapshots(output_dir):
    if not output_dir or not os.path.isdir(output_dir):
        return []
    return sorted(glob.glob(os.path.join(output_dir, "snapshot*.svg")))


def leer_bounds(output_dir):
    """Lee bounding_box de initial.xml. Retorna dict o None."""
    p = os.path.join(output_dir, "initial.xml")
    if not os.path.isfile(p):
        return None
    try:
        root = ET.parse(p).getroot()
        bds = root.find(".//microenvironment//domain//mesh//bounding_box").text.split()
        bds = [float(x) for x in bds]
        return {"xmin": bds[0], "ymin": bds[1], "zmin": bds[2],
                "xmax": bds[3], "ymax": bds[4], "zmax": bds[5]}
    except Exception:
        return None


def parse_snapshot_svg(path, bounds, show_nucleus=False):
    """Replica Studio plot_svg. Retorna dict con x,y,r,rgba,time,num."""
    tree = ET.parse(path)
    root = tree.getroot()
    title_time = ""
    tissue = None
    for child in root:
        if child.text and "Current time" in child.text:
            svals = child.text.split()
            title_time = f"{svals[2]} days, {svals[4]} hrs, {svals[7][:-3]} mins"
        if "id" in child.attrib:
            tissue = child
            break
    if tissue is None:
        return {"ok": False, "error": "sin tissue"}
    cells_parent = None
    for child in tissue:
        if child.attrib.get("id") == "cells":
            cells_parent = child
            break
    if cells_parent is None:
        return {"ok": False, "error": "sin cells"}
    x_pad = (bounds["xmax"] - bounds["xmin"]) if bounds else 10000.0
    y_pad = (bounds["ymax"] - bounds["ymin"]) if bounds else 10000.0
    xl, yl, rl, cl, tl = deque(), deque(), deque(), deque(), deque()
    n = 0
    for child in cells_parent:
        ctype = child.attrib.get("type", "")
        for circle in child:
            try:
                xval = float(circle.attrib["cx"])
            except Exception:
                continue
            if bounds:
                xval += bounds["xmin"]
            s = circle.attrib.get("fill", "black")
            if s[0:4] == "rgba":
                vals = list(map(float, s[5:-1].split(",")))
                rgba = [1, 1, 1, 1.0]
                rgba[0:3] = [np.round(vals[0]), np.round(vals[1]), np.round(vals[2])]
                rgba[0:3] = [v / 255. for v in rgba[0:3]]
                rgba[3] = min(1.0, vals[3] * 2.0)
            elif s[0:3] == "rgb":
                rgba = [1, 1, 1, 1.0]
                rgba[0:3] = list(map(int, s[4:-1].split(",")))
                rgba[0:3] = [v / 255. for v in rgba[0:3]]
            else:
                rgb = mplc.to_rgb(mplc.cnames.get(s, "black"))
                rgba = [rgb[0], rgb[1], rgb[2], 1.0]
            try:
                yval = float(circle.attrib["cy"])
            except Exception:
                break
            if bounds:
                yval += bounds["ymin"]
                if (xval < bounds["xmin"] - x_pad) or (xval > bounds["xmax"] + x_pad):
                    break
                if (yval < bounds["ymin"] - y_pad) or (yval > bounds["ymax"] + y_pad):
                    break
            try:
                rval = float(circle.attrib["r"])
            except Exception:
                break
            xl.append(xval)
            yl.append(yval)
            rl.append(rval)
            cl.append(rgba)
            tl.append(ctype)
            if not show_nucleus:
                break
        n += 1
    import numpy as _np
    return {"ok": True, "x": np.array(xl), "y": np.array(yl), "r": np.array(rl),
            "rgba": np.array(cl) if cl else np.zeros((0, 4)),
            "types": _np.array(list(tl), dtype=object),
            "time": title_time, "n": n}


def leer_grafo(output_dir, frame_idx, kind="neighbor"):
    """Lee grafo PhysiCell estilo Studio build_attachments. Retorna set de (i,j)."""
    if kind == "neighbor":
        pats = sorted(glob.glob(os.path.join(output_dir, "output*_cell_neighbor_graph.txt")))
    elif kind == "attached":
        pats = sorted(glob.glob(os.path.join(output_dir, "output*_attached_cells_graph.txt")))
    else:
        pats = sorted(glob.glob(os.path.join(output_dir, "output*_spring_attached_cells_graph.txt")))
    if not pats:
        return set()
    p = pats[max(0, min(len(pats) - 1, frame_idx))]
    pares = set()
    try:
        with open(p, "r") as f:
            for line in f.readlines()[1:]:
                if ":" not in line:
                    continue
                cell, atts = line.split(":", 1)
                cell = cell.strip()
                if not cell.isdigit() or not atts.strip():
                    continue
                for a in atts.split(","):
                    a = a.strip()
                    if a.isdigit():
                        pares.add(tuple(sorted([int(cell), int(a)])))
    except Exception:
        pass
    return pares


def dibujar_circulos(ax, x, y, r, rgba, edge=True, lw=0.5):
    zipped = np.broadcast(x, y, r)
    patches = [Circle((x_, y_), s_) for x_, y_, s_ in zipped]
    if edge:
        col = PatchCollection(patches, facecolor=rgba, edgecolor="black", linewidth=lw)
    else:
        col = PatchCollection(patches, facecolor=rgba, edgecolor="none")
    ax.add_collection(col)
    ax.autoscale_view()


def cargar_substrato(output_dir, frame_idx):
    """Lee output*_microenvironment0.mat campo 4 como Studio. Retorna xgrid,ygrid,val o None."""
    mats = sorted(glob.glob(os.path.join(output_dir, "output*_microenvironment0.mat")))
    if not mats:
        return None
    i = max(0, min(len(mats) - 1, frame_idx))
    try:
        import scipy.io
        info = {}
        scipy.io.loadmat(mats[i], info)
        M = info["multiscale_microenvironment"]
        nx = int(np.sqrt(M.shape[1])) if M.shape[1] > 0 else 0
        # Studio infiere numx/numy del mesh; aproximamos reshape cuadrado si falla
        # Mejor: leer mesh de initial.xml no da nx directo; usamos dx=20 y bounds
        b = leer_bounds(output_dir)
        if b is None:
            return None
        dx = 20.0
        nx = max(1, int(round((b["xmax"] - b["xmin"]) / dx)))
        ny = max(1, int(round((b["ymax"] - b["ymin"]) / dx)))
        if M.shape[1] < nx * ny:
            return None
        xgrid = M[0, :nx * ny].reshape(ny, nx)
        ygrid = M[1, :nx * ny].reshape(ny, nx)
        val = M[4, :nx * ny].reshape(ny, nx)
        return xgrid, ygrid, val
    except Exception:
        return None


def leer_sustratos(output_dir):
    """Nombres de variables del microambiente desde initial.xml."""
    p = os.path.join(output_dir, "initial.xml")
    try:
        root = ET.parse(p).getroot()
        names = []
        for var in root.findall(".//microenvironment//domain//variables//variable"):
            n = var.attrib.get("name")
            if n:
                names.append(n)
        return names
    except Exception:
        return []


class VisorPhysiCell(QWidget):
    def __init__(self, output_dir="", parent=None):
        super().__init__(parent)
        self.snaps = []
        self.bounds = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        top = QHBoxLayout()
        self.dir_edit = QLineEdit(output_dir)
        self.dir_edit.setPlaceholderText("Carpeta output PhysiCell (snapshot*.svg + initial.xml)")
        self.dir_edit.setToolTip("Como Studio: lee initial.xml para bounds y snapshot SVG para células con color y radio reales.")
        btn = QPushButton("Carpeta...")
        btn.setFixedWidth(90)
        btn.clicked.connect(self._browse)
        self.chk_sub = QCheckBox("substrato")
        self.chk_sub.setChecked(False)
        self.chk_sub.setToolTip("Fondo con contourf del .mat como Studio (requiere scipy)")
        self.chk_edge = QCheckBox("borde")
        self.chk_edge.setChecked(True)
        self.chk_vec = QCheckBox("vecinos")
        self.chk_vec.setChecked(True)
        self.chk_vec.setToolTip("Líneas grises entre células en contacto (cell_neighbor_graph.txt) como Studio")
        self.chk_att = QCheckBox("uniones")
        self.chk_att.setChecked(True)
        self.chk_att.setToolTip("Líneas rojas de attached/spring como Studio")
        self.btn_vtk = QPushButton("3D VTK")
        self.btn_vtk.setToolTip("Abrir esferas 3D interactivas con PyVista/VTK")
        self.btn_vtk.clicked.connect(self._abrir_vtk)
        from PyQt6.QtWidgets import QComboBox
        self.cmb_tipo = QComboBox()
        self.cmb_tipo.setToolTip("Filtrar por tipo celular del SVG (como Studio)")
        self.cmb_tipo.currentTextChanged.connect(lambda _: self._dibujar())
        self.cmb_vel = QComboBox()
        self.cmb_vel.addItems(["0.5x", "1x", "2x", "4x"])
        self.cmb_vel.setCurrentText("1x")
        self.cmb_vel.setToolTip("Velocidad de reproducción")
        self.cmb_vel.currentTextChanged.connect(self._velocidad)
        top.addWidget(self.dir_edit, 1)
        top.addWidget(btn)
        top.addWidget(self.chk_sub)
        top.addWidget(self.chk_edge)
        top.addWidget(self.chk_vec)
        top.addWidget(self.chk_att)
        top.addWidget(self.btn_vtk)
        lay.addLayout(top)
        filt = QHBoxLayout()
        filt.addWidget(QLabel("Tipo:"))
        filt.addWidget(self.cmb_tipo, 1)
        filt.addWidget(QLabel("Velocidad:"))
        filt.addWidget(self.cmb_vel)
        cflt = QWidget()
        cflt.setLayout(filt)
        lay.addWidget(cflt)
        self.lbl = QLabel("Sin datos.")
        self.lbl.setWordWrap(True)
        lay.addWidget(self.lbl)
        self.lbl_leyenda = QLabel("")
        self.lbl_leyenda.setWordWrap(True)
        lay.addWidget(self.lbl_leyenda)
        self.fig = Figure(figsize=(8, 3.8))
        self.ax2 = self.fig.add_subplot(121)
        self.ax3 = self.fig.add_subplot(122, projection="3d")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self._cbar = None
        lay.addWidget(self.canvas, 1)
        bot = QHBoxLayout()
        self.btn_prev = QPushButton("<")
        self.btn_prev.setFixedWidth(40)
        self.btn_prev.clicked.connect(lambda: self._mover(-1))
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.valueChanged.connect(self._ir)
        self.btn_next = QPushButton(">")
        self.btn_next.setFixedWidth(40)
        self.btn_next.clicked.connect(lambda: self._mover(1))
        bot.addWidget(self.btn_prev)
        bot.addWidget(self.slider, 1)
        bot.addWidget(self.btn_next)
        self.btn_play = QPushButton("Play")
        self.btn_play.setFixedWidth(60)
        self.btn_play.setToolTip("Animar frames automáticamente")
        self.btn_play.clicked.connect(self._toggle_play)
        bot.addWidget(self.btn_play)
        lay.addLayout(bot)
        from PyQt6.QtCore import QTimer
        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._avanzar)
        self.dir_edit.textChanged.connect(self._recargar)
        self.chk_sub.stateChanged.connect(lambda _: self._dibujar())
        self.chk_edge.stateChanged.connect(lambda _: self._dibujar())
        self.chk_vec.stateChanged.connect(lambda _: self._dibujar())
        self.chk_att.stateChanged.connect(lambda _: self._dibujar())
        self._recargar()

    def set_output_dir(self, d):
        self.dir_edit.setText(d or "")

    def _browse(self):
        from PyQt6.QtWidgets import QFileDialog
        d = QFileDialog.getExistingDirectory(self, "Carpeta output PhysiCell")
        if d:
            self.dir_edit.setText(d)

    def _abrir_vtk(self):
        from .visor3d_vtk import abrir_vtk
        abrir_vtk(self, self.dir_edit.text().strip() or ".",
                  titulo=f"Tumor 3D — {len(self.snaps)} frames")

    def _recargar(self):
        self.snaps = listar_snapshots(self.dir_edit.text().strip())
        self.bounds = leer_bounds(self.dir_edit.text().strip())
        self.slider.setMinimum(0)
        self.slider.setMaximum(max(0, len(self.snaps) - 1))
        self.slider.setValue(0)
        self._cargar_tipos()
        self._dibujar()

    def _cargar_tipos(self):
        tipos = set()
        for p in self.snaps[:10]:
            try:
                r = parse_snapshot_svg(p, self.bounds)
                if r.get("ok"):
                    for t in list(r.get("types", [])):
                        if t:
                            tipos.add(str(t))
            except Exception:
                pass
        actual = self.cmb_tipo.currentText() if hasattr(self, "cmb_tipo") else "Todos"
        self.cmb_tipo.blockSignals(True)
        self.cmb_tipo.clear()
        self.cmb_tipo.addItem("Todos")
        for t in sorted(tipos):
            self.cmb_tipo.addItem(t)
        if actual in tipos or actual == "Todos":
            self.cmb_tipo.setCurrentText(actual)
        self.cmb_tipo.blockSignals(False)

    def _velocidad(self, txt):
        ms = {"0.5x": 1600, "1x": 800, "2x": 400, "4x": 200}.get(txt, 800)
        self._timer.setInterval(ms)

    def _mover(self, delta):
        if not self.snaps:
            return
        self.slider.setValue(max(0, min(len(self.snaps) - 1, self.slider.value() + delta)))

    def _toggle_play(self):
        if self._timer.isActive():
            self._timer.stop()
            self.btn_play.setText("Play")
        else:
            if not self.snaps:
                return
            self._timer.start()
            self.btn_play.setText("Pausa")

    def _avanzar(self):
        if not self.snaps:
            self._timer.stop()
            self.btn_play.setText("Play")
            return
        v = self.slider.value() + 1
        if v >= len(self.snaps):
            v = 0
        self.slider.setValue(v)

    def _ir(self, v):
        self._dibujar()

    def _datos_frame(self, idx):
        """Datos filtrados del frame para dibujo 2D/3D y VTK. Retorna dict o None."""
        if not self.snaps:
            return None
        idx = max(0, min(len(self.snaps) - 1, idx))
        r = parse_snapshot_svg(self.snaps[idx], self.bounds)
        if not r.get("ok"):
            return {"ok": False, "error": r.get("error"), "idx": idx}
        x, y, rv, rgba = r["x"], r["y"], r["r"], r["rgba"]
        tipos = list(r.get("types", []))
        filtro = self.cmb_tipo.currentText() if hasattr(self, "cmb_tipo") else "Todos"
        if filtro and filtro != "Todos" and len(tipos) == len(x):
            mask = np.array([str(t) == filtro for t in tipos])
            idx_map = {old: new for new, old in enumerate([i for i, m in enumerate(mask) if m])}
        else:
            mask = np.ones(len(x), dtype=bool)
            idx_map = {i: i for i in range(len(x))}
        x, y, rv = x[mask], y[mask], rv[mask]
        rgba = rgba[mask] if len(rgba) == len(mask) else rgba
        vec0 = leer_grafo(self.dir_edit.text().strip(), idx, "neighbor") if self.chk_vec.isChecked() else set()
        att0 = leer_grafo(self.dir_edit.text().strip(), idx, "attached") if self.chk_att.isChecked() else set()
        spr0 = leer_grafo(self.dir_edit.text().strip(), idx, "spring") if self.chk_att.isChecked() else set()
        def _filt(pares):
            out = set()
            for i, j in pares:
                if i in idx_map and j in idx_map:
                    out.add((idx_map[i], idx_map[j]))
            return out
        return {"ok": True, "idx": idx, "x": x, "y": y, "rv": rv, "rgba": rgba,
                "tipos": tipos, "time": r["time"], "n": r["n"],
                "vec": _filt(vec0), "att": _filt(att0), "spr": _filt(spr0)}

    def _dibujar(self):
        self.ax2.clear()
        self.ax3.clear()
        try:
            if self._cbar is not None:
                self._cbar.remove()
        except Exception:
            pass
        self._cbar = None
        if not self.snaps:
            self.lbl.setText("Sin snapshot*.svg. Ejecuta PhysiCell para generar frames.")
            self.lbl_leyenda.setText("")
            self.ax2.set_title("2D estilo Studio - sin datos")
            self.ax3.set_title("3D - sin datos")
            self.canvas.draw()
            return
        idx = max(0, min(len(self.snaps) - 1, self.slider.value()))
        d = self._datos_frame(idx)
        if d is None:
            return
        if not d.get("ok"):
            self.lbl.setText(f"Error: {d.get('error')}")
            self.canvas.draw()
            return
        idx = d["idx"]
        x, y, rv, rgba = d["x"], d["y"], d["rv"], d["rgba"]
        tipos, vec, att, spr = d["tipos"], d["vec"], d["att"], d["spr"]
        # fondo substrato estilo Studio con barra de color
        if self.chk_sub.isChecked():
            sub = cargar_substrato(self.dir_edit.text().strip(), idx)
            if sub is not None:
                xg, yg, val = sub
                try:
                    cf = self.ax2.contourf(xg, yg, val, 15, cmap="viridis")
                    sust = (leer_sustratos(self.dir_edit.text().strip()) or ["substrato"])[0]
                    self._cbar = self.fig.colorbar(cf, ax=self.ax2, shrink=0.85)
                    self._cbar.set_label(f"{sust} (densidad)")
                except Exception:
                    pass
        if len(x):
            from matplotlib.collections import LineCollection
            def segs(pares):
                ls = []
                for i, j in pares:
                    if 0 <= i < len(x) and 0 <= j < len(x):
                        ls.append([(x[i], y[i]), (x[j], y[j])])
                return ls
            sv = segs(vec)
            if sv:
                self.ax2.add_collection(LineCollection(sv, colors="gray", linewidths=0.6, alpha=0.8))
            sa = segs(att | spr)
            if sa:
                self.ax2.add_collection(LineCollection(sa, colors="red", linewidths=0.9, alpha=0.9))
            dibujar_circulos(self.ax2, x, y, rv, rgba, edge=self.chk_edge.isChecked())
        if self.bounds:
            self.ax2.set_xlim(self.bounds["xmin"], self.bounds["xmax"])
            self.ax2.set_ylim(self.bounds["ymin"], self.bounds["ymax"])
        self.ax2.set_aspect("equal")
        self.ax2.set_facecolor("white")
        self.ax2.set_title(f"{d['time']} ({d['n']} agents)", fontsize=9)
        # 3D con mismos colores y tamaño por radio + enlaces de interacción
        if len(x):
            import numpy as _np
            z = _np.zeros_like(x, dtype=float)
            for i, j in vec:
                if 0 <= i < len(x) and 0 <= j < len(x):
                    self.ax3.plot([x[i], x[j]], [y[i], y[j]], [0, 0], color="gray", linewidth=0.8, alpha=0.7)
            for i, j in att | spr:
                if 0 <= i < len(x) and 0 <= j < len(x):
                    self.ax3.plot([x[i], x[j]], [y[i], y[j]], [0, 0], color="red", linewidth=1.0, alpha=0.9)
            self.ax3.scatter(x, y, z, s=rv * 4, c=rgba if len(rgba) else "lime", edgecolors="k", linewidths=0.4, depthshade=True)
        self.ax3.set_title(f"3D frame {idx+1}/{len(self.snaps)} vec={len(vec)} uni={len(att|spr)}", fontsize=9)
        self.ax3.set_xlabel("x")
        self.ax3.set_ylabel("y")
        self.ax3.set_zlabel("z")
        self.lbl.setText(f"{d['time']} ({d['n']} agents) - {len(x)} dibujadas, {len(vec)} contactos, {len(att|spr)} uniones. Frame {idx+1}/{len(self.snaps)}.")
        try:
            from collections import Counter as _C
            conteo = _C([str(t) if t else "desconocido" for t in tipos])
            self.lbl_leyenda.setText("Leyenda tipos: " + ", ".join(f"{k} ({v})" for k, v in sorted(conteo.items())))
        except Exception:
            self.lbl_leyenda.setText("")
        self.fig.tight_layout()
        self.canvas.draw()
