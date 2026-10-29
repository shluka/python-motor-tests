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
        with self.assertRaises(ValueError):
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

    def test_one_pulse_zero_tolerance_and_all_blocks(self):
        c = TravelCalibration()
        c.steps = 0
        c.set_zero()
        c.steps = 3200
        c.set_maximum()
        c.steps = 1
        c.validate([Block(distance=1), Block(distance=2)])
        with self.assertRaises(ValueError):
            c.validate([Block(distance=1), Block(distance=3)])
        c.steps = 2
        with self.assertRaises(ValueError):
            c.validate([Block()])

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
