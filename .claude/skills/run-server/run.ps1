# Run the sugoroku game server in the background (no console window) and report URLs.
# Not running -> start it. Already running -> stop it and start again (picks up code changes).
# Output is KEY=VALUE lines so the caller can parse it.
#   STATUS  = started | restarted | error
#   HOST_URL, JOIN_URL, NETWORK (Private/Public/...), LOG, MESSAGE

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path
$python = Join-Path $root ".venv\Scripts\python.exe"
$stop = Join-Path $PSScriptRoot "..\stop-server\stop.ps1"
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

# ---- stop the running server, if any ----
$status = "started"
if (Test-Listening) {
    # Stopping is stop-server's job; reuse it so there is only one way to stop.
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stop | Out-Null
    if (Test-Listening) {
        # stop.ps1 only stops this game's python main.py. Something else holds the port.
        "STATUS=error"
        "MESSAGE=Port $port is in use by a process that is not this game's main.py."
        exit 1
    }
    $status = "restarted"
}

# ---- first run on this PC: create .venv here (visibly) instead of inside the hidden process ----
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

# ---- start ----
# A hidden cmd hosts the console; python inherits it, so no window appears.
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUNBUFFERED = "1"
$proc = Start-Process -FilePath "cmd.exe" -WorkingDirectory $root -WindowStyle Hidden -PassThru `
    -ArgumentList "/c .venv\Scripts\python.exe main.py > `"$log`" 2>&1"

$ok = $false
for ($i = 0; $i -lt 30; $i++) {
    Start-Sleep -Seconds 1
    if (Test-Listening) { $ok = $true; break }
    if ($proc.HasExited) { break }
}
if (-not $ok) {
    "STATUS=error"
    "MESSAGE=Server did not start. See the log."
    "LOG=$log"
    exit 1
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
