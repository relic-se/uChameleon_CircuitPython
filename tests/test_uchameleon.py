# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

"""Tests of uchameleon.py that run on a computer. Run with `pytest` from the root of the repository.

The hardware modules of CircuitPython are replaced with empty stand-ins, so only logic that does not
touch hardware is tested here. See tests/hil for tests on a device.
"""

import math
import os
import sys
import types

import pytest

# Stand-ins for the modules that only exist on a device
for name, attributes in {
    "analogio": ("AnalogIn",),
    "audiobusio": ("I2SOut",),
    "audioi2sin": ("I2SIn",),
    "audiomixer": ("Mixer",),
    "board": (),
    "busio": ("I2C", "UART"),
    "digitalio": ("DigitalInOut", "Pull"),
    "microcontroller": ("cpu",),
    "pwmio": ("PWMOut",),
    "supervisor": (),
    "usb_audio": ("usb_microphone",),
    "usb_midi": (),
    "adafruit_debouncer": ("Button", "Debouncer"),
    "adafruit_midi": ("MIDI", "MIDIMessage"),
    "relic_tlv320aic3204": ("TLV320AIC3204", "INPUT_2", "INPUT_3", "IMPEDANCE_40K"),
}.items():
    module = types.ModuleType(name)
    for attribute in attributes:
        # Classes must be real types, since annotations like `I2C|None` are evaluated on import
        setattr(module, attribute, type(attribute, (), {}) if attribute[0].isupper() and not attribute.isupper() else None)
    sys.modules[name] = module
sys.modules["board"].__getattr__ = lambda name: name  # any pin name
sys.modules["supervisor"].get_setting = lambda key, default=None: False  # no USB audio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import uchameleon  # noqa: E402

MUTED = -99.9


class Codec:
    """Remembers what was written to it."""

    def __init__(self):
        self.writes = []

    def __setattr__(self, name, value):
        if name != "writes":
            self.writes.append(name)
        object.__setattr__(self, name, value)


class Pin:
    value = False


def make_pedal(mix=0.5, level=1.0, bypass=False, mono=True):
    pedal = uchameleon.uChameleon.__new__(uchameleon.uChameleon)
    pedal._codec = Codec()
    pedal._pin_bypass = Pin()
    pedal._mono = mono
    pedal._bypass = bypass
    pedal._bypass_changed = True
    pedal._mix = mix
    pedal._level = level
    pedal._wet_step = None
    pedal._dry_step = None
    pedal._needs_update = True
    pedal._update_codec()
    return pedal


def wet(pedal):
    return MUTED if pedal._codec.left_dac_muted else pedal._codec.left_dac_volume


def dry(pedal):
    return pedal._codec.left_input_passthrough_volume


def db(gain):
    return 20 * math.log10(gain)


# Conversion


def test_gain_to_db():
    assert uchameleon._gain_to_db(1.0, -63.5) == pytest.approx(0.0)
    assert uchameleon._gain_to_db(0.5, -63.5) == pytest.approx(-6.02, abs=0.01)
    assert uchameleon._gain_to_db(0.1, -63.5) == pytest.approx(-20.0)


def test_gain_to_db_mutes_below_minimum():
    assert uchameleon._gain_to_db(0.0, -63.5) == MUTED
    assert uchameleon._gain_to_db(0.02, -30.1) == MUTED  # -34 dB
    assert uchameleon._gain_to_db(0.04, -30.1) == pytest.approx(-27.96, abs=0.01)


# Level law


@pytest.mark.parametrize("level", (1.0, 0.5, 0.25, 0.1))
def test_wet_and_dry_follow_the_same_level_law(level):
    pedal = make_pedal(mix=0.5, level=level)
    assert wet(pedal) == pytest.approx(db(level))
    assert dry(pedal) == pytest.approx(db(level))


@pytest.mark.parametrize(
    ("mix", "wet_gain", "dry_gain"),
    ((0.25, 0.5, 1.0), (0.5, 1.0, 1.0), (0.75, 1.0, 0.5)),
)
def test_mix_crossfade(mix, wet_gain, dry_gain):
    pedal = make_pedal(mix=mix, level=1.0)
    assert wet(pedal) == pytest.approx(db(wet_gain))
    assert dry(pedal) == pytest.approx(db(dry_gain))


def test_full_wet_mutes_dry():
    pedal = make_pedal(mix=1.0, level=1.0)
    assert wet(pedal) == pytest.approx(0.0)
    assert dry(pedal) == MUTED


def test_full_dry_mutes_wet():
    pedal = make_pedal(mix=0.0, level=1.0)
    assert wet(pedal) == MUTED
    assert dry(pedal) == pytest.approx(0.0)


def test_zero_level_mutes_both():
    pedal = make_pedal(mix=0.5, level=0.0)
    assert wet(pedal) == MUTED
    assert dry(pedal) == MUTED


def test_bypass_mutes_wet_and_passes_dry():
    pedal = make_pedal(mix=0.5, level=0.25, bypass=True)
    assert wet(pedal) == MUTED
    assert dry(pedal) == pytest.approx(0.0)
    assert pedal._pin_bypass.value is False


def test_relay_is_on_when_not_bypassed():
    assert make_pedal(bypass=False)._pin_bypass.value is True


def test_stereo_writes_both_channels():
    pedal = make_pedal(mix=0.5, level=0.5, mono=False)
    assert pedal._codec.right_dac_volume == pedal._codec.left_dac_volume
    assert pedal._codec.right_input_passthrough_volume == pedal._codec.left_input_passthrough_volume
    assert pedal._codec.right_dac_muted is False


# Codec traffic


def test_small_changes_do_not_write_to_the_codec():
    pedal = make_pedal(mix=0.5, level=0.5)
    pedal._codec.writes.clear()
    for level in (0.501, 0.499, 0.502, 0.5):  # noise on a potentiometer, under 0.5 dB
        pedal.level = level
        pedal._update_codec()
    assert pedal._codec.writes == []


def test_larger_changes_write_to_the_codec():
    pedal = make_pedal(mix=0.5, level=0.5)
    pedal._codec.writes.clear()
    pedal.level = 0.25
    pedal._update_codec()
    assert "left_dac_volume" in pedal._codec.writes
    assert "left_input_passthrough_volume" in pedal._codec.writes


def test_volume_is_set_before_unmuting():
    pedal = make_pedal(mix=0.0, level=1.0)  # wet muted
    pedal._codec.writes.clear()
    pedal.mix = 0.5
    pedal._update_codec()
    writes = pedal._codec.writes
    assert writes.index("left_dac_volume") < writes.index("left_dac_muted")
    assert pedal._codec.left_dac_muted is False
