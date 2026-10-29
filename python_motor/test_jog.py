import unittest
from motor_core import JogController


class JogTests(unittest.TestCase):
    def test_press_heartbeat_release_and_ack(self):
        jog = JogController()
        self.assertEqual(jog.start(-1, .2, 0), 'JOG,-1,0.200000')
        self.assertIsNone(jog.start(1, .2, .01))
        self.assertIsNone(jog.tick(.05))
        self.assertEqual(jog.tick(.11), 'JOG_KEEP')
        jog.message('OK,JOG', .12)
        self.assertEqual(jog.stop(.2), 'STOP')
        self.assertIsNone(jog.stop(.21))
        self.assertIsNone(jog.tick(.5))
        jog.message('STOPPED', .6)
        self.assertTrue(jog.active)
        jog.message('READY', .61)
        self.assertFalse(jog.active)

    def test_release_before_start_ack_cannot_resume(self):
        jog = JogController()
        jog.start(1, 1, 0)
        jog.stop(.01)
        jog.message('OK,JOG', .02)
        self.assertEqual(jog.state, 'stopping')
        self.assertIsNone(jog.tick(.2))
        with self.assertRaises(ValueError):
            jog.tick(3)

    def test_validation_and_missing_ack(self):
        for direction, speed in [(0, .2), (1, .049), (1, 1.001), (1, float('nan'))]:
            with self.assertRaises(ValueError):
                JogController().start(direction, speed, 0)
        jog = JogController()
        jog.start(1, .2, 0)
        with self.assertRaises(ValueError):
            jog.tick(3)
        with self.assertRaises(ValueError):
            jog.message('ERROR,INVALID_JOG', 3)


if __name__ == '__main__':
    unittest.main()
