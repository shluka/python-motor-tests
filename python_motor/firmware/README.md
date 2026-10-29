# Mega motor firmware

There are two versions:

- `Motor_TestBench_cyclic_test`: original sketch, verified with one physical cycle.
- [Mega_Cyclic_Telemetry](Mega_Cyclic_Telemetry/README.md): adds timestamped
  executed-pulse counts for calculating revolutions and displacement in the
  GUI. Prepared separately; compile, upload, and verify it before use.

This is an unchanged copy of the supplied cyclic motor sketch. The combined
GUI works with its existing serial commands and estimated displacement.
The ESP32 uses its separate [sensor sketch](../../firmware/README.md).

## Upload step by step

1. Connect the motor-controller Arduino Mega by USB.
2. Open
   [Motor_TestBench_cyclic_test.ino](Motor_TestBench_cyclic_test/Motor_TestBench_cyclic_test.ino)
   in Arduino IDE.
3. Select the Arduino Mega board and its COM port. Close applications using it.
4. Verify the sketch's mechanical configuration against the bench:
   direction pin 2, step pin 3, 3200 steps/revolution including microstepping,
   and spindle travel 2 mm/revolution (1600 steps/mm).
5. Compile and upload.
6. Optionally open Serial Monitor at **9600 baud** and reset the board.
   Expect `READY` after startup. Do not send RUN merely to check communication.
7. Close Serial Monitor, then follow the
   [combined GUI instructions](../README.md).

The supported commands are CLEAR, BLOCK, RUN, and STOP. The GUI uploads blocks
and waits for acknowledgments before running. There is no automatic homing;
set the initial mechanical zero before a test. The sketch reports phase
boundaries rather than measured motor position.
