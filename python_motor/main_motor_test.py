"""Combined ESP32 single-sensor and Mega cyclic motor test GUI."""
import argparse
import csv
import math
import time
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import serial
from serial.tools import list_ports
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from sensor_core import Acquisition, Frame, SENSORS, parse_frame
from motor_core import Block, MotorProtocol, LineBuffer, Mechanics, BENCH_LIMITS, JogController, TravelCalibration


class App:
    def __init__(self, root, demo=False):
        self.root, self.demo = root, demo
        self.esp = self.motor = None
        self.active = self.connecting = False
        self.ready = self.sensor_ready = False
        self.jog = JogController()
        self.travel = TravelCalibration()
        self.returning = False
        self.return_supported = demo
        self.jog_supported = demo
        self.saved = True
        self.data = self.protocol = None
        self.rows = []
        self.blocks = [Block()]
        self.esp_buffer, self.motor_buffer = LineBuffer(), LineBuffer()
        self.last_plot = 0
        self.error = None
        self.outcome = 'Completed'
        root.title('ESP32 + Mega cyclic test bench' + (' — DEMO' if demo else ''))
        root.geometry('1280x720')
        root.minsize(1100, 660)
        root.protocol('WM_DELETE_WINDOW', self.close)
        left = ttk.Frame(root, padding=8)
        left.pack(side='left', fill='y')
        right = ttk.Frame(root, padding=(0, 8, 8, 8))
        right.pack(side='right', fill='both', expand=True)
        self.editable = []
        self.esp_name = tk.StringVar(value='COM30')
        self.motor_name = tk.StringVar(value='COM5')
        self.sensor = tk.StringVar(value='Sensor 2')
        self.supply = tk.StringVar(value='3.3')
        self.fixed_resistor = tk.StringVar(value='2400')
        self.alpha = tk.StringVar(value='1.0')
        self.status = tk.StringVar(value='Disconnected' if not demo else 'DEMO')
        self.readings = tk.StringVar(value='Resistencia: -- | Desplazamiento: --')
        connections = ttk.LabelFrame(left, text='Conexion y sensor', padding=6)
        connections.pack(fill='x', pady=(0, 5))
        connections.columnconfigure(1, weight=1)
        connections.columnconfigure(3, weight=1)
        for row, (label, variable, values) in enumerate([
                ('ESP32 / 115200', self.esp_name, []),
                ('Mega / 9600', self.motor_name, []),
                ('Sensor', self.sensor, list(SENSORS))]):
            ttk.Label(connections, text=label).grid(row=row, column=0, sticky='w', padx=(0, 6), pady=2)
            box = ttk.Combobox(connections, textvariable=variable, values=values, width=16)
            box.grid(row=row, column=1, columnspan=3, sticky='ew', pady=2)
            self.editable.append(box)
        self.sensor_box = box
        box.bind('<<ComboboxSelected>>', self.instructions)
        for row, label, variable in [(3, 'Resistor (ohm)', self.fixed_resistor),
                                      (4, 'Alimentacion (V)', self.supply),
                                      (5, 'Suavizado (0-1)', self.alpha)]:
            ttk.Label(connections, text=label).grid(row=row, column=0, sticky='w', pady=2)
            entry = ttk.Entry(connections, textvariable=variable, width=12)
            entry.grid(row=row, column=1, columnspan=3, sticky='ew', pady=2)
            self.editable.append(entry)
        self.refresh_button = ttk.Button(connections, text='Actualizar puertos', command=self.refresh)
        self.refresh_button.grid(row=6, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        self.connect_button = ttk.Button(connections, text='Conectar placas', command=self.connect)
        self.connect_button.grid(row=6, column=2, columnspan=2, sticky='ew', padx=(4, 0), pady=(4, 0))
        self.editable.extend([self.refresh_button, self.connect_button])
        jog_panel = ttk.LabelFrame(left, text='Movimiento manual', padding=6)
        jog_panel.pack(fill='x', pady=(0, 5))
        self.jog_speed = tk.StringVar(value='0.2')
        ttk.Label(jog_panel, text='mm/s').pack(side='left')
        speed_box = ttk.Spinbox(jog_panel, textvariable=self.jog_speed, from_=0.05, to=1,
                                increment=.05, width=5)
        speed_box.pack(side='left', padx=4)
        self.editable.append(speed_box)
        self.jog_buttons = []
        for label, direction in [('Avanzar', -1), ('Retroceder', 1)]:
            button = ttk.Button(jog_panel, text=label, state='disabled', width=12)
            button.pack(side='left', padx=2)
            button.bind('<ButtonPress-1>', lambda event, d=direction: self.jog_press(d))
            button.bind('<ButtonRelease-1>', lambda event: self.jog_release())
            button.bind('<Leave>', lambda event: self.jog_release())
            self.jog_buttons.append(button)
        self.root.bind('<ButtonRelease-1>', lambda event: self.jog_release(), add='+')
        self.root.bind('<FocusOut>', lambda event: self.root.after_idle(self.check_jog_focus), add='+')
        self.root.bind('<Unmap>', lambda event: self.stop() if event.widget == self.root and self.jog.active else None, add='+')
        travel_panel = ttk.LabelFrame(left, text='Recorrido', padding=6)
        travel_panel.pack(fill='x', pady=(0, 5))
        self.travel_text = tk.StringVar()
        ttk.Label(travel_panel, textvariable=self.travel_text).grid(row=0, column=0, columnspan=4, sticky='w')
        self.travel_buttons = []
        for col, (label, action) in enumerate([('Fijar minimo', 'zero'), ('Fijar maximo', 'maximum'), ('Borrar', 'clear')]):
            button = ttk.Button(travel_panel, text=label, width=13,
                                command=lambda a=action: self.calibrate_travel(a))
            button.grid(row=1, column=col, padx=(0, 3), pady=(4, 0))
            self.travel_buttons.append(button)
        self.return_button = ttk.Button(travel_panel, text='Volver al minimo', width=15, command=self.return_to_minimum)
        self.return_button.grid(row=2, column=0, columnspan=2, sticky='w', pady=(4, 0))
        self.update_travel()
        sequence = ttk.LabelFrame(left, text='Secuencia de bloques', padding=6)
        sequence.pack(fill='x', pady=(0, 5))
        names = ('Ciclos', 'mm', 'Av mm/s', 'Max s', 'Rt mm/s', 'Cero s', 'Fin s')
        self.table = ttk.Treeview(sequence, columns=names, show='headings', height=4, selectmode='browse')
        for name in names:
            self.table.heading(name, text=name)
            self.table.column(name, width=55, stretch=True)
        self.table.grid(row=0, column=0, sticky='nsew')
        table_scroll = ttk.Scrollbar(sequence, orient='vertical', command=self.table.yview)
        table_scroll.grid(row=0, column=1, sticky='ns')
        self.table.configure(yscrollcommand=table_scroll.set)
        self.table.bind('<Double-1>', lambda _: self.edit_block())
        buttons = ttk.Frame(sequence)
        buttons.grid(row=1, column=0, columnspan=2, sticky='ew', pady=(4, 0))
        for text, command in [('Anadir bloque', self.add_block), ('Editar', self.edit_block), ('Eliminar', self.remove_block)]:
            button = ttk.Button(buttons, text=text, command=command, width=14)
            button.pack(side='left', padx=(0, 4))
            self.editable.append(button)
        self.summary = tk.StringVar()
        ttk.Label(sequence, textvariable=self.summary).grid(row=2, column=0, columnspan=2, sticky='w', pady=(3, 0))
        self.zero = tk.BooleanVar(value=False)
        self.zero_check = ttk.Checkbutton(left, variable=self.zero, text='Cero y montaje verificados')
        self.zero_check.pack(anchor='w', pady=(0, 4))
        self.editable.append(self.zero_check)
        actions = ttk.Frame(left)
        actions.pack(fill='x')
        self.start_button = ttk.Button(actions, text='Iniciar ensayo', command=self.start, state='disabled', width=14)
        self.start_button.pack(side='left', padx=(0, 4))
        self.stop_button = ttk.Button(actions, text='STOP motor', command=self.stop, state='disabled', width=12)
        self.stop_button.pack(side='left', padx=(0, 4))
        ttk.Button(actions, text='Guardar CSV', command=self.save, width=12).pack(side='left')
        ttk.Label(right, textvariable=self.status, wraplength=600).pack(side='bottom', anchor='w', pady=(4, 0))
        ttk.Label(right, textvariable=self.readings, wraplength=600).pack(side='bottom', anchor='w', pady=(4, 0))
        figure = Figure(figsize=(7, 5), tight_layout=True)
        self.ax = figure.subplots()
        self.ax.set_title('Resistencia frente a tiempo')
        self.ax.set_xlabel('Tiempo (s)')
        self.ax.set_ylabel('Resistencia (ohm)')
        self.ax.grid(alpha=0.3)
        self.ax.ticklabel_format(useOffset=False, style='plain')
        self.line, = self.ax.plot([], [], linewidth=1)
        self.canvas = FigureCanvasTkAgg(figure, master=right)
        self.canvas.get_tk_widget().pack(fill='both', expand=True)
        self.instructions()
        self.refresh()
        self.update_table()
        self.controls()
        root.after(20, self.poll)

    def instructions(self, *_):
        fixed, _, _ = SENSORS.get(self.sensor.get(), SENSORS['Sensor 2'])
        self.fixed_resistor.set(f'{fixed:g}')

    def refresh(self):
        names = [p.device for p in list_ports.comports()]
        for box in self.editable[:2]:
            box['values'] = names

    def update_table(self):
        self.table.delete(*self.table.get_children())
        for i, block in enumerate(self.blocks):
            self.table.insert('', 'end', iid=str(i), values=[format(v, '.6g') for v in block.values()])
        self.summary.set(f'Bloques: {len(self.blocks)} | Ciclos: {sum(int(b.cycles) for b in self.blocks)} | '
                         f'Tiempo: {sum(b.duration() for b in self.blocks):.1f} s')


    def add_block(self):
        if not self.active and not self.jog.active and len(self.blocks) < 10:
            self.blocks.append(Block())
            self.update_table()
            self.table.selection_set(str(len(self.blocks) - 1))
            self.table.see(str(len(self.blocks) - 1))
            self.edit_block()

    def edit_block(self):
        if self.active or self.jog.active or not self.table.selection():
            return
        i = int(self.table.selection()[0])
        dialog = tk.Toplevel(self.root)
        dialog.title(f'Configurar bloque {i+1}')
        dialog.transient(self.root)
        dialog.grab_set()
        labels = ['Número de ciclos', 'Recorrido (mm)', 'Velocidad de avance (mm/s)',
                  'Pausa en máximo (s)', 'Velocidad de retorno (mm/s)',
                  'Pausa en cero (s)', 'Pausa después del bloque (s)']
        fields = []
        limits = BENCH_LIMITS
        ranges = [(limits.min_cycles, limits.max_cycles, 1),
                  (0, None, .01),
                  (limits.min_speed, limits.max_speed, .01),
                  (0, limits.max_hold, .1),
                  (limits.min_speed, limits.max_speed, .01),
                  (0, limits.max_hold, .1), (0, limits.max_hold, .1)]
        for row, (label, value) in enumerate(zip(labels, self.blocks[i].values())):
            low, high, increment = ranges[row]
            bounds = f' [{low:g}–{high:g}]' if high is not None else ' [> 0; sin tope de ensayo]'
            ttk.Label(dialog, text=label+bounds).grid(row=row, column=0, padx=12, pady=6, sticky='w')
            variable = tk.StringVar(value=format(value, '.6g'))
            if high is None:
                widget = ttk.Entry(dialog, textvariable=variable)
            else:
                widget = ttk.Spinbox(dialog, textvariable=variable, from_=low, to=high, increment=increment)
            widget.grid(row=row, column=1, padx=12, pady=6)
            fields.append(variable)

        def apply():
            try:
                values = [float(v.get().strip().replace(',', '.')) for v in fields]
                block = Block(*values)
                BENCH_LIMITS.validate(block)
                self.blocks[i] = block
                self.update_table()
                dialog.destroy()
            except ValueError as exc:
                messagebox.showerror('Invalid block', str(exc), parent=dialog)
        ttk.Button(dialog, text='Guardar bloque', command=apply).grid(row=7, column=0, padx=12, pady=12)
        ttk.Button(dialog, text='Cancelar', command=dialog.destroy).grid(row=7, column=1, padx=12, pady=12)

    def remove_block(self):
        if not self.active and not self.jog.active and self.table.selection():
            self.blocks.pop(int(self.table.selection()[0]))
            self.update_table()

    def controls(self):
        locked = self.active or self.connecting or self.jog.active
        for widget in self.editable:
            widget.configure(state='disabled' if locked else 'normal')
        self.start_button.configure(state='normal' if self.ready and self.sensor_ready and not locked else 'disabled')
        self.stop_button.configure(state='normal' if self.active or self.jog.active else 'disabled')
        self.return_button.configure(state='normal' if self.ready and self.return_supported and
                                     not locked and self.travel.maximum is not None else 'disabled')
        for button in self.travel_buttons:
            button.configure(state='normal' if self.ready and not locked else 'disabled')
        for button in self.jog_buttons:
            button.configure(state='normal' if not self.returning and self.ready and self.jog_supported and
                             not self.active and not self.connecting and self.jog.state not in
                             ('stopping', 'waiting_ready') else 'disabled')

    def update_travel(self):
        position = self.travel.position
        maximum = self.travel.maximum
        self.travel_text.set('Pos: ' + ('--' if position is None else f'{position:.4f} mm') +
                             ' | Max: ' + ('sin fijar' if maximum is None else f'{maximum:.4f} mm') +
                             (' | DEMO' if self.demo else ''))

    def calibrate_travel(self, action):
        if self.active or self.jog.active or self.connecting or not self.ready:
            return
        try:
            if action == 'zero':
                self.travel.set_zero()
                self.zero.set(False)
            elif action == 'maximum':
                self.travel.set_maximum()
            else:
                self.travel = TravelCalibration()
                self.zero.set(False)
            self.update_travel()
            self.controls()
        except ValueError as exc:
            messagebox.showerror('Calibracion', str(exc), parent=self.root)

    def return_to_minimum(self):
        if self.active or self.connecting or self.jog.active or not self.ready or not self.return_supported:
            return
        try:
            command = self.travel.return_command(float(self.jog_speed.get().replace(',', '.')))
            if command is None:
                self.status.set('El motor ya esta en el minimo.')
                return
            now = time.monotonic()
            speed = float(self.jog_speed.get().replace(',', '.'))
            direction = 1 if self.travel.steps < self.travel.origin else -1
            self.jog.start(direction, speed, now)
            self.returning = True
            self.return_deadline = now + abs(self.travel.position) / speed * 2 + 5
            self.zero.set(False)
            if self.demo:
                self.demo_jog_time = now
                self.demo_jog_steps = self.travel.steps
                self.demo_jog_direction, self.demo_jog_speed = direction, speed
            self.send(command)
            self.controls()
            self.status.set('Volviendo al minimo. STOP motor cancela el retorno.')
        except ValueError as exc:
            messagebox.showerror('Volver al minimo', str(exc), parent=self.root)
        except (OSError, serial.SerialException) as exc:
            self.jog_error(str(exc))

    def jog_press(self, direction):
        if self.active or self.connecting or not self.ready or not self.jog_supported:
            return 'break'
        try:
            speed = float(self.jog_speed.get().replace(',', '.'))
            if self.demo and not self.jog.active:
                self.demo_jog_time = time.monotonic()
                self.demo_jog_steps = self.travel.steps or 0
                self.demo_jog_direction, self.demo_jog_speed = direction, speed
            command = self.jog.start(direction, speed, time.monotonic())
            if command:
                self.zero.set(False)
                self.send(command)
                self.controls()
                self.status.set('Movimiento manual: suelta el botón para detener.')
        except (ValueError, OSError, serial.SerialException) as exc:
            self.jog_error(str(exc))
        return 'break'

    def jog_release(self):
        if self.returning:
            return
        command = self.jog.stop(time.monotonic())
        if command:
            try:
                self.send(command)
                self.controls()
                self.status.set('STOP manual enviado; esperando confirmación…')
            except (OSError, serial.SerialException) as exc:
                self.jog_error(str(exc))

    def check_jog_focus(self):
        if self.jog.active and self.root.focus_displayof() is None:
            self.stop()

    def jog_error(self, reason):
        self.returning = False
        if not self.demo and self.motor:
            try:
                self.motor.write(b'STOP\n')
            except (OSError, serial.SerialException):
                pass
        self.jog = JogController()
        self.connection_error(reason)

    def connect(self):
        if self.active or self.jog.active:
            return
        self.disconnect()
        self.esp_buffer, self.motor_buffer = LineBuffer(), LineBuffer()
        self.ready = self.sensor_ready = False
        self.return_supported = self.demo
        self.jog_supported = self.demo
        if self.demo:
            self.ready = self.sensor_ready = True
            self.travel.steps = 0
            self.update_travel()
            self.status.set('Demo connected — no hardware commands')
            self.controls()
            return
        try:
            esp, motor = self.esp_name.get().strip(), self.motor_name.get().strip()
            if not esp or not motor or esp.upper() == motor.upper():
                raise ValueError('Select two different ports: ESP32 and Mega.')
            self.esp = serial.Serial(esp, 115200, timeout=0, write_timeout=0.2)
            self.motor = serial.Serial(motor, 9600, timeout=0, write_timeout=0.2)
            self.connecting = True
            self.deadline = time.monotonic() + 7
            self.status.set('Waiting for Mega READY and valid ESP32 frames…')
            self.controls()
        except (OSError, serial.SerialException, ValueError) as exc:
            self.connection_error(str(exc))

    def disconnect(self):
        self.returning = False
        self.travel = TravelCalibration()
        self.zero.set(False)
        self.update_travel()
        for port in (self.esp, self.motor):
            if port:
                port.close()
        self.esp = self.motor = None

    def send(self, command):
        if not command:
            return
        if self.demo:
            if command.startswith(('JOG,', 'JOG_TO,')):
                self.jog.message('OK,JOG', time.monotonic())
            elif command == 'STOP' and self.jog.active:
                self.on_motor('STOPPED', time.monotonic())
                self.on_motor('READY', time.monotonic())
            elif command == 'STOP':
                self.demo_events = []
                self.on_motor('ABORTED', time.monotonic())
            return
        payload = (command + '\n').encode('ascii')
        if self.motor.write(payload) != len(payload):
            raise OSError('Incomplete motor command write.')

    def start(self):
        if self.active or self.jog.active or not self.ready or not self.sensor_ready:
            return
        if not self.saved and not messagebox.askyesno('Unsaved run', 'Discard the previous unsaved run?'):
            return
        try:
            if not self.zero.get():
                raise ValueError('Set the starting position to zero and confirm the hardware checkbox.')
            supply, alpha = float(self.supply.get()), float(self.alpha.get())
            if not math.isfinite(supply) or not 0.1 <= supply <= 3.6:
                raise ValueError('Supply must be between 0.1 and 3.6 V.')
            if not math.isfinite(alpha) or not 0 < alpha <= 1:
                raise ValueError('Smoothing alpha must be greater than zero and at most one.')
            fixed = float(self.fixed_resistor.get().replace(',', '.'))
            if not math.isfinite(fixed) or fixed <= 0:
                raise ValueError('La resistencia fija debe ser positiva, en ohmios.')
            if not self.sensor.get().strip():
                raise ValueError('Introduce o selecciona el nombre del sensor.')
            mechanics = Mechanics()  # Fixed calibration matching the motor firmware.
            for block in self.blocks:
                BENCH_LIMITS.validate(block)
            self.travel.validate(self.blocks)
            protocol = MotorProtocol(self.blocks, mechanics)
        except (ValueError, KeyError) as exc:
            messagebox.showerror('Configuration', str(exc))
            return
        if not self.demo and not messagebox.askokcancel('Start motor experiment',
                f'Run {len(self.blocks)} blocks, maximum {max(b.distance for b in self.blocks):g} mm?\n'
                f'Confirm {fixed:g} Ω is installed and the starting position is zero.'):
            return
        self.protocol = protocol
        self.data = Acquisition(supply, fixed)
        self.rows = []
        self.smoothing, self.filtered = alpha, None
        self.error = None
        self.outcome = 'Completed'
        self.saved = False
        self.started = self.last_sensor = time.monotonic()
        self.upload_progress = self.started
        self.baseline_start = None
        self.run_deadline = None
        self.demo_next = 0
        self.demo_events = []
        self.metadata = dict(Sensor=self.sensor.get(), GPIO=4, Fixed_resistor_ohm=fixed,
            Divider_supply_V=supply, Display_filter_alpha=alpha, Demo=self.demo,
            Started_local=datetime.now().isoformat(), ESP32_port=self.esp_name.get(),
            Mega_port=self.motor_name.get(), Displacement_method='commanded speed and host phase reception time',
            Steps_per_revolution=mechanics.steps_per_rev, Mm_per_revolution=mechanics.mm_per_rev,
            Motor_model='17HS4401',
            Motor_driver='A4988',
            Microstepping='1/16', Hardware_profile_source='SRBVM_2026____Banco_de_ensayos_.pdf, pages 2-3',
            Test_limits=vars(BENCH_LIMITS), Limits_status='provisional bench settings, not NEMA ratings',
            Synchronization='approximate host reception time; independent USB links',
            Protocol=[b.values() for b in self.blocks])
        try:
            if self.esp:
                self.esp.reset_input_buffer()
            self.esp_buffer = LineBuffer()
            self.active = True
            self.controls()
            self.send(self.protocol.begin())
            if self.demo:
                self.demo_upload()
            self.status.set('Uploading protocol; collecting pre-motion baseline…')
        except (OSError, serial.SerialException) as exc:
            self.abort(str(exc))

    def demo_upload(self):
        self.protocol.message('OK,CLEAR', time.monotonic())
        self.protocol.message('READY', time.monotonic())
        for n in range(1, len(self.blocks) + 1):
            self.protocol.message(f'OK,BLOCK,{n}', time.monotonic())
            self.protocol.message('READY', time.monotonic())

    def start_demo_motion(self, now):
        events = [(now, f'START_PROTOCOL,{len(self.protocol.blocks)}')]
        t = now
        for n, b in enumerate(self.protocol.blocks, 1):
            events.append((t, f'START_BLOCK,{n}'))
            for cycle in range(1, int(b.cycles) + 1):
                for phase, duration in [('FORWARD', b.distance / b.forward), ('HOLD_MAX', b.hold_max),
                                        ('BACKWARD', b.distance / b.backward), ('HOLD_ZERO', b.hold_zero)]:
                    events.append((t, f'START_{phase},{n},{cycle}'))
                    t += duration
                    events.append((t, f'END_{phase},{n},{cycle}'))
                events.append((t, f'END_CYCLE,{n},{cycle}'))
            events.append((t, f'START_BLOCK_HOLD,{n},0'))
            t += b.hold_after
            events.extend([(t, f'END_BLOCK_HOLD,{n}'), (t, f'END_BLOCK,{n}')])
        events.append((t, 'FIN'))
        self.demo_events = events

    def on_motor(self, line, now):
        if not line:
            return
        if line.startswith('M,'):
            fields = line.split(',')
            if len(fields) != 3 or int(fields[1]) < 0:
                raise ValueError('Telemetria de posicion invalida.')
            self.travel.steps = int(fields[2])
            self.update_travel()
        if line == 'CAPS,RETURN,1':
            self.return_supported = True
            return
        if line == 'CAPS,JOG,1':
            if self.active or self.jog.active:
                raise ValueError('Mega reiniciado durante el movimiento; referencia perdida.')
            self.travel = TravelCalibration()
            self.zero.set(False)
            self.update_travel()
            self.jog_supported = True
            return
        if self.jog.active:
            self.jog.message(line, now)
            if not self.jog.active:
                self.returning = False
                self.controls()
                self.status.set('Motor detenido. Establece el cero antes del ensayo.')
            return
        if self.connecting:
            if line == 'READY':
                self.ready = True
            elif line.startswith('ERROR'):
                raise ValueError(line)
            return
        if not self.active:
            return
        previous = self.protocol.stage
        command = self.protocol.message(line, now)
        self.send(command)
        if command or self.protocol.stage != previous:
            self.upload_progress = now
        if self.protocol.stage in ('finished', 'stopped'):
            self.finish('Error' if self.error else ('Completed' if self.protocol.stage == 'finished' else 'Stopped'))

    def accept(self, frame, now):
        if not self.active or self.protocol.stage == 'stopping':
            return
        row = self.data.add(frame, now - self.started)
        if self.baseline_start is None:
            self.baseline_start = now
        r0 = self.data.initial_resistance
        r = row[4]
        self.filtered = r if self.filtered is None else self.smoothing * r + (1-self.smoothing)*self.filtered
        self.rows.append((row[0], row[3], r, 100*(r-r0)/r0,
                          self.protocol.position(now), self.protocol.block, self.protocol.cycle,
                          self.protocol.phase, row[1], row[2], now-self.started, self.filtered,
                          self.protocol.revolutions(now), self.protocol.position_source,
                          self.protocol.motor_time_us))
        self.last_sensor = now

    def poll(self):
        now = time.monotonic()
        try:
            if self.demo and self.jog.active:
                dt = max(0, now - self.demo_jog_time)
                self.demo_jog_time = now
                self.demo_jog_steps += self.demo_jog_direction * self.demo_jog_speed * 1600 * dt
                if self.returning and (self.demo_jog_steps - self.travel.origin) * self.demo_jog_direction >= 0:
                    self.demo_jog_steps = self.travel.origin
                    self.on_motor('STOPPED', now)
                    self.on_motor('READY', now)
                self.travel.steps = round(self.demo_jog_steps)
                self.update_travel()
            if self.returning and now > self.return_deadline:
                raise ValueError('Tiempo de retorno excedido; reconecta y calibra de nuevo.')
            if self.jog.active:
                self.send(self.jog.tick(now))
            if self.motor:
                for line in self.motor_buffer.feed(self.motor.read(min(self.motor.in_waiting, 65536))):
                    self.on_motor(line, now)
            if self.esp:
                for line in self.esp_buffer.feed(self.esp.read(min(self.esp.in_waiting, 65536))):
                    frame = parse_frame(line)
                    if frame is not None:
                        self.sensor_ready = True
                        self.accept(frame, now)
                    elif self.active:
                        self.data.invalid += 1
            if self.demo and self.active:
                while self.demo_events and self.demo_events[0][0] <= now:
                    t, line = self.demo_events.pop(0)
                    self.on_motor(line, t)
                if self.active and (now-self.started) >= self.demo_next / 100:
                    # Demo samples are timestamped at actual UI reception, not fabricated catch-up bursts.
                    n = int((now-self.started)*100)
                    x = self.protocol.position(now)
                    r = 1250 * (1 + 0.02*x)
                    voltage = self.data.supply*self.data.fixed/(self.data.fixed+r)
                    self.accept(Frame(n, int((now-self.started)*1e6), voltage), now)
                    self.demo_next = n+1
            if self.connecting:
                if self.ready and self.sensor_ready:
                    self.connecting = False
                    self.status.set('Both boards connected')
                    self.controls()
                elif now > self.deadline:
                    raise ValueError('Connection timeout: need Mega READY and ESP32 S,sequence,time_us,Vout.')
            if self.active:
                stage = self.protocol.stage
                if stage == 'stopping':
                    if now > self.stop_deadline:
                        self.error = (self.error or '') + ' STOP was not acknowledged; motor state is unknown.'
                        self.ready = False
                        self.finish('Error')
                else:
                    if now-self.last_sensor > 2:
                        raise ValueError('No valid ESP32 samples for two seconds.')
                    if stage in ('uploading', 'starting') and now-self.upload_progress > 5:
                        raise ValueError('Motor command acknowledgment timed out.')
                    if stage == 'baseline' and self.baseline_start is not None and now-self.baseline_start >= 0.5:
                        self.travel.origin = 0
                        self.travel.steps = 0
                        self.send(self.protocol.baseline_ready())
                        self.upload_progress = now
                        self.run_deadline = now + sum(b.duration() for b in self.protocol.blocks)*2 + 30
                        if self.demo:
                            self.start_demo_motion(now)
                    if self.run_deadline and now > self.run_deadline:
                        raise ValueError('Motor protocol exceeded its estimated duration.')
                if now-self.last_plot >= 0.2:
                    self.draw()
                    self.last_plot = now
        except (OSError, serial.SerialException, ValueError) as exc:
            if self.jog.active:
                self.jog_error(str(exc))
            elif self.active:
                self.abort(str(exc))
            else:
                self.connection_error(str(exc))
        self.root.after(20, self.poll)

    def draw(self):
        if not self.rows:
            return
        r0 = self.data.initial_resistance
        rows = self.rows[-2500:]
        self.line.set_data([r[0] for r in rows], [r[11] for r in rows])
        self.ax.relim()
        self.ax.autoscale_view()
        r = rows[-1]
        self.readings.set(f'R: {r[2]:.3f} ohm | R0: {r0:.3f} ohm | Relativa: {r[3]:.3f}%\n'
                          f'Tiempo: {r[0]:.2f} s | Desplazamiento: {r[4]:.4f} mm\n'
                          f'Bloque {r[5]} | Ciclo {r[6]} | {r[7]}')
        self.status.set(f'{self.protocol.stage} · {len(self.rows)} samples · '
                        f'{self.data.dropped} dropped · {self.data.invalid} invalid' + (' · DEMO' if self.demo else ''))
        self.canvas.draw_idle()

    def stop(self):
        if self.jog.active:
            self.returning = False
            self.jog_release()
            return
        if not self.active or self.protocol.stage == 'stopping':
            return
        self.stop_deadline = time.monotonic()+4
        try:
            self.send(self.protocol.stop())
            if self.active:
                self.status.set('STOP sent; waiting for Mega confirmation…')
        except (OSError, serial.SerialException) as exc:
            self.error = f'STOP transmission failed: {exc}. Motor state is unknown.'
            self.ready = False
            self.finish('Error')

    def abort(self, reason):
        self.error = reason
        if self.protocol.stage == 'stopping':
            self.error += ' Communication failed while waiting for STOP; motor state is unknown.'
            self.ready = False
            self.finish('Error')
            return
        self.stop()

    def finish(self, outcome):
        self.active = False
        self.outcome = outcome
        if self.demo:
            self.travel.steps = round(self.protocol.position(time.monotonic()) * 1600)
        if not self.ready:
            self.travel = TravelCalibration()
        self.update_travel()
        self.zero.set(False)
        self.controls()
        self.draw()
        self.status.set(f'{outcome}: {self.error or str(len(self.rows)) + " samples"}')
        # Ask only after the serial loop has processed the motor's final messages.
        if self.rows:
            self.root.after_idle(self.offer_save)

    def offer_save(self):
        if not self.active and self.rows and not self.saved:
            if messagebox.askyesno('Guardar ensayo',
                                  'La prueba ha terminado. ¿Quieres guardar los datos en CSV?',
                                  parent=self.root):
                self.save()
            else:
                self.status.set('Prueba finalizada sin guardar. Los datos siguen disponibles en memoria.')

    def suggested_filename(self):
        parts = []
        for n, block in enumerate(self.protocol.blocks, 1):
            values = [format(v, '.6g').replace('.', 'p') for v in block.values()]
            c, d, f, hm, b, hz, ha = values
            parts.append(f'B{n}-{c}c-{d}mm-F{f}-HM{hm}-R{b}-HZ{hz}-HA{ha}')
        prefix = 'DEMO_' if self.demo else ''
        return f'{prefix}{"__".join(parts)}_{datetime.now():%Y%m%d_%H%M%S}.csv'

    def write_results(self, path):
        try:
            with path.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(['Time_s', 'Resistance_ohm', 'Relative_resistance_percent',
                                 'Displacement_mm'])
                for row in self.rows:
                    writer.writerow([f'{v:.6f}' if isinstance(v, float) else v
                                     for v in (row[0], row[2], row[3], row[4])])
            self.saved = True
            self.status.set(f'{self.outcome} · saved {path.name}' + (f' · {self.error}' if self.error else ''))
        except OSError as exc:
            self.saved = False
            self.status.set(f'Save failed: {exc}. Data retained; use Save results as…')

    def save(self):
        if self.active:
            messagebox.showinfo('Save', 'Stop the motor and wait for confirmation before saving.')
            return
        if not self.rows:
            return
        filename = filedialog.asksaveasfilename(parent=self.root, title='Guardar datos del ensayo',
            defaultextension='.csv', filetypes=[('CSV', '*.csv')],
            initialfile=self.suggested_filename())
        if filename:
            self.write_results(Path(filename))

    def connection_error(self, reason):
        self.connecting = self.ready = self.sensor_ready = False
        self.disconnect()
        self.controls()
        self.status.set(reason)

    def close(self):
        if self.jog.active:
            self.stop()
            self.status.set('Deteniendo movimiento manual. Cierra de nuevo tras la confirmación.')
            return
        if self.active:
            self.stop()
            self.status.set('Stopping. Close again after motor confirmation and saving.')
            return
        if not self.saved and not messagebox.askyesno('Unsaved results', 'Discard unsaved results and close?'):
            return
        self.disconnect()
        self.root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Simulate both boards without opening serial ports')
    args = parser.parse_args()
    root = tk.Tk()
    App(root, demo=args.demo)
    root.mainloop()
