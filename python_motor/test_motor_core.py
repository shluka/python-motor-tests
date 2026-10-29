import unittest
from motor_core import Block, LineBuffer, MotorProtocol, Mechanics, BENCH_LIMITS


class MotorTests(unittest.TestCase):
    def test_bench_limits_boundaries_and_rejection(self):
        for block in [Block(1, .01, .05, 0, .05, 0, 0),
                      Block(100, 1, .2, 3600, .2, 3600, 3600),
                      Block(distance=100), Block(distance=.001), Block(forward=1, backward=1)]:
            BENCH_LIMITS.validate(block)
        for block in [Block(forward=.049), Block(forward=1.001),
                      Block(backward=.049), Block(backward=1.001),
                      Block(cycles=101), Block(hold_max=3601),
                      Block(hold_zero=3601), Block(hold_after=3601)]:
            with self.subTest(block=block):
                with self.assertRaises(ValueError):
                    BENCH_LIMITS.validate(block)

    def test_revolutions_and_step_telemetry(self):
        mechanics = Mechanics(3200, 2)
        self.assertEqual(mechanics.revolutions(1600), 0.5)
        self.assertEqual(mechanics.displacement(1600), 1)
        p = self.uploaded()
        p.baseline_ready()
        p.message('START_PROTOCOL,1', 0)
        p.message('START_FORWARD,1,1', 1)
        self.assertEqual(p.position_source, 'speed_time_estimate')
        p.message('M,1500000,800', 2)
        self.assertEqual(p.position(2), 0.5)
        self.assertEqual(p.revolutions(2), 0.25)
        self.assertEqual(p.motor_time_us, 1500000)
        self.assertEqual(p.position_source, 'step_telemetry')
        self.assertEqual(p.position(100), 0.5)  # do not fabricate steps between reports
        p.stop()
        p.message('M,1600000,900', 2.1)
        p.message('ABORTED', 2.2)
        self.assertEqual(p.position(100), 900/1600)
        with self.assertRaises(ValueError):
            p.message('M,invalid,123', 3)
        for values in [(0, 2), (3200, -1), (float('nan'), 2)]:
            with self.assertRaises(ValueError):
                Mechanics(*values)

    def uploaded(self, blocks=None):
        p = MotorProtocol(blocks or [Block(2, 5, 1, 0, 2, 0, 0)])
        self.assertEqual(p.begin(), 'CLEAR')
        self.assertIsNone(p.message('READY', 0))
        p.message('OK,CLEAR', 0)
        self.assertEqual(p.message('READY', 0), p.blocks[0].command())
        for n in range(1, len(p.blocks)+1):
            p.message(f'OK,BLOCK,{n}', n)
            command = p.message('READY', n)
            if n < len(p.blocks):
                self.assertEqual(command, p.blocks[n].command())
        self.assertEqual(p.stage, 'baseline')
        return p

    def test_upload_and_baseline_gate(self):
        p = self.uploaded([Block(), Block()])
        self.assertEqual(p.baseline_ready(), 'RUN')
        self.assertIsNone(p.baseline_ready())
        p.message('START_PROTOCOL,2', 3)
        self.assertEqual(p.stage, 'running')

    def test_asymmetric_ramps_holds_and_clamping(self):
        p = self.uploaded()
        p.baseline_ready()
        p.message('START_PROTOCOL,1', 0)
        p.message('START_BLOCK,1', 0)
        p.message('START_FORWARD,1,1', 1)
        self.assertEqual(p.position(3), 2)
        self.assertEqual(p.position(10), 5)
        p.message('END_FORWARD,1,1', 7)
        p.message('START_HOLD_MAX,1,1,1000', 7)
        self.assertEqual(p.position(8), 5)
        p.message('START_BACKWARD,1,1', 9)
        self.assertEqual(p.position(10), 3)
        self.assertEqual(p.position(20), 0)
        p.message('END_BACKWARD,1,1', 12)
        p.message('START_HOLD_ZERO,1,1,1000', 12)
        self.assertEqual(p.position(13), 0)
        p.message('FIN', 14)
        self.assertEqual(p.stage, 'finished')

    def test_stop_preserves_partial_estimate(self):
        p = self.uploaded()
        p.baseline_ready()
        p.message('START_PROTOCOL,1', 0)
        p.message('START_FORWARD,1,1', 1)
        self.assertEqual(p.stop(), 'STOP')
        self.assertIsNone(p.stop())
        p.message('END_FORWARD,1,1', 2)
        p.message('ABORTED', 3)
        self.assertEqual(p.stage, 'stopped')
        self.assertEqual(p.position(99), 2)

    def test_reset_and_motor_error(self):
        p = self.uploaded()
        p.baseline_ready()
        with self.assertRaisesRegex(ValueError, 'reset'):
            p.message('READY', 1)
        with self.assertRaisesRegex(ValueError, 'Motor reported'):
            p.message('ERROR,NO_BLOCKS', 1)

    def test_validation(self):
        for values in [(0, 1, 1, 0, 1, 0, 0), (1.5, 1, 1, 0, 1, 0, 0),
                       (1, 0, 1, 0, 1, 0, 0), (1, 1, 1, -1, 1, 0, 0),
                       (1, float('nan'), 1, 0, 1, 0, 0)]:
            with self.assertRaises(ValueError):
                Block(*values)
        for blocks in [[], [Block()]*11]:
            with self.assertRaises(ValueError):
                MotorProtocol(blocks)

    def test_serial_fragments(self):
        buffer = LineBuffer()
        self.assertEqual(buffer.feed(b'START_FOR'), [])
        self.assertEqual(buffer.feed(b'WARD,1,1\r\nFIN\nREA'), ['START_FORWARD,1,1', 'FIN'])
        self.assertEqual(buffer.feed(b'DY\n'), ['READY'])
        with self.assertRaises(ValueError):
            buffer.feed(b'x'*4097)


if __name__ == '__main__':
    unittest.main()
