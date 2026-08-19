# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiomixer import Mixer
import synthio
import ulab.numpy as np

from uchameleon import uChameleon
import programs

# Constants
MIN_SPEED = 0.5
MAX_SPEED = 8.0

SPEED_MOD = (
    1.0,
    -0.5,
    3.0,
    -0.75
)

PATTERN_LENGTH = 16
PATTERNS = (
    0b1100110011001100,
    0b1010101010101010,
    0b1010001010100000,
    0b1001010110010010,
    0b1110111011101110,
    0b1000001010000010,
    0b1000010010000100,
    0b1111111011101110,
)

# Create Waveforms
SAMPLE_SIZE = 1024
SAMPLE_VOLUME = 32767
STEP_SIZE = SAMPLE_SIZE // PATTERN_LENGTH
waveforms = []
for pattern in PATTERNS:
    waveform = np.zeros(SAMPLE_SIZE, dtype=np.int16)
    for i in range(PATTERN_LENGTH):
        bit = 1 << (PATTERN_LENGTH - i - 1)
        state = bool(pattern & bit)
        for x in range(STEP_SIZE * i, STEP_SIZE * (i + 1)):
            waveform[x] = SAMPLE_VOLUME * (state * 2 - 1)
    waveforms.append(waveform)
waveforms = tuple(waveforms)
waveform = -1

# Initialize Hardware
pedal = uChameleon(
    mix=0.0,
)

# Audio Objects
lfo = synthio.Math(
    synthio.MathOperation.SCALE_OFFSET,
    synthio.LFO(
        waveform=np.zeros(SAMPLE_SIZE, dtype=np.int16),
        rate=MIN_SPEED,
        scale=0.5,
        offset=-0.5,
    ),
    0.0,  # Depth
    1.0  # Level
)

mixer = Mixer(
    voice_count=1,
    **pedal.audiosample_args,
)
mixer.voice[0].level = lfo

# Audio Chain
pedal.play(
    mixer.play(
        pedal.audio_in
    )
)

# Assign controls
def set_waveform(index: int):
    global waveform
    if index != waveform:
        waveform = index % len(waveforms)
        # waveform must be updated by element
        for i in range(SAMPLE_SIZE):
            lfo.a.waveform[i] = waveforms[waveform][i]
set_waveform(0)

mod = False
while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    mod_index = int(not pedal.left_switch.value) | (int(not pedal.right_switch.value) << 1)
    lfo.a.rate = (pots[0] * (MAX_SPEED - MIN_SPEED) + MIN_SPEED) * (1 + SPEED_MOD[mod_index] * mod)
    set_waveform(round(pots[1] * (len(waveforms) - 1)))
    lfo.b = pots[2]  # depth

    pedal.led = lfo.value * (not pedal.bypass)
    pedal.level = lfo.value

    if pedal.left_button.pressed:
        mod = True
    elif pedal.left_button.released:
        mod = False

    if pedal.right_button.pressed:
        pedal.bypass = not pedal.bypass
