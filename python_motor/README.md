# ESP32 + Mega cyclic test bench

This provides a cyclic-test GUI with single-channel ESP32 acquisition and
Arduino Mega motor control. Use `main_motor_test.py` for the combined version;
`main_sensor_test.py` remains the copied sensor-only application.

## Launch

### 1. Install dependencies (first use)

Use Python 3.10 or newer with Tkinter. Open PowerShell in the project root:

```powershell
cd python-motor-tests
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r python_motor/requirements.txt
```

If `.venv` already exists, skip its creation and install the requirements.
Activation is not required.

### 2. Prepare both boards

Upload the [ESP32 firmware](../firmware/README.md) and the supplied
[Mega motor firmware](firmware/README.md) if needed. Connect each board by
USB, identify its own COM port, and close Arduino Serial Monitor and other
GUIs using those ports. The ESP32 input wiring is
`3V3 -> sensor -> GPIO4 -> fixed resistor -> GND`.

### 3. Open the combined GUI

From the project root:

```powershell
.\.venv\Scripts\python.exe python_motor/main_motor_test.py
```

For a simulated experiment without opening serial ports or moving hardware:

```powershell
.\.venv\Scripts\python.exe python_motor/main_motor_test.py --demo
```

### 4. Configure and run

1. Close other applications using either port. Select the ESP32 port (115200
   baud) and Mega port (9600 baud), then Connect both boards. The GUI waits
   for Mega READY and a valid ESP32 frame. Reset the Mega while connecting
   if its startup READY is missed.
2. Select a sensor preset or type its name. The preset fills the recommended
   resistor; edit **Resistencia fija del divisor** to the actual installed
   value in ohms. Enter the measured supply. Defaults: Sensor 2, 2400 ohm,
   nominal 3.3 V. Sensor resistance always uses this editable resistor value.
3. Add/edit/remove blocks (maximum ten). Double-click a row or press Edit.
   A form provides separate fields for cycles, distance mm, forward mm/s,
   hold maximum s, backward mm/s, hold zero s, and hold after block s.
   Decimal points and decimal commas are accepted in that form.
   Default: one 1 mm cycle at 0.2 mm/s. The table shows total cycles and
   nominal duration. Scroll the left panel to reach the lower controls.
4. Establish the mechanical zero and check the hardware confirmation. Start
   experiment uploads CLEAR and each BLOCK with acknowledgments. It records
   the first valid resistance as R0, collects at least 0.5 seconds of sensor
   baseline, and only then sends RUN.
5. STOP motor sends STOP once and waits for motor confirmation.
   Closing an active GUI requests STOP; close again after confirmation and
   saving. Re-establish mechanical zero after an interrupted test.

One live graph displays resistance (ohms) versus motor displacement (mm).
Smoothing alpha affects the displayed resistance only (1 = raw). The graph
uses the latest 2500 samples. Exports contain all samples, including time and
relative resistance, for offline analysis.

## Posicionamiento manual con botones

1. Carga la variante [Mega_Cyclic_Telemetry](firmware/Mega_Cyclic_Telemetry/README.md)
   actualizada con soporte JOG. La versión original del firmware no admite
   este movimiento; la GUI mantiene los botones deshabilitados hasta recibir
   `CAPS,JOG,1` del Mega durante la conexión.
2. Conecta las placas y ajusta la velocidad manual entre 0,05 y 1 mm/s.
3. Mantén pulsado **Avanzar** o **Retroceder** con el ratón. Al soltarlo,
   salir del botón, minimizar o cambiar de ventana, se envía STOP.
4. Espera la confirmación de parada antes de pulsar otra dirección o iniciar
   un ensayo. El movimiento manual desmarca el cero mecánico: vuelve a
   establecerlo y confirmarlo antes del ensayo.

La GUI envía `JOG,direction,speed` y renueva `JOG_KEEP` cada 100 ms mientras
se mantiene la pulsación. El firmware detiene el movimiento si faltan estas
renovaciones durante 400 ms, incluso ante pérdida de conexión. La señal STEP
termina en LOW. STOP se comprueba en cada iteración manual, sin la espera de
100 pasos del modo cíclico. La parada depende del procesamiento y del tiempo
de un pulso; no sustituye a una parada física. No hay retorno automático ni
límite de recorrido en este modo. Los movimientos de posicionamiento no se
guardan como ensayos ni se añaden a la gráfica de resultados.

En `--demo` los botones simulan únicamente las órdenes y confirmaciones, sin
movimiento ni actualización de una posición física. No conectan puertos.

## Archivos de resultados

At the end of a completed, stopped, or interrupted run, the GUI asks whether
to save. Choosing No or cancelling the file dialog creates no files. Samples
remain in memory until a new run replaces them or the application closes.
Save results as allows saving them later.

Saving creates **one CSV with exactly four columns**: `Time_s`,
`Resistance_ohm`, `Relative_resistance_percent`, and `Displacement_mm`.
Relative resistance uses the first accepted resistance sample as R0.
No metadata, diagnostics, or motor-event files are created.

The suggested filename contains the run's protocol. For example,
`B1-3c-5mm-F1-HM2-R0p5-HZ3-HA4_20261027_190000.csv` identifies block 1,
3 cycles, 5 mm distance, forward speed 1 mm/s, maximum hold 2 s, return speed
0.5 mm/s, zero hold 3 s, and final hold 4 s. Decimal points are written as `p`.
Multiple blocks are separated by `__`; DEMO runs have a `DEMO_` prefix.
The save dialog lets the user choose the folder and edit the name.

Save results as allows another copy or a retry after a save failure. The copied
`plot_sensor_test.py` can read measurement CSVs for the two offline time plots.

### Plot results after a test

From the project root, run:

```powershell
.\.venv\Scripts\python.exe python_motor/plot_sensor_test.py
```

Select the main measurement CSV. Do not select `_motor_events.csv` or metadata.
This offline script plots resistance and relative resistance against time;
the resistance-versus-displacement graph is displayed in the combined live GUI.

Spanish Excel requires importing with comma delimiter and English (United
States) numeric locale; avoid resaving data with misinterpreted decimal points.

## Displacement and compatibility

This version works with the supplied motor firmware unchanged. Like MATLAB
UpdateDisplacement and ProcessMotorMessage, it estimates ramp displacement as
commanded speed times host elapsed time, clamps to the block distance, and
sets expected endpoints on END_FORWARD and END_BACKWARD. These are estimated
commanded positions, not encoder measurements. Both devices are associated
by host reception; ESP32 device timestamps remain the measurement time axis.
USB buffering and independent serial latency introduce synchronization error.

To use executed-pulse counts instead of the speed/time estimate, upload the
optional [telemetry firmware](firmware/Mega_Cyclic_Telemetry/README.md).
The GUI detects `M,time_us,net_steps` automatically. It calculates
`Motor_revolutions = net_steps / steps_per_revolution` and
`Displacement_mm = Motor_revolutions * mm_per_revolution`. The last reported
count is held between reports; the source column records `step_telemetry`
or `speed_time_estimate` per sample. Before the first telemetry report, the
stationary baseline uses the zero estimate. Counts represent pulses sent
to the driver, not encoder-confirmed motion. USB synchronization remains
approximate. Device timestamps and source details remain in memory only;
the exported CSV contains just the four requested vectors.

The sketch defines 3200 steps/revolution and 2 mm/revolution (1600 steps/mm).
Verify driver and spindle calibration. Spindle travel equals tendon travel
only with the corresponding direct, taut transmission. Slack, missed steps,
joint angle, and strain are not measured. Mechanical calibration is fixed
internally and is not editable in the GUI. The test editor uses distance in
mm and speed directly in mm/s. Changing the physical transmission requires
updating calibration in both Python and firmware. The original sketch is archived under
firmware/. The separate telemetry/JOG variant was compiled and linked with
Arduino AVR core 1.8.6, uploaded to the Mega on COM5 and flash-verified on
27 October 2026. Its startup CAPS,JOG,1 and READY responses were confirmed
without sending movement commands. Manual buttons have also been checked in
GUI demo mode; the physical press/release test remains pending. Reconnect the
GUI after uploading so it receives the new capability announcement.

### Input limits for initial bench testing

The editor shows bounded spinboxes and rejects typed values outside these
ranges when saving a block. All blocks are validated again before uploading:

| Parameter | Minimum | Maximum |
|---|---:|---:|
| Distance per cycle | Positive value | User-defined travel; no application cap |
| Forward and backward speed | 0.05 mm/s | 1 mm/s |
| Cycles per block | 1 | 100 |
| Each hold | 0 s | 3600 s |

The installed motor model is **17HS4401**, with an **A4988** driver; both are
kept in the application's internal run configuration. The speed
limits are provisional application limits, **not manufacturer motor ratings**.
The user has confirmed successful bench tests up to 1 mm/s; that is now the
maximum accepted speed in both directions. The automated physical check used
a 1 mm cycle at 0.2 mm/s. Distance
is chosen by the operator with no application travel cap; only positive finite
values within the firmware step-counter representation are accepted. This
does not remove the firmware's numeric limits or imply mechanical accuracy.
The minimum speed keeps the firmware's 100-step STOP
polling interval at about 1.25 seconds nominally; lower speeds would increase
that latency. Cycle and hold caps are administrative test limits, not motor
capabilities. Nominal duration is displayed before starting.

The driver current setting/microstepping, load, transmission,
available travel from the chosen zero and end-stop arrangement are needed to
establish a wider bench envelope. NEMA 17 frame size alone cannot establish
those limits. Values are centralized in `motor_core.py` as `BENCH_LIMITS` and
kept in each run's in-memory configuration. The current firmware still has its original
validation; these additional bounds are enforced by this Python GUI.

The supplied bench document `SRBVM_2026____Banco_de_ensayos_.pdf` (pages 2-3)
and the user's confirmation establish the intended configuration: 17HS4401,
1.8-degree full steps, A4988 at 1/16 microstepping, 3200 pulses/revolution,
2 mm/revolution and a 12 V motor supply. The conversion is 1600 pulses/mm
or 0.000625 mm per commanded microstep; this is not measured positioning
accuracy. Software cannot read the physical microstep pins through the
current protocol. A4988 identity alone does not establish
the usable motor speed under load. See the
[driver documentation](https://www.pololu.com/product/1183) for its microstep table.

The document reports Rs=0.1 ohm and VREF=0.952 V for its driver calibration;
these are documented hardware values, not readings made by this software.
Its 270 mm/s HIWIN specification is explicitly without the motor and must
not be used as the speed limit for this loaded assembly. The provisional
0.05-1 mm/s software range uses the user's successful tests up to 1 mm/s.

**Pin discrepancy in the source document:** Figure 4 shows STEP on Mega pin 2
and DIR on pin 3. Both supplied firmware versions use DIR=2 and STEP=3;
the successful physical test used that firmware. The code/pins are unchanged;
check the drawing against the working wiring before using it for rewiring.
The document also describes an AS5311 position sensor, which is not acquired
by the current GUI or motor firmware.

Sensor loss, sequence/time resets, motor errors, acknowledgment timeouts, and
an overall protocol timeout request STOP and retain partial data. An unconfirmed
STOP reports unknown motor state and disables another run until reconnecting.
Serial STOP is the existing firmware command, not a physical emergency stop.
The supplied firmware has no homing or limit-switch handling. The GUI sends
no RUN command when opening or connecting.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s python_motor -p "test_*.py" -v
```

Tests cover handshake and baseline gating, asymmetric ramps, holds, clamping,
partial-stop estimates, reset/error handling, validation, fragmented serial
lines, and copied sensor/CSV behavior. Hardware calibration and integration
still require a bench check. Tests do not initiate physical motor movement.

## Troubleshooting

- Port busy: close sensor-only GUI, Serial Monitor, or another process using it.
- Connection timeout: verify different ESP32/Mega ports and reset the Mega
  while connecting so its startup READY is received.
- No sensor data: verify the ESP32 firmware, GPIO4 wiring, and selected port.
- Start rejected: check the zero/hardware checkbox and all protocol values.
- STOP unconfirmed: the motor state is unknown. Check the hardware before
  reconnecting and re-establish zero before another test.
- Save failure: samples stay in memory; use Save results as to choose a
  writable location before closing or starting another test.
