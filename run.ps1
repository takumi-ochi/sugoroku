# 起動用。PowerShellで .\run.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (-not (Test-Path ".venv")) {
    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install --disable-pip-version-check -r requirements.txt
    # スマホ連携は ..\game_common にある。import できるように .pth を置く
    & "..\game_common\install.ps1" $PSScriptRoot
}
.\.venv\Scripts\python.exe main.py
