# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiofreeverb import Freeverb
from synthio import Biquad, FilterMode

from uchameleon import uChameleon
import programs

# Constants
LPF_FILTER_FREQ = 4000  # hz
HPF_FILTER_FREQ = 1000  # hz

BUFFER_SIZE     = 2048  # bytes

# Initialize Hardware
pedal = uChameleon()

# Audio Objects
effect = Freeverb(
    roomsize=0.0,
    damp=0.0,
    pre_filter=(
        Biquad(FilterMode.LOW_PASS, 10000),
        Biquad(FilterMode.HIGH_PASS, 600),
    ),
    post_filter=(
        Biquad(FilterMode.LOW_PASS, 20000 if pedal.left_switch.value else LPF_FILTER_FREQ),
        Biquad(FilterMode.HIGH_PASS, 20 if pedal.right_switch.value else HPF_FILTER_FREQ),
    ),

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)
lpf, hpf = effect.post_filter

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

infinite = False
while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    roomsize, effect.damp, pedal.mix = pots
    if pedal.usb_connected:
        effect.mix = pots[2] * (not pedal.bypass)

    if pedal.left_switch.rose or pedal.left_switch.fell:
        lpf.frequency = 20000 if pedal.left_switch.value else LPF_FILTER_FREQ
    if pedal.right_switch.rose or pedal.right_switch.fell:
        hpf.frequency = 20 if pedal.right_switch.value else HPF_FILTER_FREQ

    if pedal.left_button.pressed:
        infinite = True
    elif pedal.left_button.released:
        infinite = False
    
    effect.roomsize = 1.0 if infinite else roomsize

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        pedal.led = not pedal.bypass
