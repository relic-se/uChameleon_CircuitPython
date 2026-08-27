# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import math
import synthio
import ulab.numpy as np
import ulab.utils

_LOG2_A4 = math.log(440, 2)
_NOTE_NAMES = ["A", "A#/Bb", "B", "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab"]

def decouple(data: np.ndarray) -> np.ndarray:
    return data - np.mean(data)

def level_max(data: np.ndarray) -> float:
    return max(abs(np.max(data)), abs(np.min(data)))

def level_abs(data: np.ndarray) -> float:
    data = np.where(data >= 0.0, data, data * -1)
    return np.sum(data) / len(data)

def normalize(data: np.ndarray) -> np.ndarray:
    max_level = max(abs(np.max(data)), abs(np.min(data)))
    return data / max_level

def nearest_pow2(value: int) -> int:
    i = 0
    while True:
        current = 2 ** i
        if current > value:
            return 2 ** (i - 1)
        elif current == value:
            return value
        i += 1

def fftfreq_index(data: np.ndarray, sample_rate: int):
    data = ulab.utils.spectrogram(data[:nearest_pow2(len(data))])
    data = data[1 : (len(data) // 2) - 1]
    freq = np.argmax(data) / len(data) * sample_rate / 4
    return freq

def fftfreq_areas(data: np.ndarray, sample_rate: int, scale: float = 0.25, cutoff: float = 0.25) -> None:
    # Determine buffer_size before performing FFT
    buffer_size = nearest_pow2(len(data))

    # Linear distribution of indexes used to calculate weighted mean
    dist = np.arange(buffer_size // 2, dtype=np.int16)

    # Linear scale
    scale = np.arange(scale, 1.0, (1.0 - scale) / (buffer_size / 2), dtype=np.float)[:buffer_size // 2]

    # Perform Fourier Fast Transform (FFT) algorithm on audio signal
    data = ulab.utils.spectrogram(data[:buffer_size])
    
    # Remove upper half of spectrogram
    data = data[:len(data)//2]

    # Clear first entry (which is usually very large)
    data[0] = 0.0

    # Apply linear scale up to 1.0
    data *= scale
    
    # Replace elements below upper threshold with 0
    threshold = (np.max(data) - np.min(data)) * cutoff + np.min(data)
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
    index = np.sum(data * dist) / np.sum(data)
    
    # Determine the minimum and maximum possible frequencies
    min_freq = sample_rate / buffer_size
    max_freq = sample_rate / 2  # nyquist

    # Calculate frequency from index
    return (max_freq - min_freq) * (index / (len(data) - 1)) + min_freq

def fftfreq_crossings(data: np.ndarray, sample_rate: int) -> float|None:
    count = 0
    first_index = last_index = None
    for i in range(len(data) - 1):
        a, b = data[i], data[i + 1]
        if (a > 0 and b < 0) or (a < 0 and b > 0):
            count += 1
            if first_index is None:
                first_index = i
            else:
                last_index = i
    if count == 0:
        return None
    if first_index is not None:
        count += first_index / len(data)
    if last_index is not None:
        count += (len(data) - last_index) / len(data)
    return sample_rate / len(data) * count / 2

def fftfreq_crossings_threshold(data: np.ndarray, sample_rate: int, threshold: float = 0.75) -> float|None:
    level = level_max(data) * threshold
    data = np.where(data >= level, data, 0.0) + np.where(data <= -level, data, 0.0)

    count = 0
    last_value = first_index = last_index = None
    for i in np.nonzero(data)[0]:
        value = data[i] > 0.0
        if last_value is None:
            last_value = value
        elif value is not last_value:
            count += 1
            if first_index is None:
                first_index = i
            else:
                last_index = i
            last_value = value
    if not count:
        return None
    
    if first_index is not None:
        count += first_index / len(data)
    if last_index is not None:
        count += (len(data) - last_index) / len(data)

    return sample_rate / len(data) * count / 2

class MovingAverage:

    def __init__(self, count: int = 5, weighted: bool = True):
        self._count = count
        self._weights = np.arange(5, dtype=np.float) / count / 2 if weighted else None
        self.reset()

    def reset(self) -> None:
        self._items = None
        self._value = None

    def update(self, value: float) -> None:
        self._value = None
        if self._items is None:
            self._items = np.full(self._count, value)
        else:
            self._items[1:] = self._items[:len(self._items)-1]
            self._items[0] = value

    @property
    def value(self) -> float|None:
        if self._value is not None:
            return self._value
        if self._items is None:
            return None
        if self._weights is None:
            return np.mean(self._items)
        else:
            return np.sum(self._items * self._weights)

class Detect:

    def __init__(
        self,
        sensitivity: float = 0.25,
        attack: float = 1,  # begins calculation when level (relative to sensitivity) is above this value
        sustain: float = 0.9,  # if level dips below this threshold (relative to sensitivity) and then rises above attack again, it will be interpretted as a new note
        release: float = 0.1,  # ends calculation when level (relative to sensitivity) is below this value
        impulse_threshold: float = 0.75,
    ):
        self.sensitivity = sensitivity
        self._attack = min(max(attack, 0.0001), 1.0)
        self._sustain = min(max(sustain, 0.0001), 1.0)
        self._release = min(max(release, 0.0001), 1.0)
        self._impulse_threshold = min(max(impulse_threshold, 0.0), 1.0)

        self._level = MovingAverage(count=3, weighted=False)
        self._frequency = MovingAverage(count=16, weighted=False)

        self.reset()

    def reset(self) -> None:
        self._level.reset()
        self._frequency.reset()

        self._state = None
        self._notenum = self._notename = self._cents = None

    @property
    def sensitivity(self) -> float:
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, value: float) -> None:
        self._sensitivity = min(max(value, 0.0001), 0.9999)

    @property
    def active(self) -> bool:
        return self._state in {synthio.EnvelopeState.ATTACK, synthio.EnvelopeState.SUSTAIN}

    @property
    def level(self) -> float:
        value = self._level.value
        return min(value / (1 - self._sensitivity), 1.0) if value is not None else 0.0

    @property
    def state(self) -> synthio.EnvelopeState|None:
        return self._state

    @property
    def frequency(self) -> float|None:
        return self._frequency.value

    @property
    def notenum(self) -> int|None:
        if self._notenum is not None:
            return self._notenum
        frequency = self._frequency.value
        if frequency is None or frequency <= 0.0:
            return None
        self._notenum = round(12 * (math.log(frequency, 2) - _LOG2_A4) + 69)  # Calculate MIDI note value
        return self._notenum

    @property
    def notename(self) -> str:
        if self._notename is not None:
            return self._notename
        if (notenum := self.notenum) is None:
            return ""
        self._notename = "{:s}{:d}".format(_NOTE_NAMES[(notenum - 21) % 12], (notenum - 12) // 12) 
        return self._notename

    @property
    def cents(self) -> float|None:
        if self._cents is not None:
            return self._cents
        if (notenum := self.notenum) is None:
            return None
        self._cents = 1200.0 * math.log(self._frequency.value / synthio.midi_to_hz(notenum))
        return self._cents

    def update(self, buffer: array.array, sample_rate: int) -> synthio.EnvelopeState|None:
        self._notenum = self._notename = self._cents = None  # Go ahead and dump our cached values        

        # Convert our data to an np.ndarray object with float values ranging from -1.0 to 1.0
        data = np.array(buffer) / 32768
        data = decouple(data)

        # Calculate level
        self._level.update(level_abs(data))
        
        # Decide whether or not to perform calculations using basic noise gate
        state = self._state
        level = self.level
        if state in {None, synthio.EnvelopeState.SUSTAIN, synthio.EnvelopeState.RELEASE} and level >= self._attack:
            state = synthio.EnvelopeState.ATTACK
        elif state is not synthio.EnvelopeState.RELEASE and level <= self._release:
            self._frequency.reset()
            state = synthio.EnvelopeState.RELEASE
        elif state == synthio.EnvelopeState.ATTACK and level <= self._sustain:
            state = synthio.EnvelopeState.SUSTAIN

        # Process signal if we're active
        if state in {synthio.EnvelopeState.ATTACK, synthio.EnvelopeState.SUSTAIN}:

            # Normalize level
            data = normalize(data)

            # Clip to impulse start
            if state == synthio.EnvelopeState.ATTACK:
                impulse_start = 0
                for i, x in enumerate(data):
                    if abs(x) >= self._impulse_threshold:
                        impulse_start = i
                        break
                data = data[impulse_start:]

            # Identify most prominent frequency

            self._frequency.update(frequency)

        # Return new state on change
        if state == self._state:
            return None
        self._state = state
        return state
