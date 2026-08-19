# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiofreeverb import Freeverb
from audiofilters import Filter
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
reverb_effect = Freeverb(
    roomsize=0.0,
    damp=0.0,

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

filter_effect = Filter(
    filter=(
        Biquad(FilterMode.LOW_PASS, 20000),
        Biquad(FilterMode.HIGH_PASS, 20),
    ),

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    filter_effect.play(
        reverb_effect.play(
            pedal.audio_in
        )
    )
)

infinite = False
while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    roomsize, reverb_effect.damp, pedal.mix = pots
    if pedal.usb_connected:
        reverb_effect.mix = pots[2] * (not pedal.bypass)
        filter_effect.mix = pots[2] * (not pedal.bypass)

    lpf, hpf = filter_effect.filter
    lpf.frequency = 20000 if pedal.left_switch.value else LPF_FILTER_FREQ
    hpf.frequency = 20 if pedal.right_switch.value else HPF_FILTER_FREQ

    if pedal.left_button.pressed:
        infinite = True
    elif pedal.left_button.released:
        infinite = False
    
    reverb_effect.roomsize = 1.0 if infinite else roomsize

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        pedal.led = not pedal.bypass
