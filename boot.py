# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import storage
import supervisor
import usb_audio
import usb_cdc
import usb_hid
import usb_midi

# Rename device
supervisor.set_usb_identification(
    manufacturer="relic-se",
    product="μChameleon",
)

# Rename drive
storage.disable_usb_drive()
storage.remount("/", readonly=True)
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
