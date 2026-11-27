# SPDX-FileCopyrightText: Copyright 2026 Cooper Dalrymple (@relic-se)
#
# SPDX-License-Identifier: MIT

<#
.SYNOPSIS
    Installs the libraries and the built program on a connected CircuitPython device.
.DESCRIPTION
    PowerShell version of install.sh. Run build.py first to create the program bundle in dist.
    Use -WhatIf to see what would be installed without changing the device.
.PARAMETER BoardId
    The CircuitPython board id of the device to install to.
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [Parameter(Position = 0)]
    [string]$BoardId = "raspberry_pi_pico2"
)

$ErrorActionPreference = "Stop"

$RepoPath = Split-Path -Parent $PSScriptRoot
$Name = Split-Path -Leaf $RepoPath
$Bundle = Join-Path $RepoPath "dist\$Name.zip"
$Unpacked = Join-Path $PSScriptRoot $Name

if (-not (Test-Path $Bundle)) {
    throw "Could not find $Bundle, run build.py first."
}

Write-Host "Locating device path..."
$Pattern = "Found device $([regex]::Escape($BoardId)) at (.*?),"
$Found = (circup list 2>&1 | Out-String) -match $Pattern
if (-not $Found) {
    throw "Could not find a device with the board id $BoardId."
}
$DevicePath = $Matches[1].Trim()
Write-Host "Found device at $DevicePath`n"

Write-Host "Installing requirements..."
if ($PSCmdlet.ShouldProcess($DevicePath, "Install libraries from requirements.txt")) {
    circup --path $DevicePath install -r (Join-Path $RepoPath "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "circup failed to install the requirements."
    }
}
Write-Host ""

try {
    Write-Host "Unpacking program..."
    if (Test-Path $Unpacked) {
        Remove-Item $Unpacked -Recurse -Force -WhatIf:$false -Confirm:$false
    }
    Expand-Archive -Path $Bundle -DestinationPath $PSScriptRoot -WhatIf:$false -Confirm:$false
    $Libraries = Join-Path $Unpacked "lib"
    if (Test-Path $Libraries) {
        Remove-Item $Libraries -Recurse -Force -WhatIf:$false -Confirm:$false
    }
    Write-Host ""

    Write-Host "Installing program..."
    foreach ($Item in Get-ChildItem $Unpacked -Recurse) {
        $Relative = $Item.FullName.Substring($Unpacked.Length).TrimStart("\", "/")
        $Target = Join-Path $DevicePath $Relative
        if ($Item.PSIsContainer) {
            if (-not (Test-Path $Target)) {
                Write-Host "Making directory $Target"
                New-Item -ItemType Directory -Path $Target | Out-Null
            }
        }
        else {
            Write-Host "Copying $Relative to $Target"
            Copy-Item -Path $Item.FullName -Destination $Target -Force
        }
    }
    Write-Host ""
}
finally {
    if (Test-Path $Unpacked) {
        Remove-Item $Unpacked -Recurse -Force -WhatIf:$false -Confirm:$false
    }
}

Write-Host "Copy complete!"
