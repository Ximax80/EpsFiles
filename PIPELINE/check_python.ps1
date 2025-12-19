$procs = Get-Process python,pythonw -ErrorAction SilentlyContinue
$batch7Procs = @()

foreach ($p in $procs) {
    try {
        $cmd = (Get-CimInstance Win32_Process -Filter "ProcessId = $($p.Id)").CommandLine
        if ($cmd -and ($cmd -like "*batch7*" -or $cmd -like "*EpsteinEstateBatch7*" -or $cmd -like "*auto_commit*" -or $cmd -like "*run_batch7*")) {
            $batch7Procs += $p
            Write-Host "Found BATCH7 process: PID $($p.Id) - $cmd" -ForegroundColor Yellow
        }
    } catch {
        # Skip if we can't check
    }
}

if ($batch7Procs.Count -gt 0) {
    Write-Host "Killing $($batch7Procs.Count) BATCH7 Python process(es)..." -ForegroundColor Red
    $batch7Procs | Stop-Process -Force
    Write-Host "Done!" -ForegroundColor Green
} else {
    Write-Host "No BATCH7-related Python processes found" -ForegroundColor Gray
}

