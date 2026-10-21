# PhysiCell Lab — Gestor de experimentos PhysiCell

Aplicacion de escritorio (Python + PyQt6) para gestionar el ciclo experimental con PhysiCell sin modificar el motor: experimentos, escenarios, replicas, validacion XML, ejecucion con trazabilidad, visualizacion 2D y 3D estilo Studio, resultados, comparacion y reportes.

---

## Tabla de contenidos

1. Descripcion
2. Caracteristicas principales
3. Arquitectura y modelo de datos
4. Requisitos del sistema
5. Instalacion
6. Configuracion del motor PhysiCell
7. Extension del motor PhysiCell (opcional)
8. Flujo de uso
9. Estructura del repositorio
10. Empaquetado y distribucion
11. Ejecucion de pruebas
12. Integracion continua
13. Licencia
14. Contribucion
15. Contacto y soporte

---

## 1. Descripcion

PhysiCell Lab es una aplicacion de diseno para la gestion de experimentos de simulacion celular basados en PhysiCell. Su objetivo es proporcionar una interfaz grafica que permita crear, configurar, ejecutar y analizar multiples replicaciones de simulaciones manteniendo intacto el codigo fuente del motor PhysiCell.

La aplicacion funciona como una capa de coordinacion: importa y valida archivos de configuracion XML, genera archivos de configuracion por replica con semillas aleatorias y carpetas de salida aisladas, lanza el binario `project.exe` de PhysiCell como proceso externo, y ofrece visores de resultados en 2D y 3D ademas de reportes HTML con trazabilidad completa.

Todos los datos del usuario se persisten en una base de datos SQLite ubicada en el directorio de datos de la aplicacion (`%APPDATA%/PhysiCell_Experiments/experiments.db` en Windows).

---

## 2. Caracteristicas principales

### Gestión de experimentos
- Creacion, edicion y eliminacion de tarjetas de experimento con titulo, descripcion y etiquetas (tags).
- Asociacion de un archivo `PhysiCell_settings.xml` a cada experimento.
- Asociacion de la ruta al binario del motor (`binary_path`) para ejecutar simulaciones por experimento.
- Control de versiones implicito mediante fecha de creacion y fecha de ultima modificacion.

### Configuración y validación XML
- Importacion y lectura de archivos XML de configuracion de PhysiCell.
- Validador estructural interno flexible para detectar inconsistencias antes de ejecutar.
- Reescritura controlada de la etiqueta `<save><folder>` para aislar salidas por replica sin tocar el modelo biologico.

### Ejecución de simulaciones
- Generacion de N replicas por experimento, cada una con `random_seed` distinto y carpeta de salida aislada (`exp_X/replica_i/output`).
- Ejecucion cancelable del binario `project.exe` como proceso externo.
- Registro de estado de cada ejecucion (pendiente, en curso, completada, fallida) con marcas de tiempo de inicio y fin.

### Visualización
- Visor 2D estilo Studio con slider de frames, reproduccion, control de velocidad, filtro por tipo de celula y filtro por sufriente, y barra de color.
- Visor 3D para tumores con malla de membrana, radio real, nucleo interior, color por estado/tipo/presion/volumen, leyenda, tres luces suaves, sombreado especular, corte con plano X y seleccion por ID de celula.
- Visualizaciones globales de resultados y comparaciones lado a lado con sincronizacion de frames.
- Generacion de video 2D y 3D VTK: exportacion de frames de simulacion a video MP4/WebM (funcionalidad a implementar bajo solicitud; requiere FFmpeg o similar en el sistema).

### Resultados y reportes
- Verificacion de integridad por replica.
- Apertura de resultados en visor integrado.
- Exportacion a CSV y JSON.
- Generacion de informes HTML y PDF con trazabilidad completa.
- Limpieza de ejecuciones sin salida valida.

### Comparación
- Vistas paralelas sincronizadas entre replicas.
- Grafica de celulas finales por replica para analisis comparativo.

### Preferencias y regresión
- Configuracion de rutas por defecto y ruta al binario PhysiCell.
- Suite de pruebas de regresion ejecutable directamente.

---

## 3. Arquitectura y modelo de datos

La aplicacion esta organizada en capas dentro del paquete `app/`:

- `nucleo.py`: gestion de datos de usuario, base de datos SQLite y worker de replicas.
- `simulador.py`: creacion de escenarios, replicas y aislamiento de carpetas de salida.
- `motor_physicell.py`: ejecucion cancelable del binario `project.exe`.
- `xml_validator.py`: validacion estructural flexible de archivos XML.
- `config_manager.py`: importacion, lectura y guardado de archivos XML.
- `visualizador.py`: visor 2D basico.
- `comparacion.py`: vistas paralelas y grafica final de celulas.
- `reportes.py`: informes HTML y PDF con trazabilidad.
- `agregador.py`: consolidacion de frames y celulas a CSV.
- `visor_widget.py`: visor 2D y 3D integrado.
- `visor3d_vtk.py`: visualizacion tumoral 3D con PyVista y VTK.
- `lab_window.py`: navegacion y pantallas principales.
- `theme_lab.py`: temas visuales de la interfaz.
- `paginas/`: paginas de interfaz de usuario, una por seccion de la aplicacion.
- `legacy/`: codigo legacy archivado.

El modelo de datos relacional se basa en tres entidades principales:

```
USUARIO 1:N EXPERIMENTO
EXPERIMENTO 1:N EJECUCION
EXPERIMENTO 1:N ESCENARIO
```

### Tablas de la base de datos

**experimentos**
- `id` (clave primaria)
- `title` (texto, no nulo)
- `description` (texto)
- `config_xml_path` (texto)
- `binary_path` (texto)
- `created_at` (fecha y hora)
- `last_modified` (fecha y hora)
- `tags` (texto, valor por defecto vacio)

**ejecuciones** (runs)
- `id` (clave primaria)
- `experiment_id` (clave foranea hacia experimentos)
- `run_number` (numero entero)
- `status` (texto, valor por defecto 'pending')
- `start_time` (fecha y hora)
- `end_time` (fecha y hora)
- `output_dir` (texto)

**escenarios**
- `id` (clave primaria)
- `experiment_id` (clave foranea hacia experimentos)
- `nombre` (texto, no nulo)
- `config_xml_path` (texto)
- `parametros_json` (texto, valor por defecto '{}')
- `created_at` (fecha y hora)

Las claves foraneas garantizan la integridad referencial entre experimentos, ejecuciones y escenarios.

---

## 4. Requisitos del sistema

| Componente | Version o nota |
|---|---|
| Sistema operativo | Windows 11 (probado), Linux (Ubuntu 20.04+), macOS (10.15+) |
| Python | 3.12+ (probado en 3.13). Se recomienda usar un entorno virtual. |
| Dependencias | Ver `requirements-frozen.txt` (versiones congeladas) y `requirements.txt`. |
| Motor PhysiCell | Binario compilado `project.exe` (ver documentacion de PhysiCell). Opcional: usar `studio/download_binary.py template`. |
| Visualizador 3D | PyVista 0.49.1 + VTK 9.7 (se instala con `requirements-frozen.txt`). Si no esta disponible, la app conserva el renderizador Matplotlib. |

Dependencias principales listadas en `requirements.txt`:

- PyQt6 >= 6.6.0
- lxml >= 4.9.0
- numpy >= 1.24.0
- scipy >= 1.10.0
- matplotlib >= 3.7.0
- pyvista >= 0.43.0
- pyvistaqt >= 0.5.0
- vtk >= 9.2.0

---

## 5. Instalacion

### 5.1. Clonar el repositorio

```bash
git clone https://github.com/lunagalarcio/physicell-lab.git
cd physicell-lab
```

### 5.2. Crear y activar un entorno virtual (recomendado)

Windows (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Linux y macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 5.3. Instalar dependencias

```bash
pip install -r requirements-frozen.txt
```

O, si se prefiere instalar versiones minimas no congeladas:

```bash
pip install -r requirements.txt
```

### 5.4. Configurar el binario PhysiCell

Verificar que el binario `project.exe` este disponible en el PATH del sistema, o configurar su ruta desde Preferencias -> Binario PhysiCell dentro de la aplicacion.

### 5.5. Levantar la aplicacion

```bash
python run_app.py
```

---

## 6. Configuracion del motor PhysiCell

PhysiCell Lab no modifica ni empaqueta el motor PhysiCell. El motor se ejecuta como un proceso externo independiente. Para que la aplicacion pueda lanzar simulaciones, es necesario:

1. Disponer de una copia compilada de PhysiCell con el ejecutable `project.exe` (Windows) o `project` (Linux/macOS).
2. Indicar la ruta al ejecutable en Preferencias -> Raiz de PhysiCell dentro de la aplicacion.
3. Proporcionar un archivo `PhysiCell_settings.xml` valido como configuracion base de cada experimento.

La aplicacion genera una copia del XML de configuracion para cada replica, modificando la semilla aleatoria (`random_seed`) y la carpeta de salida (`<save><folder>`), sin alterar el archivo original ni el codigo fuente del motor.

---

## 7. Extension del motor PhysiCell (opcional)

PhysiCell Lab esta disenado como una capa de coordinacion externa y no modifica el motor PhysiCell por defecto. Si se necesita agregar funcionalidad propia al motor, por ejemplo integrar otra librería en `custom.cpp`, el proceso es independiente de esta aplicacion:

1. Localizar el archivo `custom.cpp` (y `custom.h` si corresponde) dentro del directorio fuente del motor PhysiCell, normalmente bajo `PhysiCell/custom_modules/`.
2. Editar `custom.cpp` para incluir la librería deseada y agregar las reglas de comportamiento, interacciones o módulos personalizados.
3. Recompilar el motor PhysiCell siguiendo las instrucciones oficiales del proyecto para generar un nuevo ejecutable `project.exe` (Windows) o `project` (Linux/macOS).
4. En PhysiCell Lab, abrir Preferencias -> Raiz de PhysiCell y apuntar la ruta al nuevo binario compilado.
5. Crear los experimentos y lanzar las replicaciones como de costumbre; la aplicacion lanzara el binario modificado como proceso externo.

> **Importante:** los cambios en `custom.cpp` afectan al modelo biologico del motor. PhysiCell Lab solo se encarga de lanzar el ejecutable y gestionar las carpetas de salida; no valida ni controla el contenido de `custom.cpp`.

---

## 8. Flujo de uso

| Paso | Accion | Descripcion |
|---|---|---|
| 1 | Configuraciones | Importar o crear el archivo `PhysiCell_settings.xml`. Editarlo, validarlo con el validador interno y asociarlo a un experimento. |
| 2 | Experimentos | Crear tarjetas con titulo, descripcion y etiquetas (tags). |
| 3 | Detalle -> Configuracion | Asignar el XML del experimento y la ruta al ejecutable `project.exe`. Validar y guardar. |
| 4 | Detalle -> Ejecucion | Lanzar N replicas de simulacion. Cada replica tiene un `random_seed` distinto y una carpeta de salida aislada `exp_X/replica_i/output`. Se puede cancelar en cualquier momento. |
| 5 | Visualizacion | 2D estilo Studio: slider de frames, Play, velocidad, filtro por tipo de celula y sufriente, barra de color. 3D tumor: visualizacion con malla de membrana, radio real, nucleo interior, color por estado/tipo/presion/volumen, leyenda, 3 luces suaves, sombreado especular, corte con plano X, seleccion por ID. |
| 6 | Resultados | Integridad por replica, abrir en visor, exportar CSV/JSON, informe HTML y PDF, limpieza de runs sin salida. |
| 7 | Comparacion | Vistas paralelas sincronizadas + grafica de celulas finales por replica. |
| 8 | Preferencias | Rutas por defecto, binario PhysiCell y suite de regresion. |

---

## 8. Estructura del repositorio

```
physicell_experimentos/
├─ .gitignore              # Archivos a ignorar (pycache, build, dist, datos de usuario)
├─ README.md               # Este archivo
├─ requirements.txt        # Dependencias minimas
├─ requirements-frozen.txt # Versiones congeladas (reproduccion exacta)
├─ build.spec              # Configuracion PyInstaller para .exe
├─ run_app.py              # Punto de entrada de la aplicacion
├─ app/
│  ├─ nucleo.py            # Datos usuario, SQLite, worker de replicas
│  ├─ simulador.py         # Escenarios, replicas, aislamiento de carpetas
│  ├─ motor_physicell.py   # Ejecucion cancelable del binario project.exe
│  ├─ xml_validator.py     # Validacion estructural flexible
│  ├─ config_manager.py    # Importar/leer/guardar XML
│  ├─ visualizador.py      # Visor 2D basico
│  ├─ comparacion.py       # Vistas paralelas + grafica final
│  ├─ reportes.py          # Informe HTML/PDF con trazabilidad
│  ├─ agregador.py         # Consolidar frames/celulas a CSV
│  ├─ visor_widget.py      # Visor 2D/3D integrado
│  ├─ visor3d_vtk.py       # Tumor 3D PyVista/VTK
│  ├─ lab_window.py        # Navegacion y pantallas principales
│  ├─ theme_lab.py         # Temas visuales
│  ├─ paginas/             # Paginas de UI (una por seccion)
│  └─ legacy/              # Codigo legacy archivado
│     └─ interfaz_notion.py # Ventana legacy (re-exporta nucleo)
├─ config/                 # Plantillas XML de ejemplo
├─ studio/                 # Modulos del Studio PhysiCell (referencia)
├─ tests/
│  ├─ conftest.py          # Fixtures compartidas (portables)
│  ├─ test_xml_validator.py
│  ├─ test_simulador.py
│  ├─ test_agregador.py
│  ├─ test_comparacion.py
│  ├─ test_reportes.py
│  ├─ test_visores.py
│  └─ test_regresion.py    # Suite de pruebas (ejecutable directamente)
├─ pytest.ini              # Configuracion de pytest
├─ .github/
│  └─ workflows/
│     └─ ci.yml            # CI: Ubuntu + Windows, Python 3.12/3.13
└─ dist/                   # (Generado) Ejecutable PhysiCellManager
```

---

## 9. Empaquetado y distribucion

El proyecto incluye `build.spec` para generar un ejecutable autonomo con PyInstaller. PhysiCell queda como motor externo y no se empaqueta ni se modifica.

### Windows

```powershell
pyinstaller build.spec
```

El resultado aparecera en `dist/PhysiCellManager/PhysiCellManager.exe`.

### Linux y macOS

```bash
pyinstaller build.spec
```

El resultado aparecera en `dist/PhysiCellManager/PhysiCellManager` (sin extension `.exe`).

Nota: En Linux y macOS el ejecutable no lleva extension. El motor PhysiCell (`project` o `project.exe`) debe estar compilado por separado y su ruta configurarse en Preferencias -> Raiz de PhysiCell.

Los directorios `dist/` y `build/` no se suben al repositorio (estan incluidos en `.gitignore`).

---

## 10. Ejecucion de pruebas

El proyecto incluye una suite de pruebas basada en pytest ubicada en `tests/`. El archivo de configuracion es `pytest.ini`.

Ejecutar todas las pruebas:

```bash
pytest
```

Ejecutar un archivo de prueba específico:

```bash
pytest tests/test_simulador.py
```

Las pruebas cubren:
- validador XML
- simulador (escenarios y replicas)
- agregador de resultados
- comparacion de ejecuciones
- generacion de reportes
- visores 2D y 3D
- suite de regresion

---

## 11. Integracion continua

El repositorio contiene un flujo de trabajo de CI en `.github/workflows/ci.yml` que se ejecuta en Ubuntu y Windows con Python 3.12 y 3.13. El flujo instala dependencias y ejecuta la suite de pruebas en cada push y pull request.

---

## 12. Licencia

Este proyecto esta bajo la licencia MIT. Ver el archivo `LICENSE` para mas detalles.

---

## 13. Contribucion

1. Hacer un fork del repositorio.
2. Crear una rama: `git checkout -b feature/nombre-de-la-caracteristica`.
3. Confirmar los cambios: `git commit -m "Añade tal cosa"`.
4. Subir los cambios: `git push origin main`.
5. Abrir un Pull Request describiendo que se hace y por que.

Se agradecen mejoras de interfaz de usuario, nuevos filtros de visualizacion, documentacion adicional o expansion de la suite de regresion.

---

## 14. Contacto y soporte

- GitHub: [@lunagalarcio](https://github.com/lunagalarcio)
- Email: tu-email@ejemplo.com (opcional)
- Issue Tracker: Usar la pestaña Issues del repositorio para reportar errores o sugerencias.

---

*Documentacion generada para el proyecto PhysiCell Lab.*
