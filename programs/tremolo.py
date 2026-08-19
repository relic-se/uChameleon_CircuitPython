# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiomixer import Mixer
import synthio
import ulab.numpy as np

from uchameleon import uChameleon
import programs

# Constants
MIN_SPEED = 0.1
MAX_SPEED = 20.0

SPEED_MOD = (
    1.0,
    -0.5,
    3.0,
    -0.75
)

# Create Waveforms

SAMPLE_SIZE = 1024
SAMPLE_VOLUME = 32767
waveforms = (
    np.concatenate(( # Triangle
        np.linspace(-SAMPLE_VOLUME, SAMPLE_VOLUME, num=SAMPLE_SIZE//2, dtype=np.int16),
        np.linspace(SAMPLE_VOLUME, -SAMPLE_VOLUME, num=SAMPLE_SIZE//2, dtype=np.int16)
    )),
    np.array(np.sin(np.linspace(0, 2 * np.pi, SAMPLE_SIZE, endpoint=False)) * SAMPLE_VOLUME, dtype=np.int16), # Sine
    np.linspace(-SAMPLE_VOLUME, SAMPLE_VOLUME, SAMPLE_SIZE, endpoint=False, dtype=np.int16), # Ramp Up
    np.linspace(-SAMPLE_VOLUME, SAMPLE_VOLUME, SAMPLE_SIZE, endpoint=False, dtype=np.int16), # Ramp Down
    np.concatenate(( # Square
        np.full(SAMPLE_SIZE//2, SAMPLE_VOLUME, dtype=np.int16),
        np.full(SAMPLE_SIZE//2, -SAMPLE_VOLUME, dtype=np.int16)
    )),
)
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
