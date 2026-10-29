import tempfile
import unittest
from pathlib import Path

from plot_sensor_test import make_figure, read_measurements
from sensor_core import Acquisition, Frame


class PlotDataTests(unittest.TestCase):
    def test_compare_csvs_with_independent_baselines_and_shared_colors(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'first.csv'
            second = Path(directory) / 'second.csv'
            first.write_text('Time_s,Resistance_ohm\n0,100\n1,150\n')
            second.write_text('Time_s,Resistance_ohm\n0,200\n2,180\n3,220\n')
            figure = make_figure([first, second])
            try:
                resistance, relative, displacement = figure.axes
                self.assertEqual(len(resistance.lines), 2)
                self.assertFalse(displacement.lines)
                self.assertIn('Sin Displacement_mm', displacement.texts[0].get_text())
                self.assertEqual(list(relative.lines[0].get_ydata()), [0, 50])
                self.assertEqual(list(relative.lines[1].get_ydata()), [0, -10, 10])
                self.assertEqual(list(resistance.lines[1].get_xdata()), [0, 2, 3])
                for index in (0, 1):
                    self.assertEqual(resistance.lines[index].get_color(), relative.lines[index].get_color())
                self.assertIn('second.csv', resistance.get_legend().get_texts()[1].get_text())
                output = Path(directory) / 'comparison.png'
                figure.savefig(output)
                self.assertGreater(output.stat().st_size, 0)
            finally:
                plt.close(figure)
            # Keep supporting existing callers that pass a single path.
            figure = make_figure(first)
            self.assertEqual(len(figure.axes[0].lines), 1)
            plt.close(figure)
            second.write_text('Time_s,Resistance_ohm\n0,broken\n')
            with self.assertRaisesRegex(ValueError, 'second.csv'):
                make_figure([first, second])

    def test_displacement_overlay_preserves_cycles_and_independent_axis(self):
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / 'motor.csv'
            second = Path(directory) / 'motor2.csv'
            first.write_text('Time_s,Resistance_ohm,Displacement_mm\n0,100,0\n1,150,5\n2,120,0\n')
            second.write_text('Time_s;Resistance_ohm;Displacement_mm\n0;200;0\n3;220;2,5\n')
            figure = make_figure([first, second])
            try:
                time_axis, relative_axis, displacement_axis = figure.axes
                self.assertEqual(list(displacement_axis.lines[0].get_xdata()), [0, 5, 0])
                self.assertEqual(list(displacement_axis.lines[0].get_ydata()), [0, 50, 20])
                self.assertEqual(list(displacement_axis.lines[1].get_xdata()), [0, 2.5])
                self.assertEqual(list(displacement_axis.lines[1].get_ydata()), [0, 10])
                self.assertEqual(displacement_axis.lines[1].get_color(), time_axis.lines[1].get_color())
                self.assertTrue(time_axis.get_shared_x_axes().joined(time_axis, relative_axis))
                self.assertFalse(time_axis.get_shared_x_axes().joined(time_axis, displacement_axis))
            finally:
                plt.close(figure)
            second.write_text('Time_s,Resistance_ohm,Displacement_mm\n0,200,nan\n')
            with self.assertRaisesRegex(ValueError, 'motor2.csv'):
                make_figure([first, second])

    def test_export_roundtrip(self):
        data = Acquisition(3.3, 2400)
        for n, voltage in enumerate([1.65, 1.32, 2.2]):
            data.add(Frame(n, n * 10000, voltage), n * 0.01)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.csv'
            with path.open('w', newline='') as stream:
                data.write_csv(stream)
            times, resistance, relative = read_measurements(path)
            self.assertEqual(times, [0, 0.01, 0.02])
            self.assertEqual(resistance, [2400, 3600, 1200])
            self.assertEqual(relative, [0, 50, -50])

    def test_decimal_comma_and_corrupt_spreadsheet(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'run.csv'
            path.write_text('Time_s;Voltage_V;Resistance_ohm\n0;1,65;2400\n0,01;1,32;3600\n')
            self.assertEqual(read_measurements(path)[2], [0, 50])
            path.write_text('Time_s,Voltage_V,Resistance_ohm\n0,220.375,11.938.740.782.756.600\n')
            with self.assertRaisesRegex(ValueError, 'original acquisition CSV'):
                read_measurements(path)
            path.write_text('Sensor,GPIO\nSensor 2,4\n')
            with self.assertRaisesRegex(ValueError, 'metadata'):
                read_measurements(path)


if __name__ == '__main__':
    unittest.main()
