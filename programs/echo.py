# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiodelays import Echo
from audiofilters import Filter
import synthio
import time

from uchameleon import uChameleon
import programs

# Constants
TAPE_LENGTH    = 100   # ms

MIN_DELAY      = 10    # ms
MAX_DELAY      = 1000  # ms

LFO_SPEED      = 0.5   # s
LFO_SCALE      = 0.05

FILTER_FREQ    = 4000  # hz

BUFFER_SIZE    = 2048  # bytes

# Initialize Hardware
pedal = uChameleon()

# Audio Objects
delay_lfo = synthio.LFO(
    rate=LFO_SPEED,
    scale=0.0,
)

delay_effect = Echo(
    max_delay_ms=TAPE_LENGTH,
    delay_ms=synthio.Math(
        synthio.MathOperation.SCALE_OFFSET,
        delay_lfo,
        TAPE_LENGTH,
        TAPE_LENGTH
    ),
    freq_shift=True,

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

filter_effect = Filter(
    filter=synthio.Biquad(synthio.FilterMode.LOW_PASS, FILTER_FREQ),

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    filter_effect.play(
        delay_effect.play(
            pedal.audio_in
        )
    )
)

led_state = True
infinite = False
timestamp = time.monotonic()
while True:
    pedal.update()
    programs.update(pedal)

    now = time.monotonic()
    if now - timestamp >= delay_effect.delay_ms.value / 1000:
        timestamp = now
        led_state = not led_state

    pedal.led = led_state and not pedal.bypass

    filter_effect.mix = 1.0 * (not pedal.left_switch.value) * (not pedal.bypass)
    delay_lfo.scale = LFO_SCALE * (not pedal.right_switch.value)

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass

    # TODO: left button tap tempo?
    if pedal.left_button.pressed:
        infinite = True
    elif pedal.left_button.released:
        infinite = False

    pots = pedal.pots
    pedal.mix = pots[0]
    if pedal.usb_connected:
        delay_effect.mix = pots[0] * (not pedal.bypass)
    delay_effect.decay = 1.0 if infinite else pots[1]
    delay_effect.delay_ms.b = delay_effect.delay_ms.c = pots[2] * (MAX_DELAY - MIN_DELAY) + MIN_DELAY
