# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiodelays import Echo
import synthio
import time

from uchameleon import uChameleon
import programs

# Constants
MAX_DELAY      = 1000  # ms (int)
MIN_DELAY      = MAX_DELAY / 8  # ms
TAPE_LENGTH    = MAX_DELAY  # ms

LFO_SPEED      = 0.5  # s
LFO_SCALE      = 0.05

FILTER_FREQ    = 2000  # hz

BUFFER_SIZE    = 2048  # bytes

# Overclock
import microcontroller
microcontroller.cpu.frequency = 300_000_000

# Initialize Hardware
pedal = uChameleon()

# Audio Objects
delay_lfo = synthio.LFO(
    rate=LFO_SPEED,
    scale=LFO_SCALE * (not pedal.right_switch.value),
)

lpf = synthio.Biquad(synthio.FilterMode.LOW_PASS, FILTER_FREQ)

effect = Echo(
    max_delay_ms=TAPE_LENGTH,
    delay_ms=synthio.Math(
        synthio.MathOperation.SCALE_OFFSET,
        delay_lfo,
        TAPE_LENGTH,
        TAPE_LENGTH
    ),
    freq_shift=True,
    filter=None if pedal.left_switch.value else lpf,

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

led_state = True
infinite = False
timestamp = time.monotonic()
tap_start_timestamp = None
tap_last_timestamp = None
tap_count = 0
tap_pot_lock = None
while True:
    pedal.update()
    programs.update(pedal)
    pots = pedal.pots

    now = time.monotonic()
    if now - timestamp >= effect.delay_ms.value / 1000:
        timestamp = now
        led_state = not led_state

    pedal.led = led_state and not pedal.bypass

    if pedal.left_switch.rose or pedal.left_switch.fell:
        effect.filter = None if pedal.left_switch.value else lpf
    if pedal.right_switch.rose or pedal.right_switch.fell:
        delay_lfo.scale = LFO_SCALE * (not pedal.right_switch.value)

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass

    if pedal.left_button.pressed:
        if tap_start_timestamp is None or now - tap_last_timestamp > MAX_DELAY / 1000:
            tap_start_timestamp = tap_last_timestamp = now
            tap_count = 0
        else:
            tap_last_timestamp = now
            tap_count += 1
            tap_pot_lock = pots[2]
            effect.delay_ms.b = effect.delay_ms.c = (now - tap_start_timestamp) / tap_count * 1000
    elif pedal.left_button.long_press:
        tap_start_timestamp = None
        infinite = True
    elif pedal.left_button.released:
        infinite = False

    pedal.mix = pots[0]
    if pedal.usb_connected:
        effect.mix = pots[0] * (not pedal.bypass)
    effect.decay = 1.0 if infinite else pots[1]

    if tap_pot_lock is not None and abs(tap_pot_lock - pots[2]) >= 0.05:
        tap_pot_lock = None
    if tap_pot_lock is None:
        effect.delay_ms.b = effect.delay_ms.c = pots[2] * (MAX_DELAY - MIN_DELAY) + MIN_DELAY
