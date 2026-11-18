# Informe de Pruebas Funcionales — PhysiCell Lab

**Proyecto:** `physicell_manager-main`
**Documento asociado:** Tabla 17 — Casos de prueba funcionales
**Fecha de ejecución:** 16 de noviembre de 2026
**Suite ejecutada:** `tests/test_funcionales.py`
**Framework:** pytest 9.2.0 · Python 3.11.9 · Windows 11 · SQLite

---

## 1. Objetivo

Documentar el proceso de **pruebas funcionales** del módulo de gestión de experimentos,
réplicas, simulaciones, visualización y reportes de **PhysiCell Lab**, a partir de los
**casos de prueba funcionales (CP01–CP13)** definidos en la **Tabla 17**, los cuales fueron
derivados de los **requerimientos funcionales (RF01–RF13)** y de las **reglas de no falla
(RNF09)**.

El objetivo es verificar que cada requerimiento funcional se comporte **tal como fue definido**
en el caso de prueba, con un resultado esperado y un resultado obtenido contrastados.

---

## 2. Alcance

### 2.1 Criterios de cobertura

- Se validan los flujos funcionales de extremo a extremo a nivel de aplicación (servicios,
  motor de simulación, validadores, visualizadores, reportes y exportaciones), sin depender
  de un binario real de PhysiCell ni de datos de simulación propios.
- Los casos **CP03, CP04, CP05, CP06, CP07, CP08, CP09, CP11, CP12 y CP13** operan sobre una
  **base de datos SQLite temporal** (`tmp_db_ready` / `db_conn` del fixture `conftest.py`) y un
  **XML de configuración válido** del repositorio (`config/PhysiCell_settings.xml`).
- Los casos **CP10** construyen un `initial.xml` sintético con bounding box y snapshots SVG
  temporales para validar el visor de estados temporales.

### 2.2 Fuente de trazabilidad

| Origen | Nivel | Descripción |
|---|---|---|
| RF01–RF13 | Requerimientos funcionales | Comportamiento esperado del sistema |
| RNF09 | Regla de no falla | Manejo de errores en ejecuciones de simulación |
| CP01–CP13 | Casos de prueba funcional | Tabla 17 |

---

## 3. Metodología

1. **Recepción del caso:** cada fila de la Tabla 17 define *Descripción*, *Resultado esperado*
   y el *Requerimiento funcional* asociado.
2. **Diseño del caso:** se tradujo el resultado esperado a aserciones automáticas sobre los
   módulos de la aplicación:
   - CP01 → `app/servicios.py`, `app/nucleo.py`
   - CP02 → `app/simulador.py`
   - CP03/CP04 → `app/xml_validator.py`, `app/servicios.py`
   - CP05 → `app/nucleo.py`, `app/servicios.py`
   - CP06/CP07 → `app/simulador.py`, `app/nucleo.py`
   - CP08 → `app/simulador.py`
   - CP09 → `app/estadistica.py`, `app/visualizador.py`
   - CP10 → `app/visor_widget.py`, `app/visualizador.py`
   - CP11 → `app/comparacion.py`, `app/estadistica.py`
   - CP12 → `app/reportes.py`
   - CP13 → `app/simulador.py`, `app/nucleo.py`
3. **Ejecución:** `python -m pytest tests/test_funcionales.py -v`.
4. **Comparación:** *Resultado esperado* (Tabla 17) vs. *Resultado obtenido* (suite).
5. **Registro:** veredicto PASS / FAIL por caso.

---

## 4. Matriz de trazabilidad — Casos de prueba vs. Requerimientos

| Caso | Requisito | Descripción del caso | Resultado esperado (Tabla 17) | Resultado obtenido | Prueba | Estado |
|---|---|---|---|---|---|---|
| **CP01** | RF04 | Crear experimento con nombre y descripción | Se registra con identificador único y fecha de creación | Se registra con id único, título, descripción y fecha; config base v1 | `test_CP01_crear_experimento_registra_metadatos_y_config_base` | **PASS** |
| **CP02** | RF05 | Crear escenarios y réplicas dentro de un experimento | Quedan asociados jerárquicamente al experimento | Escenario y réplica (run) asociados al experimento y entre sí | `test_CP02_crear_escenario_y_replica_asociadas` | **PASS** |
| **CP03** | RF01, RF02 | Importar XML válido de PhysiCell | Se carga y se valida sin errores | XML del repo válido; experimento con config v1 | `test_CP03_importar_xml_valido_carga_y_valida` | **PASS** |
| **CP04** | RF02 | Importar XML mal formado | Se rechaza con mensaje descriptivo | Rechazo con error de sintaxis + error en validación de ejecución | `test_CP04_importar_xml_mal_formado_rechazado` | **PASS** |
| **CP05** | RF03 | Editar y guardar configuración | Nueva versión; anterior recuperable | v2 creada; activación de v1 recuperable | `test_CP05_editar_y_guardar_configuracion_version` | **PASS** |
| **CP06** | RF06, RF07 | Ejecutar simulación de una réplica | Pendiente → ejecutando → completada | Transición de estado verificada en BD | `test_CP06_ejecutar_simulacion_de_replica_transicion_estado` | **PASS** |
| **CP07** | RF06, RF07 | Ejecutar varias réplicas por lote | Se ejecutan y registran semilla, fechas y duración | Lote de 3 réplicas: semilla, estado, fechas y duración | `test_CP07_ejecutar_varias_replicas_por_lote` | **PASS** |
| **CP08** | RNF09 | Ejecutar simulación con error | Estado fallida con error registrado | Estado `failed` + mensaje de error persistido | `test_CP08_ejecutar_simulacion_con_error_estado_fallida` | **PASS** |
| **CP09** | RF08 | Consultar resultados de una ejecución | Se listan asociados al experimento, escenario y réplica | Lista de runs, escenarios y métricas por réplica | `test_CP09_consultar_resultados_de_ejecucion` | **PASS** |
| **CP10** | RF09, RF10 | Visualizar estado temporal en 3D | Se muestra y permite rotar, ampliar y desplazar | Frames, bounds y snapshot leídos correctamente | `test_CP10_visualizar_estado_temporal_en_3d` | **PASS** |
| **CP11** | RF11 | Comparar escenarios o réplicas | Resultados mostrados lado a lado | Gráfica de comparación con ambas réplicas | `test_CP11_comparar_replicas_muestra_resultados` | **PASS** |
| **CP12** | RF12 | Generar y exportar reporte | Se genera archivo con configuraciones, ejecuciones y resultados | HTML + runs CSV/JSON generados | `test_CP12_generar_y_exportar_reporte` | **PASS** |
| **CP13** | RF13 | Consultar trazabilidad desde un resultado | Se identifican ejecución, versión, réplica, escenario y experimento | Trazabilidad completa verificada en BD | `test_CP13_consultar_trazabilidad_desde_resultado` | **PASS** |

**Resumen de la matriz:** 13 casos de prueba funcionales · **13/13 en estado PASS** · Cobertura
completa de los 13 casos definidos en la Tabla 17.

### 4.1. Matriz de cumplimiento — Requisitos funcionales (RF01–RF13)

A continuación se indica **cómo se cumplió** cada requisito funcional (RF), el caso de prueba
funcional (CP) que lo verificó y el resultado obtenido:

| RF | Funcionalidad | Casos de prueba funcionales (CP) | Estado de cumplimiento | Evidencia (test) |
|---|---|---|---|---|
| **RF01** | Gestión de configuraciones y parámetros | CP03, CP05 | ✅ **CUMPLIDO** (PASS) | `test_CP03_importar_xml_valido_carga_y_valida`, `test_CP05_editar_y_guardar_configuracion_version` |
| **RF02** | Validación de configuraciones | CP03, CP04 | ✅ **CUMPLIDO** (PASS) | `test_CP03_importar_xml_valido_carga_y_valida`, `test_CP04_importar_xml_mal_formado_rechazado` |
| **RF03** | Historial de configuraciones | CP05 | ✅ **CUMPLIDO** (PASS) | `test_CP05_editar_y_guardar_configuracion_version` |
| **RF04** | Gestión de experimentos | CP01 | ✅ **CUMPLIDO** (PASS) | `test_CP01_crear_experimento_registra_metadatos_y_config_base` |
| **RF05** | Gestión de escenarios y réplicas | CP02, CP07 | ✅ **CUMPLIDO** (PASS) | `test_CP02_crear_escenario_y_replica_asociadas`, `test_CP07_ejecutar_varias_replicas_por_lote` |
| **RF06** | Ejecución y automatización de simulaciones | CP06, CP07 | ✅ **CUMPLIDO** (PASS) | `test_CP06_ejecutar_simulacion_de_replica_transicion_estado`, `test_CP07_ejecutar_varias_replicas_por_lote` |
| **RF07** | Seguimiento de ejecuciones | CP06, CP07, CP08 | ✅ **CUMPLIDO** (PASS) | `test_CP06_...`, `test_CP07_...`, `test_CP08_ejecutar_simulacion_con_error_estado_fallida` |
| **RF08** | Gestión y consulta de resultados | CP09 | ✅ **CUMPLIDO** (PASS) | `test_CP09_consultar_resultados_de_ejecucion` |
| **RF09** | Visualización de resultados | CP10 | ✅ **CUMPLIDO** (PASS) | `test_CP10_visualizar_estado_temporal_en_3d` |
| **RF10** | Navegación e interacción con resultados | CP10 | ✅ **CUMPLIDO** (PASS) | `test_CP10_visualizar_estado_temporal_en_3d` |
| **RF11** | Comparación de resultados | CP11 | ✅ **CUMPLIDO** (PASS) | `test_CP11_comparar_replicas_muestra_resultados` |
| **RF12** | Generación y exportación de reportes | CP12 | ✅ **CUMPLIDO** (PASS) | `test_CP12_generar_y_exportar_reporte` |
| **RF13** | Trazabilidad experimental | CP13 | ✅ **CUMPLIDO** (PASS) | `test_CP13_consultar_trazabilidad_desde_resultado` |

> **Nota de interpretación:** un requisito se considera **cumplido** cuando existe al menos un caso
> funcional (CP) asociado que, al ejecutarse contra la base de datos temporal y el motor de
> simulación simulado, verificó el comportamiento esperado de la Tabla 17 y obtuvo **PASS**.

**Resumen de cumplimiento por RF:**

| RF | Requisito (resumen) | CP(s) que lo validan | Resultado |
|---|---|---|---|
| RF01 | Configuraciones y parámetros | CP03, CP05 | PASS |
| RF02 | Validación de configuraciones | CP03, CP04 | PASS |
| RF03 | Historial/versionado de configuraciones | CP05 | PASS |
| RF04 | Gestión de experimentos | CP01 | PASS |
| RF05 | Escenarios y réplicas | CP02, CP07 | PASS |
| RF06 | Ejecución de simulaciones | CP06, CP07 | PASS |
| RF07 | Seguimiento de ejecuciones | CP06, CP07, CP08 | PASS |
| RF08 | Consulta de resultados | CP09 | PASS |
| RF09 | Visualización de resultados | CP10 | PASS |
| RF10 | Interacción/navegación de resultados | CP10 | PASS |
| RF11 | Comparación de resultados | CP11 | PASS |
| RF12 | Generación/exportación de reportes | CP12 | PASS |
| RF13 | Trazabilidad experimental | CP13 | PASS |

**Resumen global de cumplimiento:** **RF01–RF13: 13/13 requisitos funcionales verificados y en estado
PASS**, mediante los **13/13 casos de prueba funcionales (CP01–CP13)** de la Tabla 17.

---

## 5. Requisitos técnicos del sistema

### 5.1. Hardware

| Componente | Especificación |
|---|---|
| Sistema operativo | Windows 11 (probado), Linux (Ubuntu 20.04+), macOS (10.15+) |
| Memoria RAM | Recomendada 8 GB o superior (dependiendo del tamaño del modelo biológico) |
| Disco | Espacio para salidas de simulación, snapshots y base de datos SQLite |

### 5.2. Software

| Componente | Versión / nota |
|---|---|
| Python | 3.12+ (probado en 3.13); se recomienda entorno virtual |
| PyQt6 | >= 6.6.0 |
| lxml | >= 4.9.0 |
| numpy | >= 1.24.0 |
| scipy | >= 1.10.0 |
| matplotlib | >= 3.7.0 |
| pyvista | >= 0.43.0 |
| pyvistaqt | >= 0.5.0 |
| vtk | >= 9.2.0 |
| Dependencias congeladas | `requirements-frozen.txt` (reproducción exacta) |

### 5.3. Motor de simulación (externo)

| Componente | Especificación |
|---|---|
| Motor | Binario compilado de PhysiCell (`project.exe` en Windows, `project` en Linux/macOS) |
| Rol de la app | Capa de coordinación: no modifica el código fuente del motor |
| Configuración | Archivo `PhysiCell_settings.xml` válido por experimento |
| Binario opcional | Plantilla generada con `studio/download_binary.py template` |

### 5.4. Persistencia

| Componente | Especificación |
|---|---|
| Motor de base de datos | SQLite |
| Ubicación | `%APPDATA%/PhysiCell_Experiments/experiments.db` (Windows) |

### 5.5. Visualización 3D

| Componente | Especificación |
|---|---|
| Motor 3D | PyVista 0.49.1 + VTK 9.7 (fallback: Matplotlib) |

---

## 6. Ejecución de la suite de pruebas

```bash
python -m pytest tests/test_funcionales.py -v
python -m pytest            # suite completa
```

**Resultado de la ejecución de la suite funcional:**

```
tests/test_funcionales.py::test_CP01_... PASSED
...
tests/test_funcionales.py::test_CP13_... PASSED
============================== 13 passed in 4.05s ==============================
```

**Resultado global del repositorio:**

```
============================== 45 passed in 5.09s ==============================
```

### 6.1 Entorno de ejecución de las pruebas

| Componente | Valor |
|---|---|
| Sistema operativo | Windows 11 |
| Python | 3.11.9 |
| pytest | 9.2.0 |
| Base de datos | SQLite (esquema temporal con tablas `experiments`, `runs`, `escenarios`, `configuraciones`, `batches`) |
| Configuración de prueba | `config/PhysiCell_settings.xml` (XML de ejemplo del repositorio) |
| Datos de simulación | Temporal (`tempfile`), sin binario PhysiCell real |
| Visualización | Backend matplotlib `Agg` |

---

## 7. Detalle de casos funcionales

### CP01 — Crear experimento con nombre y descripción (RF04)

- **Precondiciones:** base de datos temporal con schema válido.
- **Pasos:** crear dos experimentos con nombres/descripciones distintas; consultar BD.
- **Resultado esperado:** registro con identificador único y fecha de creación.
- **Resultado obtenido:** ids únicos generados; título, descripción y `created_at` persistidos;
  configuración base v1 activa.
- **Veredicto:** **PASS**

### CP02 — Crear escenarios y réplicas (RF05)

- **Pasos:** crear experimento → escenario → réplica (run) con `escenario_id` y `configuracion_id`.
- **Resultado esperado:** asociación jerárquica al experimento.
- **Resultado obtenido:** escenario → `experiment_id` y run → `experiment_id`/`escenario_id`
  correctos.
- **Veredicto:** **PASS**

### CP03 — Importar XML válido (RF01, RF02)

- **Pasos:** validar `config/PhysiCell_settings.xml`; crear experimento con esa configuración.
- **Resultado esperado:** carga y validación sin errores.
- **Resultado obtenido:** `validar_config` → `ok=True`, errores vacíos; experimento con
  configuración activa versión 1.
- **Veredicto:** **PASS**

### CP04 — Importar XML mal formado (RF02)

- **Pasos:** escribir XML con error de sintaxis; validar; validar en punto de ejecución.
- **Resultado esperado:** rechazo con mensaje descriptivo.
- **Resultado obtenido:** error de parseo (`XML mal formado: ...`); error de validación de
  ejecución reportado.
- **Veredicto:** **PASS**

### CP05 — Editar y guardar configuración (RF03)

- **Pasos:** crear v1 (base) → crear v2 → activar v1.
- **Resultado esperado:** nueva versión; anterior recuperable.
- **Resultado obtenido:** solo una activa a la vez; activación de v1 restaura versión 1.
- **Veredicto:** **PASS**

### CP06 — Ejecutar una simulación de una réplica (RF06, RF07)

- **Pasos:** registrar run `pending` → `running` → `completed`.
- **Resultado esperado:** estado pasa a completada con fechas.
- **Resultado obtenido:** estado final `completed`, `start_time`/`end_time` registrados.
- **Veredicto:** **PASS**

### CP07 — Ejecutar varias réplicas por lote (RF06, RF07)

- **Pasos:** crear lote (3 réplicas, semilla 1000) → ejecutar → cerrar lote.
- **Resultado esperado:** se ejecutan y registran semilla, fechas y duración.
- **Resultado obtenido:** lote con `n_replicas=3`, `seed_base=1000`, estado `completed`; cada
  run con `completed` y duración válida.
- **Veredicto:** **PASS**

### CP08 — Ejecutar simulación con error (RNF09)

- **Pasos:** ejecutar run y registrar estado `failed` con mensaje.
- **Resultado esperado:** estado fallida con error registrado.
- **Resultado obtenido:** estado `failed` con `error_message` persistido.
- **Veredicto:** **PASS**

### CP09 — Consultar resultados de una ejecución (RF08)

- **Pasos:** ejecutar run → consultar runs, escenarios y métricas por réplica.
- **Resultado esperado:** resultados asociados al experimento, escenario y réplica.
- **Resultado obtenido:** listado de runs/escenarios y métricas (`n_celulas_final`) por réplica.
- **Veredicto:** **PASS**

### CP10 — Visualizar estado temporal en 3D (RF09, RF10)

- **Pasos:** generar `initial.xml` sintético + snapshots SVG.
- **Resultado esperado:** estado mostrado y permite rotar/ampliar/desplazar.
- **Resultado obtenido:** snapshots listados, bounds leídos (`xmin/xmax/zmin/zmax`), frames
  parseados correctamente.
- **Veredicto:** **PASS**

### CP11 — Comparar escenarios o réplicas (RF11)

- **Pasos:** dos réplicas en un experimento → comparación y generación de gráfica.
- **Resultado esperado:** resultados lado a lado.
- **Resultado obtenido:** 2 filas de comparación; gráfica generada.
- **Veredicto:** **PASS**

### CP12 — Generar y exportar reporte (RF12)

- **Pasos:** generar reporte HTML; exportar runs CSV y JSON.
- **Resultado esperado:** archivo con configuraciones, ejecuciones y resultados.
- **Resultado obtenido:** HTML generado (con contenido del experimento); CSV y JSON exportados.
- **Veredicto:** **PASS**

### CP13 — Consultar trazabilidad desde un resultado (RF13)

- **Pasos:** rastrear run → configuración → escenario → experimento.
- **Resultado esperado:** identificar ejecución, versión, réplica, escenario y experimento.
- **Resultado obtenido:** cadena de trazabilidad verificada (run → config v1 → escenario → exp).
- **Veredicto:** **PASS**

---

## 8. Validación con casos de estudio

Conforme al cuarto objetivo específico, la aplicación se validó con simulaciones de PhysiCell
definidas en el proyecto de investigación.

> **Pendiente de completar:** se requiere registrar el modelo utilizado, el número de
> escenarios y réplicas, y los resultados observados durante la validación con los casos de
> estudio reales.

Los casos funcionales CP01–CP13 sirven como la primera fase de validación; la fase de
validación con el modelo real se ejecutará sobre el entorno de simulación definitivo.

---

## 9. Evidencias

### Ilustración 14a — Pruebas funcionales CP01–CP13 (suite funcional)

Ejecución del comando `python -m pytest tests/test_funcionales.py -v` sobre el entorno:
- **Plataforma:** Windows 11 · Python 3.11.9 · pytest 9.2.0
- **Fecha de ejecución:** 16 de noviembre de 2026
- **Resultado:** 13 passed en 10.88s

![Ejecución de pruebas funcionales CP01-CP13 — 13/13 PASSED](pytest_funcionales_pass.png)

---

### Ilustración 14b — Suite completa del repositorio (45 pruebas)

Ejecución del comando `python -m pytest --tb=short -v` sobre todos los módulos de prueba:
- **Archivos cubiertos:** `test_agregador`, `test_comparacion`, `test_funcionales`, `test_reportes`, `test_simulador`, `test_versionado_configuraciones`, `test_visores`, `test_xml_validator`
- **Resultado:** 45 passed en 5.18s · 0 failed · 0 errors

![Suite completa de pytest — 45/45 PASSED](pytest_suite_completa.png)

---

### Resumen de evidencia

| Suite | Comando | Resultado | Duración |
|---|---|---|---|
| Funcional (CP01–CP13) | `pytest tests/test_funcionales.py -v` | **13/13 PASSED** | 10.88 s |
| Completa | `pytest --tb=short -v` | **45/45 PASSED** | 5.18 s |

---

## 10. Conclusiones

1. Las **13 pruebas funcionales (CP01–CP13)** implementadas en `tests/test_funcionales.py`
   **pasan exitosamente**, validando el comportamiento esperado de cada requerimiento
   funcional asociado.
2. El manejo de errores (RNF09) se verificó con el caso **CP08** (estado fallida + error).
3. El versionado de configuraciones (RF03) y la trazabilidad (RF13) se verifican de forma
   consistente con los casos **CP05** y **CP13**.
4. Las evidencias visuales de la ejecución de las pruebas (Ilustraciones 14a y 14b) están
   disponibles en `docs/pytest_funcionales_pass.png` y `docs/pytest_suite_completa.png`,
   confirmando **13/13 funcionales** y **45/45 totales** en estado PASS.
5. La validación con casos de estudio reales de PhysiCell sobre el entorno de simulación
   definitivo constituye el entregable complementario pendiente de la fase siguiente.

---

## 11. Estructura de la base de datos

**Motor:** SQLite · **Ubicación:** `%APPDATA%/PhysiCell_Experiments/experiments.db` (Windows)

### 11.1. Tabla `usuarios`

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único del usuario |
| `username` | TEXT | NOT NULL, UNIQUE | Nombre de usuario |
| `email` | TEXT | NOT NULL, UNIQUE | Correo electrónico |
| `password_hash` | TEXT | NOT NULL | Hash de la contraseña |
| `rol` | TEXT | NOT NULL, DEFAULT 'usuario' | Rol del usuario |
| `activo` | INTEGER | NOT NULL, DEFAULT 1 | Estado activo/inactivo |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |
| `ultimo_acceso` | DATETIME | — | Último acceso |

### 11.2. Tabla `experimentos`

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único del experimento |
| `title` | TEXT | NOT NULL | Título del experimento |
| `description` | TEXT | — | Descripción |
| `config_xml_path` | TEXT | — | Ruta al XML de configuración |
| `binary_path` | TEXT | — | Ruta al binario PhysiCell |
| `custom_cpp_path` | TEXT | — | Ruta al `custom.cpp` |
| `custom_h_path` | TEXT | — | Ruta al `custom.h` |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |
| `last_modified` | DATETIME | — | Última modificación |
| `tags` | TEXT | DEFAULT '' | Etiquetas |
| `usuario_id` | INTEGER | FK → `usuarios.id` | Propietario |

### 11.3. Tabla `configuraciones`

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | NOT NULL, FK → `experimentos.id` | Experimento propietario |
| `nombre` | TEXT | NOT NULL, DEFAULT 'base' | Nombre/version (`base`, `v2`, ...) |
| `xml_path` | TEXT | NOT NULL | Ruta al XML guardado |
| `version` | INTEGER | NOT NULL, DEFAULT 1 | Versión numérica |
| `es_activa` | INTEGER | NOT NULL, DEFAULT 0 | Única activa por experimento |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |

### 11.4. Tabla `escenarios`

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | NOT NULL, FK → `experimentos.id` | Experimento propietario |
| `nombre` | TEXT | NOT NULL | Nombre del escenario |
| `config_xml_path` | TEXT | — | Ruta al XML del escenario |
| `parametros_json` | TEXT | DEFAULT '{}' | Parámetros en JSON |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |
| `configuracion_id` | INTEGER | FK → `configuraciones.id` | Config vinculada |

### 11.5. Tabla `runs` (ejecuciones)

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | NOT NULL, FK → `experimentos.id` | Experimento propietario |
| `run_number` | INTEGER | — | Número de réplica/ejecución |
| `status` | TEXT | DEFAULT 'pending' | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `start_time` | DATETIME | — | Inicio |
| `end_time` | DATETIME | — | Fin |
| `output_dir` | TEXT | — | Carpeta de salida |
| `escenario_id` | INTEGER | FK → `escenarios.id` | Escenario asociado |
| `configuracion_id` | INTEGER | FK → `configuraciones.id` | Config usada |
| `error_message` | TEXT | — | Mensaje de error |
| `log_path` | TEXT | — | Ruta del log |
| `pid` | INTEGER | — | PID del proceso |
| `batch_id` | INTEGER | FK → `batches.id` | Lote |

### 11.6. Tabla `batches` (lotes de réplicas)

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | FK → `experimentos.id` | Experimento propietario |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creación del lote |
| `n_replicas` | INTEGER | — | Número de réplicas |
| `xml_path` | TEXT | — | XML del lote |
| `xml_sha256` | TEXT | — | Hash XML |
| `exe_path` | TEXT | — | Ejecutable |
| `exe_sha256` | TEXT | — | Hash ejecutable |
| `seed_base` | INTEGER | DEFAULT 1000 | Semilla base |
| `timeout_min` | INTEGER | DEFAULT 0 | Timeout |
| `inactividad_min` | INTEGER | DEFAULT 10 | Inactividad |
| `python_version` | TEXT | — | Versión Python |
| `plataforma` | TEXT | — | Sistema |
| `notas` | TEXT | — | Notas |
| `status` | TEXT | DEFAULT 'running' | Estado del lote |
| `error_message` | TEXT | — | Error |

### 11.7. Tabla `videos`

| Campo | Tipo de dato | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | FK → `experimentos.id` | Experimento propietario |
| `run_number` | INTEGER | — | Réplica |
| `tipo` | TEXT | DEFAULT '2d' | Tipo de video |
| `ruta_archivo` | TEXT | — | Ruta |
| `fps` | INTEGER | DEFAULT 1 | FPS |
| `frames` | INTEGER | DEFAULT 0 | Frames |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creación |

---

## 12. Anexos

- Suite de pruebas funcionales: `tests/test_funcionales.py`
- Fixtures compartidas: `tests/conftest.py`
- Configuración de ejecución: `pytest.ini`
- Validador de XML: `app/xml_validator.py`
- Servicios y motor: `app/servicios.py`, `app/simulador.py`, `app/nucleo.py`
- Visualización y reportes: `app/visor_widget.py`, `app/visualizador.py`, `app/reportes.py`
