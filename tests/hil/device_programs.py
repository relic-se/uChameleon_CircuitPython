# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

# Device side of the hardware-in-the-loop checks of the programs. This file is sent to the REPL by
# run.py, followed by the source of a program from the repository. The program runs with the
# uchameleon module and the libraries that are on the device.

import array
import gc
import json
import math
import time
import traceback

import board
import digitalio
from audiocore import RawSample
from audiomixer import Mixer

import programs
import uchameleon

programs._first_update = False  # do not blink the LEDs when a program starts

_Pedal = uchameleon.uChameleon
_Pedal.usb_connected = property(lambda self: False)  # use the analog path although USB is connected
_pedal = None


class _Finished(Exception):
    pass


def _tone(cycles, length, amplitude):
    scale = amplitude * 32767
    return array.array(
        "h", [int(round(math.sin(2 * math.pi * cycles * i / length) * scale)) for i in range(length)]
    )


def run_program(source, cfg):
    """Run a program while tones are played to its input and report what it does.

    The program is played at a level of 0. With the output patched to the input it only hears the
    tones of the schedule, which are mixed into the output. The expressions of `watch` are
    evaluated with the global names of the program in every pass of its loop, and each change of
    their value is reported."""
    namespace = {"__name__": "__main__"}
    log = []
    tones = {}
    state = {"mixer": None, "start": None, "index": 0, "values": {}, "loops": 0, "worst": 0, "last": None}

    def create(mix=0.0, level=1.0, **kwargs):
        # Stands in for the class: the pins can only be claimed once, so the pedal is reused
        global _pedal
        if _pedal is None:
            # The codec may not respond until it has been reset
            reset = digitalio.DigitalInOut(board.GP4)
            reset.switch_to_output(False)
            time.sleep(0.01)
            reset.value = True
            time.sleep(0.02)
            reset.deinit()
            _pedal = _Pedal(mix=mix, level=level, bypass=False, **kwargs)
        _pedal.mix = mix
        _pedal.level = level
        _pedal.bypass = False

        # The tones are made here and not earlier, to leave the memory to the program while it starts
        for entry in cfg["schedule"]:
            cycles = entry[1]
            if cycles and cycles not in tones:
                tones[cycles] = RawSample(
                    _tone(cycles, cfg["length"], cfg["amplitude"]), sample_rate=cfg["sample_rate"]
                )

        # The tones are mixed with what the program plays
        mixer = Mixer(voice_count=2, **_pedal.audiosample_args)
        _pedal._audio_out.play(mixer)
        mixer.voice[0].level = 0.0  # the program is not heard
        state["mixer"] = mixer
        return _pedal

    def play(self, sample):
        state["mixer"].voice[0].play(sample)

    original_update = _Pedal.update

    def update(self):
        original_update(self)
        mixer = state["mixer"]
        if mixer is None:
            return
        now = time.monotonic()
        if state["start"] is None:
            state["start"] = now
            # The tones must reach the output whatever the mix of the program is
            self._codec.left_dac_volume = 0.0
            self._codec.left_dac_muted = False
        else:
            state["worst"] = max(state["worst"], now - state["last"])
        state["last"] = now
        state["loops"] += 1
        elapsed = now - state["start"]

        schedule = cfg["schedule"]
        while state["index"] < len(schedule) and elapsed >= schedule[state["index"]][0]:
            cycles = schedule[state["index"]][1]
            if cycles:
                mixer.voice[1].play(tones[cycles], loop=True)
            else:
                mixer.voice[1].stop()
            state["index"] += 1

        for name, expression in cfg["watch"]:
            try:
                value = eval(expression, namespace)
            except Exception as error:
                value = repr(error)
            if state["values"].get(name, "unset") != value:
                state["values"][name] = value
                log.append([round(elapsed, 3), name, value])

        if elapsed >= cfg["duration"]:
            raise _Finished()

    error = None
    uchameleon.uChameleon = create
    _Pedal.play = play
    _Pedal.update = update
    _Pedal.pots = property(lambda self: cfg["pots"])
    gc.collect()
    try:
        exec(compile(source, cfg["name"], "exec"), namespace)
    except _Finished:
        pass
    except Exception as e:
        error = "".join(traceback.format_exception(e)).strip()
    finally:
        uchameleon.uChameleon = _Pedal
        _Pedal.update = original_update
        if _pedal is not None:
            _pedal._audio_out.stop()

    tap = namespace.get("tap")
    print(
        "HIL-META "
        + json.dumps(
            {
                "error": error,
                "log": log,
                "loop_ms": cfg["duration"] * 1000 / max(state["loops"], 1),
                "worst_loop_ms": state["worst"] * 1000,
                "input_overflow": _pedal.audio_in.overflow if _pedal is not None else None,
                "tap_overflow": tap.overflow if tap is not None else None,
            }
        )
    )
    namespace.clear()
    gc.collect()


def finish():
    if _pedal is not None:
        _pedal.bypass = True
        _pedal.update()
