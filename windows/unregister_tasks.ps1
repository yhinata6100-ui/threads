# register_tasks.ps1 で登録したタスクをすべて削除する。
# PowerShellを「管理者として実行」で開いてから実行すること。

$names = "Threads-PostScheduled", "Threads-SyncMetrics", "Threads-ExportKpi", "Threads-RefreshToken"
foreach ($n in $names) {
    Unregister-ScheduledTask -TaskName $n -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "削除: $n"
}
