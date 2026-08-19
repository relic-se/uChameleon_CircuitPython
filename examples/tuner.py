# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from detect import Detect
from uchameleon import uChameleon

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
    level=0.0,
)

# Setup chromatic note detector
detect = Detect(
    sample_rate=pedal.sample_rate,
)

while True:
    pedal.update()
    pedal.led = (not pedal.bypass) / (1 + (not detect.active))

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.bypass:
            detect.reset()

    if not pedal.bypass and (result := detect.process(pedal.audio_in)) is not None:
        notename, cents = result
        print(notename, cents)
