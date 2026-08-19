# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiodelays import Flanger

from uchameleon import uChameleon
import programs

# Constants
MIN_DELAY    = 0.5  # ms
MAX_DELAY    = 4  # ms (must be int)

MIN_RATE     = 0.5  # hz
MAX_RATE     = 4.0  # hz

MIN_FEEDBACK = 0.25
MAX_FEEDBACK = 0.75

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)
pedal.update()

# Audio Objects
effect = Flanger(
    max_delay_ms=MAX_DELAY,
    feedback=(MIN_FEEDBACK if pedal.left_switch.value else MAX_FEEDBACK),
    invert=(not pedal.right_switch.value),
    mix=not pedal.usb_connected,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

infinite = False
while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    effect.min_delay_ms = pots[0] * (MAX_DELAY - MIN_DELAY) + MIN_DELAY
    effect.depth = pots[1]
    effect.rate = pots[2] * (MAX_RATE - MIN_RATE) + MIN_RATE

    effect.feedback = 1 if infinite else (MIN_FEEDBACK if pedal.left_switch.value else MAX_FEEDBACK)

    if pedal.right_switch.rose or pedal.right_switch.fell:
        effect.invert = not pedal.right_switch.value

    if pedal.left_button.pressed:
        infinite = True
    elif pedal.left_button.released:
        infinite = False

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.usb_connected:
            effect.mix = not pedal.bypass
    
    pedal.led = effect.lfo_value * effect.depth * (not pedal.bypass)
