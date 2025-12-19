# PowerShell script to kill all running BATCH7 workflows
# This script will:
# 1. Stop all Windows Scheduled Tasks related to BATCH7
# 2. Stop all PowerShell background jobs
# 3. Kill all Python processes related to BATCH7 pipeline

Write-Host "Stopping all BATCH7 workflows..." -ForegroundColor Yellow
Write-Host ""

# 1. Stop and disable scheduled tasks
Write-Host "=== Stopping Scheduled Tasks ===" -ForegroundColor Cyan
$ScheduledTasks = @(
    "BATCH7_Overnight_Images",
    "BATCH7_Overnight_Text",
    "BATCH7_Overnight_Natives",
    "BATCH7_AutoCommit_Webhook"
)

foreach ($TaskName in $ScheduledTasks) {
    $Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($Task) {
        Write-Host "  Stopping task: $TaskName" -ForegroundColor Yellow
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Write-Host "  Disabling task: $TaskName" -ForegroundColor Yellow
        Disable-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        Write-Host "  ✓ Task stopped and disabled" -ForegroundColor Green
    } else {
        Write-Host "  - Task '$TaskName' not found (may not be set up)" -ForegroundColor Gray
    }
}

Write-Host ""

# 2. Stop PowerShell background jobs
Write-Host "=== Stopping PowerShell Background Jobs ===" -ForegroundColor Cyan
$Jobs = Get-Job -ErrorAction SilentlyContinue | Where-Object { 
    $_.Name -like "Process_*" -or 
    $_.Command -like "*batch7*" -or 
    $_.Command -like "*run_batch7*"
}

if ($Jobs) {
    foreach ($Job in $Jobs) {
        Write-Host "  Stopping job: $($Job.Name) (ID: $($Job.Id))" -ForegroundColor Yellow
        Stop-Job -Job $Job -ErrorAction SilentlyContinue
        Remove-Job -Job $Job -Force -ErrorAction SilentlyContinue
        Write-Host "  ✓ Job stopped and removed" -ForegroundColor Green
    }
} else {
    Write-Host "  No BATCH7-related PowerShell jobs found" -ForegroundColor Gray
}

Write-Host ""

# 3. Kill Python processes related to BATCH7
Write-Host "=== Stopping Python Processes ===" -ForegroundColor Cyan
$PythonProcesses = Get-Process -Name python,pythonw -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -like "*batch7*" -or
    $_.CommandLine -like "*run_batch7*" -or
    $_.CommandLine -like "*auto_commit*" -or
    $_.CommandLine -like "*batch7_process*"
}

# Alternative: Get processes by working directory or command line
# Since CommandLine might not be available, we'll check all Python processes
# and let user confirm, or we can be more aggressive

$AllPythonProcesses = Get-Process -Name python,pythonw -ErrorAction SilentlyContinue
$Batch7Processes = @()

foreach ($Proc in $AllPythonProcesses) {
    try {
        $CommandLine = (Get-CimInstance Win32_Process -Filter "ProcessId = $($Proc.Id)").CommandLine
        if ($CommandLine -and (
            $CommandLine -like "*batch7*" -or
            $CommandLine -like "*run_batch7*" -or
            $CommandLine -like "*auto_commit*" -or
            $CommandLine -like "*batch7_process*" -or
            $CommandLine -like "*EpsteinEstateBatch7*"
        )) {
            $Batch7Processes += $Proc
        }
    } catch {
        # If we can't get command line, check if process is in our directory
        try {
            $ProcPath = $Proc.Path
            if ($ProcPath -and $ProcPath -like "*EpsteinEstateBatch7*") {
                $Batch7Processes += $Proc
            }
        } catch {
            # Skip if we can't determine
        }
    }
}

if ($Batch7Processes.Count -gt 0) {
    Write-Host "  Found $($Batch7Processes.Count) BATCH7-related Python process(es):" -ForegroundColor Yellow
    foreach ($Proc in $Batch7Processes) {
        Write-Host "    PID $($Proc.Id): $($Proc.ProcessName)" -ForegroundColor Yellow
        try {
            Stop-Process -Id $Proc.Id -Force -ErrorAction Stop
            Write-Host "    ✓ Process killed" -ForegroundColor Green
        } catch {
            Write-Host "    ✗ Error killing process: $_" -ForegroundColor Red
        }
    }
} else {
    Write-Host "  No BATCH7-related Python processes found" -ForegroundColor Gray
}

Write-Host ""

# 4. Summary
Write-Host "=== Summary ===" -ForegroundColor Green
Write-Host "All BATCH7 workflows have been stopped." -ForegroundColor Green
Write-Host ""
Write-Host "To verify:" -ForegroundColor Cyan
Write-Host '  Get-ScheduledTask | Where-Object {$_.TaskName -like "BATCH7_*"}' -ForegroundColor Gray
Write-Host "  Get-Job" -ForegroundColor Gray
Write-Host "  Get-Process python,pythonw -ErrorAction SilentlyContinue" -ForegroundColor Gray
Write-Host ""
Write-Host "To permanently remove scheduled tasks:" -ForegroundColor Yellow
Write-Host '  Unregister-ScheduledTask -TaskName BATCH7_Overnight_Images -Confirm:$false' -ForegroundColor Gray
Write-Host '  Unregister-ScheduledTask -TaskName BATCH7_Overnight_Text -Confirm:$false' -ForegroundColor Gray
Write-Host '  Unregister-ScheduledTask -TaskName BATCH7_Overnight_Natives -Confirm:$false' -ForegroundColor Gray
Write-Host '  Unregister-ScheduledTask -TaskName BATCH7_AutoCommit_Webhook -Confirm:$false' -ForegroundColor Gray

