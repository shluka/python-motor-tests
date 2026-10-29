"""Run with python python/main_sensor_test.py (or add --demo)."""
import argparse
import csv
import math
import time
from collections import deque
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import serial
from serial.tools import list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from sensor_core import Acquisition, Frame, SENSORS, parse_frame


class App:
    def __init__(self, root, demo=False, sensor='Sensor 1', port=None, autostart=False):
        self.root, self.demo = root, demo
        self.autostart = autostart
        self.port = None
        self.buffer = bytearray()
        self.running = False
        self.checking = False
        self.data = None
        self.saved = True
        self.outcome = 'Completed'
        self.plot_rows = deque(maxlen=2500)
        root.title('ESP32-S3 sensor test' + (' — DEMO' if demo else ''))
        root.geometry('1180x700')
        root.protocol('WM_DELETE_WINDOW', self.close)
        panel = ttk.Frame(root, padding=14)
        panel.pack(side='left', fill='y')
        self.sensor = tk.StringVar(value=sensor)
        self.supply = tk.StringVar(value='3.3')
        self.port_name = tk.StringVar()
        self.status = tk.StringVar(value='Disconnected')
        self.reading = tk.StringVar(value='Vout: —\nResistance: —')
        ttk.Label(panel, text='Sensor configuration', font=('', 14, 'bold')).pack()
        self.sensor_box = ttk.Combobox(panel, textvariable=self.sensor,
                                       values=list(SENSORS), state='readonly')
        self.sensor_box.pack(fill='x', pady=8)
        self.sensor_box.bind('<<ComboboxSelected>>', self.instructions)
        ttk.Label(panel, text='Measured divider supply (V)').pack(anchor='w')
        self.supply_entry = ttk.Entry(panel, textvariable=self.supply)
        self.supply_entry.pack(fill='x')
        self.hardware = ttk.Label(panel, wraplength=300, justify='left')
        self.hardware.pack(pady=14)
        self.ports = ttk.Combobox(panel, textvariable=self.port_name, state='readonly')
        self.ports.pack(fill='x')
        self.refresh_button = ttk.Button(panel, text='Refresh ports', command=self.refresh)
        self.refresh_button.pack(fill='x', pady=4)
        self.connect_button = ttk.Button(panel, text='Connect ESP32', command=self.connect)
        self.connect_button.pack(fill='x', pady=4)
        self.start_button = ttk.Button(panel, text='Start acquisition', command=self.start,
                                       state='disabled')
        self.start_button.pack(fill='x', pady=4)
        self.stop_button = ttk.Button(panel, text='Stop and save', command=self.stop,
                                      state='disabled')
        self.stop_button.pack(fill='x', pady=4)
        ttk.Button(panel, text='Save acquisition…', command=self.save).pack(fill='x', pady=4)
        ttk.Label(panel, textvariable=self.reading, font=('', 13)).pack(pady=12)
        ttk.Label(panel, textvariable=self.status, wraplength=300).pack()
        figure = Figure(figsize=(7, 5), tight_layout=True)
        self.ax = figure.add_subplot()
        self.ax.set_xlabel('ESP32 elapsed time (s)')
        self.ax.set_ylabel('Resistance (Ω)')
        self.ax.grid(alpha=0.25)
        self.line, = self.ax.plot([], [], linewidth=1.5)
        self.canvas = FigureCanvasTkAgg(figure, master=root)
        self.canvas.get_tk_widget().pack(side='right', fill='both', expand=True)
        self.instructions()
        self.refresh()
        if port:
            self.port_name.set(port)
        self.last_plot = 0
        self.root.after(20, self.poll)
        if autostart:
            self.root.after(100, self.connect)

    def instructions(self, *_):
        fixed, low, high = SENSORS[self.sensor.get()]
        self.hardware.config(text=f'GPIO4 · fixed resistor: {fixed:g} Ω\n'
                             f'Expected sensor range: {low:g}–{high:g} Ω\n\n'
                             '3V3 → sensor → GPIO4 → fixed resistor → GND\n\n'
                             'Install the indicated fixed resistor before starting.')

    def refresh(self):
        names = [p.device for p in list_ports.comports()]
        self.ports['values'] = names
        if self.port_name.get() not in names:
            self.port_name.set(names[0] if names else '')

    def connect(self):
        if self.port:
            self.port.close()
            self.port = None
        self.start_button.config(state='disabled')
        if self.demo:
            self.status.set('Demo connected — simulated measurements')
            self.start_button.config(state='normal')
            if self.autostart:
                self.autostart = False
                self.start(hardware_confirmed=True)
            return
        try:
            if not self.port_name.get():
                raise ValueError('Select an ESP32 serial port first.')
            self.port = serial.Serial(self.port_name.get(), 115200, timeout=0)
            self.port.reset_input_buffer()
            self.buffer.clear()
            self.checking = True
            self.deadline = time.monotonic() + 5
            self.connect_button.config(state='disabled')
            self.status.set('Checking ESP32 stream…')
        except (serial.SerialException, OSError, ValueError) as exc:
            self.fail(str(exc))

    def start(self, hardware_confirmed=False):
        if not self.saved and not messagebox.askyesno('Unsaved data', 'Discard the previous unsaved acquisition?'):
            return
        try:
            supply = float(self.supply.get())
            if not math.isfinite(supply) or not 0.1 <= supply <= 3.6:
                raise ValueError('Supply must be between 0.1 and 3.6 V.')
        except ValueError as exc:
            messagebox.showerror('Divider supply', str(exc))
            return
        fixed, low, high = SENSORS[self.sensor.get()]
        if not hardware_confirmed and not messagebox.askokcancel('Check hardware',
                                      f'Install {fixed:g} Ω and connect {self.sensor.get()} to GPIO4.'):
            return
        try:
            if self.port:
                self.port.reset_input_buffer()
        except (serial.SerialException, OSError) as exc:
            self.fail(str(exc))
            return
        self.buffer.clear()
        self.data = Acquisition(supply, fixed)
        self.metadata = dict(Sensor=self.sensor.get(), GPIO=4, Fixed_resistor_ohm=fixed,
                             Divider_supply_V=supply, Expected_min_ohm=low, Expected_max_ohm=high,
                             Demo=self.demo, Started_local=datetime.now().isoformat())
        self.saved = False
        self.outcome = 'Completed'
        self.plot_rows.clear()
        self.line.set_data([], [])
        self.running = True
        self.started = self.last_frame = time.monotonic()
        self.demo_sequence = 0
        self.controls(True)
        self.status.set('Acquiring…')

    def controls(self, active):
        self.sensor_box.config(state='disabled' if active else 'readonly')
        self.supply_entry.config(state='disabled' if active else 'normal')
        self.connect_button.config(state='disabled' if active else 'normal')
        self.start_button.config(state='normal' if not active and (self.port or self.demo) else 'disabled')
        self.stop_button.config(state='normal' if active else 'disabled')
        self.ports.config(state='disabled' if active else 'readonly')
        self.refresh_button.config(state='disabled' if active else 'normal')

    def accept(self, frame, now):
        row = self.data.add(frame, now - self.started)
        self.plot_rows.append(row)
        self.last_frame = now
        self.reading.set(f'Vout: {row[3]:.6f} V\nResistance: {row[4]:.2f} Ω')

    def poll(self):
        now = time.monotonic()
        try:
            if self.demo and self.running:
                target = int((now - self.started) * 100)
                while self.demo_sequence <= target:
                    n = self.demo_sequence
                    _, low, high = SENSORS[self.metadata['Sensor']]
                    r = (low + high) / 2 + (high - low) * 0.4 * math.sin(n / 100)
                    v = self.data.supply * self.data.fixed / (self.data.fixed + r)
                    self.accept(Frame(n, n * 10000, v), now)
                    self.demo_sequence += 1
            elif self.port:
                self.buffer.extend(self.port.read(min(self.port.in_waiting, 65536)))
                while b'\n' in self.buffer:
                    raw, _, tail = self.buffer.partition(b'\n')
                    self.buffer = bytearray(tail)
                    frame = parse_frame(raw.decode('ascii', errors='replace'))
                    if frame is None:
                        if self.running:
                            self.data.invalid += 1
                        continue
                    if self.checking:
                        self.checking = False
                        self.connect_button.config(state='normal')
                        self.start_button.config(state='normal')
                        self.status.set(f'Connected: {self.port.port}')
                        if self.autostart:
                            self.autostart = False
                            self.start(hardware_confirmed=True)
                            # start() flushes the stream; ignore this older frame.
                            continue
                    if self.running:
                        self.accept(frame, now)
                if len(self.buffer) > 4096:
                    raise ValueError('Serial line exceeds the protocol size limit.')
            if self.checking and now > self.deadline:
                raise ValueError('No valid ESP32 frames received within five seconds.')
            if self.running and now - self.last_frame > 2:
                raise ValueError('No valid ESP32 measurements for two seconds.')
            if self.running and now - self.last_plot >= 0.1:
                self.draw()
                self.status.set(f'{len(self.data.rows)} samples · {self.data.dropped} dropped · '
                                f'{self.data.invalid} invalid' + (' · DEMO' if self.demo else ''))
                self.last_plot = now
        except (serial.SerialException, OSError, ValueError) as exc:
            self.fail(str(exc))
        self.root.after(20, self.poll)

    def draw(self):
        if self.plot_rows:
            self.line.set_data([r[0] for r in self.plot_rows], [r[4] for r in self.plot_rows])
            end = self.plot_rows[-1][0]
            self.ax.set_xlim(max(0, end - 20), max(20, end + 0.1))
            self.ax.relim()
            self.ax.autoscale_view(scalex=False)
        self.canvas.draw_idle()

    def stop(self):
        self.running = False
        self.controls(False)
        self.draw()
        self.status.set(f'Stopped: {len(self.data.rows)} samples')
        self.save()

    def fail(self, reason):
        was_running = self.running
        self.running = self.checking = False
        if self.port:
            self.port.close()
            self.port = None
        self.controls(False)
        self.status.set(reason)
        if was_running:
            self.outcome = 'Error'
            self.draw()
        messagebox.showerror('ESP32 acquisition', reason)
        if was_running:
            self.save()

    def save(self):
        if not self.data or not self.data.rows:
            return
        if self.running:
            messagebox.showinfo('Save', 'Stop acquisition before saving.')
            return
        filename = filedialog.asksaveasfilename(defaultextension='.csv',
            filetypes=[('CSV', '*.csv')], initialfile=
            f"{self.metadata['Sensor'].replace(' ', '_')}_{datetime.now():%Y%m%d_%H%M%S}.csv")
        if not filename:
            return
        path = Path(filename)
        metadata = dict(self.metadata, Outcome=self.outcome,
                        Initial_resistance_ohm=self.data.initial_resistance,
                        Relative_resistance_formula='100 * (R - R0) / R0',
                        Dropped_frames=self.data.dropped, Invalid_frames=self.data.invalid)
        try:
            with path.open('w', newline='', encoding='utf-8') as stream:
                self.data.write_csv(stream)
            with path.with_name(path.stem + '_metadata.csv').open('w', newline='', encoding='utf-8') as stream:
                writer = csv.DictWriter(stream, fieldnames=list(metadata))
                writer.writeheader()
                writer.writerow(metadata)
        except OSError as exc:
            messagebox.showerror('Save failed', str(exc))
            return
        self.saved = True
        self.status.set(f'Saved {path.name}')

    def close(self):
        if self.running:
            if not messagebox.askokcancel('Close', 'Stop acquisition and close?'):
                return
            self.outcome = 'Stopped'
            self.stop()
        if self.data and self.data.rows and not self.saved:
            if not messagebox.askyesno('Unsaved data', 'Close and discard unsaved measurements?'):
                return
        if self.port:
            self.port.close()
        self.root.destroy()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Simulate the sensor without hardware')
    parser.add_argument('--sensor', choices=list(SENSORS), default='Sensor 1')
    parser.add_argument('--port', help='Serial port, for example COM29')
    parser.add_argument('--start', action='store_true',
                        help='Connect and start immediately; confirms the selected preset resistor is installed')
    args = parser.parse_args()
    root = tk.Tk()
    App(root, demo=args.demo, sensor=args.sensor, port=args.port, autostart=args.start)
    root.mainloop()
