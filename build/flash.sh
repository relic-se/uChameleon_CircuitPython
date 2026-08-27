#!/bin/sh

# SPDX-FileCopyrightText: Copyright 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: MIT

# Allow board id to be passed as positional argument
if [[ -z $1 ]];
then 
    BOARD_ID="raspberry_pi_pico2"
else
    BOARD_ID="$1"
fi

LATEST="$(circfirm query latest --pre-release)"

echo "Put the device in UF2 bootloader mode and then press enter."
read

picotool info --device
echo ""
picotool info --basic
echo ""

echo "Are you ready to flash this device? Press enter to continue."
read

picotool erase --all || true
echo ""
picotool reboot --usb
sleep 3
echo ""

echo "Installing latest CircuitPython firmware..."
circfirm install "${LATEST}" --board-id="${BOARD_ID}"
sleep 10
echo ""

./install.sh "${BOARD_ID}"

echo "Device flashed successfully!"
