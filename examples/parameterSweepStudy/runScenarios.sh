#!/bin/bash

# 1. Set how many scenarios you want to run at exactly the same time.
# (Check your Mac's core count. If you have 8 cores, setting this to 6 
# runs it fast but leaves 2 cores free so you can still use your browser/VS Code).
CORES=4

echo "Starting parallel sweep using $CORES cores..."

# 2. 'seq 1 4' generates the list of numbers (1, 2, 3, 4).
# We pipe that list into xargs.
seq 1 15 | xargs -n 1 -P $CORES -I {} sh -c '
    SCENARIO=$1
    echo "Starting scenario $SCENARIO..."
    
    # Run Python, force unbuffered output (-u), and save straight to a dedicated text file
    python -u examples/main_OS.py --scenario_file "examples/parameterSweepStudy/lhs_parameters.py" --scenario "$SCENARIO" --no_plot > "examples/parameterSweepStudy/logs/log_scenario_${SCENARIO}.txt" 2>&1
    
    echo "Scenario $SCENARIO finished!"
' -- {}

echo "All parallel scenarios completed!"