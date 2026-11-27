# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3
# SPDX-FileCopyrightText: Copyright (c) 2026 Tod Kurt
# SPDX-License-Identifier: MIT

import array
from audiocore import WaveFile
from audiomixer import Mixer
from audiospeed import Resampler, SpeedChanger
import audiotap
import gc
import synthio
import os

import programs
from relic_audiodetect.frequency import calculate_frequency
from relic_audiodetect.note import Note
import relic_waveform
from uchameleon import uChameleon

# Constants
BUFFER_SIZE = 512

DIR = "/samples"
DEFAULT_ROOT = 440.0  # hz, used for samples without a detectable frequency

MIN_SENSITIVITY = 0.75
MAX_SENSITIVITY = 1.0

# Read available samples
def valid_sample(filename: str) -> bool:
    return type(filename) is str and filename and not filename.startswith(".") and not filename.startswith("_") and filename.endswith(".wav")
SAMPLE_PATHS = tuple([DIR + "/" + x for x in sorted(list(filter(lambda x: valid_sample(x), os.listdir(DIR))))[:4]])

def determine_root(path: str) -> float:
    return calculate_frequency(*relic_waveform.from_wav(path, max_size=4096)) or DEFAULT_ROOT
SAMPLE_ROOTS = tuple([determine_root(x) for x in SAMPLE_PATHS])
gc.collect()  # the analysis grows the heap, give the memory back for the audio buffers

SAMPLES = tuple([WaveFile(x) for x in SAMPLE_PATHS])

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)

# Setup frequency detector
detect = Note(BUFFER_SIZE, pedal.sample_rate)

# Setup audio objects
sampler = resampler = None  # will be SpeedChanger & Resampler when a sample is loaded

mixer = Mixer(
    voice_count=2,  # the sample and the input
    **pedal.audiosample_args,
)

# Create audio chain
pedal.play(
    mixer
)

# The input is played through a tap, which keeps a copy of it for the frequency detector. It is
# played at a level of 0, so that it is not heard.
tap = audiotap.Tap(capacity=4 * BUFFER_SIZE / pedal.sample_rate)
mixer.voice[1].level = 0.0
mixer.voice[1].play(tap.play(pedal.audio_in))

# Assign sample
sample_index = -1
sample_root = DEFAULT_ROOT
def set_sample(index: int):
    global sample_index, sample_root, sampler, resampler
    if index != sample_index:
        sample_index = index % len(SAMPLES)
        sample_root = SAMPLE_ROOTS[sample_index]

        if mixer.voice[0].playing:
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
    if pressed and mixer.voice[0].playing:
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
        if tap.overflow:
            tap.clear()  # the tap was not read in time, what it holds is old
        elif tap.available >= BUFFER_SIZE:
            while tap.available >= BUFFER_SIZE:
                tap.readinto(buffer)  # skip to the latest audio if the loop is behind
            state = detect.update(buffer)
            if state is synthio.EnvelopeState.ATTACK:
                press(detect.frequency)
            elif state is synthio.EnvelopeState.RELEASE:
                release()
