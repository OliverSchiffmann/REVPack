#!/bin/bash
#SBATCH --job-name=build_osrm
#SBATCH --partition=short
#SBATCH --nodes=1               # Request exactly 1 physical machine
#SBATCH --ntasks=1              # Run 1 overall task
#SBATCH --cpus-per-task=32       # Give that task 4 dedicated CPU cores
#SBATCH --time=01:00:00
#SBATCH --mem=50G        # Give it plenty of RAM so it doesn't get killed
#SBATCH --account=EEME039424

set -e 

module load apptainer/1.3.1

# 1. Define where your stuff is
HOME_OSRM_DIR="/user/work/nj21997/REVPack/OSRM"
IMAGE_PATH="$HOME_OSRM_DIR/osrm.sif"

# 2. Go to the ultra-fast local scratch drive (Check with your HPC, but $TMPDIR or /tmp is standard)
cd $TMPDIR

# 3. Copy the raw map from your slow home drive to the fast local drive
echo "Moving file to temp storage..."
cp $HOME_OSRM_DIR/italy-latest.osm.pbf .

# 4. Do the heavy lifting (It will be much faster here)
echo "Extracting..."
apptainer exec $IMAGE_PATH osrm-extract -p /opt/car.lua italy-latest.osm.pbf

echo "Partitioning..."
apptainer exec $IMAGE_PATH osrm-partition italy-latest.osrm

echo "Customizing..."
apptainer exec $IMAGE_PATH osrm-customize italy-latest.osrm

# 5. Move the finished, processed files back to your permanent home folder
echo "Moving map back to home directory..."
cp italy-latest.osrm* $HOME_OSRM_DIR/

echo "Map build complete and saved to home folder."