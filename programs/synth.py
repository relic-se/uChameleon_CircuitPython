# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3
# SPDX-FileCopyrightText: Copyright (c) 2026 Tod Kurt
# SPDX-License-Identifier: MIT

import array
from audiomixer import Mixer
import synthio

from synthtools import Patch, SubtractiveSynth

from detect import Detect
from uchameleon import uChameleon

# Constants
VELOCITY_LEVEL = 0.05

BUFFER_SIZE = 512

# Create synth patches
PATCHES = (
    Patch(
        name="fat bass", wave="ASAW", detune=1.004,
        filt_type="LPF", filt_f=800, filt_q=1.4,
        amp_env=[0.01, 0.1, 0.8, 0.4],
        vib_rate=5.5, vib_depth=0.0,
        # AHR filter envelope: cutoff swings 800 -> 3800 Hz and back
        fenv_amount=3000, fenv_attack=0.02, fenv_release=0.30,
        # a slow cyclic wobble on top of it (0 = off)
        filt_lfo_rate=0.4, filt_lfo_amount=0.3,
    ),
    Patch(
        name="slowpad", wave="SAW",
        detune=1.004,  # two Notes per key -- see the polyphony note above
        filt_type="LPF",
        # A low floor and real resonance. Resonance is what makes a slow sweep
        # audible as MOVEMENT -- at filt_q 0.7 a slow sweep just sounds like a
        # tone control being turned, with no character to track.
        filt_f=180, filt_q=1.9,
        fenv_amount=5000, fenv_attack=1.0, fenv_release=1.0, fenv_curve=1,
        filt_lfo_rate=0.5, filt_lfo_amount=0,
        # Pad amp envelope. The release (2.6) must OUTLAST fenv_release, or the
        # voice is freed part-way down and the filter sweep is cut short --
        # it sounds like a broken envelope but is just the note ending.
        amp_env=[0.35, 0.3, 0.85, 2.6],
    ),
    Patch(
        name="bender", wave="SAW",
        # ONE oscillator on purpose. Detune makes two oscillators beat against
        # each other, and that beating muddies exactly the small pitch movement
        # this demo is about.
        detune=1.0,
        # Filter open and static -- fenv_amount 0 -- so nothing here is the
        # filter moving. This demo is only about pitch.
        filt_type="LPF", filt_f=2600, filt_q=0.9,
        fenv_amount=0,
        # Vibrato: a shared LFO on note.bend. All three default to "off".
        vib_rate=5.0, vib_depth=0.0, vib_delay=0.0,
        # Pitch envelope: bends INTO the note from penv_amount to true pitch
        # over penv_time, then on note-off drifts OUT to penv_out_amount.
        # Both amounts default to 0 = off, and a voice with both off costs
        # nothing -- it reuses the shared bend node.
        penv_amount=0.0, penv_time=0.10, penv_out_amount=0.0, penv_out_time=0.20,
        # sustain high so held notes ring while vibrato does its thing
        amp_env=[0.01, 0.08, 0.75, 0.25],
    ),
    Patch(
        name="acid", synth_type="bassline",
        wave="SAW",  # "SQU" is the 303's other switch position
        filt_type="LPF",
        filt_f=1200,  # the PEAK the sweep starts from
        filt_q=1.8,  # squelch lives here; push it up toward 3-4
        envmod=0.75,
        # THE TWO NUMBERS THAT DECIDE WHETHER YOU HEAR envmod AT ALL.
        #
        # fenv_attack is the filter FALL time, and it must be shorter than the
        # gate (here 0.9 * a 115ms step = 104ms) or the sweep is cut off
        # partway: at 0.28s it only got 23% of the way down, so envmod=0.75
        # moved 0.74 octaves instead of 2.0, and envmod=0.2 moved 0.16 -- i.e.
        # nothing. At 0.09s the sweep completes inside the note.
        #
        # The amp decay must be LONGER than that, so the note is still loud
        # while the cutoff falls. Equal times sound like one gesture (a
        # pluck), because loudness and brightness drop together and mask each
        # other. Sustain 0 means every step plucks; there is no held part.
        amp_env=[0.001, 0.25, 0.0, 0.02],
        fenv_attack=0.09,  # the FALL time (the sweep runs downward)
        fenv_release=0.05,
        # 3 gives the fast drop and long tail that reads as "analog". At 1 the
        # sweep is a straight line and sounds noticeably more synthetic.
        fenv_curve=3,
        # what an accented step gets, on top of the above
        accent=0.6,
        accent_cutoff=4000,  # Hz added at full accent
        accent_q=0.8,  # resonance added at full accent
        amp_level=0.75,  # un-accented level, so accents have room to be louder
        slide_time=0.09,
        transpose=0,
        # --- BasslineSynth's own effects chain, if this build has
        # audiofilters. A synthio.Note holds ONE Biquad, so the voice alone
        # is 12 dB/octave; one extra stage makes 24, where the squelch really
        # lives. The stage tracks synth.filter's cutoff AND resonance on its
        # own, so it follows the sweep and the accent with nothing to keep in
        # sync by hand -- see fx_filter_stages in bassline_synth.py.
        fx_filter_stages=1,
    ),
)

# Overclock
import microcontroller
microcontroller.cpu.frequency = 300_000_000

# Initialize Hardware
pedal = uChameleon(
    mix=1.0,
)

# Setup chromatic note detector
detect = Detect()

# Setup audio objects
mixer = Mixer(  # used for buffer
    voice_count=1,
    **pedal.audiosample_args,
)

engine = synthio.Synthesizer(
    sample_rate=pedal.sample_rate,
    channel_count=pedal.channel_count,
)
synth = SubtractiveSynth(engine)

# Create audio chain
pedal.play(
    mixer.play(
        engine
    )
)

# Assign patch
patch = -1
def set_patch(index: int):
    global patch
    if index != patch:
        patch = index % len(PATCHES)
        synth.load_patch(PATCHES[patch])
set_patch(0)

# Monophonic note handling
active_notenum = None
def note_off() -> None:
    global active_notenum
    if active_notenum is not None:
        synth.note_off(active_notenum)
        active_notenum = None
def note_on(notenum: int, velocity: float = 1.0) -> None:
    global active_notenum
    if notenum != active_notenum:
        note_off()
        synth.note_on(
            notenum,
            velocity=int(min(max(127 * velocity, 1), 127)),
        )
        active_notenum = notenum

buffer = array.array("h", [0] * BUFFER_SIZE)
while True:
    pedal.update()
    pedal.led = (not pedal.bypass) / (1 + (active_notenum is None))

    pots = pedal.pots
    pedal.mix, pedal.level = pots[0], pots[2]
    set_patch(round(pots[1] * (len(PATCHES) - 1)))

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        if pedal.bypass:
            detect.reset()
            note_off()

    if not pedal.bypass:
        pedal.audio_in.record(buffer, len(buffer))
        state = detect.update(buffer, pedal.sample_rate)
        # TODO: Control bend with sustain state
        if active_notenum is None and state in {synthio.EnvelopeState.ATTACK, synthio.EnvelopeState.SUSTAIN}:
            note_on(detect.notenum, min(detect.level / VELOCITY_LEVEL, 1.0))
        elif state is synthio.EnvelopeState.RELEASE:
            note_off()
