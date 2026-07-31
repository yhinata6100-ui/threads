# Threads自動投稿の定期実行をWindowsタスクスケジューラに登録する。
#
# 使い方（PowerShellを「管理者として実行」で開いてから）:
#   cd <このリポジトリのフォルダ>
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
#   .\windows\register_tasks.ps1
#
# 事前に windows\setup.bat でAPIキーを設定しておくこと。
# PCの電源が入っていて、Windowsにログインしている時間帯のみ動作する。

$ErrorActionPreference = "Stop"
$winDir = $PSScriptRoot
$repoRoot = Split-Path -Parent $winDir

function Register-ThreadsTask {
    param(
        [string]$Name,
        [string]$ScriptPath,
        $Trigger
    )
    $action = New-ScheduledTaskAction -Execute $ScriptPath -WorkingDirectory $repoRoot
    $settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
    Register-ScheduledTask -TaskName $Name -Action $action -Trigger $Trigger -Settings $settings -Force | Out-Null
    Write-Host "登録: $Name"
}

# 予約投稿: 8:00〜23:55、10分おき
$postTrigger = New-ScheduledTaskTrigger -Once -At "08:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 10) `
    -RepetitionDuration (New-TimeSpan -Hours 15 -Minutes 55)
$postTrigger.Repetition.StopAtDurationEnd = $false
Register-ThreadsTask -Name "Threads-PostScheduled" -ScriptPath "$winDir\run_post_scheduled.bat" -Trigger $postTrigger

# メトリクス同期: 8:00〜23:30、30分おき
$syncTrigger = New-ScheduledTaskTrigger -Once -At "08:00" `
    -RepetitionInterval (New-TimeSpan -Minutes 30) `
    -RepetitionDuration (New-TimeSpan -Hours 15 -Minutes 30)
$syncTrigger.Repetition.StopAtDurationEnd = $false
Register-ThreadsTask -Name "Threads-SyncMetrics" -ScriptPath "$winDir\run_sync_metrics.bat" -Trigger $syncTrigger

# KPI保険書き出し: 毎日23:30
$exportTrigger = New-ScheduledTaskTrigger -Daily -At "23:30"
Register-ThreadsTask -Name "Threads-ExportKpi" -ScriptPath "$winDir\run_export_kpi.bat" -Trigger $exportTrigger

# トークンリフレッシュ: 毎月1日・15日 9:00
$refreshTrigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth 1,15 -At "09:00"
Register-ThreadsTask -Name "Threads-RefreshToken" -ScriptPath "$winDir\run_refresh_token.bat" -Trigger $refreshTrigger

Write-Host ""
Write-Host "完了。タスクスケジューラ（taskschd.msc）で「Threads-」を検索すると確認できます。"
Write-Host "削除する場合は windows\unregister_tasks.ps1 を実行してください。"
