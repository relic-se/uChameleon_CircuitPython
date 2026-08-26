# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import ulab.numpy as np

from detect import decouple, level_abs
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

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass

    if not pedal.bypass:
        pedal.audio_in.record(buffer, len(buffer))
        data = np.array(buffer) / 32768
        data = decouple(data)
        level = level_abs(data)

    pedal.leds = (not pedal.bypass) * level
