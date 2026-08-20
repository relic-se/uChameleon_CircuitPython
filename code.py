# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import digitalio
import microcontroller

import programs
from uchameleon import _PIN_BTN0

# Initialize button input
pin_btn0 = digitalio.DigitalInOut(_PIN_BTN0)
pin_btn0.switch_to_input(pull=digitalio.Pull.UP)

if pin_btn0.value:  # don't load program if left button is pressed
    try:
        programs.load(save=False)
    except OSError:
        # Reset the device in safe mode unable to load program
        microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
        microcontroller.reset()
