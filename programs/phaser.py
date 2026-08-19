# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiofilters import Phaser
import synthio

from uchameleon import uChameleon
import programs

# Constants
STAGES_INCREMENT = 8

MIN_FREQUENCY    = 200  # hz
MAX_FREQUENCY    = 2000  # hz
MIN_DEPTH        = 0.25

MIN_RATE         = 0.05  # hz
MAX_RATE         = 4.0  # hz

MIN_FEEDBACK     = 0.5
MAX_FEEDBACK     = 1.0

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)
pedal.update()

# Audio Objects
lfo = synthio.LFO(
    offset=(MIN_FREQUENCY + MAX_FREQUENCY) / 2,
)

effect = Phaser(
    frequency=lfo,
    stages=((int(not pedal.left_switch.value) | (int(not pedal.right_switch.value) << 1)) + 1) * STAGES_INCREMENT,
    mix=1.0,

    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

while True:
    pedal.update()
    programs.update(pedal)

    pedal.led = (lfo.value - MIN_FREQUENCY) / (MAX_FREQUENCY - MIN_FREQUENCY) * (not pedal.bypass)

    pots = pedal.pots
    lfo.rate = pow(pots[0], 2) * (MAX_RATE - MIN_RATE) + MIN_RATE
    lfo.scale = (pots[1] * (1 - MIN_DEPTH) + MIN_DEPTH) * (MAX_FREQUENCY - MIN_FREQUENCY) / 2
    effect.feedback = pots[2] * (MAX_FEEDBACK - MIN_FEEDBACK) + MIN_FEEDBACK
    
    if pedal.left_switch.rose or pedal.left_switch.fell or pedal.right_switch.rose or pedal.right_switch.fell:
        effect.stages = ((int(not pedal.left_switch.value) | (int(not pedal.right_switch.value) << 1)) + 1) * STAGES_INCREMENT

    # TODO: left button?

    if pedal.right_button.pressed:
        pedal.bypass = not pedal.bypass
