#!/bin/bash
#SBATCH --job-name=REV_Sobol
#SBATCH --partition=short           # Matches your previously used partition
#SBATCH --account=EEME039424        # Matches your previously used account
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00             
#SBATCH --mem=250M                    # Memory per task
#SBATCH --array=1-185               # 18432 total scenarios / 100 per chunk = 185
#SBATCH --output=examples/parameterSweepStudy/logs/out_%A_%a.log
#SBATCH --error=examples/parameterSweepStudy/logs/error_%A_%a.txt

# Note: Ensure you generate the scenarios BEFORE submitting this job!
# Run: python examples/parameterSweepStudy/saltelli_scenarioGenerator.py

# Load environment (Adjust based on your HPC configuration)
module load python/3.10
source venv/bin/activate

export PYTHONPATH=$(pwd)

# File Paths
SCENARIO_FILE="examples/parameterSweepStudy/saltelli_parameters_24_4.py"
OUTPUT_DIR="examples/parameterSweepStudy/results"
LOGS_DIR="examples/parameterSweepStudy/logs"

# Ensure output directories exist
mkdir -p $OUTPUT_DIR
mkdir -p $LOGS_DIR

# N=1024, D=9 -> Total Scenarios = 1024 * (2*9 + 2) = 20480
MAX_SCENARIOS=18432
CHUNK_SIZE=100
SEEDS=10 # Set this if you want multiple stochastic seeds per scenario

START_ID=$(( (SLURM_ARRAY_TASK_ID - 1) * CHUNK_SIZE + 1 ))
END_ID=$(( SLURM_ARRAY_TASK_ID * CHUNK_SIZE ))

OUTPUT_FILE="${OUTPUT_DIR}/results_task_${SLURM_ARRAY_TASK_ID}.txt"
> $OUTPUT_FILE

echo "Task $SLURM_ARRAY_TASK_ID handling scenarios $START_ID to $END_ID"

for (( SCENARIO_ID=$START_ID; SCENARIO_ID<=$END_ID; SCENARIO_ID++ )); do
    if [ $SCENARIO_ID -gt $MAX_SCENARIOS ]; then
        break
    fi
    
    for (( SEED=1; SEED<=$SEEDS; SEED++ )); do
        echo "=== SCENARIO_${SCENARIO_ID} SEED_${SEED} ===" >> $OUTPUT_FILE
        python examples/parameterSweepStudy/sobol_main.py --scenario_file $SCENARIO_FILE --scenario "$SCENARIO_ID" --seed $SEED >> $OUTPUT_FILE
    done
done