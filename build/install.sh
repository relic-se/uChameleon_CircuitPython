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

REPO_PATH="$(dirname "${PWD}")"
NAME="$(basename "${REPO_PATH}")"

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

echo "Copy complete!"
