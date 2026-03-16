$cores = 15
Write-Host "Starting parallel sweep using $cores cores..."

# Array to keep track of running Python processes
$activeProcesses = @()

# Generate the list of numbers (1 to 15) and loop through them
1..1000 | ForEach-Object {
    $scenario = $_
    Write-Host "Starting scenario $scenario..."
    
    $logFile = "examples\parameterSweepStudy\logs\log_scenario_${scenario}.txt"
    $arguments = "-u examples/main_OS.py --scenario_file `"examples/parameterSweepStudy/lhs_parameters.py`" --scenario `"$scenario`" --no_plot"
    
    # Start the python process in the background, redirecting output to the log file
    $process = Start-Process -FilePath "python" -ArgumentList $arguments -RedirectStandardOutput $logFile -RedirectStandardError $errorLogFile -PassThru -WindowStyle Hidden
    $activeProcesses += $process

    # Throttle the loop: wait if we have reached the maximum number of concurrent cores
    while (($activeProcesses | Where-Object { -not $_.HasExited }).Count -ge $cores) {
        Start-Sleep -Milliseconds 500
    }
}

# Wait for any remaining scenarios to finish
$activeProcesses | Where-Object { -not $_.HasExited } | Wait-Process

Write-Host "All parallel scenarios completed!"