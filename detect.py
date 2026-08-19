# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import math
import ulab.numpy as np
import ulab.utils

from audioi2sin import I2SIn

LOG2_A4 = math.log(440, 2)
NOTES = ["A", "A#/Bb", "B", "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab"]

class Detect:

    def __init__(
        self,
        attack: float = 0.01,  # begins calculation when relative level is above this value
        release: float = 0.0025,  # ends calculation when relative level is below this value
        cutoff: float = 0.25,  # only measure frequencies above this relative threshold
        offset: float = -11.5,  # offset measured during calibration with A4 (440hz)
        scale: float = 0.25,  # linear scale up to 1.0 to tame lower frequencies
        sample_rate: int = 44100,  # hz
        buffer_size: int = 4096,  # bytes
    ):
        self._attack, self._release = attack, release
        self._cutoff, self._offset = cutoff, offset
        
        # Create recording buffer
        self._buffer = array.array("h", [0] * buffer_size)

        # Determine the minimum and maximum possible frequencies
        self._min_freq = sample_rate / buffer_size
        self._max_freq = sample_rate / 2  # nyquist

        # Linear distribution of indexes used to calculate weighted mean
        self._dist = np.arange(buffer_size // 2, dtype=np.int16)

        # Linear scale
        self._scale = np.arange(scale, 1.0, (1.0 - scale) / (buffer_size / 2), dtype=np.float)[:buffer_size // 2]

        self.reset()

    def reset(self) -> None:
        self._active = False

    @property
    def active(self) -> bool:
        return self._active

    def process(self, mic: I2SIn) -> tuple|None:
        # Grab a data from the input and convert it to an np.ndarray object
        mic.record(self._buffer, len(self._buffer))
        data = np.array(self._buffer, dtype=np.int16)

        # Calculate maximum level
        mean = np.mean(data)
        level = min(max((np.max(data) - mean) / 32768, 0.0), 1.0)
        
        # Decide whether or not to perform calculations using basic noise gate
        if not self._active and level > self._attack:
            self._active = True
        elif self._active and level < self._release:
            self._active = False
        if not self._active:
            return None
        
        # Perform Fourier Fast Transform (FFT) algorithm on audio signal
        data = ulab.utils.spectrogram(data)
        
        # Remove upper half of spectrogram
        data = data[:len(data)//2]

        # Clear first entry (which is usually very large)
        data[0] = 0.0

        # Apply linear scale up to 1.0
        data *= self._scale
        
        # Replace elements below upper threshold with 0
        threshold = (np.max(data) - np.min(data)) * self._cutoff + np.min(data)
        data = np.where(data > threshold, data, 0.0)
        
        # Only keep largest area of values
        areas = []
        area = None
        for i in range(len(data)):
            if data[i] > 0.0:
                if area is None:
                    area = [i, i, 0]
                area[1] += 1
                area[2] += data[i]
            elif area is not None:
                areas.append(area)
                area = None
        if area is not None:
            areas.append(area)
        
        # Sort areas by size
        areas = sorted(areas, key=lambda x: x[1])
        
        # Clear all areas besides the largest
        for i in range(1, len(areas)):
            for j in range(areas[i][0], areas[i][1]):
                data[j] = 0.0
        
        # Get the center index using weighted mean
        index = np.sum(data * self._dist) / np.sum(data)
        
        # Calculate frequency from index
        frequency = (self._max_freq - self._min_freq) * (index / (len(data) - 1)) + self._min_freq + self._offset
        
        # Determine MIDI note value and note name
        notenum = round(12 * (math.log(frequency, 2) - LOG2_A4) + 69)
        notename = "{:s}{:d}".format(NOTES[(notenum - 21) % 12], (notenum - 12) // 12)
        
        # Determine desired frequency
        target_frequency = math.pow(2, (notenum - 69) / 12) * 440
        
        # Calculate cents
        cents = 1200 * math.log(frequency / target_frequency)
        
        return (notename, cents)
