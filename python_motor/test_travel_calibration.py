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
