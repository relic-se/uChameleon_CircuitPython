# SPDX-FileCopyrightText: Copyright (c) 2026 Tim Cocks for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: MIT

import gc
import json
import synthio
import time

from configurator import create_effects
from uchameleon import uChameleon


# Constants

CONTROL_SMOOTHING = 0.25


# Globals

effects_chain = []
preset_index = None


# Initialize Hardware

pedal = uChameleon()

def _create_block() -> synthio.Math:
    return synthio.Math(synthio.MathOperation.SUM, 0.0, 0.0, 0.0)
control_blocks = {
    "mod": (mod_block := _create_block()),
    "sw0": (sw0_block := _create_block()),
    "sw1": (sw1_block := _create_block()),
    "btn": (btn_block := _create_block()),
}
switch_blocks = (sw0_block, sw1_block)


# Load Presets

CONFIG_PATHS = (
    "/config.json",
    "/configurator/config.json",
)
MAX_PRESETS = 4

def load_config():
    """Read and parse the JSON config file.

    Tries `CONFIG_PATHS` in order; an unreadable or malformed file at a given
    path is not fatal, it just moves on to the next one.

    :return: The parsed config dict, or ``{}`` if none of the paths worked --
        which leaves the demo with nothing but the clean spot in its preset
        cycle and no samples to play.
    """
    for path in CONFIG_PATHS:
        try:
            with open(path, "r") as file:
                return json.load(file)
        except (OSError, ValueError) as error:
            print("config {}: {}".format(path, error))
    return {}


CONFIG = load_config()
PACK_NAME = CONFIG.get("name", "none")

# Presets are passed to config_loader whole, since a preset is more than its
# effect list: it may carry a "blocks" mapping of LFOs and Math blocks that
# its effects refer to by name.
PRESETS = tuple(CONFIG.get("presets", ())[:MAX_PRESETS])


# Effects Chain

def teardown() -> None:
    """Stop the current voice, free the current chain's effects"""
    global effects_chain
    pedal.stop()
    for effect in effects_chain:
        effect.deinit()
    effects_chain = []
    gc.collect()


def build(preset):
    """Wire up ``preset`` as the live chain on mixer voice 0.

    WIRING ORDER MATTERS. Work from the voice input backwards, so the call
    that hands the mic to something is the LAST one:

        mixer.voice[0].play(head) -> ... -> tail.play(mic)

    The output side is the mixer itself, wired to I2SOut once at startup. That
    means preset switching does not restart the clock source: it only replaces
    the source feeding mixer voice 0. The clock follower I2SIn re-syncs when
    something calls play() *on the mic* (or on an effect that eventually feeds
    the mic); effects do not propagate reset_buffer(), so the mic must be wired
    last.

    :param preset: A preset from the config, or an empty one for the clean
        spot, where the mic is played directly.
    """
    global effects_chain
    if not preset:
        effects_chain = []
        pedal.play(pedal.audio_in)
        return

    # Build first: a config error or an out-of-memory here must not leave a
    # half-wired graph running. create_effects() builds without wiring, which
    # is what lets the wiring below run output-first.
    effects_chain = create_effects(preset, blocks=control_blocks, **pedal.audiosample_args)
    if not effects_chain:
        pedal.play(pedal.audio_in)
        return

    pedal.play(effects_chain[-1])
    for index in range(len(effects_chain) - 1, 0, -1):
        effects_chain[index].play(effects_chain[index - 1])
    effects_chain[0].play(pedal.audio_in)


def select_preset(index):
    """Make preset cycle position ``index`` the active chain.

    The switch is done with the DAC soft-muted, since tearing the graph down
    and back up puts a step in the output. A preset that fails to build (an
    effect this firmware lacks, or one delay line too many for RAM) falls back
    to the clean spot rather than taking the demo down.

    :param ctx: The mutable state container.
    :param index: The preset position to activate.
    """
    global preset_index

    bypassed = pedal.bypass
    pedal.bypass = True
    pedal.update()
    teardown()

    preset_index = index
    try:
        build(PRESETS[index] if 0 <= index < len(PRESETS) else [])
    except (ValueError, MemoryError) as error:
        print("preset {} failed: {}".format(index, error))
        teardown()
        build([])

    print(
        "preset {} of {} ({} effects), {} bytes free".format(
            preset_index, len(PRESETS), len(effects_chain), gc.mem_free()
        )
    )
    pedal.bypass = bypassed
    pedal.update()


# Control Loop

print(
    "pack {!r}, {} preset(s)".format(
        PACK_NAME, len(PRESETS)
    )
)

def update_control_block(block: synthio.Math, value: float|bool) -> None:
    if type(value) is bool:
        value = float(not value)
    value = min(max(value, 0.0), 1.0)
    block.a += (value - block.a) * CONTROL_SMOOTHING

def update_controls(mod_value: float) -> None:
    """Update `control_blocks` from the current control values, 0.0 off to 1.0 on."""
    update_control_block(mod_block, mod_value)
    for i, x in enumerate((pedal.left_switch, pedal.right_switch)):
        update_control_block(switch_blocks[i], x.value)
    update_control_block(btn_block, pedal.left_button.value)

for i in range(int(1 / CONTROL_SMOOTHING) + 1):
    pedal.update()
    update_controls()

select_preset(0)

try:

    _right_long_press = False

    while True:
        pedal.update()

        pedal.mix, pedal.level, mod_value = pedal.pots
        update_controls(mod_value)

        if pedal.left_button.long_press:
            select_preset((preset_index - 1) % len(PRESETS))

        if pedal.right_button.long_press:
            _right_long_press = True
            select_preset((preset_index + 1) % len(PRESETS))
        elif pedal.right_button.released:
            _right_long_press = False
            if not _right_long_press:
                pedal.bypass = not pedal.bypass

        time.sleep(0.01)

except KeyboardInterrupt:
    teardown()
    for effect in effects_chain:
        effect.deinit()
    pedal.deinit()
