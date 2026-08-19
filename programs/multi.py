# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiodelays import Echo
from audiofilters import Distortion, DistortionMode, Phaser, Filter
from synthio import LFO, Biquad, FilterMode

from uchameleon import uChameleon
import programs

# Constants
STAGES = 6

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)

# Audio Objects
effects = (
    phaser_effect := Phaser(
        stages=STAGES * (1 + int(not pedal.left_switch.value)),
        frequency=LFO(offset=1000, scale=600, rate=0.5),
        **pedal.audiosample_args,
    ),
    distortion_effect := Distortion(
        mode=DistortionMode.WAVESHAPE,
        drive=0.9,
        pre_gain=12.0,
        post_gain=-18.0,
        **pedal.audiosample_args,
    ),
    filter_effect := Filter(
        filter=Biquad(FilterMode.LOW_PASS, 4000),
        mix=not pedal.right_switch.value,
        **pedal.audiosample_args,
    ),
    echo_effect := Echo(
        max_delay_ms=200,
        delay_ms=200,
        decay=0.5,
        filter=Biquad(FilterMode.LOW_PASS, 6000),
        **pedal.audiosample_args,
    )
)

# Audio Chain
pedal.play(effects[len(effects) - 1])
for i in range(len(effects) - 1, 0, -1):
    effects[i].play(effects[i-1])
effects[0].play(pedal.audio_in)

infinite = False
while True:
    pedal.update()
    programs.update(pedal)

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        pedal.led = not pedal.bypass

    pots = [x * (not pedal.bypass) for x in pedal.pots]
    phaser_effect.mix, distortion_effect.mix = pots[:2]
    echo_effect.mix = pots[2] / 2

    if pedal.left_button.pressed:
        infinite = True
    elif pedal.left_button.released:
        infinite = False
    echo_effect.decay = 1.0 if infinite else 0.5

    if pedal.left_switch.rose or pedal.left_switch.fell:
        phaser_effect.stages = STAGES * (1 + int(not pedal.left_switch.value))

    if pedal.right_switch.rose or pedal.right_switch.fell:
        filter_effect.mix = not pedal.right_switch.value
