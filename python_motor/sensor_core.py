"""Protocol and divider calculations, independent of the GUI."""
import math
import csv
from dataclasses import dataclass


SENSORS = {
    'Sensor 1': (1500, 500, 3800),
    'Sensor 2': (2400, 2440, 2520),
    'Sensor 3': (51000, 49350, 56000),
    'Sensor 4': (56000, 58400, 58750),
}


@dataclass(frozen=True)
class Frame:
    sequence: int
    time_us: int
    voltage: float


def parse_frame(line):
    """Return None for boot messages, malformed frames or nonfinite values."""
    try:
        tag, sequence, time_us, voltage = line.strip().split(',')
        if tag != 'S' or not sequence.isascii() or not time_us.isascii():
            return None
        if not sequence.isdecimal() or not time_us.isdecimal():
            return None
        frame = Frame(int(sequence), int(time_us), float(voltage))
        if not math.isfinite(frame.voltage) or not 0 <= frame.voltage <= 3.4:
            return None
        return frame
    except (ValueError, TypeError):
        return None


def resistance(voltage, supply, fixed):
    if not 0.1 <= supply <= 3.6 or fixed <= 0:
        raise ValueError('Invalid divider configuration.')
    if not math.isfinite(voltage) or not 0.01 < voltage < min(3.05, supply):
        raise ValueError(f'Invalid Vout {voltage:.4f} V; check the divider wiring.')
    return fixed * (supply / voltage - 1)


class Acquisition:
    def __init__(self, supply, fixed):
        self.supply, self.fixed = supply, fixed
        self.rows = []
        self.dropped = self.invalid = 0
        self.last = None
        self.origin = None

    @property
    def initial_resistance(self):
        """First accepted sample of this run, in ohms."""
        return self.rows[0][4] if self.rows else None

    def write_csv(self, stream):
        """Export the three measured vectors and derived resistance change."""
        writer = csv.writer(stream)
        writer.writerow(['Time_s', 'Voltage_V', 'Resistance_ohm',
                         'Relative_resistance_percent'])
        r0 = self.initial_resistance
        for row in self.rows:
            writer.writerow([f'{row[0]:.6f}', f'{row[3]:.6f}', f'{row[4]:.6f}',
                             f'{(row[4] - r0) / r0 * 100:.6f}'])

    def add(self, frame, host_time):
        if self.last is not None:
            if frame.sequence <= self.last.sequence or frame.time_us <= self.last.time_us:
                raise ValueError('ESP32 restarted or sequence/timestamp is not monotonic.')
        value = resistance(frame.voltage, self.supply, self.fixed)
        if self.last is not None:
            self.dropped += frame.sequence - self.last.sequence - 1
        if self.origin is None:
            self.origin = frame.time_us
        row = ((frame.time_us - self.origin) / 1e6, frame.time_us / 1e6,
               frame.sequence, frame.voltage, value, host_time)
        self.rows.append(row)
        self.last = frame
        return row
