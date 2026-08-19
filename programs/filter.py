# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

from audiofilters import Filter
import synthio

from uchameleon import uChameleon
import programs

# Constants
MIN_Q       = 0.7
MAX_Q       = 8.0

MIN_FILTER  = 80  # hz
MAX_FILTER  = 4000  # hz

MIN_SPEED   = 0.2  # hz
MAX_SPEED   = 8.0  # hz

MAX_DEPTH   = (MAX_FILTER - MIN_FILTER) / 4  # hz

MIN_POLES   = 1
MAX_POLES   = 2

BUFFER_SIZE = 2048  # bytes

# Initialize Hardware
pedal = uChameleon()

# Audio Objects
lfo = synthio.LFO(
    rate=MIN_SPEED,
    scale=0.0,
)

filter_frequency = synthio.Math(
    synthio.MathOperation.MID,
    20,
    synthio.Math(
        synthio.MathOperation.SCALE_OFFSET,
        lfo,  # auto-wah
        MAX_DEPTH, # max auto-wah depth
        MIN_FILTER
    ),
    20000
)

filters = [
    synthio.Biquad(
        synthio.FilterMode.BAND_PASS,
        filter_frequency,
        MIN_Q,
    )
    for i in range(MAX_POLES)
]

effect = Filter(
    filter=tuple(filters[:MIN_POLES]),

    buffer_size=BUFFER_SIZE,
    **pedal.audiosample_args,
)

# Audio Chain
pedal.play(
    effect.play(
        pedal.audio_in
    )
)

auto = False
while True:
    pedal.update()
    programs.update(pedal)

    pots = pedal.pots
    filter_frequency.b.c = pots[0] * (MAX_FILTER - MIN_FILTER) + MIN_FILTER
    q = pow(pots[1], 2) * (MAX_Q - MIN_Q) + MIN_Q
    for x in filters:
        x.Q = q
    lfo.rate = (pow(pots[2], 2) * (MAX_SPEED - MIN_SPEED) + MIN_SPEED) * (1 + (not pedal.left_switch.value and auto))

    lfo.scale = (not pedal.left_switch.value or auto)

    poles = MIN_POLES if pedal.right_switch.value else MAX_POLES
    if len(effect.filter) != poles:
        effect.filter = tuple(filters[:poles])

    if pedal.left_button.pressed:
        auto = True
    elif pedal.left_button.released:
        auto = False

    if pedal.right_button.released:
        pedal.bypass = not pedal.bypass
        pedal.mix = not pedal.bypass
        effect.mix = not pedal.bypass

    pedal.led = (lfo.value + 1) / 2 * (not pedal.bypass)
