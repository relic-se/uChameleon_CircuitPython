# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array

from detect import Note
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 1024

MIN_SENSITIVITY = 0.75
MAX_SENSITIVITY = 1.0

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
    level=0.0,
)

# Setup chromatic note detector
detect = Note(BUFFER_SIZE, pedal.sample_rate)

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
        # Record ADC input into buffer
        pedal.audio_in.record(buffer, len(buffer))

        # Update detector
        state = detect.update(buffer)

        # Display frequency information
        if detect.active:
            print(detect.notename, detect.cents)
    
    pedal.leds = (not pedal.bypass) / (1 + (not detect.active)) * detect.level
