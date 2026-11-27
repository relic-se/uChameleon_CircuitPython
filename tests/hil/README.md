# Hardware-in-the-loop audio test

Plays a tone through the codec's DAC, records it through the ADC and measures the recording on the
computer. It is used to check changes to the codec configuration and clocking on real hardware.

## Setup

1. Patch the output jack of the pedal to its input jack with an instrument cable.
2. Connect the pedal over USB without holding the left footswitch, so that the serial console is
   available and the USB drive is disabled.
3. Install the requirements: `pip install -r tests/hil/requirements.txt`

## Usage

```
python tests/hil/run.py run bclk-150 mclk-304.8 --output tests/hil/results/example.json
```

Each clock configuration is measured with a 3 kHz tone, a 1 kHz tone and silence. The running
program is stopped for the test, restart it with `python tests/hil/run.py resume`.

To test a driver that is not installed on the device, upload it to a separate folder and load it
from there:

```
python tests/hil/run.py upload ../CircuitPython_TLV320AIC3204/relic_tlv320aic3204.py /hil/relic_tlv320aic3204.py
python tests/hil/run.py run mclk-304.8 --lib /hil
```

## Firmware checks

```
python tests/hil/run.py firmware
```

Checks the firmware that is installed on the device and exits with an error if a check fails:

- Note detection reports A4 for a 440 Hz tone.
- The distortion chain does not turn a DC offset at the input into even harmonics.

Use `--lib /folder` to load modules from another folder on the device first, for example to check a
changed `detect.py` before installing it.

## Program checks

```
python tests/hil/run.py programs
```

Runs the programs of this repository that listen to the input (`level`, `tuner`, `synth` and
`sampler`) on the device, without installing them, and plays three tones to their input. Name the
programs to run only some of them. The modules and libraries are the ones on the device, so
`--lib /folder` is needed for changes outside of the program itself.

A program is played at a level of 0, so that it only hears the tones through the patch cable. What
it does is read from its global names: the note that the tuner shows, the note that the synth plays
and the frequency that the sampler plays at.

## Clock configurations

| Name | Codec clock source | System clock |
|------|--------------------|--------------|
| `pwm12-150` | PLL from a 12 MHz main clock requested from `PWMOut` | 150 MHz |
| `pwm12-300` | PLL from a 12 MHz main clock requested from `PWMOut` | 300 MHz |
| `bclk-150` | PLL from BCLK | 150 MHz |
| `bclk-304.8` | PLL from BCLK | 304.8 MHz |
| `mclk-304.8` | Main clock at 256 times the frame rate, no PLL | 304.8 MHz |

`mclk-304.8` needs a driver with the `mclk_multiplier` argument.

## Results

| Value | Meaning |
|-------|---------|
| `level_dbfs` | Level of the recorded tone |
| `thd_n_db` | Everything in the recording that is not the tone, relative to the tone |
| `thd_n_typical_db` | The same, ignoring short glitches |
| `glitches` | Short bursts of error, as caused by a dropped or repeated sample |
| `slips` | Lasting steps in the phase of the tone of at least half a sample |
| `phase_rms_deg` | Variation of the phase of the tone |
| `frequency_error_ppm` | Difference between the played and the recorded frequency |
| `noise_dbfs` | Level of the recording with the DAC muted |

A codec that is synchronized with the I2S bus has no glitches or slips, and `thd_n_db` equals
`thd_n_typical_db`.
