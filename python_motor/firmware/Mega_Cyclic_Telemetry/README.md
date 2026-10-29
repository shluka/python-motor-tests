# Firmware con contador de pulsos

Variante del sketch original. Conserva comandos, pines, calibración y
9600 baudios. Añade mensajes `M,time_us,net_steps` durante el movimiento y
las pausas. El contador vuelve a cero al recibir RUN, por lo que debes situar
el mecanismo en su cero inicial antes de cada ensayo.

También incorpora posicionamiento manual: anuncia `CAPS,JOG,1` antes de
READY. `JOG,1,0.2` avanza y `JOG,-1,0.2` retrocede a 0,2 mm/s. Acepta
0,05–1 mm/s. Solo continúa mientras recibe `JOG_KEEP` al menos cada 400 ms;
STOP lo detiene y responde STOPPED seguido de READY. La GUI renueva cada
100 ms mientras el botón está pulsado. No envíes estas órdenes desde el
Monitor Serie para probar una pulsación: utiliza los botones de la GUI.

## Cargar y usar

1. Detén cualquier ensayo y cierra la GUI y el Monitor Serie.
2. Abre `Mega_Cyclic_Telemetry.ino` en Arduino IDE.
3. Selecciona Arduino Mega y su puerto (COM5 en la última prueba).
4. Comprueba los parámetros: 3200 pasos/vuelta y 2 mm/vuelta. Deben coincidir
   con el driver y el mecanismo. Compila y carga el sketch.
5. Abre `python_motor/main_motor_test.py` y conecta ambas placas.
6. Configura y ejecuta un ensayo desde la GUI. Detectará automáticamente los
   mensajes M y mostrará `pulsos ejecutados` como fuente del desplazamiento.

Conversión: vueltas = pasos netos / pasos por vuelta;
desplazamiento = vueltas * mm por vuelta.

Se cuentan pulsos enviados al driver, no vueltas medidas con encoder.
No se detectan pérdidas de pasos ni holguras. Los reportes se limitan a
20 Hz y se omiten si el búfer de salida está ocupado. La impresión periódica
no espera a que se vacíe el puerto serie; sí añade trabajo al bucle y puede
reducir la velocidad respecto al sketch original. Los mensajes forzados de
inicio/final pueden esperar al puerto. Conviene verificar de nuevo velocidad
y recorrido en el banco después de cargar esta variante.

La GUI conserva el último contador recibido entre reportes y guarda tanto
el tiempo del motor como el de recepción. La asociación con el ESP32 sigue
teniendo latencia USB; no es una sincronización física de las dos placas.
Con el firmware antiguo la fuente será `speed_time_estimate`.

El 27 de octubre de 2026 esta versión se compiló y enlazó con el core Arduino
AVR 1.8.6 para ATmega2560 y se cargó en el Mega de COM5. La memoria flash se
verificó correctamente y se comprobó el arranque con `CAPS,JOG,1` y `READY`.
La comprobación no envió órdenes de movimiento; la prueba física de pulsación,
soltado y parada queda pendiente.
