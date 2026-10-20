#!/usr/bin/env python3
"""Reportes de configuraciones, ejecuciones y resultados."""
import os
import sqlite3
import json
from datetime import datetime


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def generar_reporte_html(experiment_id, db_path, out_html):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT id, title, description, tags, config_xml_path, created_at, last_modified FROM experiments WHERE id=?", (experiment_id,))
    exp = cur.fetchone()
    if not exp:
        conn.close()
        return {"ok": False, "error": "Experimento no existe"}
    cur.execute("SELECT id, nombre, config_xml_path FROM escenarios WHERE experiment_id=? ORDER BY id", (experiment_id,))
    escenarios = cur.fetchall()
    cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    runs = cur.fetchall()
    conn.close()
    eid, title, desc, tags, cfg, created, modif = exp
    os.makedirs(os.path.dirname(out_html) or ".", exist_ok=True)
    parts = []
    parts.append("<html><head><meta charset='utf-8'><title>Reporte experimento</title></head><body>")
    parts.append(f"<h1>Experimento {eid}: {_esc(title)}</h1>")
    parts.append(f"<p>{_esc(desc) or 'Sin descripción'}</p>")
    parts.append(f"<p><b>Etiquetas:</b> {_esc(tags) or '—'}<br><b>Config base:</b> {_esc(cfg)}"
                 f"<br><b>Creado:</b> {_esc(created)}<br><b>Modificado:</b> {_esc(modif)}"
                 f"<br><b>Fecha reporte:</b> {datetime.now().isoformat(timespec='seconds')}</p>")
    parts.append("<h2>Parámetros del modelo (leídos del XML)</h2>")
    pm = extraer_parametros(cfg)
    if pm.get("ok"):
        d = pm["dominio"]
        parts.append("<table border='1' cellpadding='4'>"
                     f"<tr><th>Dominio X</th><td>{_esc(d['x_min'])} … {_esc(d['x_max'])}</td>"
                     f"<th>Dominio Y</th><td>{_esc(d['y_min'])} … {_esc(d['y_max'])}</td></tr>"
                     f"<tr><th>Dominio Z</th><td>{_esc(d['z_min'])} … {_esc(d['z_max'])}</td>"
                     f"<th>Malla</th><td>dx={_esc(d['dx'])} dy={_esc(d['dy'])} dz={_esc(d['dz'])}</td></tr>"
                     f"<tr><th>Tiempo máx</th><td>{_esc(pm['max_time'])}</td>"
                     f"<th>Pasos</th><td>dif={_esc(pm['dt_diffusion'])} mec={_esc(pm['dt_mechanics'])} fen={_esc(pm['dt_phenotype'])}</td></tr>"
                     f"<tr><th>Sustratos</th><td>{_esc(', '.join(pm['sustratos']))}</td>"
                     f"<th>Tipos celulares</th><td>{_esc(', '.join(pm['tipos']))}</td></tr>"
                     f"<tr><th>Reglas</th><td colspan='3'>{_esc('; '.join(pm['reglas']))}</td></tr></table>")
        if pm["user"]:
            parts.append("<p><b>Parámetros de usuario:</b> " +
                         "; ".join(f"{_esc(k)}={_esc(v)}" for k, v in pm["user"].items()) + "</p>")
    else:
        parts.append(f"<p>No disponibles: {_esc(pm.get('error', ''))}</p>")
    parts.append("<h2>Escenarios</h2>")
    if escenarios:
        parts.append("<ul>")
        for sid, nom, cpath in escenarios:
            parts.append(f"<li>#{sid} {_esc(nom)} - {_esc(cpath)}</li>")
        parts.append("</ul>")
    else:
        parts.append("<p>Sin escenarios registrados.</p>")
    parts.append("<h2>Replicas / Ejecuciones</h2>")
    if runs:
        from .visualizador import verificar_integridad
        parts.append("<table border='1' cellpadding='4'><tr><th>#</th><th>Estado</th><th>Inicio</th><th>Fin</th>"
                     "<th>Duración</th><th>Semilla</th><th>Integridad</th><th>Salida</th></tr>")
        for rnum, st, s0, s1, od in runs:
            integ = "—"
            for d in ([os.path.join(od, "output"), od] if od else []):
                if d and os.path.isdir(d):
                    try:
                        vi = verificar_integridad(d)
                        integ = "OK" if vi.get("ok") else "Falta: " + ", ".join(vi.get("faltan", []))
                    except Exception:
                        integ = "?"
                    break
            parts.append(f"<tr><td>{rnum}</td><td>{_esc(st)}</td><td>{_esc(s0)}</td><td>{_esc(s1)}</td>"
                         f"<td>{_esc(_duracion(s0, s1))}</td><td>{_esc(_semilla_replica(od))}</td>"
                         f"<td>{_esc(integ)}</td><td>{_esc(od)}</td></tr>")
        parts.append("</table>")
    else:
        parts.append("<p>Sin runs.</p>")
    parts.append("<h2>Archivos de análisis</h2>")
    try:
        from .agregador import agregar_experimento
        ag = agregar_experimento(db_path, experiment_id, os.path.dirname(out_html))
        if ag.get("replicas"):
            parts.append(f"<p>Consolidado de {ag['replicas']} réplicas con datos: "
                         f"<b>frames_todas.csv</b>, <b>celulas_todas.csv</b> junto a este informe.</p>")
        else:
            parts.append("<p>Sin réplicas con datos para consolidar.</p>")
    except Exception as e:
        parts.append(f"<p>Consolidado no disponible: {_esc(str(e))}</p>")
    try:
        from .comparacion import generar_grafica_comparacion, generar_grafica_temporal
        chart = os.path.join(os.path.dirname(out_html), "comparacion.png")
        generar_grafica_comparacion(db_path, experiment_id, chart)
        if os.path.isfile(chart):
            parts.append("<h2>Comparación (células finales por réplica)</h2>")
            parts.append("<img src='comparacion.png' style='max-width:700px'>")
    except Exception as e:
        parts.append(f"<p>Gráfica no disponible: {_esc(str(e))}</p>")
    parts.append("<h2>Estadística por réplica</h2>")
    outs = _salidas_con_datos(runs)
    if outs:
        parts.append("<table border='1' cellpadding='4'><tr><th>Réplica</th><th>Frames</th><th>N inicial</th>"
                     "<th>N final</th><th>Cambio %</th><th>Vivas</th><th>Apop.</th><th>Necr.</th>"
                     "<th>Vol. medio</th><th>T final (min)</th></tr>")
        for rnum, st, d in outs:
            e = _estadisticas(d)
            if not e.get("ok"):
                parts.append(f"<tr><td>{rnum}</td><td colspan='9'>{_esc(e.get('error', ''))}</td></tr>")
                continue
            parts.append(f"<tr><td>{rnum} ({_esc(st)})</td><td>{e['frames']}</td><td>{e['n_inicial']}</td>"
                         f"<td>{e['n_final']}</td><td>{e['cambio_pct'] if e['cambio_pct'] is None else round(e['cambio_pct'], 1)}</td>"
                         f"<td>{e['vivas_fin']}</td><td>{e['apop_fin']}</td><td>{e['nec_fin']}</td>"
                         f"<td>{round(e['vol_medio_fin'], 1) if e['vol_medio_fin'] is not None else '—'}</td>"
                         f"<td>{e['t_final'] if e['t_final'] is not None else '—'}</td></tr>")
        parts.append("</table>")
        parts.append("<h2>Análisis estadístico</h2>")
        series_n = []
        for rnum, _st, d in outs:
            e = _estadisticas(d)
            if e.get("ok") and e.get("serie_n"):
                series_n.append((rnum, e["serie_n"]))
        tasas = []
        for rnum, sn in series_n:
            t = _tasa_crecimiento(sn)
            if t is not None:
                tasas.append(t)
                parts.append(f"- Réplica {rnum}: tasa de cambio {t:+.3f} células/frame.")
        if tasas:
            tasa_global = sum(tasas) / len(tasas)
        else:
            tasa_global = None
        datos = [(rnum, st, d) for rnum, st, d in outs]
        varianza = _varianza_replicas(datos)
        if varianza:
            parts.append(f"- Comparación final entre réplicas: media {varianza['media']:.1f}, "
                         f"desviación {varianza['std']:.1f}, rango {varianza['min']:.0f}–{varianza['max']:.0f} "
                         f"(n={varianza['n']}).")
        anomalias = _detectar_anomalias(outs)
        if anomalias:
            total = sum(a["perdidas"] for a in anomalias)
            parts.append(f"- Anomalías: {total} desapariciones de células entre frames consecutivos "
                         f"en {len(anomalias)} transiciones.")
        else:
            parts.append("- Anomalías: ninguna desaparición celular entre frames consecutivos.")
        for linea in _interpretacion(outs, varianza, anomalias, tasa_global):
            parts.append(f"<p>{_esc(linea) if not linea.startswith('#') else linea}</p>")
        parts.append("<h2>Evolución temporal y pantallazos visuales</h2>")
        for rnum, _st, d in outs:
            safe = f"rep{rnum}"
            tp = os.path.join(os.path.dirname(out_html), f"temporal_{safe}.png")
            try:
                generar_grafica_temporal(d, tp)
            except Exception:
                pass
            f0 = os.path.join(os.path.dirname(out_html), f"frame_{safe}_ini.png")
            f1 = os.path.join(os.path.dirname(out_html), f"frame_{safe}_fin.png")
            _render_frame(d, 0, f0)
            import glob as _g
            _sn = sorted(_g.glob(os.path.join(d, "snapshot*.svg")))
            _render_frame(d, len(_sn) - 1, f1)
            parts.append(f"<h3>Réplica {rnum}</h3>")
            if os.path.isfile(tp):
                parts.append(f"<img src='temporal_{safe}.png' style='max-width:650px'>")
            if os.path.isfile(f0):
                parts.append(f"<p>Inicial:</p><img src='frame_{safe}_ini.png' style='max-width:450px'>")
            if os.path.isfile(f1):
                parts.append(f"<p>Final:</p><img src='frame_{safe}_fin.png' style='max-width:450px'>")
    else:
        parts.append("<p>Sin réplicas con datos de simulación.</p>")
    parts.append("<p><i>Simulaciones ejecutadas por PhysiCell. Esta app no modifica modelos internos.</i></p>")
    parts.append("</body></html>")
    with open(out_html, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return {"ok": True, "path": out_html}


def _tasa_crecimiento(serie_n):
    """Crecimiento medio por frame (pendiente lineal)."""
    import numpy as np
    try:
        n = len(serie_n)
        if n < 2:
            return None
        x = np.arange(n)
        y = np.asarray([float(v) for v in serie_n if v is not None and str(v).replace('.', '').replace('-', '').isdigit() or isinstance(v, (int, float))], dtype=float)
        if len(y) < 2:
            return None
        return float(np.polyfit(x, y, 1)[0])
    except Exception:
        return None


def _varianza_replicas(datos_por_replica):
    """Comparación entre réplicas: desviación estándar y rango."""
    import numpy as np
    finals = []
    for _rnum, _st, d in datos_por_replica:
        try:
            e = _estadisticas(d)
            if e.get("ok") and e.get("n_final") is not None:
                finals.append(float(e["n_final"]))
        except Exception:
            pass
    if len(finals) < 2:
        return None
    arr = np.asarray(finals, dtype=float)
    return {"media": float(arr.mean()), "std": float(arr.std(ddof=0)),
            "min": float(arr.min()), "max": float(arr.max()), "n": len(finals)}


def _detectar_anomalias(outs):
    """Células que desaparecen entre frames consecutivos (posible muerte o error)."""
    anomalias = []
    for rnum, _st, d in outs:
        try:
            import glob as _g
            snaps = sorted(_g.glob(os.path.join(d, "snapshot*.svg")))
            if len(snaps) < 2:
                continue
            from .visor_widget import parse_snapshot_svg, leer_bounds
            b = leer_bounds(d)
            prev = set()
            for i, p in enumerate(snaps):
                r = parse_snapshot_svg(p, b)
                if not r.get("ok"):
                    continue
                try:
                    from .agregador import leer_frame
                    fr = leer_frame(d, p)
                    ids = {c["id"] for c in fr["celulas"]} if fr.get("ok") else set()
                except Exception:
                    ids = set()
                if i > 0 and prev and ids:
                    perdidas = prev - ids
                    if perdidas:
                        anomalias.append({"replica": rnum, "frame": i,
                                          "perdidas": len(perdidas), "ids": list(perdidas)[:5]})
                prev = ids
        except Exception:
            pass
    return anomalias


def _interpretacion(outs, varianza, anomalias, tasa_global):
    """Redacta interpretación objetiva sin biología inventada."""
    L = []
    if not outs:
        return ["Sin datos suficientes para interpretación."]
    L.append("### Interpretación objetiva")
    if tasa_global is not None:
        if tasa_global > 0.1:
            L.append(f"- Tendencia de crecimiento positivo: +{tasa_global:.2f} células por frame en promedio.")
        elif tasa_global < -0.1:
            L.append(f"- Tendencia de reducción: {tasa_global:.2f} células por frame en promedio.")
        else:
            L.append(f"- Población aproximadamente estable ({tasa_global:+.2f} células por frame).")
    if varianza:
        if varianza["std"] / max(varianza["media"], 1) < 0.1:
            L.append(f"- Alta consistencia entre réplicas (desviación {varianza['std']:.1f}, n={varianza['n']}).")
        else:
            L.append(f"- Variabilidad entre réplicas: rango {varianza['min']:.0f}–{varianza['max']:.0f} "
                     f"(desviación {varianza['std']:.1f}, n={varianza['n']}).")
    if anomalias:
        total = sum(a["perdidas"] for a in anomalias)
        L.append(f"- Se detectaron {total} desapariciones de células entre frames consecutivos "
                 f"en {len(anomalias)} transiciones. Posibles causas: muerte celular, "
                 f"división no capturada o lote de datos incompleto.")
    else:
        L.append("- No se detectaron desapariciones anómalas entre frames.")
    L.append("\n_Limitaciones: análisis basado únicamente en snapshots SVG y cells.mat. "
             "No se incluyen variables intracelulares ni dinámicas de señal._")
    return L


def _salidas_con_datos(runs):
    """Carpetas de salida con snapshots, una por réplica."""
    import glob as _g
    outs = []
    for rnum, st, _s0, _s1, od in runs:
        for d in ([os.path.join(od, "output"), od] if od else []):
            if d and os.path.isdir(d) and _g.glob(os.path.join(d, "snapshot*.svg")):
                outs.append((rnum, st, d))
                break
    return outs


def _duracion(s0, s1):
    try:
        from datetime import datetime as _dt
        a = _dt.fromisoformat(s0)
        b = _dt.fromisoformat(s1)
        s = (b - a).total_seconds()
        return f"{s:.0f} s" if s < 120 else f"{s/60:.1f} min"
    except Exception:
        return "—"


def _semilla_replica(output_dir):
    """Lee random_seed del XML de réplica si existe junto a la salida."""
    import glob as _g
    for d in ([output_dir, os.path.dirname(output_dir or "")] if output_dir else []):
        for p in _g.glob(os.path.join(d or "", "replica_*.xml")):
            try:
                import xml.etree.ElementTree as ET
                root = ET.parse(p).getroot()
                for el in root.iter():
                    if el.tag.split("}")[-1] == "random_seed" and (el.text or "").strip():
                        return el.text.strip()
            except Exception:
                pass
    return "—"


def extraer_parametros(xml_path):
    """Parámetros clave del modelo para el informe. Solo lectura."""
    info = {"ok": False}
    if not xml_path or not os.path.isfile(xml_path):
        info["error"] = "XML no accesible"
        return info
    try:
        import xml.etree.ElementTree as ET
        root = ET.parse(xml_path).getroot()

        def _t(path):
            el = root.find(path)
            if el is None or not (el.text or "").strip():
                return "—"
            u = el.attrib.get("units", "")
            return f"{el.text.strip()}{(' ' + u) if u else ''}"

        dom = {k: _t(f".//domain/{k}") for k in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max", "dx", "dy", "dz")}
        subs = []
        for var in root.findall(".//microenvironment_setup/variable"):
            subs.append(var.attrib.get("name", "?"))
        cells = [c.attrib.get("name", "?") for c in root.findall(".//cell_definitions/cell_definition")]
        rules = []
        for rs in root.findall(".//cell_rules/ruleset"):
            rules.append(f"{rs.attrib.get('protocol', '?')} v{rs.attrib.get('version', '?')} "
                         f"({'on' if rs.attrib.get('enabled', 'false').lower() == 'true' else 'off'})")
        ups = {}
        for up in root.findall(".//user_parameters/*"):
            ups[up.tag] = (up.text or "").strip()
        info.update({"ok": True, "dominio": dom, "max_time": _t(".//max_time"),
                     "dt_diffusion": _t(".//dt_diffusion"), "dt_mechanics": _t(".//dt_mechanics"),
                     "dt_phenotype": _t(".//dt_phenotype"), "sustratos": subs or ["—"],
                     "tipos": cells or ["—"], "reglas": rules or ["—"], "user": ups})
    except Exception as e:
        info["error"] = str(e)
    return info
    """Carpetas de salida con snapshots, una por réplica."""
    import glob as _g
    outs = []
    for rnum, st, _s0, _s1, od in runs:
        for d in ([os.path.join(od, "output"), od] if od else []):
            if d and os.path.isdir(d) and _g.glob(os.path.join(d, "snapshot*.svg")):
                outs.append((rnum, st, d))
                break
    return outs


def _render_frame(output_dir, frame_idx, out_png):
    """PNG 2D de un frame con colores/radios reales (como Studio)."""
    import glob as _g
    snaps = sorted(_g.glob(os.path.join(output_dir, "snapshot*.svg")))
    if not snaps:
        return False
    from .visor_widget import parse_snapshot_svg, leer_bounds, dibujar_circulos
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    b = leer_bounds(output_dir)
    r = parse_snapshot_svg(snaps[max(0, min(len(snaps) - 1, frame_idx))], b)
    if not r.get("ok") or not len(r["x"]):
        return False
    fig, ax = plt.subplots(figsize=(6, 6))
    dibujar_circulos(ax, r["x"], r["y"], r["r"], r["rgba"])
    if b:
        ax.set_xlim(b["xmin"], b["xmax"])
        ax.set_ylim(b["ymin"], b["ymax"])
    ax.set_aspect("equal")
    ax.set_title(f"{r.get('time','')} ({r.get('n',0)} agentes)")
    fig.tight_layout()
    fig.savefig(out_png, dpi=100)
    plt.close(fig)
    return True


def _estadisticas(output_dir):
    """Resumen por réplica desde los frames: conteos, estados, volumen medio."""
    import glob as _g
    from .agregador import leer_frame
    snaps = sorted(_g.glob(os.path.join(output_dir, "snapshot*.svg")))
    if not snaps:
        return {"ok": False, "error": "Sin snapshots"}
    ns, vivas, vols, tiempos = [], [], [], []
    for p in snaps:
        fr = leer_frame(output_dir, p)
        if not fr.get("ok"):
            continue
        cels = fr["celulas"]
        est = [c["estado"] for c in cels]
        ns.append(len(cels))
        vivas.append(est.count("viva"))
        vm = [c["volumen"] for c in cels if c["volumen"] is not None]
        vols.append(sum(vm) / len(vm) if vm else None)
        tiempos.append(fr.get("tiempo"))
    if not ns:
        return {"ok": False, "error": "Sin frames legibles"}
    fin = [c["estado"] for c in leer_frame(output_dir, snaps[-1])["celulas"]]
    cambio = ((ns[-1] - ns[0]) / ns[0] * 100.0) if ns[0] else None
    return {"ok": True, "frames": len(ns), "n_inicial": ns[0], "n_final": ns[-1],
            "cambio_pct": cambio, "vivas_fin": fin.count("viva"),
            "apop_fin": fin.count("apoptotica"), "nec_fin": fin.count("necrotica"),
            "vol_medio_fin": vols[-1], "t_final": tiempos[-1], "serie_n": ns,
            "serie_t": tiempos}


def exportar_reporte_pdf(html_path, pdf_path):
    """Convierte el informe HTML a PDF con Qt (sin dependencias nuevas)."""
    import os as _o
    if not html_path or not _o.path.isfile(html_path):
        return {"ok": False, "error": "HTML no existe"}
    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtPrintSupport import QPrinter
        from PyQt6.QtGui import QTextDocument
        from PyQt6.QtCore import QUrl
        app = QApplication.instance() or QApplication([])
        with open(html_path, "r", encoding="utf-8") as f:
            html = f.read()
        base = QUrl.fromLocalFile(_o.path.dirname(_o.path.abspath(html_path)) + "/")
        doc = QTextDocument()
        doc.setBaseUrl(base)
        doc.setHtml(html)
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(pdf_path)
        doc.print(printer)
        return {"ok": True, "path": pdf_path}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def exportar_runs_csv(experiment_id, db_path, out_csv):
    import csv
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    rows = cur.fetchall()
    conn.close()
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["run_number", "status", "start_time", "end_time", "output_dir"])
        w.writerows(rows)
    return {"ok": True, "path": out_csv, "n": len(rows)}


def exportar_runs_json(experiment_id, db_path, out_json):
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT run_number, status, start_time, end_time, output_dir FROM runs WHERE experiment_id=? ORDER BY run_number", (experiment_id,))
    rows = [{"run_number": a, "status": b, "start_time": c, "end_time": d, "output_dir": e} for a, b, c, d, e in cur.fetchall()]
    conn.close()
    os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"experiment_id": experiment_id, "runs": rows}, f, indent=2, ensure_ascii=False)
    return {"ok": True, "path": out_json, "n": len(rows)}
