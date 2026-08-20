# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3
# SPDX-FileCopyrightText: Copyright (c) 2026 Tod Kurt
# SPDX-License-Identifier: MIT

import array
from audiocore import WaveFile
from audiomixer import Mixer
from audiospeed import Resampler, SpeedChanger
import synthio
import os

from detect import Detect, fftfreq_areas as fftfreq
import relic_waveform
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 256

DIR = "/samples"

# Read available samples
def valid_sample(filename: str) -> bool:
    return type(filename) is str and filename and not filename.startswith(".") and not filename.startswith("_") and filename.endswith(".wav")
SAMPLE_PATHS = tuple([DIR + "/" + x for x in sorted(list(filter(lambda x: valid_sample(x), os.listdir(DIR))))])

def determine_root(path: str) -> float:
    return fftfreq(*relic_waveform.from_wav(path, max_size=8192))
SAMPLE_ROOTS = tuple([determine_root(x) for x in SAMPLE_PATHS])

SAMPLES = tuple([WaveFile(x) for x in SAMPLE_PATHS])

# Overclock
import microcontroller
microcontroller.cpu.frequency = 300_000_000

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)

# Setup frequency detector
detect = Detect()

# Setup audio objects
sampler = resampler = None  # will be SpeedChanger & Resampler when a sample is loaded

mixer = Mixer(  # used for buffer
    voice_count=1,
    **pedal.audiosample_args,
)

# Create audio chain
pedal.play(
    mixer
)

# Assign sample
sample_index = -1
sample_root = 440
def set_sample(index: int):
    global sample_index, sample_root, sampler, resampler
    if index != sample_index:
        sample_index = index % len(SAMPLES)
        sample_root = SAMPLE_ROOTS[sample_index]

        if mixer.playing:
            mixer.stop_voice()

        if sampler is not None:
            sampler.deinit()
        sampler = SpeedChanger(SAMPLES[sample_index])

        if resampler is not None:
            resampler.deinit()
        resampler = Resampler(sampler)

set_sample(0)

# Monophonic note handling
pressed = False
def release() -> None:
    global pressed
    if pressed and mixer.playing:
        mixer.stop_voice()
    pressed = False
def press(frequency: float) -> None:
    global pressed
    sampler.rate = frequency / sample_root
    if not pressed:
        mixer.play(resampler, loop=not pedal.left_switch.value)
    pressed = True

buffer = array.array("h", [0] * BUFFER_SIZE)
while True:
    pedal.update()
    pedal.led = (not pedal.bypass) / (1 + (not pressed))

    pots = pedal.pots
    pedal.mix, pedal.level = pots[0], pots[2]
    set_sample(round(pots[1] * (len(SAMPLES) - 1)))

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.bypass:
            detect.reset()
            release()

    if not pedal.bypass:
        pedal.audio_in.record(buffer, len(buffer))
        state = detect.update(buffer, pedal.sample_rate)
        if state in {synthio.EnvelopeState.ATTACK, synthio.EnvelopeState.SUSTAIN}:
            press(detect.frequency)
        elif state is synthio.EnvelopeState.RELEASE:
            release()
