# Manual de Usuario — PhysiCell Lab

**Aplicación:** PhysiCell Lab — Gestor de experimentos PhysiCell  
**Versión del documento:** 1.0  
**Fecha:** Noviembre 2026  
**Alcance:** Guía operativa completa para el usuario final

---

## Tabla de contenidos

1. [Introducción](#1-introducción)
2. [Requisitos del sistema](#2-requisitos-del-sistema)
3. [Instalación](#3-instalación)
4. [Primeros pasos — Inicio de sesión y registro](#4-primeros-pasos--inicio-de-sesión-y-registro)
5. [Interfaz principal](#5-interfaz-principal)
6. [Gestión de experimentos](#6-gestión-de-experimentos)
7. [Configuración del experimento](#7-configuración-del-experimento)
8. [Ejecución de simulaciones](#8-ejecución-de-simulaciones)
9. [Visualización 2D y 3D](#9-visualización-2d-y-3d)
10. [Resultados y exportación](#10-resultados-y-exportación)
11. [Comparación de réplicas](#11-comparación-de-réplicas)
12. [Reportes](#12-reportes)
13. [Preferencias](#13-preferencias)
14. [Solución de problemas](#14-solución-de-problemas)
15. [Privacidad y datos del usuario](#15-privacidad-y-datos-del-usuario)
16. [Glosario](#16-glosario)

---

## 1. Introducción

**PhysiCell Lab** es una aplicación de escritorio desarrollada en Python + PyQt6 que actúa como gestor completo del ciclo experimental de simulaciones celulares con el motor **PhysiCell**. Su objetivo es permitir que investigadores y estudiantes puedan:

- Crear, organizar y versionar configuraciones de experimentos de simulación.
- Lanzar múltiples réplicas de simulación de forma automática y controlada.
- Visualizar los resultados de las simulaciones en 2D y 3D de forma interactiva.
- Comparar escenarios y réplicas para análisis estadístico.
- Generar reportes HTML y PDF con trazabilidad completa.

> **Importante:** PhysiCell Lab **no modifica** el código fuente del motor PhysiCell. Funciona como una capa de coordinación externa que lanza el binario compilado (`project.exe` / `project`) y organiza sus salidas.

---

## 2. Requisitos del sistema

### 2.1 Hardware

| Componente | Especificación mínima |
|---|---|
| Sistema operativo | Windows 11, Linux (Ubuntu 20.04+) o macOS (10.15+) |
| Memoria RAM | 8 GB o superior (recomendado) |
| Almacenamiento | Espacio suficiente para salidas de simulación, snapshots y base de datos |

### 2.2 Software

| Componente | Versión |
|---|---|
| Python | 3.12 o superior (se recomienda 3.13) |
| Entorno virtual | Recomendado (`.venv`) |

### 2.3 Motor de simulación (externo, requerido)

| Componente | Especificación |
|---|---|
| Binario PhysiCell | `project.exe` (Windows) o `project` (Linux/macOS), compilado por separado |
| Archivo de configuración | `PhysiCell_settings.xml` válido por experimento |

> El binario de PhysiCell debe obtenerse y compilarse de forma independiente siguiendo las instrucciones oficiales de PhysiCell. PhysiCell Lab solo necesita la ruta a ese binario.

---

## 3. Instalación

### 3.1 Clonar el repositorio

```bash
git clone https://github.com/lunagalarcio/physicell-lab.git
cd physicell-lab
```

### 3.2 Crear y activar el entorno virtual

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux y macOS:**
```bash
python -m venv .venv
source .venv/bin/activate
```

### 3.3 Instalar dependencias

Instalación con versiones congeladas (reproducción exacta, recomendado):
```bash
pip install -r requirements-frozen.txt
```

Instalación con versiones mínimas:
```bash
pip install -r requirements.txt
```

### 3.4 Configurar el motor PhysiCell

Antes de ejecutar simulaciones, debes tener disponible el binario compilado de PhysiCell (`project.exe` en Windows o `project` en Linux/macOS). Puedes configurar su ruta:

- Desde la aplicación: **Preferencias → Raíz de PhysiCell** o **Preferencias → Binario por defecto**
- O directamente al crear/editar un experimento en la pestaña **Ajustes del experimento**

### 3.5 Iniciar la aplicación

```bash
python run_app.py
```

---

## 4. Primeros pasos — Inicio de sesión y registro

Al iniciar PhysiCell Lab por primera vez, aparecerá la pantalla de **inicio de sesión**.

### 4.1 Crear una cuenta (primer uso)

1. Haz clic en **"Crear cuenta"**.
2. Ingresa un **nombre de usuario**, un **correo electrónico** y una **contraseña**.
3. Haz clic en **"Aceptar"**.
4. Aparecerá el mensaje: *"Cuenta creada. Ahora puedes iniciar sesión."*

### 4.2 Iniciar sesión

1. Escribe tu **usuario** y **contraseña** en los campos correspondientes.
2. Pulsa **Enter** o haz clic en **"Entrar"**.
3. Si los datos son correctos, accederás a la pantalla principal de la aplicación.

> Si el usuario o la contraseña son incorrectos, aparecerá un mensaje de error en rojo debajo del formulario.

---

## 5. Interfaz principal

La interfaz principal de PhysiCell Lab está organizada en un **menú lateral** (barra de navegación) con las siguientes secciones:

| Sección | Descripción |
|---|---|
| **Resumen** | Vista general del estado de todos los experimentos |
| **Experimentos** | Lista y gestión de tarjetas de experimento |
| **Configuraciones** | Importación y validación de archivos XML |
| **Visualización 2D/3D** | Visor de simulaciones en 2D y 3D |
| **Resultados** | Consulta y exportación de resultados |
| **Comparación** | Vista paralela y análisis comparativo |
| **Reportes** | Generación de informes HTML y PDF |
| **Preferencias** | Configuración de rutas, motor y apariencia |

---

## 6. Gestión de experimentos

### 6.1 Crear un experimento

1. Navega a la sección **"Experimentos"**.
2. Haz clic en **"Nuevo experimento"** (o botón equivalente con el ícono **+**).
3. Completa los campos:
   - **Título:** nombre descriptivo del experimento (obligatorio).
   - **Descripción:** detalle opcional del objetivo o contexto.
   - **Etiquetas (tags):** palabras clave separadas por comas para organizar y buscar.
4. Haz clic en **"Guardar"** o **"Crear"**.

El experimento aparecerá como una **tarjeta** en la lista de experimentos, mostrando su estado actual (sin configuración, pendiente, en ejecución, completado, con errores).

### 6.2 Ver el detalle de un experimento

Haz clic sobre la tarjeta de un experimento para abrir su **página de detalle**, que contiene las siguientes pestañas:

| Pestaña | Contenido |
|---|---|
| **Resumen** | Estado general, KPIs, descripción, etiquetas |
| **Ajustes del experimento** | Rutas XML, motor y versionado de configuraciones |
| **Ejecuciones** | Escenarios, lanzamiento de réplicas y tabla de runs |
| **Visualización 2D/3D** | Visor integrado de frames y malla 3D |
| **Resultados** | Integridad, exportación, limpieza |
| **Comparación** | Vista paralela de réplicas |
| **Reportes** | Generación de informes HTML/PDF |

### 6.3 Editar un experimento

Dentro de la pestaña **Resumen** o **Ajustes del experimento**, puedes modificar el título, la descripción, las etiquetas y las rutas asociadas al experimento.

### 6.4 Eliminar un experimento

Desde la lista de experimentos, busca la opción de eliminación (ícono de papelera o botón "Eliminar"). Se pedirá confirmación antes de borrar.

> **Advertencia:** eliminar un experimento elimina también sus ejecuciones y datos asociados de la base de datos. Los archivos de salida en disco no se eliminan automáticamente.

---

## 7. Configuración del experimento

### 7.1 Asociar un archivo XML

Dentro del experimento → pestaña **"Ajustes del experimento"**:

1. En el campo **"XML del experimento"**, haz clic en **"…"** para seleccionar el archivo `PhysiCell_settings.xml`.
2. El campo mostrará la ruta seleccionada.
3. Haz clic en **"Validar archivos"** para comprobar la validez del XML.
4. Haz clic en **"Guardar configuración"** para asociar el XML al experimento.

### 7.2 Asociar el motor PhysiCell

1. En el campo **"Motor PhysiCell"**, haz clic en **"…"** para seleccionar el ejecutable `project.exe`.
2. Haz clic en **"Probar motor"** para verificar que el motor arranca, genera resultados y los guarda correctamente (prueba automática en segundos).
3. Haz clic en **"Guardar configuración"**.

### 7.3 Editar el XML dentro de la aplicación

1. Haz clic en **"Editar XML…"** para abrir el editor de texto integrado.
2. El XML se muestra con validación en tiempo real (el estado aparece en verde si es válido, en rojo si tiene errores).
3. Realiza los cambios necesarios y haz clic en **"Guardar"** para guardar los cambios en el archivo.

### 7.4 Versionado de configuraciones

PhysiCell Lab mantiene un historial de versiones del XML de cada experimento.

**Registrar una nueva versión:**
1. Haz clic en **"Registrar nueva versión…"**.
2. Selecciona el archivo XML a versionar.
3. Asigna un nombre de versión (ej: `v2`, `alta-densidad`).
4. Haz clic en **"Aceptar"**. La nueva versión queda activa.

**Activar una versión anterior:**
1. Selecciona la versión deseada en la tabla de versiones.
2. Haz clic en **"Activar versión seleccionada"**.
3. La versión seleccionada pasa a estar activa; las demás quedan inactivas.

La tabla de versiones muestra: número de versión, nombre, archivo XML, estado (Activa / Inactiva) y fecha de creación.

### 7.5 Crear variantes (escenarios)

Una variante o **escenario** es una copia del XML base con un nombre identificador, que puede usarse para comparar distintas condiciones experimentales.

1. En el campo **"Nombre de la variante"**, escribe un nombre descriptivo (ej: `o2-bajo`).
2. Haz clic en **"Crear variante"**.
3. El escenario aparecerá disponible en la pestaña **Ejecuciones** para seleccionar al lanzar réplicas.

---

## 8. Ejecución de simulaciones

### 8.1 Lanzar réplicas

Dentro del experimento → pestaña **"Ejecuciones"**:

1. **Seleccionar escenario:** elige el escenario (variante XML) a ejecutar, o deja la opción predeterminada *"Sin escenario (configuración activa del experimento)"*.
2. **Número de réplicas:** ajusta el contador de réplicas (1–50).
3. **Límite por réplica (min):** tiempo máximo por réplica en minutos. `0` = sin límite absoluto (recomendado). La aplicación cancela automáticamente una réplica si el motor deja de escribir durante 10 minutos seguidos.
4. Haz clic en **"Ejecutar"**.

La aplicación lanza las réplicas en segundo plano. Cada réplica se ejecuta con:
- Una **semilla aleatoria** (`random_seed`) distinta.
- Una **carpeta de salida aislada**: `exp_X/replica_i/output`.

### 8.2 Monitorear el progreso

- La **barra de progreso** muestra el avance general del lote.
- El **panel de log** muestra mensajes en tiempo real del motor.
- La **tabla de réplicas** lista cada run con su estado (`pending`, `running`, `completed`, `failed`, `cancelled`), tiempos de inicio y fin, y posibles mensajes de error.

### 8.3 Detener una ejecución

Haz clic en **"Detener"** para cancelar el lote en curso. Las réplicas que ya completaron mantienen su estado `completed`.

### 8.4 Estados de una réplica

| Estado | Descripción |
|---|---|
| `pending` | Registrada, pendiente de ejecución |
| `running` | En ejecución actualmente |
| `completed` | Finalizada con éxito |
| `failed` | Terminó con error (el motivo se muestra en la tabla) |
| `cancelled` | Cancelada por el usuario o por inactividad del motor |

### 8.5 Ver detalle de una réplica

Haz doble clic sobre una fila de la tabla de réplicas para abrir un diálogo con el detalle completo: estado, tiempos, semilla, carpeta de salida, log y mensaje de error.

---

## 9. Visualización 2D y 3D

### 9.1 Visor 2D (estilo Studio)

Dentro del experimento → pestaña **"Visualización 2D/3D"** → modo **2D**:

| Control | Descripción |
|---|---|
| **Slider de frames** | Navega entre los instantes de tiempo de la simulación |
| **Play / Pausa** | Reproduce los frames automáticamente |
| **Control de velocidad** | Ajusta la velocidad de reproducción |
| **Filtro por tipo de célula** | Muestra solo las células del tipo seleccionado |
| **Filtro por sustrato** | Superpone la concentración del sustrato seleccionado |
| **Barra de color** | Muestra la escala de colores activa |

### 9.2 Visor 3D (tumor interactivo)

Modo **3D** dentro de la pestaña de visualización:

| Control | Descripción |
|---|---|
| **Color por** | Estado, tipo celular, presión u volumen |
| **Malla de membrana** | Activa/desactiva la superficie del tumor |
| **Núcleo interior** | Muestra el núcleo celular interno |
| **Radio real** | Representa las células con su radio físico real |
| **Plano de corte X** | Genera un corte transversal del tumor en el eje X |
| **Selección por ID** | Selecciona e inspecciona una célula por su identificador |
| **Leyenda** | Muestra la leyenda de colores activa |
| **Luces suaves** | 3 fuentes de luz para iluminación realista |
| **Sombreado especular** | Activa el brillo especular de las superficies |
| **Rotación / Zoom** | Interacción con el mouse: girar, acercar y desplazar |

### 9.3 Comparación visual

Desde la pestaña **"Comparación"**, puedes ver dos réplicas lado a lado con sincronización de frames.

---

## 10. Resultados y exportación

Dentro del experimento → pestaña **"Resultados"**:

### 10.1 Verificar integridad

La aplicación comprueba si cada réplica generó archivos de salida válidos. Las réplicas con salida incompleta se marcan como inconsistentes.

### 10.2 Abrir en visor

Selecciona una réplica y haz clic en **"Abrir en visor"** para ver sus resultados directamente en el visor 2D/3D.

### 10.3 Exportar resultados

| Formato | Descripción |
|---|---|
| **CSV** | Tabla de runs y métricas por réplica |
| **JSON** | Datos estructurados de las ejecuciones |

Haz clic en **"Exportar CSV"** o **"Exportar JSON"** y selecciona la carpeta de destino.

### 10.4 Limpiar ejecuciones

La opción **"Limpiar"** elimina las entradas de réplicas que no generaron salida válida, manteniendo limpio el historial.

---

## 11. Comparación de réplicas

Dentro del experimento → pestaña **"Comparación"**:

- **Vista paralela:** dos paneles de visor sincronizados, uno por réplica, con slider de frames compartido.
- **Gráfica de células finales:** muestra el número de células al final de cada réplica para comparar resultados entre escenarios.
- **Prueba t de Student:** compara métricas (número de células finales) entre dos experimentos, con exportación de resultados a CSV.

---

## 12. Reportes

Dentro del experimento → pestaña **"Reportes"**:

### 12.1 Generar informe HTML

1. Haz clic en **"Generar informe HTML"**.
2. El informe se guarda en la carpeta de salida del experimento.
3. Contiene: metadatos del experimento, configuración activa, lista de ejecuciones con estados y tiempos, métricas y trazabilidad completa.

### 12.2 Generar informe PDF

1. Haz clic en **"Generar informe PDF"**.
2. El PDF incluye la misma información que el HTML, formateada para impresión.

### 12.3 Trazabilidad

Cada informe incluye el rastro completo de cada resultado: experimento → escenario → configuración versión → réplica → archivo de salida.

---

## 13. Preferencias

Navega a **"Preferencias"** (ícono de engranaje o sección del menú):

### 13.1 Rutas del motor PhysiCell

| Campo | Descripción |
|---|---|
| **Raíz de PhysiCell** | Carpeta raíz del motor externo (no se modifica) |
| **Binario por defecto** | Ruta al ejecutable `project.exe` para nuevas ejecuciones |

Haz clic en **"Detectar binario en la raíz"** para que la aplicación busque automáticamente el ejecutable dentro de la carpeta raíz indicada.  
Haz clic en **"Guardar ajustes"** para persistir los cambios.

### 13.2 Apariencia

| Opción | Descripción |
|---|---|
| **Oscuro** | Tema oscuro (predeterminado) |
| **Claro** | Tema claro |

Selecciona el tema en el menú desplegable **"Apariencia"**. El cambio se aplica de inmediato.

### 13.3 Cambiar cuenta

Haz clic en **"Cambiar cuenta"** para cerrar la sesión actual y volver a la pantalla de inicio de sesión.

### 13.4 Pruebas de regresión

Haz clic en **"Ejecutar pruebas de regresión"** para lanzar la suite automática de verificación de la aplicación. El resultado se muestra en el panel de log de la propia pantalla de Preferencias.

---

## 14. Solución de problemas

### El motor PhysiCell no ejecuta

1. Verifica que el binario `project.exe` existe en la ruta configurada.
2. Usa el botón **"Probar motor"** en la pestaña **Ajustes del experimento** para obtener un diagnóstico detallado.
3. Revisa que el XML del experimento sea válido (botón **"Validar archivos"**).
4. En Windows, verifica que las DLLs necesarias estén presentes (el diagnóstico indica DLLs faltantes).

### El XML se rechaza como inválido

1. Abre el XML con el editor integrado (**"Editar XML…"**) y revisa los errores indicados en tiempo real.
2. Verifica que el archivo tenga la estructura esperada de `PhysiCell_settings.xml`.
3. Comprueba que el archivo no esté vacío ni dañado.

### Una réplica queda en estado `failed`

1. Haz doble clic sobre la réplica en la tabla para ver el mensaje de error detallado.
2. Revisa el archivo de log asociado a esa réplica (campo `log_path`).
3. Verifica que el ejecutable del motor y el XML sean compatibles.

### La visualización 3D no carga

1. Verifica que PyVista y VTK estén correctamente instalados.
2. Si PyVista no está disponible, la aplicación usa Matplotlib como fallback para visualización básica.
3. Reinstala las dependencias: `pip install -r requirements-frozen.txt`.

### La aplicación no arranca

1. Asegúrate de que el entorno virtual esté activado.
2. Verifica que Python 3.12+ esté en uso: `python --version`.
3. Reinstala las dependencias.
4. Revisa el archivo `output.log` en la raíz del proyecto para mensajes de error de inicio.

---

## 15. Privacidad y datos del usuario

- Todos los datos del usuario (experimentos, configuraciones, réplicas, usuarios) se almacenan **localmente** en una base de datos SQLite.
- **Ubicación de la base de datos:**
  - Windows: `%APPDATA%\PhysiCell_Experiments\experiments.db`
  - Linux/macOS: `~/.local/share/PhysiCell_Experiments/experiments.db`
- Las contraseñas se almacenan como **hash** (no en texto plano).
- La aplicación **no envía datos a servidores externos**.
- Las carpetas de salida de simulación se crean en el mismo directorio que la base de datos, bajo `exp_X/replica_i/output`.

---

## 16. Glosario

| Término | Definición |
|---|---|
| **Experimento** | Unidad de gestión que agrupa configuración XML, escenarios, réplicas y resultados |
| **Réplica (run)** | Una ejecución individual del motor PhysiCell con una semilla aleatoria única |
| **Lote (batch)** | Grupo de réplicas lanzadas en conjunto |
| **Escenario (variante)** | Copia del XML base con parámetros distintos para comparación |
| **Configuración** | Versión del archivo `PhysiCell_settings.xml` asociada a un experimento |
| **random_seed** | Semilla aleatoria única asignada a cada réplica para reproducibilidad |
| **SVG** | Formato de imagen vectorial usado por PhysiCell para los snapshots 2D |
| **VTK** | Formato de datos usado por PhysiCell para los snapshots 3D |
| **Trazabilidad** | Capacidad de rastrear un resultado hasta su configuración, versión y réplica exacta |
| **Motor PhysiCell** | Binario externo `project.exe` / `project` que ejecuta la simulación celular |

---

*Documento generado para PhysiCell Lab — Gestor de experimentos PhysiCell.*  
*Repositorio: [https://github.com/lunagalarcio/physicell-lab](https://github.com/lunagalarcio/physicell-lab)*