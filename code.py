# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import microcontroller
import supervisor

import programs

# Initialize button input
if supervisor.runtime.usb_connected:
    import digitalio
    
    from uchameleon import _PIN_BTN0
    
    pin_btn0 = digitalio.DigitalInOut(_PIN_BTN0)
    pin_btn0.switch_to_input(pull=digitalio.Pull.UP)

if not supervisor.runtime.usb_connected or pin_btn0.value:  # don't load program if left button is pressed
    try:
        programs.load(save=False)
    except OSError:
        # Reset the device in safe mode unable to load program
        microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
        microcontroller.reset()
