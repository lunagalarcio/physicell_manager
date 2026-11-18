# PhysiCell Lab — Gestor de experimentos PhysiCell

Aplicación de escritorio (Python + PyQt6) para gestionar el ciclo experimental con PhysiCell sin modificar el motor: experimentos, escenarios, replicas, validacion XML, ejecucion con trazabilidad, visualizacion 2D y 3D estilo Studio, resultados, comparacion y reportes.

---

## Tabla de contenidos

1. [Descripcion](#1-descripcion)
2. [Caracteristicas principales](#2-caracteristicas-principales)
3. [Arquitectura y modelo de datos](#3-arquitectura-y-modelo-de-datos)
4. [Requisitos tecnicos del sistema](#4-requisitos-tecnicos-del-sistema)
5. [Estructura de la base de datos](#5-estructura-de-la-base-de-datos)
6. [Instalacion](#6-instalacion)
7. [Configuracion del motor PhysiCell](#7-configuracion-del-motor-physicell)
8. [Extension del motor PhysiCell (opcional)](#8-extension-del-motor-physicell-opcional)
9. [Flujo de uso](#9-flujo-de-uso)
10. [Estructura del repositorio](#10-estructura-del-repositorio)
11. [Empaquetado y distribucion](#11-empaquetado-y-distribucion)
12. [Ejecucion de pruebas](#12-ejecucion-de-pruebas)
13. [Integracion continua](#13-integracion-continua)
14. [Licencia](#14-licencia)
15. [Contribucion](#15-contribucion)
16. [Contacto y soporte](#16-contacto-y-soporte)

---

## 1. Descripcion

PhysiCell Lab es una aplicacion de diseno para la gestion de experimentos de simulacion celular basados en PhysiCell. Su objetivo es proporcionar una interfaz grafica que permita crear, configurar, ejecutar y analizar multiples replicaciones de simulaciones manteniendo intacto el codigo fuente del motor PhysiCell.

La aplicacion funciona como una capa de coordinacion: importa y valida archivos de configuracion XML, genera archivos de configuracion por replica con semillas aleatorias y carpetas de salida aisladas, lanza el binario `project.exe` de PhysiCell como proceso externo, y ofrece visores de resultados en 2D y 3D ademas de reportes HTML con trazabilidad completa.

Todos los datos del usuario se persisten en una base de datos SQLite ubicada en el directorio de datos de la aplicacion (`%APPDATA%/PhysiCell_Experiments/experiments.db` en Windows).

---

## 2. Caracteristicas principales

### 2.1. Gestion de experimentos
- Creacion, edicion y eliminacion de tarjetas de experimento con titulo, descripcion y etiquetas (tags).
- Asociacion de un archivo `PhysiCell_settings.xml` a cada experimento.
- Asociacion de la ruta al binario del motor (`binary_path`) para ejecutar simulaciones por experimento.
- Control de versiones con historial de configuraciones: registrar nuevas versiones del XML (con copia de resguardo), activar/restaurar versiones anteriores y validar el historial por experimento.

### 2.2. Configuracion y validacion XML
- Importacion y lectura de archivos XML de configuracion de PhysiCell.
- Validador estructural interno flexible para detectar inconsistencias antes de ejecutar.
- Reescritura controlada de la etiqueta `<save><folder>` para aislar salidas por replica sin tocar el modelo biologico.

### 2.3. Ejecucion de simulaciones
- Generacion de N replicas por experimento, cada una con `random_seed` distinto y carpeta de salida aislada (`exp_X/replica_i/output`).
- Ejecucion cancelable del binario `project.exe` como proceso externo.
- Registro de estado de cada ejecucion (pendiente, en curso, completada, fallida) con marcas de tiempo de inicio y fin.

### 2.4. Visualizacion
- Visor 2D estilo Studio con slider de frames, reproduccion, control de velocidad, filtro por tipo de celula y filtro por sustrato, y barra de color.
- Visor 3D para tumores con malla de membrana, radio real, nucleo interior, color por estado/tipo/precion/volumen, leyenda, tres luces suaves, sombreado especular, corte con plano X y seleccion por ID de celula.
- Visualizaciones globales de resultados y comparaciones lado a lado con sincronizacion de frames.
- Generacion de video 2D y 3D VTK: exportacion de frames de simulacion a video MP4/WebM (funcionalidad a implementar bajo solicitud; requiere FFmpeg o similar en el sistema).

### 2.5. Resultados y reportes
- Verificacion de integridad por replica.
- Apertura de resultados en visor integrado.
- Exportacion a CSV y JSON.
- Generacion de informes HTML y PDF con trazabilidad completa.
- Limpieza de ejecuciones sin salida valida.

### 2.6. Comparacion
- Vistas paralelas sincronizadas entre replicas.
- Grafica de celulas finales por replica para analisis comparativo.
- Prueba t de Student entre dos experimentos sobre metricas de replicas (n. de celulas finales), con exportacion de resultados a CSV.

### 2.7. Preferencias y regresion
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
- `estadistica.py`: metricas por replica y pruebas t de Student entre experimentos.
- `servicios.py`: capa de servicios que coordina nucleo, simulador, motor y estadistica.
- `visualizador.py`: visor 2D basico.
- `comparacion.py`: vistas paralelas y grafica final de celulas.
- `reportes.py`: informes HTML y PDF con trazabilidad.
- `agregador.py`: consolidacion de frames y celulas a CSV.
- `visor_widget.py`: visor 2D y 3D integrado.
- `visor3d_vtk.py`: visualizacion tumoral 3D con PyVista y VTK.
- `lab_window.py`: navegacion y pantallas principales.
- `theme_lab.py`: temas visuales.
- `paginas/`: paginas de interfaz de usuario, una por seccion de la aplicacion.
- `legacy/`: codigo legacy archivado.
- `motor_physicell.py` complementario: diagnosticos, hashes, conteo de salidas, intervalos de guardado.

### 3.1. Modelo de datos

```
USUARIO 1:N EXPERIMENTO
EXPERIMENTO 1:N CONFIGURACION
EXPERIMENTO 1:N ESCENARIO
EXPERIMENTO 1:N EJECUCION
ESCENARIO 1:N EJECUCION (via escenario_id)
```

### 3.2. Tablas de la base de datos

| Tabla | Descripcion |
|---|---|
| `usuarios` | Usuarios de la app (autenticacion local). |
| `experimentos` | Experimentos con metadatos y rutas. |
| `configuraciones` | Versiones de configuracion por experimento. |
| `escenarios` | Escenarios dentro de un experimento. |
| `runs` | Ejecuciones / replicas (estados, tiempos, errores, trazabilidad). |
| `batches` | Lotes de ejecuciones de varias replicas. |
| `videos` | Videos/exportaciones generadas por replica. |

> Ver detalle completo con campos, tipos de dato, restricciones y descripciones en la
> [seccion 5](#5-estructura-de-la-base-de-datos).

---

## 4. Requisitos tecnicos del sistema

### 4.1. Hardware

| Componente | Especificacion |
|---|---|
| Sistema operativo | Windows 11 (probado), Linux (Ubuntu 20.04+), macOS (10.15+) |
| Memoria RAM | Recomendada 8 GB o superior (dependiendo del tamano del modelo biologico) |
| Disco | Espacio para salidas de simulacion, snapshots y base de datos SQLite |

### 4.2. Software

| Componente | Version / Nota |
|---|---|
| Python | 3.12+ (probado en 3.13); entorno virtual recomendado |
| PyQt6 | >= 6.6.0 |
| lxml | >= 4.9.0 |
| numpy | >= 1.24.0 |
| scipy | >= 1.10.0 |
| matplotlib | >= 3.7.0 |
| pyvista | >= 0.43.0 |
| pyvistaqt | >= 0.5.0 |
| vtk | >= 9.2.0 |
| Dependencias congeladas | `requirements-frozen.txt` |

### 4.3. Motor de simulacion (externo)

| Componente | Especificacion |
|---|---|
| Motor | Binario compilado de PhysiCell (`project.exe` en Windows, `project` en Linux/macOS) |
| Rol de la app | Capa de coordinacion: no modifica el codigo fuente del motor |
| Configuracion | Archivo `PhysiCell_settings.xml` valido por experimento |

### 4.4. Persistencia

| Componente | Especificacion |
|---|---|
| Motor de base de datos | SQLite |
| Ubicacion | `%APPDATA%/PhysiCell_Experiments/experiments.db` (Windows) |

### 4.5. Visualizacion 3D

| Componente | Especificacion |
|---|---|
| Motor 3D | PyVista 0.49.1 + VTK 9.7 (fallback: Matplotlib) |

---

## 5. Estructura de la base de datos

**Motor:** SQLite · **Ubicacion:** `%APPDATA%/PhysiCell_Experiments/experiments.db`

### 5.1. Tabla `usuarios`

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico del usuario |
| `username` | TEXT | NOT NULL, UNIQUE | Nombre de usuario |
| `email` | TEXT | NOT NULL, UNIQUE | Correo electronico |
| `password_hash` | TEXT | NOT NULL | Hash de la contrasena |
| `rol` | TEXT | NOT NULL, DEFAULT 'usuario' | Rol del usuario |
| `activo` | INTEGER | NOT NULL, DEFAULT 1 | Estado activo/inactivo |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creacion |
| `ultimo_acceso` | DATETIME | - | Ultimo acceso |

### 5.2. Tabla `experimentos`

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico del experimento |
| `title` | TEXT | NOT NULL | Titulo del experimento |
| `description` | TEXT | - | Descripcion |
| `config_xml_path` | TEXT | - | Ruta al XML de configuracion |
| `binary_path` | TEXT | - | Ruta al binario PhysiCell |
| `custom_cpp_path` | TEXT | - | Ruta al custom.cpp |
| `custom_h_path` | TEXT | - | Ruta al custom.h |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creacion |
| `last_modified` | DATETIME | - | Ultima modificacion |
| `tags` | TEXT | DEFAULT '' | Etiquetas |
| `usuario_id` | INTEGER | FK -> usuarios | Propietario |

### 5.3. Tabla `configuraciones`

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico |
| `experiment_id` | INTEGER | NOT NULL, FK -> experimentos | Experimento propietario |
| `nombre` | TEXT | NOT NULL, DEFAULT 'base' | Nombre/version (`base`, `v2`, ...) |
| `xml_path` | TEXT | NOT NULL | Ruta al XML guardado |
| `version` | INTEGER | NOT NULL, DEFAULT 1 | Version numerica |
| `es_activa` | INTEGER | NOT NULL, DEFAULT 0 | Unica activa por experimento |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creacion |

### 5.4. Tabla `escenarios`

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico |
| `experiment_id` | INTEGER | NOT NULL, FK -> experimentos | Experimento propietario |
| `nombre` | TEXT | NOT NULL | Nombre del escenario |
| `config_xml_path` | TEXT | - | Ruta al XML del escenario |
| `parametros_json` | TEXT | DEFAULT '{}' | Parametros en JSON |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creacion |
| `configuracion_id` | INTEGER | FK -> configuraciones | Config vinculada |

### 5.5. Tabla `runs` (ejecuciones)

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico |
| `experiment_id` | INTEGER | NOT NULL, FK -> experimentos | Experimento propietario |
| `run_number` | INTEGER | - | Numero de replica/ejecucion |
| `status` | TEXT | DEFAULT 'pending' | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `start_time` | DATETIME | - | Inicio |
| `end_time` | DATETIME | - | Fin |
| `output_dir` | TEXT | - | Carpeta de salida |
| `escenario_id` | INTEGER | FK -> escenarios | Escenario |
| `configuracion_id` | INTEGER | FK -> configuraciones | Config |
| `error_message` | TEXT | - | Error |
| `log_path` | TEXT | - | Log |
| `pid` | INTEGER | - | PID |
| `batch_id` | INTEGER | FK -> batches | Lote |

### 5.6. Tabla `batches` (lotes de ejecuciones)

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico |
| `experiment_id` | INTEGER | FK -> experimentos | Experimento propietario |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creacion del lote |
| `n_replicas` | INTEGER | - | Numero de replicas |
| `xml_path` | TEXT | - | XML |
| `xml_sha256` | TEXT | - | Hash XML |
| `exe_path` | TEXT | - | Ejecutable |
| `exe_sha256` | TEXT | - | Hash ejecutable |
| `seed_base` | INTEGER | DEFAULT 1000 | Semilla base |
| `timeout_min` | INTEGER | DEFAULT 0 | Timeout |
| `inactividad_min` | INTEGER | DEFAULT 10 | Inactividad |
| `python_version` | TEXT | - | Version Python |
| `plataforma` | TEXT | - | Sistema |
| `notas` | TEXT | - | Notas |
| `status` | TEXT | DEFAULT 'running' | Estado lote |
| `error_message` | TEXT | - | Error |

### 5.7. Tabla `videos`

| Campo | Tipo | Restriccion | Descripcion |
|---|---|---|---|
| `id` | INTEGER | PK | Identificador unico |
| `experiment_id` | INTEGER | FK -> experimentos | Experimento propietario |
| `run_number` | INTEGER | - | Replica |
| `tipo` | TEXT | DEFAULT '2d' | Tipo video |
| `ruta_archivo` | TEXT | - | Ruta |
| `fps` | INTEGER | DEFAULT 1 | FPS |
| `frames` | INTEGER | DEFAULT 0 | Frames |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creacion |

---

## 6. Instalacion

### 6.1. Clonar el repositorio

```bash
git clone https://github.com/lunagalarcio/physicell-lab.git
cd physicell-lab
```

### 6.2. Crear y activar un entorno virtual (recomendado)

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

### 6.3. Instalar dependencias

```bash
pip install -r requirements-frozen.txt
```

o, si se prefiere instalar versiones minimas no congeladas:

```bash
pip install -r requirements.txt
```

### 6.4. Configurar el binario PhysiCell

Verificar que el binario `project.exe` este disponible en el PATH del sistema, o configurar su ruta desde Preferencias -> Binario PhysiCell dentro de la aplicacion.

### 6.5. Levantar la aplicacion

```bash
python run_app.py
```

---

## 7. Configuracion del motor PhysiCell

PhysiCell Lab no modifica ni empaqueta el motor PhysiCell. El motor se ejecuta como un proceso externo independiente.

Para que la aplicacion pueda lanzar simulaciones, es necesario:

1. Disponer de una copia compilada de PhysiCell con el ejecutable `project.exe` (Windows) o `project` (Linux/macOS).
2. Indicar la ruta al ejecutable en Preferencias -> Raiz de PhysiCell dentro de la aplicacion.
3. Proporcionar un archivo `PhysiCell_settings.xml` valido como configuracion base de cada experimento.

La aplicacion genera una copia del XML de configuracion para cada replica, modificando la semilla aleatoria (`random_seed`) y la carpeta de salida (`<save><folder>`), sin alterar el archivo original ni el codigo fuente del motor.

---

## 8. Extension del motor PhysiCell (opcional)

PhysiCell Lab esta disenado como una capa de coordinacion externa y no modifica el motor PhysiCell por defecto. Si se necesita agregar funcionalidad propia al motor:

1. Localizar el archivo `custom.cpp` (y `custom.h` si corresponde) dentro del directorio fuente del motor PhysiCell, normalmente bajo `PhysiCell/custom_modules/`.
2. Editar `custom.cpp` para incluir la libreria deseada y agregar las reglas de comportamiento, interacciones o modulos personalizados.
3. Recompilar el motor PhysiCell siguiendo las instrucciones oficiales del proyecto para generar un nuevo ejecutable `project.exe` (Windows) o `project` (Linux/macOS).
4. En PhysiCell Lab, abrir Preferencias -> Raiz de PhysiCell y apuntar la ruta al nuevo binario compilado.
5. Crear los experimentos y lanzar las replicaciones como de costumbre; la aplicacion lanzara el binario modificado como proceso externo.

> **Importante:** los cambios en `custom.cpp` afectan al modelo biologico del motor. PhysiCell Lab solo se encarga de lanzar el ejecutable y gestionar las carpetas de salida; no valida ni controla el contenido de `custom.cpp`.

---

## 9. Flujo de uso

| Paso | Accion | Descripcion |
|---|---|---|
| 1 | Configuraciones | Importar o crear el archivo `PhysiCell_settings.xml`. Editarlo, validarlo con el validador interno y asociarlo a un experimento. |
| 2 | Experimentos | Crear tarjetas con titulo, descripcion y etiquetas (tags). |
| 3 | Detalle -> Configuracion | Asignar el XML del experimento y la ruta al ejecutable `project.exe`. Validar y guardar. |
| 4 | Detalle -> Ejecucion | Lanzar N replicas de simulacion. Cada replica tiene un `random_seed` distinto y una carpeta de salida aislada `exp_X/replica_i/output`. Se puede cancelar en cualquier momento. |
| 5 | Visualizacion | 2D estilo Studio: slider de frames, Play, velocidad, filtro por tipo de celula y sustrato, barra de color. 3D tumor: visualizacion con malla de membrana, radio real, nucleo interior, color por estado/tipo/precion/volumen, leyenda, 3 luces suaves, sombreado especular, corte con plano X, seleccion por ID. |
| 6 | Resultados | Integridad por replica, abrir en visor, exportar CSV/JSON, informe HTML y PDF, limpieza de runs sin salida. |
| 7 | Comparacion | Vistas paralelas sincronizadas + grafica de celulas finales por replica. |
| 8 | Preferencias | Rutas por defecto, binario PhysiCell y suite de regresion. |

---

## 10. Estructura del repositorio

```
physicell_manager-main/
+-.gitignore               # Archivos a ignorar (pycache, build, dist, datos de usuario)
+-README.md               # Este archivo
+-requirements.txt        # Dependencias minimas
+-requirements-frozen.txt # Versiones congeladas (reproduccion exacta)
+-build.spec              # Configuracion PyInstaller para .exe
+-run_app.py              # Punto de entrada de la aplicacion
+-app/
|  +-nucleo.py            # Datos usuario, SQLite, worker de replicas
|  +-simulador.py         # Escenarios, replicas, aislamiento de carpetas
|  +-motor_physicell.py   # Ejecucion cancelable del binario project.exe
|  +-xml_validator.py     # Validacion estructural flexible
|  +-config_manager.py    # Importar/leer/guardar XML
|  +-visualizador.py      # Visor 2D basico
|  +-comparacion.py       # Vistas paralelas + grafica final
|  +-reportes.py          # Informe HTML/PDF con trazabilidad
|  +-agregador.py         # Consolidar frames/celulas a CSV
|  +-visor_widget.py      # Visor 2D/3D integrado
|  +-visor3d_vtk.py       # Tumor 3D PyVista/VTK
|  +-lab_window.py        # Navegacion y pantallas principales
|  +-theme_lab.py         # Temas visuales
|  +-paginas/             # Paginas de UI (una por seccion)
|  +-legacy/              # Codigo legacy archivado
|     +-interfaz_notion.py # Ventana legacy
+-config/                 # Plantillas XML de ejemplo
+-studio/                 # Modulos del Studio PhysiCell (referencia)
+-tests/
|  +-conftest.py          # Fixtures compartidas (portables)
|  +-test_agregador.py
|  +-test_comparacion.py
|  +-test_funcionales.py # Pruebas funcionales CP01-CP13 (Tabla 17)
|  +-test_regresion.py    # Suite de pruebas (ejecutable directamente)
|  +-test_reportes.py
|  +-test_simulador.py
|  +-test_visores.py
|  +-test_versionado_configuraciones.py
|  +-test_xml_validator.py
+-pytest.ini              # Configuracion de pytest
+-.github/
|  +-workflows/
|     +-ci.yml            # CI: Ubuntu + Windows, Python 3.12/3.13
+-dist/                   # (Generado) Ejecutable PhysiCellManager
```

---

## 11. Empaquetado y distribucion

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

## 12. Ejecucion de pruebas

El proyecto incluye una suite de pruebas basada en pytest ubicada en `tests/`. El archivo de configuracion es `pytest.ini`.

### 12.1. Comandos basicos

Ejecutar todas las pruebas:

```bash
pytest
```

Ejecutar un archivo de prueba especifico:

```bash
pytest tests/test_simulador.py
pytest tests/test_funcionales.py -v
```

### 12.2. Suites disponibles

| Archivo | Contenido |
|---|---|
| `tests/test_xml_validator.py` | Validacion de XML de PhysiCell. |
| `tests/test_simulador.py` | Escenarios, replicas, runs. |
| `tests/test_agregador.py` | Consolidacion de frames/celulas. |
| `tests/test_comparacion.py` | Comparaciones y graficas. |
| `tests/test_reportes.py` | Reportes HTML/CSV/JSON. |
| `tests/test_visores.py` | Visores 2D/3D. |
| `tests/test_versionado_configuraciones.py` | Versionado de configuraciones. |
| `tests/test_regresion.py` | Suite de regresion (ejecutable directamente). |
| `tests/test_funcionales.py` | **Pruebas funcionales CP01-CP13** (Tabla 17). |

### 12.3. Pruebas funcionales (CP01-CP13)

Los casos funcionales derivados de los requerimientos funcionales (RF01-RF13) y la regla de no falla (RNF09) se implementan en `tests/test_funcionales.py`:

| Caso | Requisito | Descripcion | Estado |
|---|---|---|---|
| CP01 | RF04 | Crear experimento con nombre y descripcion | PASS |
| CP02 | RF05 | Crear escenarios y replicas | PASS |
| CP03 | RF01/RF02 | Importar XML valido | PASS |
| CP04 | RF02 | Importar XML mal formado (rechazo) | PASS |
| CP05 | RF03 | Editar/guardar configuracion (versionado) | PASS |
| CP06 | RF06/RF07 | Ejecutar simulacion de replica | PASS |
| CP07 | RF06/RF07 | Ejecutar varias replicas por lote | PASS |
| CP08 | RNF09 | Ejecutar simulacion con error | PASS |
| CP09 | RF08 | Consultar resultados | PASS |
| CP10 | RF09/RF10 | Visualizar estado temporal 3D | PASS |
| CP11 | RF11 | Comparar escenarios/replicas | PASS |
| CP12 | RF12 | Generar/exportar reporte | PASS |
| CP13 | RF13 | Trazabilidad desde resultado | PASS |

Resultado: **13/13 pruebas funcionales en estado PASS** · Suite completa: **45 tests passed, 0 failed**.

> Ver detalle completo en: [docs/informe_pruebas_funcionales.md](docs/informe_pruebas_funcionales.md).

### 12.4. Suite de regresion

```bash
python tests/test_regresion.py
```

---

## 13. Integracion continua

El repositorio contiene un flujo de trabajo de CI en `.github/workflows/ci.yml` que se ejecuta en Ubuntu y Windows con Python 3.12 y 3.13. El flujo instala dependencias y ejecuta la suite de pruebas en cada push y pull request.

---

## 14. Licencia

Este proyecto esta bajo la licencia MIT. Ver el archivo `LICENSE` para mas detalles.

---

## 15. Contribucion

1. Hacer un fork del repositorio.
2. Crear una rama: `git checkout -b feature/nombre-de-la-caracteristica`.
3. Confirmar los cambios: `git commit -m "Añade tal cosa"`.
4. Subir los cambios: `git push origin main`.
5. Abrir un Pull Request describiendo que se hace y por que.

Se agradecen mejoras de interfaz de usuario, nuevos filtros de visualizacion, documentacion adicional o expansion de la suite de regresion.

---

## 16. Contacto y soporte

- GitHub: [@lunagalarcio](https://github.com/lunagalarcio)
- Email: tu-email@ejemplo.com (opcional)
- Issue Tracker: Usar la pestaña Issues del repositorio para reportar errores o sugerencias.

---

*Documentacion generada para el proyecto PhysiCell Lab.*
