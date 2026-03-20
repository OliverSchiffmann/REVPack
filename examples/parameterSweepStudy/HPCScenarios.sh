#!/bin/bash

#SBATCH --job-name=HPCRunScenarios
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=0:10:0
#SBATCH --mem=100M
#SBATCH --account=EEME039424
#SBATCH --array=1-5000


# Load in python
module add languages/python/3.14.0
 
# Go to working dir
cd /user/work/nj21997/REVPack/
 
# Load in pre-configured venv
source .venv/bin/activate

for subtask in {1..4}
do
    for i in {1..10}
    do
        SCENARIO_ID=$(( $SLURM_ARRAY_TASK_ID + 5000 * ( $subtask - 1 ) ))
        if [ $SCENARIO_ID -gt 18433 ]; then
            break
        fi

        # echo "Running scenario $SCENARIO_ID"
        python -u examples/main_OS.py \
            --scenario_file "examples/parameterSweepStudy/saltelli_parameters.py" \
            --scenario "$SCENARIO_ID" \
            --no_plot \
            --seed $i \
            > "examples/parameterSweepStudy/results/out_scenario_${SCENARIO_ID}_seed_${i}.txt" \
            2> "examples/parameterSweepStudy/logs/err_scenario_${SCENARIO_ID}_seed_${i}.txt"
    done
done