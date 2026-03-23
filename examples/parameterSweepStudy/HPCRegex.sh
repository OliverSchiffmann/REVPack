#!/bin/bash

#SBATCH --job-name=HPCProfitRegex
#SBATCH --partition=short
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=1
#SBATCH --cpus-per-task=1
#SBATCH --time=1:00:0
#SBATCH --mem=10G
#SBATCH --account=EEME039424


# Load in python
module add languages/python/3.14.0
 
# Go to working dir
cd /user/work/nj21997/REVPack/
 
# Load in pre-configured venv
source .venv/bin/activate

python -u examples/parameterSweepStudy/profitRegex.py 