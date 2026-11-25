"""Compara tres ensayos de aristas y tres de vértices de un sensor."""
import argparse
import math
from pathlib import Path

from python_motor.plot_sensor_test import read_measurements
from .sensor_dialog import choose_sensor


def make_figure(runs, sensor, group):
    import matplotlib.pyplot as plt

    measurements = []
    for label, path in runs:
        try:
            times, _, relative = read_measurements(path)
            if not any(map(math.isfinite, relative)):
                raise ValueError('El CSV no contiene resistencia calculable.')
        except (OSError, ValueError) as exc:
            raise ValueError(f'{label} ({path}): {exc}') from exc
        measurements.append((label, times, relative))

    figure, axis = plt.subplots(figsize=(10, 5), layout='constrained')
    for label, times, relative in measurements:
        axis.plot(times, relative, label=label)
    axis.set_title(f'Ensayos cíclicos - {sensor} - {group}', fontsize=17)
    axis.set_xlabel('Tiempo (s)', fontsize=16, fontweight='bold')
    axis.set_ylabel(r'$\mathbf{\Delta R/R_0}$ (%)', fontsize=16, fontweight='bold')
    axis.tick_params(labelsize=13)
    axis.grid(alpha=0.3)
    axis.legend()
    first = min(times[0] for _, times, _ in measurements)
    last = max(times[-1] for _, times, _ in measurements)
    axis.set_xlim(first, last + 10)
    return figure


def main():
    import tkinter as tk
    from tkinter import filedialog

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, help='Nombre base de los PNG de aristas y vértices')
    parser.add_argument('--no-show', action='store_true', help='Guarda el PNG sin mostrar la gráfica')
    args = parser.parse_args()
    if args.no_show and not args.output:
        parser.error('--no-show requiere --output')

    root = tk.Tk()
    root.withdraw()
    try:
        sensor = choose_sensor(root)
        if sensor is None:
            return

        groups = []
        for group, suffix in (('Aristas', 'aristas'), ('Vértices', 'vertices')):
            runs = []
            for number in range(1, 4):
                label = f'Ensayo {number}'
                path = filedialog.askopenfilename(
                    parent=root, title=f'{sensor} - {group} - {label}',
                    filetypes=[('CSV', '*.csv')],
                )
                if not path:
                    return
                runs.append((label, path))
            groups.append((group, suffix, runs))
    finally:
        root.destroy()

    if args.no_show:
        import matplotlib
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    open_figures = set(plt.get_fignums())
    try:
        figures = [(suffix, make_figure(runs, sensor, group))
                   for group, suffix, runs in groups]
        if args.output:
            for suffix, figure in figures:
                path = args.output.with_name(f'{args.output.stem}_{suffix}.png')
                figure.savefig(path, dpi=180)
        if not args.no_show:
            plt.show()
    except (OSError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')
    finally:
        for number in set(plt.get_fignums()) - open_figures:
            plt.close(number)


if __name__ == '__main__':
    main()
