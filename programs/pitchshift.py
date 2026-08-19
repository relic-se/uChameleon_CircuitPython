# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiodelays import PitchShift

from uchameleon import uChameleon
import programs

# Initialize Hardware
pedal = uChameleon()

# Audio Object
effect = PitchShift(
    window=2048,
    overlap=512,
    buffer_size=2048,
    
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

toggle = False
momentary = False
while True:
    pedal.update()
    programs.update(pedal)
    
    pedal.bypass = not momentary and not toggle
    pedal.led = not pedal.bypass

    pots = pedal.pots
    pedal.mix = pots[0]
    if pedal.usb_connected:
        effect.mix = pots[0] * (not pedal.bypass)
    pedal.level = pots[1]

    semitones = pots[2] * 24 - 12
    if not pedal.left_switch.value:
        semitones = round(semitones)
    if not pedal.right_switch.value:
        semitones *= 2
    effect.semitones = semitones

    if pedal.left_button.pressed:
        momentary = True
    elif pedal.left_button.released:
        momentary = False

    if pedal.right_button.pressed:
        toggle = not toggle
