#!/bin/bash
#SBATCH --job-name=local_osrm
#SBATCH --time=00:30:00
#SBATCH --mem=12G  # Need enough RAM to hold the Italy map

# 1. Start the OSRM server in the background
apptainer exec osrm.sif osrm-routed --algorithm mld italy-latest.osrm &
OSRM_PID=$!

# 2. Wait a few seconds for the server to spin up
sleep 10

# 3. Run your Python script 
# (Make sure to change the URL in your Python script from 'router.project-osrm.org' to 'localhost:5000' and remove the time.sleep(1))
python build_matrix.py

# 4. Kill the OSRM server when finished
kill $OSRM_PID