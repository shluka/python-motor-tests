# Procesamiento de datos

## Abrir el repositorio desde PowerShell

Entra en la carpeta que contiene `data_processing` y `python_motor`. Cambia
la ruta del ejemplo por la ubicación del repositorio en tu ordenador.

```powershell
cd 'C:\ruta\a\python-motor-tests'
git rev-parse --show-toplevel
```

Si ya tienes el repositorio clonado y quieres descargar la última versión:

```powershell
git pull --ff-only origin main
```

Si todavía no lo tienes, ejecuta estos comandos desde la carpeta donde quieras
guardarlo:

```powershell
git clone https://github.com/shluka/python-motor-tests.git
cd python-motor-tests
```

## Preparar Python

Necesitas Python 3.10 o posterior con Tkinter. Si aún no tienes el entorno
virtual del banco, créalo e instala las dependencias desde la raíz:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r python_motor/requirements.txt
```

Los comandos de abajo usan directamente el Python de `.venv`. Si ya tienes el
entorno del banco activo en la terminal, puedes sustituir
`.\.venv\Scripts\python.exe` por `python`.

## Ensayos de velocidad

```powershell
.\.venv\Scripts\python.exe -m data_processing.plot_speed_tests
```

1. Elige el sensor en el desplegable.
2. Selecciona sus CSV en este orden: **0.1, 0.5 y 1 mm/s**.
3. Se abre una sola gráfica de **ΔR/R₀ (%) frente al tiempo (s)**. El título
   indica el sensor y cada curva lleva su velocidad al final. Las curvas se
   desplazan verticalmente para separarlas y conservan su amplitud.

Para guardar la figura en PNG:

```powershell
.\.venv\Scripts\python.exe -m data_processing.plot_speed_tests --output "velocidades_sensor1.png"
```

## Ensayos cíclicos

```powershell
.\.venv\Scripts\python.exe -m data_processing.plot_cyclic_tests
```

1. Elige el sensor en el desplegable.
2. Selecciona sus **tres CSV de aristas** y después sus **tres CSV de vértices**,
   en el orden en que quieras numerar los ensayos en la leyenda.
3. Se abren dos gráficas de **ΔR/R₀ (%) frente al tiempo (s)**, una por grupo.
   Cada gráfica superpone sus tres ensayos, muestra las señales originales
   sin suavizado y deja 10 s de margen tras el ensayo más largo.

Cada CSV de este protocolo contiene la secuencia completa de seis ciclos por
amplitud para **3, 6, 9, 12 y 15 mm**.

```powershell
.\.venv\Scripts\python.exe -m data_processing.plot_cyclic_tests --output "ciclos_sensor1.png"
```

El comando guarda `ciclos_sensor1_aristas.png` y
`ciclos_sensor1_vertices.png`.

## Archivos y opciones

- Usa los CSV originales del banco con las columnas `Time_s` y
  `Resistance_ohm`. Cada ensayo calcula ΔR/R₀ con su primera resistencia
  calculable. Las muestras de 0 V con resistencia vacía aparecen como huecos.
- Añade `--no-show` junto con `--output` para guardar los PNG tras elegir los
  CSV y omitir la ventana de la gráfica.
- Las rutas de salida relativas se guardan en la carpeta desde la que ejecutas
  el comando. Puedes usar una ruta absoluta entre comillas.
- `sensor_dialog.py` contiene el selector de sensor que usan ambos programas.
