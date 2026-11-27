# SPDX-FileCopyrightText: 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: GPLv3

"""Hardware-in-the-loop audio test for the uChameleon.

Connect the pedal over USB and patch its output jack to its input jack. The test stops the running
program, plays a tone through the codec's DAC, records it through the ADC and analyzes the
recording on this computer. See README.md for details.
"""

import argparse
import base64
import json
import sys
import time
from pathlib import Path

import numpy as np
import serial
from serial.tools import list_ports

from analysis import analyze_harmonics, analyze_silence, analyze_tone

HERE = Path(__file__).parent
USB_VENDORS = (0x239A, 0x2E8A)  # Adafruit, Raspberry Pi

DEFAULTS = {
    "sample_rate": 44100,
    "input_gain": 8.0,  # dB, as in settings.toml
    "output_gain": 3,  # dB, as in settings.toml
    "dac_db": 0.0,
    "amplitude": 0.25,
    "tone_samples": 441,
    "tone_cycles": 30,
    "settle": 0.5,
    "passthrough_db": None,
    "lib_path": None,
    "codec_first": False,
    "mclk_divider": 27,
    "mclk_multiplier": 256,
}

# Clock configurations of the codec. "pwm12" is the behaviour before the clocking fixes.
CLOCKS = {
    "pwm12-150": {"clock": "pwm12", "cpu_frequency": 150_000_000, "codec_first": True},
    "pwm12-300": {"clock": "pwm12", "cpu_frequency": 300_000_000, "codec_first": True},
    "bclk-150": {"clock": "bclk", "cpu_frequency": 150_000_000},
    "bclk-304.8": {"clock": "bclk", "cpu_frequency": 304_800_000},
    "mclk-304.8": {"clock": "mclk", "cpu_frequency": 304_800_000},
}

SIGNALS = {
    "tone3k": {"tone_cycles": 30},
    "tone1k": {"tone_cycles": 10},
    "silence": {"amplitude": 0.0},
}


class Board:
    """Runs code on a CircuitPython device through the raw REPL of its serial console."""

    def __init__(self, port: str) -> None:
        self._serial = serial.Serial(port, 115200, timeout=1, write_timeout=5)
        self._pending = bytearray()

    def close(self) -> None:
        self._serial.close()

    def _read_until(self, ending: bytes, timeout: float) -> bytes:
        """Read up to and including `ending`, keeping anything after it for the next read."""
        deadline = time.monotonic() + timeout
        while ending not in self._pending:
            if time.monotonic() > deadline:
                received = bytes(self._pending[-200:])
                raise TimeoutError(f"No {ending!r} from device, received {received!r}")
            self._pending += self._serial.read(max(self._serial.in_waiting, 1))
        end = self._pending.index(ending) + len(ending)
        data = bytes(self._pending[:end])
        del self._pending[:end]
        return data

    def enter_raw_repl(self) -> None:
        for attempt in range(3):
            self._serial.write(b"\r\x03")  # stop the running program
            time.sleep(0.1)
            self._serial.write(b"\x03")
            time.sleep(0.5)
            self._serial.write(b"\x02")  # leave a raw REPL that was left open
            time.sleep(0.3)
            self._serial.write(b"\r")  # "press any key to enter the REPL"
            time.sleep(0.3)
            self._serial.reset_input_buffer()
            self._pending.clear()
            self._serial.write(b"\x01")
            try:
                self._read_until(b"raw REPL; CTRL-B to exit\r\n>", 3)
                return
            except TimeoutError:
                if attempt == 2:
                    raise

    def exit_raw_repl(self, reload: bool = False) -> None:
        self._serial.write(b"\x02")
        if reload:
            time.sleep(0.2)
            self._serial.write(b"\x04")  # reload code.py

    def run(self, code: str, timeout: float = 30) -> str:
        data = code.encode()
        for start in range(0, len(data), 256):
            self._serial.write(data[start : start + 256])
            time.sleep(0.01)
        self._serial.write(b"\x04")
        self._read_until(b"OK", 5)
        output = self._read_until(b"\x04", timeout)[:-1]
        error = self._read_until(b"\x04", timeout)[:-1]
        self._read_until(b">", 5)
        if error:
            raise RuntimeError(error.decode(errors="replace"))
        return output.decode(errors="replace")

    def upload(self, local: Path, remote: str) -> None:
        """Write a file to the device. Only works while the USB drive is disabled by boot.py."""
        self.run(
            "import binascii, os, storage\n"
            "storage.remount('/', False)\n"
            f"path = {remote!r}\n"
            "parts = path.strip('/').split('/')[:-1]\n"
            "for i in range(len(parts)):\n"
            "    try:\n"
            "        os.mkdir('/' + '/'.join(parts[: i + 1]))\n"
            "    except OSError:\n"
            "        pass\n"
            "f = open(path, 'wb')\n"
        )
        data = local.read_bytes()
        for start in range(0, len(data), 768):
            chunk = base64.b64encode(data[start : start + 768]).decode()
            self.run(f"f.write(binascii.a2b_base64({chunk!r}))\n")
        self.run("f.close()\nstorage.remount('/', True)\n")


def find_port(port: str | None) -> str:
    if port:
        return port
    ports = [p for p in list_ports.comports() if p.vid in USB_VENDORS]
    if len(ports) != 1:
        found = ", ".join(p.device for p in list_ports.comports()) or "none"
        sys.exit(f"Could not pick a serial port (found: {found}), use --port")
    return ports[0].device


def parse(output: str) -> tuple[dict, np.ndarray]:
    meta = None
    encoded = []
    in_data = False
    for line in output.splitlines():
        if line.startswith("HIL-META "):
            meta = json.loads(line[len("HIL-META ") :])
        elif line == "HIL-DATA-BEGIN":
            in_data = True
        elif line == "HIL-DATA-END":
            in_data = False
        elif in_data:
            encoded.append(line)
    if meta is None:
        raise RuntimeError(f"No result from device:\n{output}")
    samples = np.frombuffer(base64.b64decode("".join(encoded)), dtype="<i2")
    return meta, samples


def capture(board: Board, config: dict) -> tuple[dict, np.ndarray]:
    code = (HERE / "device_capture.py").read_text() + f"\nrun({config!r})\n"
    return parse(board.run(code, timeout=120))


def check(name: str, passed: bool, detail: str) -> bool:
    print(f"{'PASS' if passed else 'FAIL'}  {name}: {detail}")
    return passed


def firmware(board: Board, lib: str | None = None) -> bool:
    """Checks of the firmware that is installed on the device."""
    code = (HERE / "device_firmware.py").read_text()
    if lib:
        code = f"import sys{chr(10)}sys.path.insert(0, {lib!r}){chr(10)}" + code
    board.run(code, timeout=60)
    passed = True

    # Note detection: A4 played as 44 cycles in 4410 samples. The length is even because the mixer
    # that plays the tone drops the last sample of a loop with an odd length.
    config = {
        "cycles": 44,
        "length": 4410,
        "amplitude": 0.5,
        "sensitivity": 0.9,
        "buffer_size": 2048,
        "updates": 12,
    }
    result, _ = parse(board.run(f"detect({config!r})\n", timeout=60))
    frequency = result["frequency"] or 0.0
    passed &= check(
        "detect is active",
        result["active"] and result["updates"] == config["updates"],
        f"level {result['level']:.2f} after {result['updates']} updates",
    )
    passed &= check("detect note", result["notename"] == "A4", f"{result['notename']!r}, expected 'A4'")
    passed &= check(
        "detect frequency",
        abs(frequency - 440.0) < 44100 / 1024,
        f"{frequency:.1f} Hz, expected 440 Hz within one bin ({result['update_ms']:.1f} ms per update)",
    )

    # Distortion with boost: a DC offset at the input must not add even harmonics
    config = {
        "cycles": 10,
        "length": 441,
        "amplitude": 0.1,
        "offset": 100,
        "input_filter": 40,
        "mode": "CLIP",
        "pre_gain": 24,
        "drive": 0.5,
        "output_filter": 12000,
        "capture_samples": 44100,
    }
    for input_filter in (0, 40):
        config["input_filter"] = input_filter
        _, samples = parse(board.run(f"distortion({config!r})\n", timeout=90))
        result = analyze_harmonics(samples[4410:], config["cycles"], config["length"])
        detail = (
            f"even harmonics {result['even_harmonics_dbc']} dBc,"
            f" aliasing and noise {result['non_harmonic_dbc']} dBc"
        )
        if input_filter:
            passed &= check("distortion with input filter", result["even_harmonics_dbc"] < -55, detail)
        else:
            print(f"INFO  distortion without input filter: {detail}")

    board.run("finish()\n")
    return passed


def measure(board: Board, clock: str, signal: str, args: argparse.Namespace) -> dict:
    config = dict(DEFAULTS)
    config.update(CLOCKS[clock])
    config.update(SIGNALS[signal])
    config["label"] = f"{clock}/{signal}"
    config["lib_path"] = args.lib
    config["passthrough_db"] = args.passthrough
    for override in args.set:
        key, _, value = override.partition("=")
        if key not in config:
            sys.exit(f"Unknown setting: {key}")
        config[key] = json.loads(value)
    config["capture_samples"] = int(args.seconds * config["sample_rate"])

    meta, samples = capture(board, config)
    samples = samples[config["sample_rate"] // 10 :]  # skip the first 100 ms
    if config["amplitude"] > 0.0:
        result = analyze_tone(
            samples, config["tone_cycles"], config["tone_samples"], meta["bus_sample_rate"]
        )
    else:
        result = analyze_silence(samples)
    if args.raw:
        Path(args.raw).mkdir(parents=True, exist_ok=True)
        np.save(Path(args.raw) / f"{clock}_{signal}.npy", samples)
    return {"clock": clock, "signal": signal, "device": meta, "result": result}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", help="serial port of the device, detected if omitted")
    commands = parser.add_subparsers(dest="command", required=True)

    upload = commands.add_parser("upload", help="copy a file to the device")
    upload.add_argument("local", type=Path)
    upload.add_argument("remote", help="absolute path on the device")

    run = commands.add_parser("run", help="record and analyze the loopback signal")
    run.add_argument("clocks", nargs="+", choices=sorted(CLOCKS))
    run.add_argument("--signals", nargs="+", choices=sorted(SIGNALS), default=sorted(SIGNALS))
    run.add_argument("--lib", help="folder on the device to load relic_tlv320aic3204 from")
    run.add_argument("--seconds", type=float, default=1.5, help="length of each recording")
    run.add_argument("--passthrough", type=float, help="enable the dry passthrough at this dB")
    run.add_argument("--output", type=Path, help="write the results to this JSON file")
    run.add_argument("--raw", help="folder to save the raw recordings in")
    run.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="KEY=VALUE",
        help="override a setting of the device script, for example sample_rate=48000",
    )

    check_firmware = commands.add_parser(
        "firmware", help="check the firmware that is installed on the device"
    )
    check_firmware.add_argument("--lib", help="folder on the device to load modules from first")
    commands.add_parser("resume", help="restart the program on the device")

    args = parser.parse_args()
    board = Board(find_port(args.port))
    try:
        board.enter_raw_repl()
        if args.command == "upload":
            board.upload(args.local, args.remote)
            board.exit_raw_repl()
        elif args.command == "resume":
            board.exit_raw_repl(reload=True)
        elif args.command == "firmware":
            passed = firmware(board, args.lib)
            board.exit_raw_repl()
            if not passed:
                sys.exit(1)
        else:
            results = []
            for clock in args.clocks:
                for signal in args.signals:
                    entry = measure(board, clock, signal, args)
                    results.append(entry)
                    print(f"{clock:11} {signal:8} {json.dumps(entry['result'])}")
            board.exit_raw_repl()
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(results, indent=2) + "\n")
    finally:
        board.close()


if __name__ == "__main__":
    main()
