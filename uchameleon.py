# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from analogio import AnalogIn
from audiobusio import I2SOut
from audioi2sin import I2SIn
from audiomixer import Mixer
import board
from busio import I2C
import digitalio
from pwmio import PWMOut
import supervisor
from usb_audio import usb_microphone

from adafruit_debouncer import Button, Debouncer
from relic_tlv320aic3204 import TLV320AIC3204, INPUT_1, IMPEDANCE_40K

_PIN_BTN0 = board.GP10
_PIN_BTN1 = board.GP11

_PIN_SW0 = board.GP12
_PIN_SW1 = board.GP19

_PIN_LED = board.GP22

_PIN_POT0 = board.GP26
_PIN_POT1 = board.GP27
_PIN_POT2 = board.GP28

_PIN_SDA = board.GP20
_PIN_SCL = board.GP21

_PIN_RST = board.GP2
_PIN_MCLK = board.GP3
_PIN_BCLK = board.GP4
_PIN_WCLK = board.GP5
_PIN_DOUT = board.GP6
_PIN_DIN = board.GP7

_PIN_BYPASS = board.GP8

class uChameleon:

    def __init__(
        self,
        sample_rate: int|None = None,
        mono: bool|None = None,
        input_gain: float|None = None,
        output_gain: float|None = None,
        mix: float = 0.0,
        level: float = 1.0,
        bypass: bool = True,
    ) -> None:
        self._sample_rate = sample_rate if sample_rate is not None else int(supervisor.get_setting("SAMPLE_RATE", 44100))
        self._mono = mono if mono is not None else bool(supervisor.get_setting("MONO", True))

        # Setup Controls
        self._led = PWMOut(
            _PIN_LED,
            duty_cycle=0,
            frequency=44100*2,
        )

        _pin_btn0 = digitalio.DigitalInOut(_PIN_BTN0)
        _pin_btn0.switch_to_input(pull=digitalio.Pull.UP)
        self._left_button = Button(_pin_btn0)

        _pin_btn1 = digitalio.DigitalInOut(_PIN_BTN1)
        _pin_btn1.switch_to_input(pull=digitalio.Pull.UP)
        self._right_button = Button(_pin_btn1)

        _pin_sw0 = digitalio.DigitalInOut(_PIN_SW0)
        _pin_sw0.switch_to_input(pull=digitalio.Pull.UP)
        self._left_switch = Debouncer(_pin_sw0)

        _pin_sw1 = digitalio.DigitalInOut(_PIN_SW1)
        _pin_sw1.switch_to_input(pull=digitalio.Pull.UP)
        self._right_switch = Debouncer(_pin_sw1)

        self._pots = (
            AnalogIn(_PIN_POT0),
            AnalogIn(_PIN_POT1),
            AnalogIn(_PIN_POT2)
        )

        # Configure Codec
        self._codec = TLV320AIC3204(
            i2c=I2C(_PIN_SCL, _PIN_SDA),
            mclk=_PIN_MCLK,
            rst=_PIN_RST,
            sample_rate=self._sample_rate,
        )

        # Configure I2S Bus
        self._audio_in = I2SIn(
            bit_clock=_PIN_BCLK,
            word_select=_PIN_WCLK,
            data=_PIN_DIN,
            sample_rate=self._codec.sample_rate,
            bit_depth=self._codec.bit_depth,
            samples_signed=True,
            mono=self._mono,
        )
        
        if not self.usb_connected:
            self._audio_out = I2SOut(
                bit_clock=_PIN_BCLK,
                word_select=_PIN_WCLK,
                data=_PIN_DOUT,
                external_clock=True,
            )

        else:
            # USB Output Mixer
            self._usb_mixer = Mixer(
                voice_count=1,
                **self.audiosample_args,
            )
            self._sample = None

        # Connect IN1L to Left MICPGA
        input_gain = input_gain if input_gain is not None else float(supervisor.get_setting("INPUT_GAIN", 0.0))  # dB
        self._codec.connect_left_input(INPUT_1, IMPEDANCE_40K)
        self._codec.left_input_gain = input_gain  # dB
        if not self._mono:
            self._codec.connect_right_input(INPUT_1, IMPEDANCE_40K)
            self._codec.right_input_gain = input_gain  # dB

        # Setup DAC Output
        self._codec.left_dac_enabled = True
        self._codec.left_dac_to_left_line_output = True
        if not self._mono:
            self._codec.right_dac_enabled = True
            self._codec.right_dac_to_right_line_output = True

        # Setup ADC Input
        self._codec.left_adc_volume = 0.0  # dB
        self._codec.left_adc_enabled = True
        self._codec.left_adc_muted = False
        if not self._mono:
            self._codec.right_adc_volume = 0.0  # dB
            self._codec.right_adc_enabled = True
            self._codec.right_adc_muted = False

        # Setup Passthrough Input Mixer
        self._codec.left_input_passthrough_enabled = True
        self._codec.left_input_to_left_line_output = True
        if not self._mono:
            self._codec.right_input_passthrough_enabled = True
            self._codec.right_input_to_right_line_output = True

        # Line Output
        output_gain = output_gain if output_gain is not None else int(supervisor.get_setting("OUTPUT_GAIN", 0))  # dB
        self._codec.left_line_output_enabled = True
        self._codec.left_line_output_gain = output_gain
        self._codec.left_line_output_muted = False
        if not self._mono:
            self._codec.right_line_output_enabled = True
            self._codec.right_line_output_gain = output_gain
            self._codec.right_line_output_muted = False

        # True Bypass
        self._pin_bypass = digitalio.DigitalInOut(_PIN_BYPASS)
        self._pin_bypass.switch_to_output()
        if self.usb_connected:
            self._pin_bypass.value = True  # Always on if using USB audio

        # Control Parameters
        self._bypass = bypass
        self._bypass_changed = True
        self._mix = mix
        self._level = level
        self._needs_update = True
        self._update_codec()

        # Prepare initial state
        self.update()

    def _update_codec(self) -> None:
        if not self._needs_update:
            return
        self._needs_update = False

        dac_muted = self._bypass or self._mix <= 0.01 or self._level <= 0.01
        dac_volume = -63.5 * (1.0 - min(self._mix * 2.0, 1.0) * self._level)

        self._codec.left_dac_muted = dac_muted
        self._codec.left_dac_volume = dac_volume
        if not self._mono:
            self._codec.right_dac_muted = dac_muted
            self._codec.right_dac_volume = dac_volume

        input_volume = -99.9 if not self._bypass and self._mix >= 0.99 else (-30.1 * (1.0 - min(2.0 - self._mix * 2.0, 1.0) * self._level)) * (not self._bypass)
        
        self._codec.left_input_passthrough_volume = input_volume
        if not self._mono:
            self._codec.right_input_passthrough_volume = input_volume

        if self.usb_connected:
            self._usb_mixer.voice[0].level = self._level
            if self._bypass_changed:
                self._bypass_changed = False
                self._usb_mixer.stop_voice()
                usb_microphone.stop()
                usb_microphone.play(self._audio_in if self._bypass else self._usb_mixer)
                if not self._bypass and self._sample is not None:
                    self._usb_mixer.play(self._sample)
        else:
            self._pin_bypass.value = not self._bypass
            self._bypass_changed = False

    @property
    def usb_connected(self) -> bool:
        if not supervisor.get_setting("USB_AUDIO", True):
            return False
        if hasattr(self, "_usb_mixer") and self._usb_mixer is None:
            return False
        return supervisor.runtime.usb_connected and usb_microphone is not None

    @property
    def led(self) -> float:
        return self._led.duty_cycle / (2 ** 16 - 1)

    @led.setter
    def led(self, value: float) -> None:
        self._led.duty_cycle = int((2 ** 16 - 1) * min(max(value, 0.0), 1.0))

    @property
    def left_button(self) -> Button:
        return self._left_button
    
    @property
    def right_button(self) -> Button:
        return self._right_button

    @property
    def left_switch(self) -> Debouncer:
        return self._left_switch

    @property
    def right_switch(self) -> Debouncer:
        return self._right_switch

    @property
    def pots(self) -> tuple:
        return tuple([adc.value / (2 ** 16 - 1) for adc in self._pots])

    @property
    def codec(self) -> TLV320AIC3204:
        return self._codec

    @property
    def audio_in(self) -> I2SIn:
        return self._audio_in

    def play(self, sample) -> None:
        if not self.usb_connected:
            self._audio_out.play(sample)
        else:
            self._sample = sample
            self._needs_update = True

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def bits_per_sample(self) -> int:
        return self._audio_in.bits_per_sample

    @property
    def samples_signed(self) -> bool:
        return self._audio_in.samples_signed

    @property
    def channel_count(self) -> int:
        return self._audio_in.channel_count

    @property
    def audiosample_args(self) -> dict:
        return {
            "sample_rate": self.sample_rate,
            "bits_per_sample": self.bits_per_sample,
            "samples_signed": self.samples_signed,
            "channel_count": self.channel_count,
        }

    @property
    def bypass(self) -> bool:
        return self._bypass

    @bypass.setter
    def bypass(self, value: bool) -> None:
        if value is not self._bypass:
            self._bypass = value
            self._bypass_changed = True
            self._needs_update = True

    @property
    def mix(self) -> float:
        return self._mix

    @mix.setter
    def mix(self, value: float) -> None:
        value = min(max(value, 0.0), 1.0)
        if value != self._mix:
            self._mix = value
            self._needs_update = True

    @property
    def level(self) -> float:
        return self._level
    
    @level.setter
    def level(self, value: float) -> None:
        value = min(max(value, 0.0), 1.0)
        if value != self._level:
            self._level = value
            self._needs_update = True

    def update(self) -> None:
        self._update_codec()
        
        for debouncer in (self._left_button, self._right_button, self._left_switch, self._right_switch):
            debouncer.update()
