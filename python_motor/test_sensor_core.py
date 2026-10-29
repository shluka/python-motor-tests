import unittest
import csv
import io
from sensor_core import Acquisition, Frame, parse_frame, resistance


class ProtocolTests(unittest.TestCase):
    def test_csv_baseline_and_relative_resistance(self):
        data = Acquisition(3.3, 2400)
        # R=2400, 3600, 1200 ohm: relative changes 0%, +50%, -50%.
        for n, voltage in enumerate([1.65, 1.32, 2.2]):
            data.add(Frame(n, 1000000 + n * 10000, voltage), n * 0.02)
        stream = io.StringIO()
        data.write_csv(stream)
        stream.seek(0)
        reader = csv.DictReader(stream)
        self.assertEqual(reader.fieldnames, ['Time_s', 'Voltage_V', 'Resistance_ohm',
                                            'Relative_resistance_percent'])
        rows = list(reader)
        self.assertAlmostEqual(data.initial_resistance, 2400)
        for row, t, expected in zip(rows, [0, 0.01, 0.02], [0, 50, -50]):
            self.assertAlmostEqual(float(row['Time_s']), t)
            self.assertAlmostEqual(float(row['Relative_resistance_percent']), expected)
        self.assertIsNone(Acquisition(3.3, 2400).initial_resistance)

    def test_parser(self):
        self.assertEqual(parse_frame('S,123,456000,1.650000\r\n'), Frame(123, 456000, 1.65))
        for value in ['boot', 'S,1,2,nan', 'S,-1,2,1', 'S,1.5,2,1', 'S,1,2,inf', 'S,1,2,3.5']:
            self.assertIsNone(parse_frame(value))

    def test_divider(self):
        self.assertAlmostEqual(resistance(1.65, 3.3, 1500), 1500)
        for voltage in [0, 0.01, 3.05, 3.3, float('nan')]:
            with self.assertRaises(ValueError):
                resistance(voltage, 3.3, 1500)

    def test_timing_gaps_and_reset(self):
        data = Acquisition(3.3, 1500)
        data.add(Frame(100, 5000000, 1.65), 0.2)
        row = data.add(Frame(103, 5030000, 1.65), 0.9)
        self.assertEqual(data.dropped, 2)
        self.assertAlmostEqual(row[0], 0.03)
        with self.assertRaises(ValueError):
            data.add(Frame(0, 0, 1.65), 1)
        with self.assertRaises(ValueError):
            data.add(Frame(104, 5030000, 1.65), 1)


if __name__ == '__main__':
    unittest.main()
