# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import synthio

from detect import Detect
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 2048

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
    level=0.0,
)

# Setup chromatic note detector
detect = Detect()

buffer = array.array("h", [0] * BUFFER_SIZE)
while True:
    pedal.update()
    pedal.led = (not pedal.bypass) / (1 + (not detect.active))

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.bypass:
            detect.reset()

    if not pedal.bypass:
        pedal.audio_in.record(buffer, len(buffer))
        state = detect.update(buffer, pedal.sample_rate)
        if state in {synthio.EnvelopeState.ATTACK, synthio.EnvelopeState.SUSTAIN}:
            print(detect.notename, detect.cents)
