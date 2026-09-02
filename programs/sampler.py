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

from detect import Note, calculate_frequency
import programs
import relic_waveform
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 256

DIR = "/samples"

MIN_SENSITIVITY = 0.75
MAX_SENSITIVITY = 1.0

# Read available samples
def valid_sample(filename: str) -> bool:
    return type(filename) is str and filename and not filename.startswith(".") and not filename.startswith("_") and filename.endswith(".wav")
SAMPLE_PATHS = tuple([DIR + "/" + x for x in sorted(list(filter(lambda x: valid_sample(x), os.listdir(DIR))))[:4]])

def determine_root(path: str) -> float:
    return calculate_frequency(*relic_waveform.from_wav(path, max_size=8192))
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
detect = Note(BUFFER_SIZE, pedal.sample_rate)

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
        mixer.play(resampler)
    pressed = True

buffer = array.array("h", [0] * BUFFER_SIZE)
while True:
    pedal.update()
    programs.update(pedal)

    pedal.leds = (not pedal.bypass) / (1 + (not pressed))

    pots = pedal.pots
    pedal.mix, pedal.level = pots[0], pots[2]
    detect.sensitivity = (1 - pow(1 - pots[1], 2)) * (MAX_SENSITIVITY - MIN_SENSITIVITY) + MIN_SENSITIVITY

    set_sample((int(not pedal.left_switch.value) << 1) | int(not pedal.right_switch.value))

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.bypass:
            detect.reset()
            release()

    if not pedal.bypass:
        pedal.audio_in.record(buffer, len(buffer))
        state = detect.update(buffer)
        if detect.active and detect.frequency is not None:
            press(detect.frequency)
        elif state is synthio.EnvelopeState.RELEASE:
            release()
