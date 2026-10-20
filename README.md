# PhysiCell Lab — Gestor de experimentos PhysiCell

Aplicación de escritorio (Python + PyQt6) para gestionar el ciclo experimental
con PhysiCell **sin modificar el motor**: experimentos, escenarios, réplicas,
validación XML, ejecución con trazabilidad, visualización 2D/3D estilo Studio,
resultados, comparación y reportes.

## Requisitos

- Python 3.12+ (probado en 3.13, Windows 11)
- `pip install -r requirements-frozen.txt`
- Motor PhysiCell compilado (`project.exe`) o precompilado vía
  `PhysiCell/beta/download_binary.py template`

## Ejecución

```powershell
cd "C:\Users\PC\Downloads\physicell_experimentos"
python run_app.py
```

## Flujo de uso

1. **Configuraciones**: importa o crea tu `PhysiCell_settings.xml`, edítalo,
   valídalo y asócialo a un experimento.
2. **Experimentos**: crea tarjetas con título, descripción y etiquetas.
3. **Detalle → Configuración**: asigna el XML del experimento y el
   `project.exe`; valida y guarda.
4. **Detalle → Ejecución**: lanza N réplicas (cada una con `random_seed`
   distinto y carpeta de salida aislada `exp_X/replica_i/output`).
   Detener cancela el proceso real.
5. **Visualización**: 2D estilo Studio + 3D con vecinos (gris) y uniones
   (rojo), slider de frames, Play, velocidad, filtro por tipo y sustrato
   con barra de color.
6. **Resultados**: integridad por réplica, abrir en visor, CSV/JSON,
   informe HTML y PDF, limpieza de runs sin salida.
7. **Comparación**: vistas paralelas sincronizadas + gráfica de células finales.
8. **Preferencias**: rutas, binario por defecto y suite de regresión.

## Estructura

- `run_app.py`: entrada (lanza PhysiCell Lab).
- `app/lab_window.py`: navegación y pantallas.
- `app/nucleo.py`: datos por usuario, esquema SQLite y worker de réplicas.
- `app/interfaz_notion.py`: ventana legacy (conservada, reexporta el núcleo).
- `app/motor_physicell.py`: ejecución cancelable del binario.
- `app/simulador.py`: escenarios, réplicas, aislamiento de salidas.
- `app/xml_validator.py`: validación estructural flexible.
- `app/visor_widget.py`: visor 2D/3D integrado.
- `app/visor3d_vtk.py`: tumor 3D (PyVista 0.49.1 + VTK 9.7): membrana con radio
  real y núcleo interior con `nuclear_radius` real de PhysiCell (aproximación
  etiquetada si no hay `.mat`); color por estado/tipo/presión/volumen con
  leyenda y escala; 3 luces suaves, sombreado especular discreto, fondo oscuro;
  corte con plano X, selección con propiedades, frames con play/velocidad;
  glyph compartido por grupo para miles de células. Botón «3D VTK» en el visor,
  sincronizado con el frame. Si PyVista no está instalado, avisa y se conserva
  el 3D Matplotlib.
- Selección 3D por ID real del `.mat`: clic selecciona con contorno lima sin
  tocar la geometría, clic en vacío o botón Limpiar la quita; persiste entre
  frames si la célula existe; panel con ID, tipo, estado, posición, radio,
  volumen, oxígeno local del microambiente, daño, presión, contactos y ciclo;
  botón Centrar cámara; «No disponible» donde no hay dato.
- `app/visualizador.py`, `app/comparacion.py`, `app/reportes.py`,
  `app/config_manager.py`, `app/theme_lab.py`.
- `app/agregador.py`: consolida frames y células a CSV para análisis.
- `app/reportes.py`: informe HTML con trazabilidad, estadística por réplica,
  gráficas comparativa y temporal, pantallazos 2D inicial/final; exporta PDF.
- `tests/test_regresion.py`: suite con datos reales.
- `build.spec`: empaquetado (`pyinstaller build.spec` →
  `dist/PhysiCellManager/PhysiCellManager.exe`).

## Datos

SQLite por usuario del SO (aislado por login). Reportes y salidas bajo la
carpeta de datos del usuario (`%APPDATA%/PhysiCell_Experiments` en Windows).
