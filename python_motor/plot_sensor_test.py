"""Select an acquisition CSV and plot resistance and relative resistance."""
import argparse
import csv
import math
from pathlib import Path


def read_measurements(path):
    """Read original dot-decimal CSVs or semicolon/comma-decimal CSVs.

    Relative resistance is recalculated from the first resistance sample.
    Ambiguous grouped numbers are rejected rather than silently repaired.
    """
    times, resistances = [], []
    with Path(path).open(newline='', encoding='utf-8-sig') as stream:
        first = stream.readline()
        delimiter = ';' if ';' in first else ','
        stream.seek(0)
        reader = csv.DictReader(stream, delimiter=delimiter)
        required = {'Time_s', 'Resistance_ohm'}
        if not required.issubset(reader.fieldnames or []):
            raise ValueError('Select the measurement CSV with Time_s and Resistance_ohm '
                             'columns, not the metadata CSV.')
        for number, row in enumerate(reader, start=2):
            if not any(row.values()):
                continue
            try:
                if None in row:
                    raise ValueError('extra columns')
                def numeric(name):
                    text = row[name].strip()
                    if delimiter == ';':
                        text = text.replace(',', '.')
                    value = float(text)
                    if not math.isfinite(value):
                        raise ValueError('nonfinite value')
                    return value
                t, r = numeric('Time_s'), numeric('Resistance_ohm')
                if t < 0 or r <= 0:
                    raise ValueError('negative time or nonpositive resistance')
                if times and t <= times[-1]:
                    raise ValueError('time must increase')
                if 'Voltage_V' in row and not 0 < numeric('Voltage_V') < 3.4:
                    raise ValueError('voltage outside ESP32 range')
            except (ValueError, TypeError, AttributeError) as exc:
                raise ValueError(f'Invalid data on CSV line {number}: {exc}. '
                                 'Use the original acquisition CSV. A spreadsheet may '
                                 'have interpreted decimal points as thousands separators.') from exc
            times.append(t)
            resistances.append(r)
    if not times:
        raise ValueError('The selected CSV contains no measurements.')
    r0 = resistances[0]
    relative = [100 * (r - r0) / r0 for r in resistances]
    return times, resistances, relative


def make_figure(path):
    import matplotlib.pyplot as plt

    times, resistances, relative = read_measurements(path)
    figure, axes = plt.subplots(2, 1, sharex=True, figsize=(10, 7),
                                constrained_layout=True)
    figure.suptitle(f'{Path(path).name}\nInitial resistance R₀ = {resistances[0]:.3f} Ω')
    axes[0].plot(times, resistances, color='tab:blue', linewidth=1)
    axes[0].set_ylabel('Resistance (Ω)')
    axes[0].ticklabel_format(axis='y', style='plain', useOffset=False)
    axes[1].plot(times, relative, color='tab:orange', linewidth=1)
    axes[1].axhline(0, color='gray', linewidth=0.7, linestyle='--')
    axes[1].set_ylabel('ΔR/R₀ × 100 (%)')
    axes[1].set_xlabel('Time (s)')
    for ax in axes:
        ax.grid(alpha=0.3)
    return figure


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', nargs='?', help='CSV path; omit to open a file selector')
    parser.add_argument('--output', type=Path, help='Also save the figure, e.g. plot.png')
    parser.add_argument('--no-show', action='store_true', help='Save without opening a plot window')
    args = parser.parse_args()
    if args.no_show and not args.output:
        parser.error('--no-show requires --output')
    root = None
    try:
        path = args.csv
        if not path:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(title='Select sensor acquisition CSV',
                                              filetypes=[('CSV files', '*.csv')])
            if not path:
                return
        if args.no_show:
            import matplotlib
            matplotlib.use('Agg')
        figure = make_figure(path)
        if args.output:
            figure.savefig(args.output, dpi=180)
            print(f'Saved {args.output}')
        if root:
            root.destroy()
            root = None
        import matplotlib.pyplot as plt
        if not args.no_show:
            plt.show()
        plt.close(figure)
    except (OSError, ValueError) as exc:
        if root:
            from tkinter import messagebox
            messagebox.showerror('Cannot plot CSV', str(exc), parent=root)
        parser.exit(1, f'{exc}\n')
    finally:
        if root:
            root.destroy()


if __name__ == '__main__':
    main()
