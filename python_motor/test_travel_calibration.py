import unittest
from motor_core import TravelCalibration, Block


class TravelTests(unittest.TestCase):
    def test_zero_maximum_and_return_with_multiple_jogs(self):
        c = TravelCalibration()
        c.steps = -800
        c.set_zero()
        c.steps = 2400
        self.assertEqual(c.position, 2)
        c.set_maximum()
        c.steps = 800
        c.validate([Block(distance=1)])
        c.steps = -800
        c.validate([Block(distance=2)])
        with self.assertRaises(ValueError):
            c.validate([Block(distance=2.001)])

    def test_missing_telemetry_wrong_direction_and_new_zero(self):
        c = TravelCalibration()
        with self.assertRaises(ValueError):
            c.set_zero()
        c.steps = 0
        c.set_zero()
        for steps in (0, -1600):
            c.steps = steps
            with self.assertRaises(ValueError):
                c.set_maximum()
        c.steps = 1600
        c.set_maximum()
        c.set_zero()
        self.assertIsNone(c.maximum)
        with self.assertRaises(ValueError):
            c.validate([Block()])

    def test_start_away_from_zero_still_checks_all_block_distances(self):
        c = TravelCalibration()
        c.steps = 0
        c.set_zero()
        c.steps = 3200
        c.set_maximum()
        c.steps = 1
        c.validate([Block(distance=1), Block(distance=2)])
        with self.assertRaises(ValueError):
            c.validate([Block(distance=1), Block(distance=3)])
        for steps in (2, 1600, 3200):
            c.steps = steps
            c.validate([Block()])

    def test_return_keeps_original_minimum_after_run_resets_counter(self):
        c = TravelCalibration()
        c.steps = 100
        c.set_zero()
        c.steps = 16100
        c.set_maximum()
        c.steps = 4900  # Start a cyclic test 3 mm above the minimum.
        c.rebase_for_run()
        self.assertEqual(c.position, 3)
        self.assertEqual(c.maximum, 10)
        self.assertEqual(c.return_command(.2), 'JOG_TO,-4800,0.200000')
        c.steps = -4800
        self.assertEqual(c.position, 0)
        self.assertIsNone(c.return_command(.2))

    def test_return_target_uses_original_pulse_zero(self):
        c = TravelCalibration()
        with self.assertRaises(ValueError):
            c.return_command(.2)
        c.steps = -800
        c.set_zero()
        c.steps = 15200
        c.set_maximum()
        self.assertEqual(c.return_command(.2), 'JOG_TO,-800,0.200000')
        c.steps = -800
        self.assertIsNone(c.return_command(.2))
        for speed in (.01, 2, float('nan')):
            with self.assertRaises(ValueError):
                c.return_command(speed)
        c.steps = -801
        with self.assertRaises(ValueError):
            c.return_command(.2)
        c.steps = 15201
        with self.assertRaises(ValueError):
            c.return_command(.2)

    def test_gui_return_waits_for_ready_and_stop_cancels(self):
        from unittest.mock import Mock
        from main_motor_test import App
        from motor_core import JogController
        app = App.__new__(App)
        app.active = app.connecting = app.demo = False
        app.ready = app.return_supported = True
        app.returning = False
        app.jog = JogController()
        app.travel = TravelCalibration()
        app.travel.steps = 100
        app.travel.set_zero()
        app.travel.steps = 8100
        app.travel.set_maximum()
        app.jog_speed = Mock()
        app.jog_speed.get.return_value = '0.2'
        app.zero = Mock()
        app.send = Mock()
        app.controls = Mock()
        app.status = Mock()
        app.update_travel = Mock()
        app.return_to_minimum()
        app.send.assert_called_once_with('JOG_TO,100,0.200000')
        self.assertTrue(app.returning)
        app.jog_release()  # Mouse release must not cancel the automatic return.
        self.assertEqual(app.send.call_count, 1)
        app.on_motor('OK,JOG', 1)
        app.on_motor('M,100,100', 2)
        app.on_motor('STOPPED', 2)
        self.assertTrue(app.returning)
        app.on_motor('READY', 2.1)
        self.assertFalse(app.returning)
        self.assertFalse(app.jog.active)
        self.assertEqual(app.travel.position, 0)
        app.travel.steps = 8100
        app.send.reset_mock()
        app.return_to_minimum()
        app.stop()
        self.assertFalse(app.returning)
        app.send.assert_called_with('STOP')

    def test_gui_starts_away_from_zero_and_rejects_excess_distance(self):
        from unittest.mock import Mock, patch
        from main_motor_test import App
        from motor_core import JogController
        app = App.__new__(App)
        app.active = False
        app.demo = app.ready = app.sensor_ready = app.saved = True
        app.jog = JogController()
        app.travel = TravelCalibration()
        app.travel.steps = 0
        app.travel.set_zero()
        app.travel.steps = 16000
        app.travel.set_maximum()
        app.travel.steps = 4800
        for name, value in [('zero', True), ('supply', '3.3'), ('alpha', '1'),
                            ('fixed_resistor', '2400'), ('sensor', 'Sensor 2'),
                            ('esp_name', 'DEMO'), ('motor_name', 'DEMO')]:
            setattr(app, name, Mock(get=Mock(return_value=value)))
        app.blocks = [Block(distance=5)]
        app.esp = None
        app.controls = app.send = app.status = Mock()
        app.start()
        self.assertTrue(app.active)
        self.assertEqual(app.protocol.stage, 'baseline')
        self.assertEqual(app.travel.position, 3)
        app.active = False
        app.saved = True
        app.blocks = [Block(distance=11)]
        with patch('main_motor_test.messagebox.showerror') as error:
            app.start()
            error.assert_called_once()
        self.assertFalse(app.active)
