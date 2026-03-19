#!/bin/bash

#SBATCH --job-name=HPCRunScenarios
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=0:10:0
#SBATCH --mem=100M
#SBATCH --account=EEME039424
#SBATCH --array=1-2458


# Load in python
module add languages/python/3.14.0
 
# Go to working dir
cd /user/work/nj21997/REVPack/
 
# Load in pre-configured venv
source .venv/bin/activate

for i in {1..10}
do
    SCENARIO_ID=$(((SLURM_ARRAY_TASK_ID - 1) * 10 + i))
    if [ $SCENARIO_ID -ge 24576 ]; then
        break
    fi

    # echo "Running scenario $SCENARIO_ID"
    python -u examples/main_OS.py \
        --scenario_file "examples/parameterSweepStudy/saltelli_parameters.py" \
        --scenario "$SCENARIO_ID" \
        --no_plot \
        > "examples/parameterSweepStudy/results/out_scenario_${SCENARIO_ID}.txt" \
        2> "examples/parameterSweepStudy/logs/err_scenario_${SCENARIO_ID}.txt"
done
