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
REPO_PATH="$(dirname "${PWD}")"
NAME="$(basename "${REPO_PATH}")"

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

echo "Installing requirements..."
circup install -r ../requirements.txt
echo ""

echo "Unpacking program..."
rm -rf "./${NAME}" || true
unzip "../dist/${NAME}.zip"
rm -rf "./${NAME}/lib" || true
echo ""

echo "Locating device path..."
DEVICE_PATH="$(circup list | perl -n -e "/Found device ${BOARD_ID} at (.*),/ && print \$1")"
echo "Found device at ${DEVICE_PATH}\n"

echo "Installing program..."
for dir in $(find ./${NAME} -mindepth 1 -type d)
do
    echo "Making directory ${DEVICE_PATH}${dir##./${NAME}}"
    mkdir "${DEVICE_PATH}${dir##./${NAME}}"
done
for file in $(find ./${NAME} -type f)
do
    echo "Copying ${file##./${NAME}/} to ${DEVICE_PATH}${file##./${NAME}}"
    cp "${file}" "${DEVICE_PATH}${file##./${NAME}}"
done
rm -rf "./${NAME}" || true
echo ""

echo "Device flashed successfully!"
