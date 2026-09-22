# Stop the sugoroku game server, whichever way it was started.
#   STATUS = stopped | not_running

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..")).Path

# ポートは共通側（../game_common/mobilelink/network.py）が持っている
$port = 8000
$portFile = Join-Path $root "..\game_common\mobilelink\network.py"
if (Test-Path $portFile) {
    $m = Select-String -Path $portFile -Pattern '^PORT\s*=\s*(\d+)' | Select-Object -First 1
    if ($m) { $port = [int]$m.Matches[0].Groups[1].Value }
}

$listeners = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
if (-not $listeners) {
    "STATUS=not_running"
    exit 0
}

# The venv python.exe is a launcher that spawns the real interpreter as a child,
# so stop the listening process and every python ancestor running main.py.
$targets = @()
foreach ($procId in ($listeners.OwningProcess | Sort-Object -Unique)) {
    $cur = Get-CimInstance Win32_Process -Filter "ProcessId=$procId"
    while ($cur -and $cur.Name -eq "python.exe" -and $cur.CommandLine -like "*main.py*") {
        $targets += $cur.ProcessId
        $cur = Get-CimInstance Win32_Process -Filter "ProcessId=$($cur.ParentProcessId)"
    }
}

foreach ($procId in ($targets | Sort-Object -Unique)) {
    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
}

for ($i = 0; $i -lt 10; $i++) {
    if (-not (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)) { break }
    Start-Sleep -Milliseconds 500
}

"STATUS=stopped"
