import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from main_motor_test import App
from motor_core import Block, MotorProtocol
from sensor_core import Acquisition, Frame


class Status:
    def set(self, text):
        self.text = text


class ExportTests(unittest.TestCase):
    def test_custom_resistor_and_motor_csv(self):
        # Exercise real GUI acquisition/export logic without creating a window or a serial port.
        app = App.__new__(App)
        app.active, app.started, app.baseline_start = True, 0, None
        app.protocol = MotorProtocol([Block()])
        app.data = Acquisition(3.3, 4700)
        app.rows = []
        app.smoothing, app.filtered = 1, None
        app.accept(Frame(0, 10000, 1.65), 1)
        app.protocol.message('M,20000,800', 1.01)
        app.accept(Frame(1, 20000, 1.1), 1.01)
        app.metadata, app.error, app.outcome, app.status = {}, None, 'Completed', Status()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'run.csv'
            app.write_results(path)
            self.assertTrue(app.saved)
            with path.open() as stream:
                reader = csv.DictReader(stream)
                self.assertEqual(reader.fieldnames, ['Time_s', 'Resistance_ohm',
                    'Relative_resistance_percent', 'Displacement_mm'])
                rows = list(reader)
            self.assertAlmostEqual(float(rows[0]['Resistance_ohm']), 4700)
            self.assertAlmostEqual(float(rows[1]['Relative_resistance_percent']), 100)
            self.assertEqual(float(rows[1]['Displacement_mm']), .5)
            self.assertEqual(list(Path(directory).iterdir()), [path])

    def test_filename_contains_frozen_protocol(self):
        app = App.__new__(App)
        app.demo = False
        app.protocol = MotorProtocol([Block(3, 5, 1, 2, .5, 3, 4)])
        self.assertTrue(app.suggested_filename().startswith('B1-3c-5mm-F1-HM2-R0p5-HZ3-HA4_'))

    def test_declining_save_does_not_write(self):
        app = App.__new__(App)
        app.active, app.saved, app.rows, app.root, app.status = False, False, [(0,)], None, Status()
        with patch('main_motor_test.messagebox.askyesno', return_value=False), \
                patch.object(app, 'save') as save:
            app.offer_save()
            save.assert_not_called()
        with patch('main_motor_test.messagebox.askyesno', return_value=True), \
                patch.object(app, 'save') as save:
            app.offer_save()
            save.assert_called_once()


if __name__ == '__main__':
    unittest.main()
