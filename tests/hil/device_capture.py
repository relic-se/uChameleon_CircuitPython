# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

# Device side of the hardware-in-the-loop audio test. This file is sent to the REPL by run.py, it
# is not meant to be copied to the device. It plays a tone through the DAC, records it through the
# ADC (the output jack must be patched to the input jack) and prints the recording as base64.

import array
import binascii
import gc
import json
import math
import sys
import time

import board
import digitalio
import microcontroller
from audiobusio import I2SOut
from audiocore import RawSample
from audioi2sin import I2SIn
from busio import I2C

_ADDRESS = 0x18


def _read_register(i2c, page, register):
    buffer = bytearray(1)
    while not i2c.try_lock():
        pass
    try:
        i2c.writeto(_ADDRESS, bytes((0, page)))
        i2c.writeto_then_readfrom(_ADDRESS, bytes((register,)), buffer)
    finally:
        i2c.unlock()
    return buffer[0]


def run(cfg):
    if cfg.get("lib_path"):
        sys.path.insert(0, cfg["lib_path"])
    import relic_tlv320aic3204 as tlv

    microcontroller.cpu.frequency = cfg["cpu_frequency"]
    sample_rate = cfg["sample_rate"]
    resources = []
    codec = None
    try:
        # Keep the relay in true bypass until the codec is ready
        bypass = digitalio.DigitalInOut(board.GP10)
        bypass.switch_to_output(False)
        resources.append(bypass)

        i2c = I2C(board.GP21, board.GP20)
        resources.append(i2c)

        def make_bus():
            bus = I2SIn(
                bit_clock=board.GP6,
                word_select=board.GP7,
                data=board.GP9,
                sample_rate=sample_rate,
                bit_depth=16,
                samples_signed=True,
                mono=True,
            )
            resources.append(bus)
            return bus

        def make_codec():
            clock = cfg["clock"]
            if clock == "pwm12":  # 12 MHz requested from PWMOut, PLL from MCLK
                return tlv.TLV320AIC3204(
                    i2c=i2c, mclk=board.GP5, rst=board.GP4, sample_rate=sample_rate
                )
            if clock == "bclk":  # PLL from BCLK
                mclk = digitalio.DigitalInOut(board.GP5)
                mclk.switch_to_output(False)
                resources.append(mclk)
                return tlv.TLV320AIC3204(i2c=i2c, rst=board.GP4, sample_rate=sample_rate)
            if clock == "mclk":  # MCLK as an exact multiple of the frame rate, no PLL
                return tlv.TLV320AIC3204(
                    i2c=i2c,
                    mclk=board.GP5,
                    rst=board.GP4,
                    sample_rate=sample_rate,
                    mclk_frequency=microcontroller.cpu.frequency // cfg["mclk_divider"],
                    mclk_multiplier=cfg["mclk_multiplier"],
                )
            raise ValueError("Unknown clock mode")

        if cfg["codec_first"]:
            codec = make_codec()
            audio_in = make_bus()
        else:
            audio_in = make_bus()
            codec = make_codec()

        audio_out = I2SOut(
            bit_clock=board.GP6,
            word_select=board.GP7,
            data=board.GP8,
            external_clock=True,
        )
        resources.append(audio_out)

        # Same signal path as uchameleon.py in mono
        codec.connect_left_input(tlv.INPUT_2, tlv.IMPEDANCE_40K, balanced=True)
        codec.left_input_gain = cfg["input_gain"]
        codec.left_dac_enabled = True
        codec.left_dac_to_left_line_output = True
        codec.left_adc_volume = 0.0
        codec.left_adc_enabled = True
        codec.left_adc_muted = False
        passthrough = None
        if cfg["passthrough_db"] is not None:
            # The patch cable closes a loop through the passthrough, keep it well below unity
            codec.left_input_passthrough_enabled = True
            codec.left_input_to_left_line_output = True
            codec.left_input_passthrough_volume = min(cfg["passthrough_db"], -12.0)
            passthrough = codec.left_input_passthrough_volume
        codec.left_line_output_enabled = True
        codec.left_line_output_gain = cfg["output_gain"]
        codec.left_line_output_muted = False
        codec.left_dac_volume = cfg["dac_db"]
        codec.left_dac_muted = cfg["amplitude"] <= 0.0

        # A whole number of cycles so that the looped tone is continuous
        length = cfg["tone_samples"]
        cycles = cfg["tone_cycles"]
        scale = cfg["amplitude"] * 32767
        tone = array.array(
            "h",
            [int(round(math.sin(2 * math.pi * cycles * i / length) * scale)) for i in range(length)],
        )
        audio_out.play(RawSample(tone, sample_rate=sample_rate), loop=True)

        bypass.value = True
        time.sleep(cfg["settle"])

        count = cfg["capture_samples"]
        gc.collect()
        recording = array.array("h", bytes(count * 2))
        recorded = audio_in.record(recording, count)

        bypass.value = False
        audio_out.stop()

        meta = {
            "label": cfg["label"],
            "cpu_frequency": microcontroller.cpu.frequency,
            "bus_sample_rate": audio_in.sample_rate,
            "recorded": recorded,
            "passthrough_readback": passthrough,
            "driver": getattr(tlv, "__file__", None),
            "adc_flags": _read_register(i2c, 0, 36),
            "dac_flags": _read_register(i2c, 0, 37),
            "clock_mux": _read_register(i2c, 0, 4),
            "pll": _read_register(i2c, 0, 5),
        }
        print("HIL-META " + json.dumps(meta))
        print("HIL-DATA-BEGIN")
        view = memoryview(recording)
        for start in range(0, count, 384):
            print(str(binascii.b2a_base64(view[start : start + 384]), "ascii"), end="")
        print("HIL-DATA-END")
    finally:
        for name in ("_mclk", "_reset"):
            resource = getattr(codec, name, None)
            if hasattr(resource, "deinit"):
                resource.deinit()
        for resource in reversed(resources):
            resource.deinit()
