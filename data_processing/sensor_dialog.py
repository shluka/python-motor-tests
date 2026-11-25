SENSORS = ('Sensor 1', 'Sensor 2', 'Sensor 3', 'Sensor 4')


def choose_sensor(parent):
    from tkinter import simpledialog, ttk

    class SensorDialog(simpledialog.Dialog):
        def body(self, master):
            ttk.Label(master, text='Sensor del ensayo').pack(pady=(0, 4))
            self.sensor = ttk.Combobox(
                master, values=SENSORS,
                state='readonly',
            )
            self.sensor.current(0)
            self.sensor.pack()
            return self.sensor

        def apply(self):
            self.result = self.sensor.get()

    return SensorDialog(parent, title='Selecciona el sensor').result
