# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

import array
import math

try:
    from synthio import EnvelopeState, midi_to_hz
    import ulab.numpy as np
    from ulab.utils import spectrogram as fft

except ModuleNotFoundError:
    import numpy as np
    from scipy.fft import fft
    from scipy.signal import find_peaks

    BLINKA = True

else:
    BLINKA = False

_LOG2_A4 = math.log(440, 2)
_NOTE_NAMES = ["A", "A#/Bb", "B", "C", "C#/Db", "D", "D#/Eb", "E", "F", "F#/Gb", "G", "G#/Ab"]

def _sort_peaks(peaks: tuple|list, heights: tuple|list) -> tuple[float]:
    peaks = [(x, heights[i]) for i, x in enumerate(peaks)]
    peaks = sorted(peaks, key=lambda x: x[1], reverse=True)
    return tuple([x[0] for x in peaks])

if not BLINKA:
    _DTYPE_FLOAT = np.float

    def _fftfreq(size: int, spacing: float = 1.0) -> np.ndarray:
        # we're ignoring imaginary half
        return np.arange(size // 2, dtype=np.int16) / (size * spacing)

    def _local_maxima_1d(data: np.ndarray) -> tuple:
        midpoints = []

        i = 1
        while i < len(data) - 1:
            # Test if previous sample is smaller
            if data[i - 1] < data[i]:

                # Find next sample that is unequal to x[i]
                j = i + 1  # Index to look ahead of current sample
                while j < len(data) - 1 and data[j] == data[i]:
                    j += 1

                # Maxima is found if next unequal sample is smaller than x[i]
                if data[j] < data[i]:
                    midpoints.append((i + j - 1) // 2)

                    # Skip samples that can't be maximum
                    i = j
            i += 1

        return tuple(midpoints)

    def _find_peaks(data: np.ndarray, height: float|None = None, sort: bool = True) -> tuple[float]:
        peaks = _local_maxima_1d(data)
        peak_heights = np.array([data[i] for i in peaks], dtype=_DTYPE_FLOAT)

        if height is None:
            height = 7 * np.std(data)

        # Remove elements which are less than the height
        peak_heights = np.where(peak_heights > height, peak_heights, 0)
        valid_peaks = np.nonzero(peak_heights)[0]
        peaks = tuple([peaks[i] for i in valid_peaks])
        if not sort:
            return peaks
        
        peak_heights = np.array([peak_heights[i] for i in valid_peaks], dtype=_DTYPE_FLOAT)
        return _sort_peaks(peaks, peak_heights)
    
else:
    _DTYPE_FLOAT = np.float32

    def _fftfreq(size: int, spacing: float = 1.0) -> np.ndarray:
        return np.fft.fftfreq(size, spacing)[:size // 2]

    def _find_peaks(data: np.ndarray, height: float|None = None, sort: bool = True) -> tuple[float]:
        if height is None:
            height = 7 * np.std(data)
        peaks = find_peaks(data, height=height)
        if not sort:
            return tuple(peaks[0])
        return _sort_peaks(peaks[0], peaks[1]["peak_heights"])

    class EnvelopeState:
        ATTACK = 0
        SUSTAIN = 1
        RELEASE = 2

    def midi_to_hz(notenum: int) -> float:
        return 440.0 * (2.0 ** ((notenum - 69.0) / 12.0))

def _prepare_data(data: list|tuple|array.array|np.ndarray) -> np.ndarray:
    if type(data) is not np.ndarray or data.dtype != _DTYPE_FLOAT:
        # Convert our data to an np.ndarray object with float values ranging from -1.0 to 1.0
        return np.array(data, dtype=_DTYPE_FLOAT) / (2 ** 15)
    else:
        return data

def decouple_signal(data: np.ndarray) -> np.ndarray:
    return data - np.mean(data)

def calculate_level(data: np.ndarray) -> float:
    return np.sum(abs(data)) / len(data)

def _nearest_pow2(value: int, max: int = 32) -> int:
    for i in range(1, max + 1):
        current = 2 ** i
        if current > value:
            return 2 ** (i - 1)
        elif current == value:
            return value
    return None

def _is_pow2(value: int, max: int = 32) -> bool:
    return _nearest_pow2(value, max) == value

class MovingAverage:

    def __init__(self, count: int = 3, weighted: bool = False):
        self._count = count
        self._weights = np.arange(count, dtype=np.float) / count / 2 if weighted else None
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

class Frequency:

    def __init__(self, data_size: int, sample_rate: int, window_size: int = 17):
        if not _is_pow2(data_size):
            raise ValueError("data_size must be a power of 2")
        
        self._data_size = data_size
        self._sample_rate = sample_rate
        self._window_size = min(window_size + 1 if (window_size % 2) == 0 else window_size, 3)
        self._half_window_size = self._window_size // 2

        # Calculate fftfreq plot
        self._fftfreq = _fftfreq(self._data_size, 1 / self._sample_rate)

        # Linear distribution of indexes used to calculate weighted mean
        self._window_dist = np.arange(self._window_size, dtype=np.int16)

    def _get_frequency(self, index: int, data: np.ndarray) -> float|None:
        # Skip weighted mean if we're at the edge
        if index <= self._half_window_size or index >= self._data_size - self._half_window_size - 1:
            return self._fftfreq[index]

        # Isolate the window area
        window = data[index - self._half_window_size:index + self._half_window_size + 1]

        # Get the center index using weighted mean
        window_sum = np.sum(window)
        if window_sum <= 0:
            return None
        weighted_index = np.sum(window * self._window_dist) / window_sum

        # Adjust index by weighted mean
        index += weighted_index - (self._half_window_size)

        # Check if we're centered at a frequency index
        index_floor, index_ceil = math.floor(index), math.ceil(index)
        if index_floor == index_ceil:
            return self._fftfreq[index]

        # Perform linear interpolation to adjust detected frequency
        value_floor, value_ceil = self._fftfreq[index_floor], self._fftfreq[index_ceil]
        return (index - index_floor) * (value_ceil - value_floor) + value_floor

    def process(self, data: list|tuple|array.array|np.ndarray) -> tuple[float]:
        if len(data) != self._data_size:
            raise ValueError("Data size invalid")

        # Convert data to float
        data = _prepare_data(data)

        # Perform FFT
        if BLINKA:
            data = np.abs(fft(data, axis=0)[:len(data) // 2])
        else:
            data = fft(data)[:len(data) // 2]

        # Find the index of the peaks (sorted by height)
        peaks = _find_peaks(data)

        # Calculate frequencies (with windowed weighted mean) for each peak
        frequencies = [self._get_frequency(index, data) for index in peaks]

        # Remove any values with `None`
        return tuple(filter(lambda x: x is not None, frequencies))

def calculate_frequencies(data: list|tuple|array.array|np.ndarray, sample_rate: int) -> tuple[float]:
    data = data[:_nearest_pow2(len(data))]
    return Frequency(len(data), sample_rate).process(data)

def calculate_frequency(data: list|tuple|array.array|np.ndarray, sample_rate: int) -> float|None:
    frequencies = calculate_frequencies(data, sample_rate)
    return frequencies[0] if frequencies else None

class Envelope:

    def __init__(
        self,
        sensitivity: float = 0.25,
        attack: float = 1,  # begins calculation when level (relative to sensitivity) is above this value
        sustain: float = 0.9,  # if level dips below this threshold (relative to sensitivity) and then rises above attack again, it will be interpretted as a new note
        release: float = 0.1,  # ends calculation when level (relative to sensitivity) is below this value
    ):
        self._sensitivity = min(max(sensitivity, 0.0), 1.0)
        self._attack = min(max(attack, 0.0001), 1.0)
        self._sustain = min(max(sustain, 0.0001), 1.0)
        self._release = min(max(release, 0.0001), 1.0)

        self.reset()

    def reset(self) -> None:
        self._level = 0.0
        self._state = None

    @property
    def sensitivity(self) -> float:
        return self._sensitivity

    @sensitivity.setter
    def sensitivity(self, value: float) -> None:
        self._sensitivity = min(max(value, 0.0), 1.0)

    @property
    def active(self) -> bool:
        return self._state in {EnvelopeState.ATTACK, EnvelopeState.SUSTAIN}

    @property
    def level(self) -> float:
        return min(self._level / max(1 - self._sensitivity, 0.0001), 1.0)

    @property
    def state(self) -> EnvelopeState|None:
        return self._state

    def update(self, data: list|tuple|array.array|np.ndarray) -> EnvelopeState|None:
        # Convert to float
        data = _prepare_data(data)
        
        # Decouple signal (re-center around mean)
        data = decouple_signal(data)

        # Update level
        self._level = calculate_level(data)
        
        # Handle state machine
        level = self.level  # Calculate level using sensitivity (in getter)
        if self._state in {None, EnvelopeState.SUSTAIN, EnvelopeState.RELEASE} and level >= self._attack:
            self._state = EnvelopeState.ATTACK
        elif self._state is not EnvelopeState.RELEASE and level <= self._release:
            self._state = EnvelopeState.RELEASE
        elif self._state == EnvelopeState.ATTACK and level <= self._sustain:
            self._state = EnvelopeState.SUSTAIN
        else:
            return None  # no change occurred
        
        # Return new state on change
        return self._state

class Note:

    def __init__(self, data_size: int, sample_rate: int, average_count: int = 5):
        self._envelope = Envelope()
        self._frequency = Frequency(data_size, sample_rate)
        self._frequency_value = MovingAverage(average_count)

        self.reset()

    def reset(self) -> None:
        self._envelope.reset()
        self._frequency_value.reset()
        self._notenum = self._notename = self._cents = None

    @property
    def sensitivity(self) -> float:
        return self._envelope.sensitivity

    @sensitivity.setter
    def sensitivity(self, value: float) -> None:
        self._envelope.sensitivity = value

    @property
    def active(self) -> bool:
        return self._envelope.active

    @property
    def level(self) -> float:
        return self._envelope.level

    @property
    def state(self) -> EnvelopeState|None:
        return self._envelope.state

    @property
    def frequency(self) -> float|None:
        return self._frequency_value.value

    @property
    def notenum(self) -> int|None:
        if self._notenum is not None:
            return self._notenum
        frequency = self._frequency_value.value
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
        self._cents = 1200.0 * math.log(self._frequency_value.value / midi_to_hz(notenum))
        return self._cents

    def update(self, data: list|tuple|array.array|np.ndarray) -> EnvelopeState|None:
        self._notenum = self._notename = self._cents = None  # Go ahead and dump our cached values

        # Convert to float
        data = _prepare_data(data)

        # Update envelope
        state = self._envelope.update(data)

        # Process signal if we're active
        if self._envelope.active:

            # Detect frequencies
            frequencies = self._frequency.process(data)
            if not frequencies:
                return None  # exit just in case something went wrong

            self._frequency_value.update(frequencies[0])  # Use frequency with largest peak

        return state
