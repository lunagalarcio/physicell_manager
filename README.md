# PhysiCell Lab — Gestor de experimentos PhysiCell

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[Windows 11](https://www.microsoft.com/windows/get-windows-11) | [Linux](https://linux.org/) | [macOS](https://macos.com)

> Aplicación de escritorio (Python + PyQt6) para gestionar el ciclo experimental con **PhysiCell** **sin modificar el motor**: experimentos, escenarios, réplicas, validación XML, ejecución con trazabilidad, visualización 2D/3D estilo Studio, resultados, comparación y reportes.

---

## 📸 Capturas de pantalla

> **Nota:** Las imágenes de abajo son *placeholders*. Reemplázalas con capturas reales de la aplicación (menú principal, visor 2D, visor 3D, panel de reportes). Guardarlas en la carpeta `docs/screenshots/` y actualizar las rutas.

| Funcionalidad | Captura |
|---|---|
| **Ventana principal – navegación y tarjetas de experimento** | ![Screenshot de la ventana principal](screenshots/main_window.png) |
| **Configuración – importación y validación de XML** | ![Screenshot de la pantalla de configuración](screenshots/config_window.png) |
| **Visualizador 2D estilo Studio** | ![Screenshot del visor 2D](screenshots/visor2d.png) |
| **Visualizador 3D tumor (PyVista/VTK)** | ![Screenshot del visor 3D](screenshots/visor3d.png) |
| **Panel de reportes – HTML con trazabilidad** | ![Screenshot de reportes](screenshots/reportes.png) |

> *Sugerencia:* hacer capturas con el modo “Play” detenido, resaltando el frame actual y la leyenda de colores. Guardar en `README.md` con ruta relativa `./screenshots/...`.

---

## 🛠 Requisitos

| Componente | Versión / Nota |
|---|---|
| **Sistema operativo** | Windows 11 (probado), Linux (Ubuntu 20.04+), macOS (10.15+) |
| **Python** | **3.12+** (probado en 3.13). Se recomienda usar un entorno virtual. |
| **Dependencias** | Ver `requirements-frozen.txt` (versiones congeladas) y `requirements.txt`. |
| **Motor PhysiCell** | Binario compilado `project.exe` (ver [PhysiCell documentation](https://physicell.github.io/)). Opcional: usar `PhysiCell/beta/download_binary.py template`. |
| **Visualizador 3D** | PyVista 0.49.1 + VTK 9.7 (se instala con `requirements-frozen.txt`). Si no está, la app conserva el renderizador Matplotlib. |

### Instalación rápida

```powershell
# 1. Clonar repositorio (o descomprimir este zip)
git clone https://github.com/lunagalarcio/physicell-lab.git
cd physicell-lab

# 2. Crear y activar entorno virtual (recomendado)
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows PowerShell

# 3. Instalar dependencias
pip install -r requirements-frozen.txt

# 4. (Opcional) Verificar que el binario project.exe esté en el PATH
#    o configurarlo desde Preferencias → Binario PhysiCell.

# 5. Levantar la aplicación
python run_app.py
```

---

## 🚀 Flujo de uso (guía paso a paso)

| # | Acción | Descripción |
|---|---|---|
| **1** | **Configuraciones** | Importar o crear el archivo `PhysiCell_settings.xml`. Editarlo, validarlo con el validador interno y asociarlo a un experimento. |
| **2** | **Experimentos** | Crear “tarjetas” con título, descripción y etiquetas (tags). |
| **3** | **Detalle → Configuración** | Asignar el XML del experimento y la ruta al ejecutable `project.exe`. Validar y guardar. |
| **4** | **Detalle → Ejecución** | Lanzar **N réplicas** de simulación. Cada réplica tiene un `random_seed` distinto y una carpeta de salida aislada `exp_X/replica_i/output`. Se puede cancelar en cualquier momento. |
| **5** | **Visualización** | - **2D estilo Studio**: slider de frames, Play, velocidad, filtro por tipo de célula y sufriente, barra de color.<br>- **3D tumor**: visualización con malla de membrana, radio real, núcleo interior, color por estado/tipo/presión/volumen, leyenda, 3 luces suaves, sombreado especular, corte con plano X, selección por ID. |
| **6** | **Resultados** | Integridad por réplica, abrir en visor, exportar CSV/JSON, informe HTML y PDF, limpieza de runs sin salida. |
| **7** | **Comparación** | Vistas paralelas sincronizadas + gráfica de células finales por réplica. |
| **8** | **Preferencias** | Rutas por defecto, binario PhysiCell y suite de regresión. |

---

## 📊 Diagrama Entidad‑Relación (Mermaid)

El siguiente diagrama muestra la estructura de la base de datos SQLite que persiste los datos por usuario.

```mermaid
erDiagram
    USER ||--|{ EXPERIMENTO : "posee"
    EXPERIMENTO ||--|{ EJECUCION : "tiene"
    EJECUCION }|--|{ ESCENARIO : "vinculado"

    EXPERIMENTO {
        int id PK
        text title NOT NULL
        text description
        text config_xml_path
        datetime created_at
        datetime last_modified
        text tags DEFAULT ''
    }

    EJECUCION {
        int id PK
        int experiment_id FK
        int run_number
        text status DEFAULT 'pending'
        datetime start_time
        datetime end_time
        text output_dir
    }

    ESCENARIO {
        int id PK
        int experiment_id FK
        text nombre NOT NULL
        text config_xml_path
        text parametros_json DEFAULT '{}'
        datetime created_at
    }
```

*Las claves foráneas (`FK`) garantizan la integridad referencial entre experimentos, ejecuciones y escenarios. La base de datos se guarda en `%APPDATA%/PhysiCell_Experiments/experiments.db` (Windows).*

---

## 🗂 Estructura del repositorio

```
physicell_experimentos/
├─ .gitignore              # Archivos a ignorar (pycache, build, dist, datos de usuario)
├─ README.md               # Este archivo
├─ requirements.txt        # Dependencias mínimas
├─ requirements-frozen.txt # Versiones congeladas (reprod. exacta)
├─ build.spec              # Configuración PyInstaller → .exe
├─ run_app.py              # Punto de entrada
├─ app/
│  ├─ nucleo.py            # Datos usuario, SQLite, worker de réplicas
│  ├─ simulador.py         # Escenarios, réplicas, aislamiento de carpetas
│  ├─ motor_physicell.py   # Ejecución cancelable del binario project.exe
│  ├─ xml_validator.py     # Validación estructural flexible
│  ├─ config_manager.py    # Importar/leer/guardar XML
│  ├─ visualizador.py      # Visor 2D básico
│  ├─ comparacion.py       # Vistas paralelas + gráfica final
│  ├─ reportes.py          # Informe HTML/PDF con trazabilidad
│  ├─ agregador.py         # Consolidar frames/células a CSV
│  ├─ visor_widget.py      # Visor 2D/3D integrado
│  ├─ visor3d_vtk.py       # Tumor 3D PyVista/VTK
│  ├─ lab_window.py        # Navegación y pantallas principales
│  ├─ theme_lab.py         # Temas visuales
│  ├─ paginas/             # Páginas de UI (una por sección)
│  └─ legacy/              # Código legacy (archivado)
│     └─ interfaz_notion.py # Ventana legacy (re‑exporta núcleo)
├─ config/                 # Plantillas XML de ejemplo
├─ studio/                 # Módulos del “Studio” PhysiCell (referencia)
├─ tests/
│  ├─ conftest.py          # Fixtures compartidas (portables)
│  ├─ test_xml_validator.py
│  ├─ test_simulador.py
│  ├─ test_agregador.py
│  ├─ test_comparacion.py
│  ├─ test_reportes.py
│  ├─ test_visores.py
│  └─ test_regresion.py    # Suite de pruebas (ejecutable directamente)
├─ pytest.ini              # Configuración de pytest
├─ .github/
│  └─ workflows/
│     └─ ci.yml            # CI: Ubuntu + Windows, Python 3.12/3.13
└─ dist/                   # (Generado) Ejecutable PhysiCellManager
```

---

## 📦 Empaquetado y distribución

El proyecto incluye `build.spec` para generar un ejecutable autónomo con **PyInstaller**.
PhysiCell queda como motor externo (no se empaqueta ni modifica).

### Windows

```powershell
pyinstaller build.spec
```

El resultado aparecerá en `dist/PhysiCellManager/PhysiCellManager.exe`.

### Linux / macOS

```bash
pyinstaller build.spec
```

El resultado aparecerá en `dist/PhysiCellManager/PhysiCellManager` (sin extensión `.exe`).

> **Nota:** En Linux y macOS el ejecutable no lleva extensión. El motor PhysiCell (`project` o `project.exe`) debe estar compilado por separado y su ruta configurarse en Preferencias → Raíz de PhysiCell.

**No se sube el `dist/` ni el `build/` al repositorio** (están en `.gitignore`).

---

## 🛡 Licencia

Este proyecto está bajo la licencia **MIT**. Ver el archivo `LICENSE` para más detalles.

---

## 👥 Contribución

1. Fork el repositorio.
2. Crea una rama: `git checkout -b feature/tu-caracteristica`.
3. Commit tus cambios: `git commit -m "Añade tal cosa"`.
4. Push: `git push origin main`.
5. Abre un **Pull Request** describiendo qué se hace y por qué.

*Se agradecen mejoras de UI, nuevos filtros de visualización, documentación adicional o expansión de la suite de regresión.*

---

## 📧 Contacto

- **GitHub:** [@lunagalarcio](https://github.com/lunagalarcio)
- **Email:** *tu-email@ejemplo.com* (opcional)
- **Issue Tracker:** Usa la pestaña *Issues* del repositorio para reportar bugs o sugerencias.

---

*Generado el **$(date +%Y)** con ❤️ por la comunidad de PhysiLab.*