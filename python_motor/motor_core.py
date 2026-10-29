"""Cyclic protocol validation and MATLAB-compatible displacement estimation."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class TestLimits:
    """Provisional bench envelope, not manufacturer ratings for all NEMA 17 motors."""
    min_speed: float = 0.05
    max_speed: float = 1.0
    min_cycles: int = 1
    max_cycles: int = 100
    max_hold: float = 3600

    def validate(self, block):
        if not all(self.min_speed <= v <= self.max_speed for v in (block.forward, block.backward)):
            raise ValueError(f'Velocidad permitida en ambos sentidos: {self.min_speed:g}–{self.max_speed:g} mm/s.')
        if not self.min_cycles <= block.cycles <= self.max_cycles:
            raise ValueError(f'Ciclos permitidos por bloque: {self.min_cycles}–{self.max_cycles}.')
        if any(v > self.max_hold for v in (block.hold_max, block.hold_zero, block.hold_after)):
            raise ValueError(f'Pausas permitidas: 0–{self.max_hold:g} s.')


BENCH_LIMITS = TestLimits()


class JogController:
    """Press-and-hold motion with explicit STOP acknowledgment and a firmware lease."""
    def __init__(self):
        self.state = 'idle'
        self.last_ping = self.deadline = 0

    @property
    def active(self):
        return self.state != 'idle'

    def start(self, direction, speed, now):
        if self.active:
            return None
        if direction not in (-1, 1) or not math.isfinite(speed) or not BENCH_LIMITS.min_speed <= speed <= BENCH_LIMITS.max_speed:
            raise ValueError('Velocidad manual permitida: 0,05–1 mm/s.')
        self.state = 'starting'
        self.last_ping = now
        self.deadline = now + 2
        return f'JOG,{direction},{speed:.6f}'

    def stop(self, now):
        if self.state in ('starting', 'moving'):
            self.state = 'stopping'
            self.deadline = now + 2
            return 'STOP'

    def message(self, line, now):
        if line == 'OK,JOG' and self.state == 'starting':
            self.state = 'moving'
        elif line.startswith('ERROR') and self.active:
            raise ValueError('Motor: ' + line)
        elif line == 'STOPPED' and self.active:
            self.state = 'waiting_ready'
            self.deadline = now + 2
        elif line == 'READY' and self.state == 'waiting_ready':
            self.state = 'idle'

    def tick(self, now):
        if self.state in ('starting', 'stopping', 'waiting_ready') and now > self.deadline:
            raise ValueError('Movimiento manual sin confirmación del Mega; reconecta antes de continuar.')
        if self.state in ('starting', 'moving') and now-self.last_ping >= .1:
            self.last_ping = now
            return 'JOG_KEEP'


@dataclass(frozen=True)
class Mechanics:
    steps_per_rev: float = 3200
    mm_per_rev: float = 2

    def __post_init__(self):
        if not all(math.isfinite(v) and v > 0 for v in (self.steps_per_rev, self.mm_per_rev)):
            raise ValueError('Steps/revolution and mm/revolution must be positive finite values.')

    def displacement(self, steps):
        return steps / self.steps_per_rev * self.mm_per_rev

    def revolutions(self, steps):
        return steps / self.steps_per_rev


@dataclass(frozen=True)
class Block:
    cycles: int = 1
    distance: float = 1
    forward: float = 0.2
    hold_max: float = 0
    backward: float = 0.2
    hold_zero: float = 0
    hold_after: float = 0

    def __post_init__(self):
        values = self.values()
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Block values must be finite.')
        if not 1 <= self.cycles <= 32767 or int(self.cycles) != self.cycles:
            raise ValueError('Cycles must be an integer from 1 to 32767.')
        if min(self.distance, self.forward, self.backward) <= 0:
            raise ValueError('Distance and both speeds must be positive.')
        if min(self.hold_max, self.hold_zero, self.hold_after) < 0:
            raise ValueError('Hold durations must be nonnegative.')
        if max(self.hold_max, self.hold_zero, self.hold_after) > 2147483:
            raise ValueError('Hold duration exceeds firmware timer conversion range.')
        if self.distance * 1600 > 2147483647:
            raise ValueError('Distance exceeds firmware step counter range.')
        if min(self.forward, self.backward) < 0.000001:
            raise ValueError('Speed is below the supported range.')

    def values(self):
        return (self.cycles, self.distance, self.forward, self.hold_max,
                self.backward, self.hold_zero, self.hold_after)

    def command(self):
        return 'BLOCK,' + ','.join(format(v, '.9g') for v in self.values())

    def duration(self):
        return self.cycles * (self.distance / self.forward + self.hold_max +
                              self.distance / self.backward + self.hold_zero) + self.hold_after


class MotorProtocol:
    """Pure state machine. Caller transmits returned commands and timestamps replies.

    Commands are uploaded one at a time, waiting for both acknowledgment and
    READY before sending the next. RUN is returned only after baseline_ready().
    """
    def __init__(self, blocks, mechanics=None):
        if not 1 <= len(blocks) <= 10:
            raise ValueError('Use between 1 and 10 protocol blocks.')
        self.blocks = tuple(blocks)
        self.mechanics = mechanics or Mechanics()
        self.reported_steps = None
        self.motor_time_us = None
        self.stage = 'idle'
        self.pending = None
        self.ack = False
        self.uploaded = 0
        self.block = self.cycle = 0
        self.phase = 'BASELINE'
        self.x = self.origin_x = self.segment_start = 0
        self.speed = 0
        self.direction = 0
        self.events = []

    def begin(self):
        self.stage = 'uploading'
        self.pending = 'OK,CLEAR'
        return 'CLEAR'

    def baseline_ready(self):
        if self.stage == 'baseline':
            self.stage = 'starting'
            return 'RUN'

    def position(self, now):
        if self.reported_steps is not None:
            return self.mechanics.displacement(self.reported_steps)
        distance = self.blocks[self.block - 1].distance if self.block else 0
        return max(0, min(distance, self.origin_x + self.direction * self.speed *
                          max(0, now - self.segment_start)))

    def revolutions(self, now):
        if self.reported_steps is not None:
            return self.mechanics.revolutions(self.reported_steps)
        return self.position(now) / self.mechanics.mm_per_rev

    @property
    def position_source(self):
        return 'step_telemetry' if self.reported_steps is not None else 'speed_time_estimate'

    def stop(self):
        if self.stage not in ('finished', 'stopped', 'stopping'):
            self.stage = 'stopping'
            return 'STOP'

    def message(self, line, now):
        self.events.append((now, line))
        fields = line.strip().split(',')
        event = fields[0]
        if event == 'ERROR':
            raise ValueError('Motor reported: ' + line)
        if event == 'M':
            if len(fields) != 3:
                raise ValueError('Malformed motor step telemetry.')
            timestamp, steps = int(fields[1]), int(fields[2])
            if timestamp < 0:
                raise ValueError('Invalid motor timestamp.')
            self.motor_time_us, self.reported_steps = timestamp, steps
            return
        if self.stage == 'stopping':
            if event in ('ABORTED', 'STOPPED', 'FIN'):
                self.x = self.origin_x = self.position(now)
                self.direction = 0
                self.phase = 'STOPPED'
                self.stage = 'stopped'
            return
        if self.stage == 'uploading':
            if line == self.pending:
                self.ack = True
            elif event == 'READY' and self.ack:
                self.ack = False
                if self.uploaded < len(self.blocks):
                    command = self.blocks[self.uploaded].command()
                    self.uploaded += 1
                    self.pending = f'OK,BLOCK,{self.uploaded}'
                    return command
                self.pending = None
                self.stage = 'baseline'
            return
        if self.stage not in ('starting', 'running'):
            return
        if event in ('OK', 'CONFIG_BLOCK'):
            return
        if event == 'READY':
            raise ValueError('Motor reset or unexpectedly became READY during the test.')
        if event == 'START_PROTOCOL':
            if len(fields) != 2 or int(fields[1]) != len(self.blocks):
                raise ValueError('Motor protocol block count mismatch.')
            self.stage = 'running'
            self.phase = 'PROTOCOL_START'
            return
        if event == 'FIN':
            self.stage, self.phase = 'finished', 'FINISHED'
            self.direction = 0
            self.x = self.origin_x = 0
            return
        if event in ('ABORTED', 'STOPPED'):
            self.x = self.origin_x = self.position(now)
            self.direction = 0
            self.stage, self.phase = 'stopped', 'STOPPED'
            return
        phases = {'START_BLOCK', 'START_FORWARD', 'END_FORWARD', 'START_HOLD_MAX',
                  'END_HOLD_MAX', 'START_BACKWARD', 'END_BACKWARD', 'START_HOLD_ZERO',
                  'END_HOLD_ZERO', 'END_CYCLE', 'START_BLOCK_HOLD', 'END_BLOCK_HOLD', 'END_BLOCK'}
        if event not in phases:
            return
        if len(fields) < 2 or not 1 <= int(fields[1]) <= len(self.blocks):
            raise ValueError('Invalid block index in motor event.')
        previous = self.position(now)
        self.block = int(fields[1])
        block = self.blocks[self.block - 1]
        if event not in ('START_BLOCK', 'START_BLOCK_HOLD', 'END_BLOCK_HOLD', 'END_BLOCK'):
            if len(fields) < 3 or not 1 <= int(fields[2]) <= block.cycles:
                raise ValueError('Invalid cycle index in motor event.')
            self.cycle = int(fields[2])
        elif event == 'START_BLOCK':
            self.cycle = 0
        self.direction = 0
        self.segment_start = now
        self.phase = event
        if event == 'START_FORWARD':
            self.origin_x, self.speed, self.direction = previous, block.forward, 1
        elif event == 'START_BACKWARD':
            self.origin_x, self.speed, self.direction = block.distance, block.backward, -1
        elif event in ('END_FORWARD', 'START_HOLD_MAX', 'END_HOLD_MAX'):
            self.origin_x = block.distance
        else:
            self.origin_x = 0


class LineBuffer:
    def __init__(self):
        self.buffer = bytearray()

    def feed(self, data):
        self.buffer.extend(data)
        lines = []
        while b'\n' in self.buffer:
            raw, _, tail = self.buffer.partition(b'\n')
            self.buffer = bytearray(tail)
            if len(raw) > 4096:
                raise ValueError('Oversized serial line.')
            lines.append(raw.decode('ascii', errors='replace').strip())
        if len(self.buffer) > 4096:
            raise ValueError('Unterminated serial line exceeds size limit.')
        return lines


class TravelCalibration:
    """Session reference from commanded pulse telemetry, not encoder feedback."""
    def __init__(self):
        self.steps = self.origin = self.maximum = None

    @property
    def position(self):
        if self.steps is None or self.origin is None:
            return None
        return Mechanics().displacement(self.steps - self.origin)

    def set_zero(self):
        if self.steps is None:
            raise ValueError('Sin telemetria de posicion. Mueve brevemente el motor y espera su parada.')
        self.origin = self.steps
        self.maximum = None

    def set_maximum(self):
        if self.position is None or self.position <= 0:
            raise ValueError('Fija primero el cero y desplazate en Avanzar hasta un maximo positivo.')
        self.maximum = self.position

    def validate(self, blocks):
        if self.maximum is None:
            raise ValueError('Calibra el recorrido: fija cero, avanza y fija maximo; despues vuelve al cero.')
        if self.position is None or abs(self.position) > Mechanics().displacement(1):
            raise ValueError('Vuelve al cero con los botones antes de iniciar el ensayo (tolerancia: un pulso).')
        if any(b.distance > self.maximum for b in blocks):
            raise ValueError(f'El ensayo supera el recorrido maximo calibrado: {self.maximum:.4f} mm.')


    def return_command(self, speed):
        if self.maximum is None or self.position is None:
            raise ValueError('Fija primero el minimo (cero) y el maximo.')
        if not math.isfinite(speed) or not BENCH_LIMITS.min_speed <= speed <= BENCH_LIMITS.max_speed:
            raise ValueError('Velocidad manual permitida: 0,05-1 mm/s.')
        if not 0 <= self.position <= self.maximum:
            raise ValueError('Posicion fuera del recorrido calibrado; revisa la referencia.')
        if self.steps == self.origin:
            return None
        return f'JOG_TO,{self.origin},{speed:.6f}'
