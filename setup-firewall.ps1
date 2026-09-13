# スマホからこのPCのサーバーへ接続できるようにする。
# 管理者権限が必要。実行後は元に戻すコマンドも表示される。
#
# 実行: PowerShellを「管理者として実行」して
#         .\setup-firewall.ps1

$ErrorActionPreference = "Stop"
$PORT = 8000
$RULE = "GameServer $PORT (Private)"

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "管理者権限がありません。PowerShellを『管理者として実行』してから、もう一度実行してください。" -ForegroundColor Red
    exit 1
}

Write-Host "`n=== 変更前 ===" -ForegroundColor Cyan
Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory | Format-Table -AutoSize

# 1) 実際に通信に使っているNICのプロファイルだけをプライベートにする
$ifIndex = (Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Sort-Object RouteMetric | Select-Object -First 1).InterfaceIndex
$profile = Get-NetConnectionProfile -InterfaceIndex $ifIndex

if ($profile.NetworkCategory -eq "Public") {
    Set-NetConnectionProfile -InterfaceIndex $ifIndex -NetworkCategory Private
    Write-Host "[変更] $($profile.Name) ($($profile.InterfaceAlias)) を Public -> Private にしました" -ForegroundColor Green
} else {
    Write-Host "[スキップ] $($profile.Name) は既に $($profile.NetworkCategory) です" -ForegroundColor DarkGray
}

# 2) 8000番の受信を、プライベートプロファイルに限って許可
if (Get-NetFirewallRule -DisplayName $RULE -ErrorAction SilentlyContinue) {
    Write-Host "[スキップ] ファイアウォール規則『$RULE』は既にあります" -ForegroundColor DarkGray
} else {
    New-NetFirewallRule -DisplayName $RULE -Direction Inbound -Protocol TCP `
        -LocalPort $PORT -Profile Private -Action Allow | Out-Null
    Write-Host "[変更] ファイアウォール規則『$RULE』を追加しました" -ForegroundColor Green
}

Write-Host "`n=== 変更後 ===" -ForegroundColor Cyan
Get-NetConnectionProfile | Select-Object Name, InterfaceAlias, NetworkCategory | Format-Table -AutoSize
Get-NetFirewallRule -DisplayName $RULE | Select-Object DisplayName, Direction, Action, Enabled, Profile | Format-Table -AutoSize

Write-Host "元に戻すには（管理者PowerShellで）:" -ForegroundColor Yellow
Write-Host "  Remove-NetFirewallRule -DisplayName `"$RULE`""
Write-Host "  Set-NetConnectionProfile -InterfaceIndex $ifIndex -NetworkCategory Public`n"
