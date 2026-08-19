# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiodelays import GranularPitchShift
from audiofreeverb import Freeverb
from synthio import Biquad, FilterMode

from uchameleon import uChameleon
import programs

# Constants
FILTER_FREQ = 3000  # hz

PITCH_MIX = 0.5  # 0.0 to 1.0

BUFFER_SIZE     = 2048  # bytes

# Overclock
import microcontroller
microcontroller.cpu.frequency = 300_000_000

# Initialize Hardware
pedal = uChameleon()

# Audio Objects

effect_pitch = GranularPitchShift(
    semitones=24.0,
    mix=0.0,
    grain_size=2048,
    density=8,
    spread=1.0,
    buffer_size=2048,
    
    **pedal.audiosample_args,
)

lpf = Biquad(FilterMode.LOW_PASS, FILTER_FREQ)
effect_reverb = Freeverb(
    roomsize=0.0,
    damp=0.0,
    pre_filter=(
        Biquad(FilterMode.LOW_PASS, 16000),
        Biquad(FilterMode.HIGH_PASS, 200),
    ),
    post_filter=None if pedal.left_switch.value else lpf,

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect_reverb.play(
        effect_pitch.play(
            pedal.audio_in
        )
    )
)

infinite = False
while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    roomsize, effect_reverb.damp, pedal.mix = pots
    if pedal.usb_connected:
        effect_reverb.mix = pots[2] * (not pedal.bypass)

    if pedal.left_switch.rose or pedal.left_switch.fell:
        effect_reverb.post_filter = None if pedal.left_switch.value else lpf
    
    if pedal.right_switch.rose or pedal.right_switch.fell:
        effect_pitch.mix = PITCH_MIX * (not pedal.right_switch.value) * (not pedal.bypass)

    if pedal.left_button.pressed:
        infinite = True
    elif pedal.left_button.released:
        infinite = False
    
    effect_reverb.roomsize = 1.0 if infinite else roomsize

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        pedal.led = not pedal.bypass
        effect_pitch.mix = PITCH_MIX * (not pedal.right_switch.value) * (not pedal.bypass)
