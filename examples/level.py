# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import audiotap
import time

from uchameleon import uChameleon

# Constants
INTERVAL = 0.025  # seconds of audio that each level is measured from

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
    level=0.0,
)

# The input is played through a tap to measure its level. It is not heard, because the output of
# the DAC is muted by the mix.
tap = audiotap.Tap(capacity=0)
levels = audiotap.LevelReader(tap)
pedal.play(tap.play(pedal.audio_in))

level = 0.0
while True:
    pedal.update()

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass

    if not pedal.bypass:
        level = levels.rms  # of the audio since it was last read

    pedal.leds = (not pedal.bypass) * level
    time.sleep(INTERVAL)
