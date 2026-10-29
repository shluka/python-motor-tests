# Python motor tests

Aplicaci?n Python para ensayos c?clicos con motor controlado por Arduino Mega y adquisici?n de un sensor mediante ESP32.

## Instalaci?n y uso

Requiere Python 3.10 o posterior con Tkinter.

```powershell
git clone https://github.com/shluka/python-motor-tests.git
cd python-motor-tests
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r python_motor/requirements.txt
.\.venv\Scripts\python.exe python_motor/main_motor_test.py --demo
```

Para usar las placas, ejecuta el mismo comando sin `--demo`. Consulta la [gu?a completa](python_motor/README.md) para cargar el firmware, configurar los puertos, preparar el ensayo y guardar o representar resultados.

## Pruebas autom?ticas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s python_motor -p "test_*.py" -v
```

Las pruebas autom?ticas no abren puertos ni mueven el motor. El modo `--demo` permite explorar la interfaz sin hardware.

## Contenido

- `python_motor/`: interfaz, adquisici?n, protocolo del motor, gr?ficas y tests.
- `python_motor/firmware/`: firmware del Mega, incluida la variante con telemetr?a y JOG.
- `firmware/ESP32_Sensors/`: adquisici?n del sensor.
- `test_results/` y `python_motor/Results/`: carpetas para resultados, excluidos de Git salvo sus instrucciones.

El desplazamiento representa ?rdenes o pulsos enviados; no es una lectura de encoder. Antes de un ensayo f?sico, revisa el cableado y la calibraci?n descritos en la gu?a.
