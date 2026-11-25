"""Compara la resistencia relativa de un sensor a 0.1, 0.5 y 1 mm/s."""
import argparse
import math
from pathlib import Path

from python_motor.plot_sensor_test import read_measurements
from .sensor_dialog import choose_sensor


def make_figure(runs, sensor):
    import matplotlib.pyplot as plt

    measurements = []
    for speed, path in runs:
        try:
            times, _, relative = read_measurements(path)
        except (OSError, ValueError) as exc:
            raise ValueError(f'{speed} mm/s ({path}): {exc}') from exc
        finite = [value for value in relative if math.isfinite(value)]
        if not finite:
            raise ValueError(f'{speed} mm/s ({path}): el CSV no contiene resistencia calculable.')
        measurements.append((speed, times, relative, min(finite), max(finite)))

    figure, axis = plt.subplots(figsize=(9, 5), layout='constrained')
    spacing = 0.2 * max((high - low for _, _, _, low, high in measurements), default=0)
    if spacing == 0:
        spacing = 1
    bottom = 0
    colors = ("#0A8F05", '#c62828', '#174bb5')
    # Stack from bottom to top, keeping the lowest speed at the top.
    for (speed, times, relative, low, high), color in reversed(list(zip(measurements, colors))):
        offset = bottom - low
        shifted = [value + offset for value in relative]
        axis.plot(times, shifted, color=color)
        last = next(i for i in range(len(shifted) - 1, -1, -1) if math.isfinite(shifted[i]))
        axis.annotate(f'{speed} mm/s', (times[last], shifted[last]),
                      xytext=(5, 0), textcoords='offset points', va='center',
                      color=color, fontsize=14, fontweight='bold')
        bottom += high - low + spacing

    axis.set_title(f'Ensayos de velocidad - {sensor}', fontsize=17)
    axis.set_xlabel('Tiempo (s)', fontsize=16, fontweight='bold')
    axis.set_ylabel(r'$\mathbf{\Delta R/R_0}$ (%)', fontsize=16, fontweight='bold')
    axis.set_yticks([])
    axis.tick_params(axis='x', labelsize=13)
    axis.margins(x=0.17, y=0.1)
    first_time = min(times[0] for _, times, _, _, _ in measurements)
    axis.set_xlim(left=first_time)
    return figure


def select_runs():
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        sensor = choose_sensor(root)
        if sensor is None:
            return None

        runs = []
        for speed in ('0.1', '0.5', '1'):
            selected = filedialog.askopenfilename(
                parent=root, title=f'Selecciona el CSV de {sensor} a {speed} mm/s',
                filetypes=[('CSV', '*.csv')],
            )
            if not selected:
                return None
            runs.append((speed, Path(selected)))
        return sensor, runs
    finally:
        root.destroy()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Ruta de salida, por ejemplo sensor.png')
    parser.add_argument('--no-show', action='store_true', help='Guarda la figura sin abrir una ventana')
    args = parser.parse_args()
    if args.no_show and not args.output:
        parser.error('--no-show requiere --output')

    selection = select_runs()
    if selection is None:
        return
    sensor, runs = selection

    if args.no_show:
        import matplotlib
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    try:
        figure = make_figure(runs, sensor)
        if args.output:
            figure.savefig(args.output, dpi=180)
        if not args.no_show:
            plt.show()
        plt.close(figure)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    main()
