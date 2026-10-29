# ESP32-S3 sensor firmware

This firmware continuously measures the single voltage divider on GPIO4.
The Python and MATLAB sensor GUIs use the same sketch.

## Upload step by step

1. Connect the ESP32-S3 to the PC using its USB connection.
2. In Arduino IDE, open
   [ESP32_Sensors.ino](ESP32_Sensors/ESP32_Sensors.ino).
3. Select the installed ESP32 board support and your specific ESP32-S3 board.
4. Select the ESP32 COM port. Close any GUI or Serial Monitor using that port.
5. Compile and upload. Use the board's boot/upload procedure if required by
   that board.
6. Optionally open Serial Monitor at **115200 baud**. After startup, expect
   lines such as `S,123,4560000,2.168000`.
7. Close Serial Monitor before launching a Python or MATLAB GUI.

## Wiring and output

`3V3 -> sensor -> GPIO4 -> fixed resistor -> GND`

Choose the physical fixed resistor to match the GUI preset. The firmware
reports voltage only; resistance and relative resistance are calculated on
the PC. Output format is `S,sequence,time_us,Vout`, approximately 100 samples
per second. Sequence gaps indicate skipped acquisition slots or lost frames.

Next: [sensor-only Python instructions](../python/README.md) or
[combined motor instructions](../python_motor/README.md).
