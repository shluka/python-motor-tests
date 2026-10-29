"""Read-only serial diagnostic; does not transmit commands to the board."""
import argparse
import csv
import json
import statistics
import time
from datetime import datetime
from pathlib import Path

import serial
from sensor_core import parse_frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('port')
    parser.add_argument('--seconds', type=float, default=10)
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error('--seconds must be positive')
    folder = Path(__file__).resolve().parents[1] / 'test_results'
    folder.mkdir(exist_ok=True)
    stem = folder / datetime.now().strftime('hardware_%Y%m%d_%H%M%S')
    frames = []
    invalid = []
    buffer = bytearray()
    with serial.Serial(args.port, 115200, timeout=0.1) as port:
        port.reset_input_buffer()
        deadline = time.monotonic() + 5
        end = None
        while time.monotonic() < (end if end is not None else deadline):
            buffer.extend(port.read(min(max(port.in_waiting, 1), 65536)))
            while b'\n' in buffer:
                raw, _, tail = buffer.partition(b'\n')
                buffer = bytearray(tail)
                line = raw.decode('ascii', errors='replace')
                frame = parse_frame(line)
                if frame is None:
                    invalid.append(line[:200])
                    continue
                if end is None:
                    end = time.monotonic() + args.seconds
                frames.append(frame)
            if len(buffer) > 4096:
                invalid.append('Oversized unterminated line: ' + repr(buffer[:100]))
                buffer.clear()
    with stem.with_suffix('.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['Sequence', 'ESP32_time_us', 'Voltage_V'])
        writer.writerows((f.sequence, f.time_us, f.voltage) for f in frames)
    gaps = sum(max(0, b.sequence - a.sequence - 1) for a, b in zip(frames, frames[1:]))
    nonmonotonic = sum(b.sequence <= a.sequence or b.time_us <= a.time_us
                       for a, b in zip(frames, frames[1:]))
    summary = dict(port=args.port, baud=115200, samples=len(frames),
                   invalid_lines=len(invalid), invalid_examples=invalid[:5],
                   dropped_slots=gaps, nonmonotonic_transitions=nonmonotonic,
                   csv=str(stem.with_suffix('.csv')),
                   note='No resistance calculated: installed fixed resistor and measured supply unconfirmed.')
    if len(frames) > 1:
        duration = (frames[-1].time_us - frames[0].time_us) / 1e6
        summary.update(device_duration_s=duration,
                       received_rate_hz=(len(frames)-1)/duration if duration > 0 else None,
                       voltage_min=min(f.voltage for f in frames),
                       voltage_max=max(f.voltage for f in frames),
                       voltage_mean=statistics.mean(f.voltage for f in frames),
                       voltage_stdev=statistics.stdev(f.voltage for f in frames),
                       outside_gui_voltage_limits=sum(not 0.01 < f.voltage < 3.05 for f in frames))
    stem.with_suffix('.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')
    print(json.dumps(summary, indent=2))
    if not frames:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
