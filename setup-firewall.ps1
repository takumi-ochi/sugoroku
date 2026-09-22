# スマホからこのPCのサーバーへ接続できるようにする。
# 中身は共通側にある（どのゲームでもやることが同じなので）。
#
# 実行: PowerShellを「管理者として実行」して
#         .\setup-firewall.ps1

& (Join-Path $PSScriptRoot "..\game_common\setup-firewall.ps1") -Port 8000
