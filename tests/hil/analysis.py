# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

"""Analysis of loopback recordings made by the hardware-in-the-loop audio test."""

import math

import numpy as np

_BURST_WINDOW = 32  # samples of the short-time level used to find glitches
_BURST_RATIO = 4.0  # a glitch is this many times above the typical residual level


def _db(value: float) -> float:
    return float(20 * np.log10(max(value, 1e-12)))


def _count_runs(mask: np.ndarray, gap: int) -> int:
    """Count groups of `True` values, merging groups that are closer than `gap` samples."""
    positions = np.flatnonzero(mask)
    if not positions.size:
        return 0
    return int(1 + np.count_nonzero(np.diff(positions) > gap))


def analyze_tone(samples: np.ndarray, cycles: int, length: int, sample_rate: float) -> dict:
    """Measure a recorded sine wave that was played as a loop of `cycles` cycles in `length` samples.

    The tone is played and recorded by the same codec, so its frequency in the recording only
    stays at the played value if no samples are dropped or repeated on the way. A slipped sample
    steps the phase of the tone by one sample period and leaves a burst in the residual.
    """
    x = samples.astype(np.float64) / 32768
    omega = 2 * np.pi * cycles / length

    # Track the tone with a moving average over a whole number of cycles. This follows slow phase
    # changes while rejecting DC and every harmonic of the tone.
    period = length // math.gcd(cycles, length)
    kernel = np.ones(period) / period
    n = np.arange(len(x))
    baseband = np.convolve(x * np.exp(-1j * omega * n), kernel, mode="valid")
    dc = np.convolve(x, kernel, mode="valid")
    centre = n[(period - 1) // 2 :][: len(baseband)]
    fundamental = 2 * np.real(baseband * np.exp(1j * omega * centre))
    residual = x[centre] - fundamental - dc

    amplitude = 2 * float(np.median(np.abs(baseband)))
    reference = amplitude / np.sqrt(2)

    # Glitches are short bursts in the residual
    short = np.sqrt(np.convolve(residual**2, np.ones(_BURST_WINDOW) / _BURST_WINDOW, mode="valid"))
    typical = float(np.median(short))
    glitches = _count_runs(short > _BURST_RATIO * max(typical, 1e-6), period)

    # A net slip moves the phase by one sample period (omega) and it stays there
    phase = np.unwrap(np.angle(baseband))
    lag = 2 * period
    slips = _count_runs(np.abs(phase[lag:] - phase[:-lag]) > omega / 2, lag)

    index = np.arange(len(phase))
    trend = np.polyfit(index, phase, 1)
    duration = len(x) / sample_rate

    return {
        "level_dbfs": round(_db(amplitude), 2),
        "thd_n_db": round(_db(np.sqrt(np.mean(residual**2)) / reference), 2),
        "thd_n_typical_db": round(_db(typical / reference), 2),
        "dc_dbfs": round(_db(abs(float(np.mean(dc)))), 2),
        "glitches": glitches,
        "glitches_per_second": round(glitches / duration, 2),
        "slips": slips,
        "slips_per_second": round(slips / duration, 2),
        "phase_rms_deg": round(float(np.degrees(np.std(phase - np.polyval(trend, index)))), 3),
        "frequency_error_ppm": round(float(trend[0] / omega * 1e6), 2),
        "clipped": bool(np.max(np.abs(samples)) >= 32767),
    }


def analyze_silence(samples: np.ndarray) -> dict:
    """Measure the noise floor of a recording made with the DAC muted."""
    x = samples.astype(np.float64) / 32768
    dc = float(np.mean(x))
    return {
        "noise_dbfs": round(_db(np.sqrt(np.mean((x - dc) ** 2))), 2),
        "dc_dbfs": round(_db(abs(dc)), 2),
    }
