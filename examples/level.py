# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import ulab.numpy as np

from detect import decouple_signal, calculate_level
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 1024

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
    level=0.0,
)

level = 0.0
buffer = array.array("h", [0] * BUFFER_SIZE)
while True:
    pedal.update()
    
    sensitivity, _, _ = pedal.pots

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass

    if not pedal.bypass:

        # Record ADC input into buffer
        pedal.audio_in.record(buffer, len(buffer))

        # Convert integer data to float from -1.0 to 1.0
        data = np.array(buffer, dtype=np.float) / 32768

        # Re-center the signal around the mean
        data = decouple_signal(data)

        # Calculate the level
        level = calculate_level(data)

        # Adjust based on sensitivity
        level /= max(pow(1 - sensitivity, 2), 0.001)

        # Clip at 1.0
        level = min(level, 1.0)
        print(level)

    pedal.leds = (not pedal.bypass) * level
