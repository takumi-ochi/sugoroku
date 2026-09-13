# Start the sugoroku game server in the background (no console window) and report URLs.
# Output is KEY=VALUE lines so the caller can parse it.
#   STATUS  = already_running | started | error
#   HOST_URL, JOIN_URL, NETWORK (Private/Public/...), LOG, MESSAGE

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$log = Join-Path $env:TEMP "sugoroku-server.log"

$port = 8000
$m = Select-String -Path (Join-Path $root "config.py") -Pattern '^PORT\s*=\s*(\d+)' | Select-Object -First 1
if ($m) { $port = [int]$m.Matches[0].Groups[1].Value }

function Test-Listening {
    $null -ne (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Get-LanIp {
    # Same trick as config.py: ask the OS which local address routes outward.
    $sock = New-Object System.Net.Sockets.Socket([System.Net.Sockets.AddressFamily]::InterNetwork, [System.Net.Sockets.SocketType]::Dgram, [System.Net.Sockets.ProtocolType]::Udp)
    try { $sock.Connect("8.8.8.8", 80); $sock.LocalEndPoint.Address.ToString() }
    catch { "127.0.0.1" }
    finally { $sock.Close() }
}

if (Test-Listening) {
    $status = "already_running"
} else {
    # First run on this PC: create .venv here (visibly) instead of inside the hidden process.
    if (-not (Test-Path $python)) {
        if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
            "STATUS=error"
            "MESSAGE=Python is not installed and .venv does not exist."
            exit 1
        }
        Push-Location $root
        try {
            python -m venv .venv
            & $python -m pip install --disable-pip-version-check -q -r requirements.txt
        } finally { Pop-Location }
    }

    # A hidden cmd hosts the console; python inherits it, so no window appears.
    $env:PYTHONIOENCODING = "utf-8"
    $env:PYTHONUNBUFFERED = "1"
    $proc = Start-Process -FilePath "cmd.exe" -WorkingDirectory $root -WindowStyle Hidden -PassThru `
        -ArgumentList "/c .venv\Scripts\python.exe main.py > `"$log`" 2>&1"

    $status = "error"
    for ($i = 0; $i -lt 30; $i++) {
        Start-Sleep -Seconds 1
        if (Test-Listening) { $status = "started"; break }
        if ($proc.HasExited) { break }
    }
    if ($status -eq "error") {
        "STATUS=error"
        "MESSAGE=Server did not start. See the log."
        "LOG=$log"
        exit 1
    }
}

$ip = Get-LanIp
$network = "Unknown"
$ifIndex = (Get-NetIPAddress -IPAddress $ip -ErrorAction SilentlyContinue).InterfaceIndex
if ($ifIndex) {
    $prof = Get-NetConnectionProfile -InterfaceIndex $ifIndex -ErrorAction SilentlyContinue
    if ($prof) { $network = [string]$prof.NetworkCategory }
}

"STATUS=$status"
"HOST_URL=http://localhost:$port/host"
"JOIN_URL=http://${ip}:$port/"
"NETWORK=$network"
"LOG=$log"
