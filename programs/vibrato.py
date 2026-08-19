# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

from audiodelays import PitchShift
import synthio
import ulab.numpy as np

from uchameleon import uChameleon
import programs

# Constants
MAX_DEPTH = 2.0  # semitones

MIN_RATE  = 0.1  # hz
MAX_RATE  = 8.0  # hz

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

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)

# Audio Objects
lfo = synthio.Math(
    synthio.MathOperation.SCALE_OFFSET,
    synthio.LFO(
        waveform=np.zeros(SAMPLE_SIZE, dtype=np.int16),
        rate=MIN_RATE,
        scale=0.5,
        offset=-0.5,
    ),
    0.0,  # Semitones
    0.0  # Offset
)

effect = PitchShift(
    semitones=lfo,
    window=2048,
    overlap=512,
    buffer_size=2048,
    mix=0.0,
    
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

# Assign controls
waveform = -1
def set_waveform(index: int):
    global waveform
    if index != waveform:
        waveform = index % len(waveforms)
        # waveform must be updated by element
        for i in range(SAMPLE_SIZE):
            lfo.a.waveform[i] = waveforms[waveform][i]
set_waveform(0)

while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    lfo.a.rate = (pow(pots[0], 2) * (MAX_RATE - MIN_RATE) + MIN_RATE)
    set_waveform(round(pots[1] * (len(waveforms) - 1)))
    lfo.b = MAX_DEPTH * pots[2]  # depth

    # TODO: left button and switches

    if pedal.right_button.pressed:
        pedal.bypass = not pedal.bypass
        effect.mix = not pedal.bypass

    pedal.led = (lfo.value / MAX_DEPTH / 2 + 0.5) * (not pedal.bypass)
