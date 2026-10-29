import tempfile
import unittest
from pathlib import Path

from plot_sensor_test import read_measurements
from sensor_core import Acquisition, Frame


class PlotDataTests(unittest.TestCase):
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
