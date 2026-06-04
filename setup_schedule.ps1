# Setup daily autopilot schedule via Windows Task Scheduler
# Run this once to schedule the autopilot to run every weekday at 4:30 PM.

$TaskName = "AdvanceStockPredictor-Autopilot"
$ProjectDir = "C:\Users\nihal\Videos\New folder\Apps\Coding For Home\Advance Stock Predictor"
$PythonExe = "python"

$Action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$ProjectDir\autopilot_run.py`"" -WorkingDirectory $ProjectDir
$Trigger = New-ScheduledTaskTrigger -Daily -At 04:30PM
$Trigger.DaysOfWeek = "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"

# Only run on weekdays
if ($Trigger.DaysOfWeek -is [string]) {
    $Trigger.DaysOfWeek = @("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")
}

$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force

Write-Host "Scheduled task '$TaskName' created."
Write-Host "Runs weekdays at 4:30 PM."
Write-Host ""
Write-Host "To approve next week's trading:"
Write-Host "  $PythonExe `"$ProjectDir\autopilot_run.py`" --approve"
Write-Host ""
Write-Host "To view status:"
Write-Host "  $PythonExe `"$ProjectDir\autopilot_run.py`" --status"
