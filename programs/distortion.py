# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiofilters import Distortion, Filter, DistortionMode
import synthio

from uchameleon import uChameleon
import programs

# Constants
MIN_FILTER = 600
MAX_FILTER = 12000

BOOST_GAIN = 24

OVERDRIVE_GAIN = 24

MODES = (
    DistortionMode.CLIP,
    DistortionMode.OVERDRIVE,
    DistortionMode.WAVESHAPE,
    DistortionMode.LOFI,
)

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)

# Audio Objects
distortion_effect = Distortion(
    soft_clip=True,
    mix=not pedal.usb_connected,
    **pedal.audiosample_args,
)

filter_effect = Filter(
    filter=synthio.Biquad(synthio.FilterMode.LOW_PASS, MAX_FILTER),
    mix=not pedal.usb_connected,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    filter_effect.play(
        distortion_effect.play(
            pedal.audio_in
        )
    )
)

boost = False
while True:
    pedal.update()
    programs.update(pedal)

    if pedal.right_button.pressed:
        pedal.bypass = not pedal.bypass
        if pedal.usb_connected:
            distortion_effect.mix = not pedal.bypass
            filter_effect.mix = not pedal.bypass

    pedal.led = (not pedal.bypass) / (1 + (not boost) * 3)

    mode_index = int(not pedal.left_switch.value) | (int(not pedal.right_switch.value) << 1)
    distortion_effect.mode = MODES[mode_index]

    pots = pedal.pots
    filter_effect.filter.frequency = pots[0] * (MAX_FILTER - MIN_FILTER) + MIN_FILTER
    pedal.level = pots[1]

    if pedal.left_button.pressed:
        boost = not boost
    
    if distortion_effect.mode == DistortionMode.OVERDRIVE:
        distortion_effect.pre_gain = BOOST_GAIN * boost + OVERDRIVE_GAIN * pots[2]
        distortion_effect.drive = 0.0
    else:
        distortion_effect.pre_gain = BOOST_GAIN * boost
        distortion_effect.drive = pots[2]
