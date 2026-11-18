# Manual Técnico — PhysiCell Lab

**Aplicación:** PhysiCell Lab — Gestor de experimentos PhysiCell  
**Versión del documento:** 1.0  
**Fecha:** Noviembre 2026  
**Alcance:** Referencia técnica completa para desarrolladores y mantenedores del sistema

---

## Tabla de contenidos

1. [Descripción general del sistema](#1-descripción-general-del-sistema)
2. [Stack tecnológico](#2-stack-tecnológico)
3. [Requisitos técnicos del sistema](#3-requisitos-técnicos-del-sistema)
4. [Arquitectura de la aplicación](#4-arquitectura-de-la-aplicación)
5. [Estructura del repositorio](#5-estructura-del-repositorio)
6. [Modelo de datos y base de datos](#6-modelo-de-datos-y-base-de-datos)
7. [Módulos principales](#7-módulos-principales)
8. [Interfaz de usuario (UI)](#8-interfaz-de-usuario-ui)
9. [Motor de ejecución PhysiCell](#9-motor-de-ejecución-physicell)
10. [Validación de configuraciones XML](#10-validación-de-configuraciones-xml)
11. [Visualización 2D y 3D](#11-visualización-2d-y-3d)
12. [Sistema de reportes y exportación](#12-sistema-de-reportes-y-exportación)
13. [Análisis estadístico y comparación](#13-análisis-estadístico-y-comparación)
14. [Sistema de temas visuales](#14-sistema-de-temas-visuales)
15. [Empaquetado y distribución](#15-empaquetado-y-distribución)
16. [Suite de pruebas](#16-suite-de-pruebas)
17. [Integración continua (CI)](#17-integración-continua-ci)
18. [Consideraciones de diseño y decisiones arquitectónicas](#18-consideraciones-de-diseño-y-decisiones-arquitectónicas)
19. [Guía de extensión y contribución](#19-guía-de-extensión-y-contribución)

---

## 1. Descripción general del sistema

**PhysiCell Lab** es una aplicación de escritorio multiplataforma (Windows, Linux, macOS) construida con Python y PyQt6 que actúa como capa de coordinación externa para el motor de simulación celular PhysiCell.

### 1.1 Responsabilidades del sistema

- **Gestión de experimentos:** crear, versionar, editar y eliminar experimentos con metadatos y configuraciones XML.
- **Generación de réplicas:** producir N copias del XML base con `random_seed` y carpetas de salida aisladas por réplica.
- **Ejecución controlada:** lanzar el binario externo `project.exe` como proceso hijo, con trazabilidad de estado, PID, tiempos y log.
- **Visualización:** visor 2D (frames SVG) y visor 3D (mallas VTK con PyVista).
- **Análisis:** métricas por réplica, pruebas estadísticas y comparación de escenarios.
- **Reportes:** generación de informes HTML/PDF con trazabilidad completa.
- **Persistencia:** base de datos SQLite local con historial completo de experimentos, configuraciones, ejecuciones y lotes.

### 1.2 Lo que el sistema NO hace

- No modifica ni recompila el motor PhysiCell.
- No distribuye ni empaqueta el binario de PhysiCell.
- No envía datos a servidores externos.
- No valida el modelo biológico de `custom.cpp` (solo gestiona la capa de orquestación).

---

## 2. Stack tecnológico

| Componente | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.12+ (probado en 3.13) |
| Interfaz gráfica | PyQt6 | >= 6.6.0 |
| Parseo XML | lxml | >= 4.9.0 |
| Álgebra numérica | numpy | >= 1.24.0 |
| Estadística | scipy | >= 1.10.0 |
| Visualización 2D | matplotlib | >= 3.7.0 |
| Visualización 3D | PyVista + VTK | >= 0.43.0 / >= 9.2.0 |
| Integración PyQt6-PyVista | pyvistaqt | >= 0.5.0 |
| Persistencia | SQLite3 (stdlib) | — |
| Empaquetado | PyInstaller | >= 5.0 |
| Pruebas | pytest | >= 7.0 |
| CI | GitHub Actions | — |

---

## 3. Requisitos técnicos del sistema

### 3.1 Hardware

| Componente | Especificación |
|---|---|
| Sistema operativo | Windows 11 (probado), Linux Ubuntu 20.04+, macOS 10.15+ |
| Memoria RAM | 8 GB o superior (recomendado) |
| Disco | Espacio para salidas de simulación, snapshots y base de datos SQLite |

### 3.2 Dependencias Python (versiones congeladas)

Ver archivo [`requirements-frozen.txt`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/requirements-frozen.txt) para reproducción exacta.

### 3.3 Motor de simulación externo

| Componente | Especificación |
|---|---|
| Binario | `project.exe` (Windows) / `project` (Linux/macOS) compilado de PhysiCell |
| Formato de configuración | `PhysiCell_settings.xml` estructurado según el estándar de PhysiCell |
| Rol en la app | Proceso hijo externo; la app solo lanza el binario y gestiona salidas |

### 3.4 Persistencia

| Componente | Especificación |
|---|---|
| Motor | SQLite (módulo `sqlite3` de la stdlib de Python) |
| Ubicación (Windows) | `%APPDATA%\PhysiCell_Experiments\experiments.db` |
| Ubicación (Linux/macOS) | `~/.local/share/PhysiCell_Experiments/experiments.db` |

---

## 4. Arquitectura de la aplicación

La aplicación sigue una arquitectura en capas con separación clara entre persistencia, lógica de negocio e interfaz de usuario:

```
┌─────────────────────────────────────────────────────────┐
│                   Capa de Presentación (UI)              │
│  lab_window.py · paginas/ · theme_lab.py · themes.py    │
└───────────────────────┬─────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────┐
│                   Capa de Servicios                       │
│               servicios.py (orquestación)                │
└──┬──────────────────────────────────────────────────┬───┘
   │                                                  │
┌──▼──────────────┐                        ┌──────────▼───────────┐
│  Lógica de      │                        │  Motor de simulación  │
│  negocio        │                        │  motor_physicell.py   │
│  nucleo.py      │                        │  simulador.py         │
│  estadistica.py │                        │  xml_validator.py     │
│  comparacion.py │                        │  config_manager.py    │
│  reportes.py    │                        └──────────────────────┘
│  agregador.py   │
└──┬──────────────┘
   │
┌──▼──────────────────────────────────────────────────────┐
│                   Capa de Persistencia                    │
│            SQLite (nucleo.py · sqlite3 stdlib)            │
└─────────────────────────────────────────────────────────┘
```

### 4.1 Principio de no modificación del motor

PhysiCell Lab respeta el principio de **no-intrusión** en el motor: el binario `project.exe` se trata como una caja negra. La única interacción con el motor es:
1. Generar una copia del XML de configuración por réplica (modificando solo `random_seed` y `<save><folder>`).
2. Lanzar el proceso con `subprocess`.
3. Leer los archivos de salida generados en la carpeta de salida.

---

## 5. Estructura del repositorio

```
physicell_manager-main/
├── run_app.py                  # Punto de entrada principal
├── requirements.txt            # Dependencias mínimas
├── requirements-frozen.txt     # Dependencias congeladas (reproducción exacta)
├── build.spec                  # Configuración PyInstaller
├── pytest.ini                  # Configuración pytest
├── output.log                  # Log de inicio de la aplicación
│
├── app/                        # Paquete principal de la aplicación
│   ├── __init__.py
│   ├── nucleo.py               # Persistencia SQLite, usuarios, worker de réplicas
│   ├── simulador.py            # Escenarios, réplicas, aislamiento de carpetas
│   ├── motor_physicell.py      # Ejecución cancelable del binario project.exe
│   ├── xml_validator.py        # Validación estructural flexible de XML
│   ├── config_manager.py       # Lectura/escritura de archivos XML
│   ├── servicios.py            # Orquestación de casos de uso (capa de servicios)
│   ├── estadistica.py          # Métricas por réplica y pruebas t de Student
│   ├── comparacion.py          # Vistas paralelas y gráfica comparativa
│   ├── reportes.py             # Informes HTML/PDF con trazabilidad
│   ├── agregador.py            # Consolidación de frames/células a CSV
│   ├── visualizador.py         # Visor 2D básico
│   ├── visor_widget.py         # Visor 2D/3D integrado (widget PyQt6)
│   ├── visor3d_vtk.py          # Visualización tumoral 3D con PyVista/VTK
│   ├── animacion.py            # Animaciones de UI
│   ├── exportacion.py          # Exportación a video 2D/3D
│   ├── lab_window.py           # Ventana principal y navegación por secciones
│   ├── theme_lab.py            # Definición de temas visuales (oscuro/claro)
│   ├── themes.py               # Utilidades de temas
│   ├── config_manager.py       # Importar/leer/guardar XML
│   ├── paginas/                # Páginas de UI, una por sección
│   │   ├── __init__.py
│   │   ├── base.py             # Clases base y componentes reutilizables de UI
│   │   ├── login.py            # Pantalla de autenticación
│   │   ├── experimentos.py     # Lista de experimentos
│   │   ├── detalle.py          # Detalle de experimento (pestañas)
│   │   ├── configuraciones.py  # Gestión de configuraciones XML
│   │   ├── ejecuciones.py      # Vista global de ejecuciones
│   │   ├── visualizacion_global.py # Vista global de visualización
│   │   ├── resultados_global.py    # Vista global de resultados
│   │   ├── comparacion_global.py  # Vista global de comparación
│   │   ├── reportes.py         # Vista de reportes
│   │   ├── resumen.py          # Vista de resumen general
│   │   ├── preferencias.py     # Pantalla de ajustes
│   │   └── dialogo_run.py      # Diálogo de detalle de réplica
│   ├── assets/                 # Recursos gráficos
│   └── legacy/                 # Código legacy archivado
│       └── interfaz_notion.py
│
├── config/                     # Plantillas XML de ejemplo
├── studio/                     # Módulos del Studio PhysiCell (referencia)
├── custom_modules/             # Módulos personalizados del motor
│
├── tests/                      # Suite de pruebas
│   ├── conftest.py             # Fixtures compartidas (portables)
│   ├── test_xml_validator.py
│   ├── test_simulador.py
│   ├── test_agregador.py
│   ├── test_comparacion.py
│   ├── test_reportes.py
│   ├── test_visores.py
│   ├── test_versionado_configuraciones.py
│   ├── test_regresion.py       # Suite de regresión (ejecutable directamente)
│   └── test_funcionales.py     # Pruebas funcionales CP01–CP13
│
├── docs/                       # Documentación del proyecto
│   ├── manual_de_usuario.md
│   ├── manual_tecnico.md
│   └── informe_pruebas_funcionales.md
│
└── .github/
    └── workflows/
        └── ci.yml              # Flujo CI: Ubuntu + Windows, Python 3.12/3.13
```

---

## 6. Modelo de datos y base de datos

### 6.1 Diagrama de relaciones (ERD simplificado)

```
usuarios (1) ──────────────── (N) experimentos
experimentos (1) ──────────── (N) configuraciones
experimentos (1) ──────────── (N) escenarios
experimentos (1) ──────────── (N) runs
experimentos (1) ──────────── (N) batches
experimentos (1) ──────────── (N) videos
escenarios (1) ─────────────── (N) runs (via escenario_id)
configuraciones (1) ──────── (N) runs (via configuracion_id)
configuraciones (1) ──────── (N) escenarios (via configuracion_id)
batches (1) ──────────────── (N) runs (via batch_id)
```

### 6.2 Tablas

#### Tabla `usuarios`

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único del usuario |
| `username` | TEXT | NOT NULL, UNIQUE | Nombre de usuario |
| `email` | TEXT | NOT NULL, UNIQUE | Correo electrónico |
| `password_hash` | TEXT | NOT NULL | Hash SHA-256 de la contraseña |
| `rol` | TEXT | NOT NULL, DEFAULT 'usuario' | Rol del usuario |
| `activo` | INTEGER | NOT NULL, DEFAULT 1 | Estado activo (1) / inactivo (0) |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |
| `ultimo_acceso` | DATETIME | — | Último acceso registrado |

#### Tabla `experimentos`

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `title` | TEXT | NOT NULL | Título del experimento |
| `description` | TEXT | — | Descripción libre |
| `config_xml_path` | TEXT | — | Ruta al XML activo |
| `binary_path` | TEXT | — | Ruta al binario PhysiCell |
| `custom_cpp_path` | TEXT | — | Ruta a `custom.cpp` (opcional) |
| `custom_h_path` | TEXT | — | Ruta a `custom.h` (opcional) |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |
| `last_modified` | DATETIME | — | Última modificación |
| `tags` | TEXT | DEFAULT '' | Etiquetas separadas por comas |
| `usuario_id` | INTEGER | FK → `usuarios.id` | Propietario del experimento |

#### Tabla `configuraciones`

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | NOT NULL, FK → `experimentos.id` | Experimento propietario |
| `nombre` | TEXT | NOT NULL, DEFAULT 'base' | Nombre de la versión (`base`, `v2`, ...) |
| `xml_path` | TEXT | NOT NULL | Ruta al XML guardado de esta versión |
| `version` | INTEGER | NOT NULL, DEFAULT 1 | Número de versión |
| `es_activa` | INTEGER | NOT NULL, DEFAULT 0 | 1 si es la versión activa (única) |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |

#### Tabla `escenarios`

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | NOT NULL, FK → `experimentos.id` | Experimento propietario |
| `nombre` | TEXT | NOT NULL | Nombre del escenario/variante |
| `config_xml_path` | TEXT | — | Ruta al XML del escenario |
| `parametros_json` | TEXT | DEFAULT '{}' | Parámetros adicionales en JSON |
| `created_at` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |
| `configuracion_id` | INTEGER | FK → `configuraciones.id` | Config vinculada |

#### Tabla `runs` (ejecuciones / réplicas)

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | NOT NULL, FK → `experimentos.id` | Experimento propietario |
| `run_number` | INTEGER | — | Número de réplica dentro del experimento |
| `status` | TEXT | DEFAULT 'pending' | `pending`, `running`, `completed`, `failed`, `cancelled` |
| `start_time` | DATETIME | — | Marca de tiempo de inicio |
| `end_time` | DATETIME | — | Marca de tiempo de fin |
| `output_dir` | TEXT | — | Carpeta de salida de la réplica |
| `escenario_id` | INTEGER | FK → `escenarios.id` | Escenario asociado |
| `configuracion_id` | INTEGER | FK → `configuraciones.id` | Configuración usada |
| `error_message` | TEXT | — | Mensaje de error si `status = 'failed'` |
| `log_path` | TEXT | — | Ruta al log del proceso |
| `pid` | INTEGER | — | PID del proceso hijo lanzado |
| `batch_id` | INTEGER | FK → `batches.id` | Lote al que pertenece |

#### Tabla `batches` (lotes de ejecuciones)

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | FK → `experimentos.id` | Experimento propietario |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación del lote |
| `n_replicas` | INTEGER | — | Número de réplicas del lote |
| `xml_path` | TEXT | — | XML usado en el lote |
| `xml_sha256` | TEXT | — | Hash SHA-256 del XML para trazabilidad |
| `exe_path` | TEXT | — | Ruta al ejecutable usado |
| `exe_sha256` | TEXT | — | Hash SHA-256 del ejecutable para trazabilidad |
| `seed_base` | INTEGER | DEFAULT 1000 | Semilla base (réplica i usa `seed_base + i`) |
| `timeout_min` | INTEGER | DEFAULT 0 | Timeout máximo en minutos (0 = sin límite) |
| `inactividad_min` | INTEGER | DEFAULT 10 | Minutos sin escritura antes de cancelar |
| `python_version` | TEXT | — | Versión Python del entorno de ejecución |
| `plataforma` | TEXT | — | Sistema operativo y arquitectura |
| `notas` | TEXT | — | Notas libres del lote |
| `status` | TEXT | DEFAULT 'running' | Estado del lote (`running`, `completed`, `failed`) |
| `error_message` | TEXT | — | Error del lote (si aplica) |

#### Tabla `videos`

| Campo | Tipo | Restricción | Descripción |
|---|---|---|---|
| `id` | INTEGER | PRIMARY KEY | Identificador único |
| `experiment_id` | INTEGER | FK → `experimentos.id` | Experimento propietario |
| `run_number` | INTEGER | — | Réplica de origen |
| `tipo` | TEXT | DEFAULT '2d' | Tipo de video (`2d`, `3d`) |
| `ruta_archivo` | TEXT | — | Ruta al archivo de video generado |
| `fps` | INTEGER | DEFAULT 1 | Fotogramas por segundo |
| `frames` | INTEGER | DEFAULT 0 | Número de frames exportados |
| `creado_en` | DATETIME | DEFAULT CURRENT_TIMESTAMP | Fecha de creación |

---

## 7. Módulos principales

### 7.1 `nucleo.py` — Persistencia y autenticación

**Responsabilidades:**
- Creación y migración del esquema SQLite.
- CRUD de usuarios, experimentos, configuraciones, escenarios, runs, batches y videos.
- Clase `AuthService`: registro y login de usuarios con hash de contraseña.
- Funciones `cargar_preferencias()` / `guardar_preferencias()` para configuración persistente en JSON.

**Clases y funciones clave:**

| Símbolo | Descripción |
|---|---|
| `crear_tablas(conn)` | Inicializa el esquema completo de la BD |
| `AuthService.login(user, pw)` | Verifica credenciales y devuelve `{ok, usuario}` |
| `AuthService.registrar(user, email, pw)` | Registra nuevo usuario con hash de contraseña |
| `cargar_preferencias()` | Carga preferencias desde JSON en `%APPDATA%` |
| `guardar_preferencias(prefs)` | Persiste preferencias en JSON |

### 7.2 `simulador.py` — Escenarios, réplicas y lotes

**Responsabilidades:**
- Crear escenarios (variantes XML) asociados a un experimento.
- Crear réplicas individuales con `random_seed` asignada y carpeta de salida aislada.
- Crear lotes (`batches`) de N réplicas con trazabilidad completa (hashes SHA-256 de XML y ejecutable).
- Funciones de consulta: `listar_runs()`, `listar_escenarios()`, `tanda_de_estados()`.

**Lógica de semillas y carpetas:**
```python
# Para cada réplica i dentro de un lote:
random_seed = seed_base + i          # ej: 1000, 1001, 1002, ...
output_dir = f"exp_{eid}/replica_{i}/output"
```

El XML generado por réplica es una copia del XML base con:
- `<random_seed>` reemplazado por la semilla de esa réplica.
- `<save><folder>` reemplazado por la carpeta de salida de esa réplica.

### 7.3 `motor_physicell.py` — Ejecución del binario

**Responsabilidades:**
- Lanzar `project.exe` como proceso hijo con `subprocess.Popen`.
- Monitorear el proceso: detectar inactividad (sin escritura en disco durante N minutos).
- Cancelar el proceso de forma limpia (`terminate()` + `kill()` si no responde).
- Registrar PID, tiempos, log y estado en la BD.
- Funciones de diagnóstico: `autodiagnostico()`, `verificar_binario()`, `intervalos_guardado()`.

**Estados del proceso:**

```
pending → running → completed
                 → failed
                 → cancelled
```

**Criterio de inactividad:** si el directorio de salida no recibe archivos nuevos durante `inactividad_min` minutos (por defecto 10), la réplica se cancela automáticamente y se registra el motivo.

### 7.4 `xml_validator.py` — Validación de XML

**Responsabilidades:**
- Validar la estructura y contenido de archivos `PhysiCell_settings.xml`.
- Detectar errores de sintaxis (XML mal formado).
- Detectar inconsistencias estructurales flexibles (etiquetas faltantes, valores inválidos).
- Generar avisos (*warnings*) para configuraciones potencialmente problemáticas (ej: sin intervalos de guardado).

**Funciones principales:**

| Función | Descripción |
|---|---|
| `validar_config(path)` | Valida un XML por ruta de archivo; devuelve `{ok, errores, warnings}` |
| `validar_texto(texto_xml)` | Valida XML desde string (para el editor en tiempo real) |

### 7.5 `config_manager.py` — Lectura y escritura de XML

**Responsabilidades:**
- Leer el contenido completo de un XML como texto (`leer_texto(path)`).
- Guardar contenido de texto en un XML (`guardar_texto(path, texto)`).
- Importar y parsear XML para extracción de parámetros.

### 7.6 `servicios.py` — Capa de servicios (orquestación)

**Responsabilidades:**
- Punto de entrada único para las operaciones de alto nivel desde la UI.
- Orquesta llamadas a `nucleo.py`, `simulador.py`, `motor_physicell.py` y `xml_validator.py`.

**Servicios clave:**

| Función | Descripción |
|---|---|
| `obtener_experimento_completo(db, eid)` | Devuelve experimento + escenarios + configuraciones + runs |
| `actualizar_rutas_experimento(db, eid, ...)` | Actualiza XML, binario y archivos custom del experimento |
| `registrar_nueva_configuracion(db, eid, ...)` | Registra nueva versión de configuración con copia de respaldo |
| `activar_configuracion_servicio(db, cfg_id)` | Activa una versión de configuración (desactiva las demás) |
| `AuthService` | Clase heredada de `nucleo.py` para autenticación |

### 7.7 `estadistica.py` — Análisis estadístico

**Responsabilidades:**
- Calcular métricas por réplica (número de células finales, tiempo de simulación).
- Ejecutar prueba t de Student entre dos experimentos sobre métricas de réplicas.
- Exportar resultados estadísticos a CSV.

### 7.8 `comparacion.py` — Comparación de réplicas

**Responsabilidades:**
- Generar vistas paralelas sincronizadas de dos réplicas.
- Producir gráficas comparativas del número de células finales por réplica.

### 7.9 `reportes.py` — Informes

**Responsabilidades:**
- Generar informes HTML con trazabilidad completa del experimento.
- Generar informes PDF a partir del HTML.
- Exportar runs a CSV y JSON.

**Contenido del informe:**
- Metadatos del experimento (título, descripción, tags, fechas).
- Configuración activa y versiones registradas.
- Tabla de réplicas con estados, tiempos y errores.
- Métricas de resultados.
- Trazabilidad: `run → configuración_versión → escenario → experimento`.

### 7.10 `agregador.py` — Consolidación de datos

**Responsabilidades:**
- Leer los archivos de salida de PhysiCell (CSV por frame).
- Consolidar múltiples frames de una réplica en un único DataFrame.
- Exportar datos consolidados a CSV.

### 7.11 `exportacion.py` — Exportación de video

**Responsabilidades:**
- Generar video 2D a partir de frames SVG (requiere FFmpeg o similar en el sistema).
- Generar video 3D a partir de snapshots VTK con PyVista.

---

## 8. Interfaz de usuario (UI)

### 8.1 Punto de entrada

[`run_app.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/run_app.py): inicializa la aplicación Qt (`QApplication`), aplica el tema, crea la ventana principal (`LabWindow`) y la muestra.

### 8.2 Ventana principal — `lab_window.py`

[`LabWindow`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/lab_window.py) es la ventana raíz (`QMainWindow`). Contiene:

- **Barra lateral de navegación:** botones de sección (Resumen, Experimentos, Configuraciones, Visualización, Resultados, Comparación, Reportes, Preferencias).
- **`QStackedWidget`:** pila de páginas; cada sección corresponde a una instancia de `PaginaBase`.
- **Lógica de autenticación:** manejo de sesión de usuario actual, flujo de login/logout.
- **Métodos de refresco:** `refrescar_exps()`, `refrescar_detalle()`, `refrescar_resumen()` para propagar cambios entre páginas.

### 8.3 Clase base de páginas — `paginas/base.py`

[`PaginaBase`](file:///c:/Users/lunaj\Downloads\physicell_manager-main\physicell_manager-main\app\paginas\base.py) es la clase base de todas las páginas (hereda de `QWidget`). Proporciona:

- Acceso a la base de datos: `self.db_path()`, `self.conn()`.
- Referencia a la ventana principal: `self.lw`.
- Componentes reutilizables: `Seccion`, `Tarjeta`, `TablaBase`, `BadgeEstado`, `CampoFormulario`, `DialogoBase`.
- Constantes de espaciado: `ESPACIO_S`, `ESPACIO_M`, `ESPACIO_L`.
- Funciones de estado: `xml_estado()`, `exe_estado()`, `exp_estado()`.

### 8.4 Páginas de UI

| Archivo | Clase | Descripción |
|---|---|---|
| [`login.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/login.py) | `PaginaLogin` | Pantalla de inicio de sesión y registro |
| [`experimentos.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/experimentos.py) | `PaginaExperimentos` | Lista de experimentos con tarjetas |
| [`detalle.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/detalle.py) | `PaginaDetalle` | Detalle de experimento (7 pestañas) |
| [`configuraciones.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/configuraciones.py) | `PaginaConfiguraciones` | Gestión global de configuraciones XML |
| [`preferencias.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/preferencias.py) | `PaginaPreferencias` | Ajustes de motor, tema y cuenta |
| [`resumen.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/resumen.py) | `PaginaResumen` | Vista global de estado de experimentos |
| [`reportes.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/reportes.py) | `PaginaReportes` | Generación y acceso a reportes |

### 8.5 `PaginaDetalle` — Pestañas internas

[`PaginaDetalle`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/paginas/detalle.py) organiza el detalle de un experimento en 7 pestañas (`QTabWidget`):

| Pestaña | Método | Contenido |
|---|---|---|
| Resumen | `_tab_resumen()` | KPIs, estado, descripción, tags, fechas |
| Ajustes del experimento | `_tab_config()` | XML, motor, versiones de configuración |
| Ejecuciones | `_tab_ejecucion()` | Escenarios, lanzamiento y tabla de runs |
| Visualización 2D/3D | `_tab_vis()` | Visor 2D/3D integrado |
| Resultados | `_tab_resultados()` | Integridad, exportación, limpieza |
| Comparación | `_tab_comparacion()` | Vista paralela de réplicas |
| Reportes | `_tab_reportes()` | Generación de informes |

### 8.6 Hilo de trabajo — `_DiagWorker` y workers de réplicas

Para evitar congelar la UI, las operaciones de larga duración corren en hilos (`QThread`):

- **`_DiagWorker`** (en `detalle.py`): ejecuta el autodiagnóstico del motor en segundo plano y emite `done(dict)` al terminar.
- **Worker de réplicas** (en `nucleo.py`): gestiona la ejecución secuencial de N réplicas en un hilo separado, emitiendo señales de progreso hacia la UI.

---

## 9. Motor de ejecución PhysiCell

### 9.1 Clase `MotorPhysiCell`

Ubicada en [`motor_physicell.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/motor_physicell.py).

**Métodos principales:**

| Método | Descripción |
|---|---|
| `resolver_binario()` | Busca `project.exe` en la raíz configurada |
| `ejecutar(xml, out_dir, seed, timeout, ...)` | Lanza el proceso y espera con monitoreo de inactividad |
| `cancelar()` | Termina el proceso activo de forma limpia |
| `autodiagnostico(exe, xml, log_path)` | Prueba el motor con un XML reducido y devuelve diagnóstico |
| `verificar_binario(exe)` | Verifica la existencia y permisos del binario |
| `intervalos_guardado(xml)` | Extrae los intervalos de guardado SVG y full_data del XML |

### 9.2 Generación de XML por réplica

Para cada réplica, `simulador.py` genera una copia del XML base en la que se reemplazan:

```xml
<!-- En el XML original -->
<random_seed>12345</random_seed>
<save><folder>output</folder></save>

<!-- En la copia por réplica -->
<random_seed>1001</random_seed>  <!-- seed_base + i -->
<save><folder>exp_3/replica_1/output</folder></save>
```

### 9.3 Verificación de hashes

Al crear un lote (`batch`), se calculan y almacenan los hashes SHA-256 del XML y del ejecutable:

```python
xml_sha256 = hashlib.sha256(open(xml_path, "rb").read()).hexdigest()
exe_sha256 = hashlib.sha256(open(exe_path, "rb").read()).hexdigest()
```

Esto permite verificar que los mismos archivos se usaron en diferentes lotes (trazabilidad).

---

## 10. Validación de configuraciones XML

### 10.1 Proceso de validación en dos pasos

1. **Validación sintáctica:** `lxml.etree.fromstring()` para detectar XML mal formado.
2. **Validación estructural:** comprobación de etiquetas y atributos clave de `PhysiCell_settings.xml`:
   - `<overall>`, `<max_time>`, `<parallel_threads>`
   - `<save>`, `<full_data>`, `<SVG>`, `<folder>`
   - `<user_parameters>`, `<cell_definitions>`, etc.

### 10.2 Resultado de la validación

```python
{
    "ok": True | False,
    "errores": ["Error de sintaxis: ...", "Falta la etiqueta <save>"],
    "warnings": ["No se encontraron intervalos de guardado SVG"]
}
```

### 10.3 Validación en tiempo real (editor integrado)

El editor XML integrado en `PaginaDetalle._editar_xml_detalle()` usa un `QTimer` con debounce de 400 ms para disparar la validación tras cada keystroke, minimizando la carga de CPU.

---

## 11. Visualización 2D y 3D

### 11.1 Visor 2D — `visor_widget.py`

[`VisorPhysiCell`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/visor_widget.py) es el widget de visualización 2D integrado en la UI:

- Lee archivos SVG de salida de PhysiCell (snapshots por frame).
- Ofrece slider de frames, reproducción con velocidad configurable.
- Filtros: por tipo de célula y por sustrato.
- Barra de color escalada al valor máximo del sustrato activo.
- Implementado con `matplotlib` integrado en un `QWidget` vía `FigureCanvasQTAgg`.

### 11.2 Visor 3D — `visor3d_vtk.py`

[`visor3d_vtk.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/visor3d_vtk.py) implementa la visualización tumoral 3D con PyVista/VTK:

- Lee archivos `.xml` de PhysiCell (formato MultiCellDS) con posición, radio, estado y tipo de cada célula.
- Construye mallas esféricas por célula con su radio real.
- Coloreado por: estado celular, tipo celular, presión u volumen.
- Funcionalidades avanzadas:
  - Malla de membrana del tumor (convex hull o surface).
  - Núcleo interior de cada célula.
  - Plano de corte configurable en el eje X.
  - Selección de célula por ID.
  - Tres fuentes de luz suaves + sombreado especular.
  - Leyenda interactiva de colores.
- Integrado en la UI vía `pyvistaqt.BackgroundPlotter` o `QtInteractor`.

**Fallback:** si PyVista no está disponible, `visor_widget.py` usa Matplotlib para renderizado 3D básico.

### 11.3 Función `abrir_vtk()`

Función de alto nivel en `visor3d_vtk.py` que abre el visor 3D en una ventana independiente para un directorio de salida dado.

---

## 12. Sistema de reportes y exportación

### 12.1 Informes HTML

[`reportes.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/app/reportes.py) genera informes HTML usando plantillas de cadena Python (sin dependencia de Jinja2 u otro motor de plantillas).

**Contenido del informe:**
- Cabecera: título, descripción, tags, fechas de creación y modificación.
- Configuraciones: historial de versiones XML con estado activo/inactivo.
- Ejecuciones: tabla de runs con estado, tiempos, semilla, carpeta de salida y errores.
- Métricas: número de células finales por réplica.
- Trazabilidad: cadena completa `run → config → escenario → experimento`.

### 12.2 Exportación a PDF

La generación de PDF se realiza convirtiendo el HTML generado a PDF usando las capacidades del sistema o librerías disponibles (ej: `weasyprint` o impresión del sistema).

### 12.3 Exportación CSV y JSON

- **CSV:** tabla de runs con todos los campos relevantes (`id`, `status`, `start_time`, `end_time`, `output_dir`, `error_message`, etc.).
- **JSON:** misma información en formato estructurado.

---

## 13. Análisis estadístico y comparación

### 13.1 Métricas por réplica — `estadistica.py`

- Extrae el número de células al final de la simulación de los archivos de salida.
- Calcula media, desviación estándar y otros estadísticos descriptivos.

### 13.2 Prueba t de Student

Compara el número de células finales entre dos experimentos:

```python
from scipy import stats
t_stat, p_value = stats.ttest_ind(metricas_exp1, metricas_exp2)
```

Resultado exportable a CSV con: valor t, p-valor, medias, desviaciones estándar de ambos grupos.

### 13.3 Comparación visual — `comparacion.py`

- Genera un layout de dos paneles (`QHBoxLayout`) con un visor por réplica.
- Sincronización de slider: mover el frame en un panel mueve el otro automáticamente.
- Gráfica de barras con `matplotlib`: número de células finales por réplica para cada experimento.

---

## 14. Sistema de temas visuales

### 14.1 `theme_lab.py`

Define los estilos completos de la aplicación mediante `QStyleSheet` de PyQt6:

- **Tema oscuro** (predeterminado): paleta de grises oscuros, acentos en verde PhysiCell (`#3DDC84`) y azules.
- **Tema claro**: fondo blanco, textos oscuros, mismos acentos.

**Tokens de diseño:**

| Token | Valor (oscuro) | Descripción |
|---|---|---|
| Fondo principal | `#1A1A2E` | Fondo de ventana |
| Superficie | `#16213E` | Fondo de tarjetas |
| Acento | `#3DDC84` | Color primario (verde) |
| Error | `#E5484D` | Color de error |
| Aviso | `#FFB020` | Color de advertencia |
| Texto principal | `#E8E8E8` | Texto normal |
| Texto secundario | `#A6A6A6` | Texto muted |

### 14.2 Cambio de tema en tiempo de ejecución

```python
# En LabWindow:
def cambiar_tema(self, nombre: str):
    sheet = LIMA if nombre == "claro" else OSCURO
    self.setStyleSheet(sheet)
```

---

## 15. Empaquetado y distribución

### 15.1 Configuración PyInstaller

[`build.spec`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/build.spec) define:

- **Nombre del ejecutable:** `PhysiCellManager`
- **Archivos incluidos:** el paquete `app/`, `config/`, `assets/`.
- **Excluidos:** `.venv`, `tests/`, `dist/`, `build/`.
- **Modo:** `--onedir` (carpeta con ejecutable y dependencias).

### 15.2 Comandos de empaquetado

**Windows:**
```powershell
pyinstaller build.spec
# Resultado: dist/PhysiCellManager/PhysiCellManager.exe
```

**Linux / macOS:**
```bash
pyinstaller build.spec
# Resultado: dist/PhysiCellManager/PhysiCellManager
```

### 15.3 Notas de distribución

- El motor PhysiCell (`project.exe` / `project`) **no se incluye** en el paquete distribuible; el usuario debe obtenerlo por separado.
- Los directorios `dist/` y `build/` están excluidos del control de versiones (`.gitignore`).

---

## 16. Suite de pruebas

### 16.1 Configuración de pytest

[`pytest.ini`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/pytest.ini) configura:
- Directorio de pruebas: `tests/`.
- Marcadores personalizados: `funcional`, `regresion`, `ui`.

### 16.2 Fixtures compartidas — `conftest.py`

[`tests/conftest.py`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/tests/conftest.py) proporciona fixtures portables:

| Fixture | Descripción |
|---|---|
| `tmp_db_ready` | BD SQLite temporal con esquema completo inicializado |
| `db_conn` | Conexión a la BD temporal para pruebas de integración |
| `xml_valido` | Ruta al XML de ejemplo del repositorio (`config/PhysiCell_settings.xml`) |

### 16.3 Suites de pruebas

| Archivo | Tipo | Cobertura |
|---|---|---|
| `test_xml_validator.py` | Unitario | Validación de XML válidos e inválidos |
| `test_simulador.py` | Integración | Escenarios, réplicas, runs, lotes |
| `test_agregador.py` | Unitario | Consolidación de frames/células |
| `test_comparacion.py` | Integración | Comparaciones y gráficas |
| `test_reportes.py` | Integración | Reportes HTML, CSV, JSON |
| `test_visores.py` | Integración | Visores 2D/3D (backend Agg) |
| `test_versionado_configuraciones.py` | Integración | Versionado de configuraciones |
| `test_regresion.py` | Regresión | Suite completa ejecutable directamente |
| `test_funcionales.py` | Funcional | CP01–CP13 (derivados de RF01–RF13) |

### 16.4 Pruebas funcionales — CP01–CP13

Los casos funcionales cubren los 13 requerimientos funcionales (RF01–RF13) y la regla de no falla (RNF09):

| Caso | Requisito | Módulos cubiertos |
|---|---|---|
| CP01 | RF04 | `servicios.py`, `nucleo.py` |
| CP02 | RF05 | `simulador.py` |
| CP03 | RF01, RF02 | `xml_validator.py`, `servicios.py` |
| CP04 | RF02 | `xml_validator.py` |
| CP05 | RF03 | `nucleo.py`, `servicios.py` |
| CP06 | RF06, RF07 | `simulador.py`, `nucleo.py` |
| CP07 | RF06, RF07 | `simulador.py`, `nucleo.py` |
| CP08 | RNF09 | `simulador.py` |
| CP09 | RF08 | `estadistica.py`, `visualizador.py` |
| CP10 | RF09, RF10 | `visor_widget.py`, `visualizador.py` |
| CP11 | RF11 | `comparacion.py`, `estadistica.py` |
| CP12 | RF12 | `reportes.py` |
| CP13 | RF13 | `simulador.py`, `nucleo.py` |

**Resultado global:** 45 tests passed, 0 failed (suite completa).

### 16.5 Comandos de prueba

```bash
# Suite completa
pytest

# Solo pruebas funcionales (CP01–CP13) con detalle
pytest tests/test_funcionales.py -v

# Pruebas de un módulo específico
pytest tests/test_simulador.py

# Suite de regresión (ejecutable directamente)
python tests/test_regresion.py
```

---

## 17. Integración continua (CI)

### 17.1 Configuración GitHub Actions

[`.github/workflows/ci.yml`](file:///c:/Users/lunaj/Downloads/physicell_manager-main/physicell_manager-main/.github/workflows/ci.yml) define el flujo de CI con:

- **Plataformas:** Ubuntu (Linux) + Windows.
- **Versiones Python:** 3.12 y 3.13.
- **Disparadores:** `push` y `pull_request` a cualquier rama.

### 17.2 Pasos del flujo CI

```yaml
steps:
  - Checkout del repositorio
  - Configurar Python (matrix: 3.12, 3.13)
  - Instalar dependencias: pip install -r requirements-frozen.txt
  - Ejecutar pruebas: pytest
```

### 17.3 Cobertura de la matriz CI

| OS | Python 3.12 | Python 3.13 |
|---|---|---|
| Ubuntu | ✅ | ✅ |
| Windows | ✅ | ✅ |

---

## 18. Consideraciones de diseño y decisiones arquitectónicas

### 18.1 Motor externo sin modificaciones

La decisión de no empaquetar ni modificar el motor PhysiCell permite:
- Independencia de la versión del motor: el usuario puede actualizar el motor sin cambiar la app.
- Flexibilidad: cualquier variante de PhysiCell (con `custom.cpp` propio) es compatible.
- Simplicidad del repositorio: sin código C++ ni compilaciones en el pipeline.

### 18.2 SQLite como motor de persistencia

SQLite fue elegido por:
- Sin servidor requerido (embedded, archivo único).
- Portabilidad total entre Windows, Linux y macOS.
- Soporte nativo en Python (`sqlite3` stdlib, sin dependencias adicionales).
- Suficiente para el volumen esperado de datos (experimentos de investigación locales).

### 18.3 Versionado de configuraciones

El historial de versiones XML permite recuperabilidad ante cambios: si una nueva versión del XML produce resultados inesperados, el investigador puede activar una versión anterior y relanzar el experimento con exactamente la misma configuración.

### 18.4 Trazabilidad mediante hashes SHA-256

El almacenamiento de `xml_sha256` y `exe_sha256` en cada lote garantiza que siempre se pueda verificar que dos lotes usaron exactamente los mismos archivos binario y de configuración, incluso si los archivos cambian en disco posteriormente.

### 18.5 Hilo de worker para réplicas

Las réplicas se ejecutan en un `QThread` separado para mantener la UI responsiva durante ejecuciones de larga duración. Las señales Qt (`pyqtSignal`) comunican el progreso al hilo principal de la UI de forma segura.

### 18.6 Cancelación limpia del proceso

La cancelación de una ejecución en curso sigue el protocolo:
1. `process.terminate()` → señal SIGTERM (graceful).
2. Espera 3 segundos.
3. Si el proceso sigue vivo: `process.kill()` → señal SIGKILL (forzado).
4. Se registra el estado `cancelled` en la BD con la marca de tiempo.

---

## 19. Guía de extensión y contribución

### 19.1 Agregar una nueva página de UI

1. Crear un archivo en `app/paginas/nueva_pagina.py` con una clase que herede de `PaginaBase`.
2. Implementar el método `build()` que construye el layout de la página.
3. Registrar la página en `lab_window.py`: agregar al `QStackedWidget` y al menú lateral.

### 19.2 Agregar un nuevo servicio de negocio

1. Implementar la lógica en el módulo correspondiente (`nucleo.py`, `simulador.py`, etc.).
2. Exponer el servicio desde `servicios.py` si será llamado desde la UI.
3. Agregar pruebas unitarias en `tests/`.

### 19.3 Agregar pruebas

```python
# En tests/test_mi_modulo.py
def test_mi_funcionalidad(tmp_db_ready):
    conn = tmp_db_ready
    # ... tu código de prueba
    assert resultado == esperado
```

### 19.4 Flujo de Pull Request

1. Fork del repositorio en GitHub.
2. Crear rama: `git checkout -b feature/nombre-de-la-caracteristica`.
3. Implementar cambios con pruebas.
4. Verificar que `pytest` pasa completamente.
5. Abrir Pull Request describiendo qué cambia y por qué.

### 19.5 Extensión del motor PhysiCell (custom.cpp)

Si se necesita modificar el comportamiento biológico del motor:
1. Editar `custom.cpp` en la carpeta fuente de PhysiCell.
2. Recompilar: `make` (Linux/macOS) o equivalente en Windows.
3. En PhysiCell Lab, actualizar la ruta al nuevo binario en **Preferencias → Binario por defecto** o en **Ajustes del experimento → Motor PhysiCell**.
4. PhysiCell Lab lanzará el nuevo binario sin modificaciones adicionales.

> **Nota:** PhysiCell Lab no valida ni controla el contenido de `custom.cpp`. Los cambios en el modelo biológico son responsabilidad del investigador.

---

*Documento generado para PhysiCell Lab — Gestor de experimentos PhysiCell.*  
*Repositorio: [https://github.com/lunagalarcio/physicell-lab](https://github.com/lunagalarcio/physicell-lab)*
