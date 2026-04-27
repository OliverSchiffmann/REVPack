#!/bin/bash
#SBATCH --job-name=matrix_100
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=00:15:00       # 15 minutes is more than enough
#SBATCH --mem=12G             # Standard memory for the Italy map
#SBATCH --account=EEME039424

# Load in python
module add languages/python/3.14.0
module load apptainer/1.3.1

# Go to working dir
cd /user/work/nj21997/REVPack/

# Load in pre-configured venv
source .venv/bin/activate

# 1. Boot the local server
echo "Starting OSRM server..."
apptainer exec OSRM/osrm.sif osrm-routed -p 6578 --algorithm mld OSRM/italy-latest.osrm &
OSRM_PID=$!

# 3. The "Smart Wait" Loop
# This pings localhost:5000 every 5 seconds until the server responds
echo "Waiting for OSRM map data to load into RAM (this can take a minute)..."
while ! curl -s "http://localhost:6578/" > /dev/null; do
    sleep 5
    # If the OSRM process died, exit the script so it doesn't loop forever
    if ! kill -0 $OSRM_PID 2>/dev/null; then
        echo "ERROR: OSRM server crashed! Check your slurm .err log."
        exit 1
    fi
done

echo "OSRM Server is UP! Starting Python..."

# 3. Execute python script
python -u examples/locations/buildDistanceMatrix.py

# 4. Kill the server so the job ends cleanly
kill $OSRM_PID
echo "Job complete."