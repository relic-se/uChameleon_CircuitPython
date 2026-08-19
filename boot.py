# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import digitalio
import microcontroller
import storage
import supervisor
import usb_audio
import usb_cdc
import usb_hid
import usb_midi

from uchameleon import _PIN_BTN0, _PIN_BTN1

# Initialize button inputs
pin_btn0 = digitalio.DigitalInOut(_PIN_BTN0)
pin_btn0.switch_to_input(pull=digitalio.Pull.UP)

pin_btn1 = digitalio.DigitalInOut(_PIN_BTN1)
pin_btn1.switch_to_input(pull=digitalio.Pull.UP)

# Reset to bootloader mode if right button is pressed
if not pin_btn1.value:
    microcontroller.on_next_reset(microcontroller.RunMode.UF2)
    microcontroller.reset()

# Rename device
supervisor.set_usb_identification(
    manufacturer="relic-se",
    product="μChameleon",
)

# Mount and rename drive, allow USB file access if left button is pressed
if pin_btn0.value:
    storage.disable_usb_drive()
storage.remount(
    "/",
    readonly=pin_btn0.value,
    disable_concurrent_write_protection=not pin_btn0.value,
)
mnt = storage.getmount("/")
mnt.label = "uChameleon"

# Disable unused usb features
usb_hid.disable()
usb_cdc.enable(console=True, data=False)

# Setup MIDI
usb_midi.enable()
usb_midi.set_names(
    streaming_interface_name="μChameleon MIDI",
    audio_control_interface_name="μChameleon Audio",
    in_jack_name="μChameleon",
    out_jack_name="μChameleon",
)

# Setup Audio
usb_audio.enable(
    sample_rate=int(supervisor.get_setting("SAMPLE_RATE", 44100)),
    channel_count=1 if supervisor.get_setting("MONO", True) else 2,
    microphone=True,
    speaker=False,
)
