# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple
#
# SPDX-License-Identifier: GPLv3

import microcontroller
import os
import supervisor

from uchameleon import uChameleon

KEY = "PROGRAM"
DIR = "/programs"

_programs = None

def _save(value: str) -> None:
    try:
        import cptoml
        import storage
    except ImportError:
        pass
    else:
        try:
            storage.remount("/", False)
            cptoml.put(KEY, value)
            storage.remount("/", True)
        except RuntimeError:
            pass

def _valid(filename: str) -> bool:
    if type(filename) is not str or not filename or filename.startswith(".") or filename.startswith("_") or not filename.endswith(".py"):
        return False
    if _programs is not None and filename not in _programs:
        return False
    return True

def get_all() -> tuple:
    global _programs
    if _programs is None:
        _programs = tuple(sorted(list(filter(lambda x: _valid(x), os.listdir(DIR)))))
    return _programs

def get_default() -> str|None:
    programs = get_all()
    return programs[0] if programs else None

def get_current() -> str|None:
    program = os.getenv(KEY)
    return program if _valid(program) else get_default()

def get_next() -> str|None:
    program = get_current()
    if program is None:
        return None
    programs = get_all()
    return programs[(programs.index(program) + 1) % len(programs)]

def load(program: str|None = None, save: bool = True) -> None:
    if program is None:
        program = get_current()
    if not _valid(program):
        raise OSError("Invalid program")
        
    if save:
        _save(program)

    supervisor.set_next_code_file(
        filename="/".join((DIR, program)),
        reload_on_success=False,
        reload_on_error=False,
        sticky_on_success=False,
        sticky_on_error=False,
        sticky_on_reload=False,
    )
    supervisor.reload()

def load_next(save: bool = True) -> None:
    load(get_next(), save)

_left_long_press = False
_right_long_press = False
def update(device: uChameleon) -> None:
    global _left_long_press, _right_long_press
    
    if device.left_button.long_press:
        _left_long_press = True
    elif device.left_button.released:
        _left_long_press = False

    if device.right_button.long_press:
        _right_long_press = True
    elif device.right_button.released:
        _right_long_press = False

    if _left_long_press and _right_long_press:
        try:
            load_next()
        except OSError:
            # Reset the device in safe mode unable to load program
            microcontroller.on_next_reset(microcontroller.RunMode.SAFE_MODE)
            microcontroller.reset()
    