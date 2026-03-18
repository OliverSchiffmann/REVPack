$threads = 24
$totalRuns = 1..10000
$pythonScript = "examples/main_OS.py"
$scenarioFile = "examples/parameterSweepStudy/lhs_parameters.py"

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
Write-Host "Starting parallel sweep using $threads cores..."

# Generate the list of numbers (1 to 1000) and process in parallel
$results = $totalRuns | ForEach-Object -Parallel {
    $pythonScript = $using:pythonScript
    $scenarioFile = $using:scenarioFile
    $scenario = $_
    Write-Host "Starting scenario $scenario..."
    
    # $logFile = "examples\parameterSweepStudy\logs\log_scenario_${scenario}.txt"
    # $arguments = "-u $pythonScript --scenario_file `"$scenarioFile`" --scenario `"$scenario`" --no_plot"
    
    #Start-Process -FilePath "python" -ArgumentList $arguments -RedirectStandardOutput $logFile -Wait -WindowStyle Hidden
    $output = python3 $pythonScript --scenario_file $scenarioFile --scenario $scenario --no_plot --json_output

    $jsonLine = $output | Where-Object { $_ -match '\{.*\}' } | Select-Object -First 1

    if ($jsonLine){
        # Convert string to a PowerShell object
        return ($jsonLine | ConvertFrom-Json)
    }
} -ThrottleLimit $threads

$results | Export-Csv -Path "examples\parameterSweepStudy\logs\Sim_master_results.csv" -NoTypeInformation

$stopwatch.Stop()
Write-Host "All parallel scenarios completed in $($stopwatch.Elapsed.TotalSeconds) seconds!"