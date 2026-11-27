# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

# Device side of the hardware-in-the-loop checks of the installed firmware. This file is sent to
# the REPL by run.py, it is not meant to be copied to the device. Unlike device_capture.py it uses
# the uchameleon and detect modules that are on the device.

import array
import binascii
import gc
import json
import math
import time

import board
import digitalio
from audiocore import RawSample

import uchameleon

# Use the analog path although USB is connected for the test
uchameleon.uChameleon.usb_connected = property(lambda self: False)

_pedal = None


def pedal():
    global _pedal
    if _pedal is None:
        # The codec may not respond until it has been reset
        reset = digitalio.DigitalInOut(board.GP4)
        reset.switch_to_output(False)
        time.sleep(0.01)
        reset.value = True
        time.sleep(0.02)
        reset.deinit()
        _pedal = uchameleon.uChameleon(mix=1.0, level=1.0, bypass=False)
    return _pedal


def _tone(cycles, length, amplitude, offset=0):
    scale = amplitude * 32767
    return array.array(
        "h",
        [int(round(math.sin(2 * math.pi * cycles * i / length) * scale)) + offset for i in range(length)],
    )


def detect(cfg):
    """Play a tone through the DAC and run the note detection of the firmware on the input."""
    import audiotap
    from audiomixer import Mixer
    from detect import Detect

    device = pedal()
    size = cfg["buffer_size"]
    samples = _tone(cfg["cycles"], cfg["length"], cfg["amplitude"])

    # The input is read through a tap that is played at a level of 0, as in the programs
    mixer = Mixer(voice_count=2, **device.audiosample_args)
    tap = audiotap.Tap(capacity=4 * size / device.sample_rate)
    device._audio_out.play(mixer)
    mixer.voice[0].play(RawSample(samples, sample_rate=device.sample_rate), loop=True)
    mixer.voice[1].level = 0.0
    mixer.voice[1].play(tap.play(device.audio_in))
    device.update()
    time.sleep(0.5)
    tap.clear()

    detector = Detect()
    detector.sensitivity = cfg["sensitivity"]
    buffer = array.array("h", [0] * size)
    worst = 0
    updates = 0
    deadline = time.monotonic() + 10
    while updates < cfg["updates"] and time.monotonic() < deadline:
        if tap.available < size:
            continue
        while tap.available >= size:
            tap.readinto(buffer)
        start = time.monotonic_ns()
        detector.update(buffer, device.sample_rate)
        worst = max(worst, time.monotonic_ns() - start)
        updates += 1
    device._audio_out.stop()
    print(
        "HIL-META "
        + json.dumps(
            {
                "active": detector.active,
                "frequency": detector.frequency,
                "notename": detector.notename,
                "cents": detector.cents,
                "level": detector.level,
                "updates": updates,
                "update_ms": worst / 1e6,
            }
        )
    )


def distortion(cfg):
    """Play a tone through the chain of programs/distortion.py and record the result."""
    import synthio
    from audiofilters import Distortion, DistortionMode, Filter

    device = pedal()
    args = device.audiosample_args
    samples = _tone(cfg["cycles"], cfg["length"], cfg["amplitude"], cfg["offset"])
    chain = RawSample(samples, sample_rate=device.sample_rate)
    keep = [chain]

    if cfg["input_filter"]:
        effect = Filter(
            filter=synthio.Biquad(synthio.FilterMode.HIGH_PASS, cfg["input_filter"]), **args
        )
        effect.play(chain, loop=True)
        chain = effect
        keep.append(effect)

    effect = Distortion(soft_clip=True, **args)
    effect.mode = getattr(DistortionMode, cfg["mode"])
    effect.pre_gain = cfg["pre_gain"]
    effect.drive = cfg["drive"]
    effect.play(chain, loop=len(keep) == 1)
    chain = effect
    keep.append(effect)

    effect = Filter(filter=synthio.Biquad(synthio.FilterMode.LOW_PASS, cfg["output_filter"]), **args)
    effect.play(chain)
    keep.append(effect)

    device._audio_out.play(effect)
    time.sleep(0.6)
    count = cfg["capture_samples"]
    gc.collect()
    recording = array.array("h", (0,)) * count
    recorded = device.audio_in.record(recording, count)
    device._audio_out.stop()

    print("HIL-META " + json.dumps({"recorded": recorded}))
    print("HIL-DATA-BEGIN")
    view = memoryview(recording)
    for start in range(0, count, 384):
        print(str(binascii.b2a_base64(view[start : start + 384]), "ascii"), end="")
    print("HIL-DATA-END")


def finish():
    if _pedal is not None:
        _pedal.bypass = True
        _pedal.update()
