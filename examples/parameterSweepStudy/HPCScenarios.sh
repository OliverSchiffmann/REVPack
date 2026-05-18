#!/bin/bash
#SBATCH --job-name=REV_Sobol
#SBATCH --partition=short           # Matches your previously used partition
#SBATCH --account=EEME039424        # Matches your previously used account
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:30:00             
#SBATCH --mem=4G                    # Memory per task
#SBATCH --array=1-328               # 16384 total scenarios / 50 per chunk = 327.7
#SBATCH --output=examples/parameterSweepStudy/logs/out_%A_%a.log
#SBATCH --error=examples/parameterSweepStudy/logs/error_%A_%a.txt

# Note: Ensure you generate the scenarios BEFORE submitting this job!
# Run: python examples/parameterSweepStudy/saltelli_scenarioGenerator.py

# Load environment (Adjust based on your HPC configuration)
module add languages/python/3.14.0
source .venv/bin/activate

cd /user/work/nj21997/REVPack/

export PYTHONPATH=$(pwd)

# File Paths
# Scenario file contains the dictionary/json of all the different scenarios that were generated in the previous step.
SCENARIO_FILE="examples/parameterSweepStudy/saltelli_parameters_6_5.py"

# Sets the output directory for all the results and potential error files
OUTPUT_DIR="examples/parameterSweepStudy/Outputs/may_6/results"

# Ensure output directories exist
mkdir -p $OUTPUT_DIR

# Ensure that the max number of scenarios matches the number that you have generated (either do the maths, or it will tell you in the command box)
MAX_SCENARIOS=16384
CHUNK_SIZE=50
SEEDS=10 # Set this if you want multiple seeds per scenario, which we probably do since lots of the randomness comes from the seed

# Define the start and end scenarios for this chunk
START_ID=$(( (SLURM_ARRAY_TASK_ID - 1) * CHUNK_SIZE + 1 ))
END_ID=$(( SLURM_ARRAY_TASK_ID * CHUNK_SIZE ))

OUTPUT_FILE="${OUTPUT_DIR}/results_task_${SLURM_ARRAY_TASK_ID}.txt"
> $OUTPUT_FILE

echo "Task $SLURM_ARRAY_TASK_ID handling scenarios $START_ID to $END_ID"

for (( SCENARIO_ID=$START_ID; SCENARIO_ID<=$END_ID; SCENARIO_ID++ )); do
    if [ $SCENARIO_ID -gt $MAX_SCENARIOS ]; then
        echo "Breaking ID ${SCENARIO_ID} too large"
        break
    fi
    
    for (( SEED=1; SEED<=$SEEDS; SEED++ )); do
        echo "=== SCENARIO_${SCENARIO_ID} SEED_${SEED} ===" >> $OUTPUT_FILE
        python examples/parameterSweepStudy/sobol_main.py --scenario_file $SCENARIO_FILE --scenario "$SCENARIO_ID" --seed $SEED >> $OUTPUT_FILE
    done
done