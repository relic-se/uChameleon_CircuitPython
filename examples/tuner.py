# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import audiotap
import synthio

from detect import Detect
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 2048

MIN_SENSITIVITY = 0.75
MAX_SENSITIVITY = 1.0

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
    level=0.0,
)

# The input is played through a tap, which keeps a copy of it for the note detector. It is not
# heard, because the output of the DAC is muted by the mix.
tap = audiotap.Tap(capacity=4 * BUFFER_SIZE / pedal.sample_rate)
pedal.play(tap.play(pedal.audio_in))

# Setup chromatic note detector
detect = Detect()

buffer = array.array("h", [0] * BUFFER_SIZE)
while True:
    pedal.update()
    
    pots = pedal.pots
    detect.sensitivity = (1 - pow(1 - pots[0], 2)) * (MAX_SENSITIVITY - MIN_SENSITIVITY) + MIN_SENSITIVITY

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.bypass:
            detect.reset()

    if not pedal.bypass:
        if tap.overflow:
            tap.clear()  # the tap was not read in time, what it holds is old
        elif tap.available >= BUFFER_SIZE:
            while tap.available >= BUFFER_SIZE:
                tap.readinto(buffer)  # skip to the latest audio if the loop is behind
            state = detect.update(buffer, pedal.sample_rate)
            if detect.state in {synthio.EnvelopeState.ATTACK, synthio.EnvelopeState.SUSTAIN}:
                print(detect.notename, detect.cents)
    
    pedal.leds = (not pedal.bypass) / (1 + (not detect.active)) * detect.level
