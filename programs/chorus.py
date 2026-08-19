# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiodelays import Chorus
from audiofilters import Filter
from synthio import LFO, Biquad, FilterMode

from uchameleon import uChameleon
import programs

# Constants
MIN_DELAY   = 4  # ms
MAX_DELAY   = 40  # ms

MIN_SPEED   = 0.05  # hz
MAX_SPEED   = 4.0  # hz

MIN_VOICES  = 2
MAX_VOICES  = 4

FILTER_FREQ = 4000  # hz

BUFFER_SIZE = 2048  # bytes

# Overclock
import microcontroller
microcontroller.cpu.frequency = 300_000_000

# Initialize Hardware
pedal = uChameleon()

# Audio Objects
lfo = LFO(
    offset=MIN_DELAY,
    scale=0,
)

chorus_effect = Chorus(
    max_delay_ms=MAX_DELAY,
    delay_ms=lfo,
    voices=(MIN_VOICES if pedal.right_switch.value else MAX_VOICES),

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

filter_effect = Filter(
    filter=Biquad(FilterMode.LOW_PASS, FILTER_FREQ),
    mix=(not pedal.left_switch.value),

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    filter_effect.play(
        chorus_effect.play(
            pedal.audio_in
        )
    )
)

double = False
while True:
    pedal.update()
    programs.update(pedal)

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass

    pots = pedal.pots
    pedal.mix = pots[0]
    if pedal.usb_connected:
        chorus_effect.mix = pots[0] * (not pedal.bypass)
    lfo.rate = (pots[1] * (MAX_SPEED - MIN_SPEED) + MIN_SPEED) * (1 + int(double))
    lfo.offset = pots[2] * (MAX_DELAY - MIN_DELAY) + MIN_DELAY
    lfo.scale = lfo.offset / 2

    filter_effect.mix = not pedal.bypass and not pedal.left_switch.value
    if pedal.right_switch.rose or pedal.right_switch.fell:
        chorus_effect.voices = MIN_VOICES if pedal.right_switch.value else MAX_VOICES

    if pedal.left_button.pressed:
        double = True
    elif pedal.left_button.released:
        double = False

    pedal.led = ((lfo.value - lfo.offset) / lfo.scale * pots[2] + 1) / 2 * (not pedal.bypass)
