# Diagnostic recordings

This folder contains the early serial hardware-test CSVs and JSON summaries.
It is not a runnable application. GUI acquisitions are saved to the location
chosen in the sensor-only GUI, or to `python_motor/Results` for motor tests.

## Create another diagnostic recording

1. Close GUIs and Serial Monitor using the ESP32 port.
2. Open PowerShell in the project root.
3. Run, substituting the current ESP32 port if needed:

```powershell
.\.venv\Scripts\python.exe python/test_hardware.py COM29 --seconds 10
```

4. Inspect the timestamped CSV and JSON summary created here. The diagnostic
   reports raw voltage, frame counts, timing, and dropped slots.

The early `hardware_20261026_211453_resistance.csv` was calculated using
2400 ohm and an assumed 3.3 V supply. It has no `Time_s` column and cannot be
selected directly by the offline GUI plotter. New GUI measurement CSVs have
the required time vector. Files named `*_stderr.log` are GUI launch logs,
not measurement data.
