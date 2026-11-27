# SPDX-FileCopyrightText: Copyright 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
    Erases a device, flashes the latest CircuitPython firmware and installs the program.
.DESCRIPTION
    PowerShell version of flash.sh. Requires picotool, circfirm and circup, and a program bundle
    created by build.py.
.PARAMETER BoardId
    The CircuitPython board id of the device to flash.
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$BoardId = "raspberry_pi_pico2"
)

$ErrorActionPreference = "Stop"

$Latest = (circfirm query latest --pre-release | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $Latest) {
    throw "Could not determine the latest CircuitPython version."
}

Read-Host "Put the device in UF2 bootloader mode and then press enter" | Out-Null

picotool info --device
Write-Host ""
picotool info --basic
Write-Host ""

Read-Host "Are you ready to flash this device? Press enter to continue" | Out-Null

picotool erase --all
Write-Host ""
picotool reboot --usb
Start-Sleep -Seconds 3
Write-Host ""

Write-Host "Installing CircuitPython $Latest..."
circfirm install $Latest --board-id=$BoardId
if ($LASTEXITCODE -ne 0) {
    throw "circfirm failed to install the firmware."
}
Start-Sleep -Seconds 10
Write-Host ""

& (Join-Path $PSScriptRoot "install.ps1") $BoardId

Write-Host "Device flashed successfully!"
