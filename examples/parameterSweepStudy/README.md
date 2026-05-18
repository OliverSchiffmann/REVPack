# Parameter Sweep & Sensitivity Analysis Guide

This folder contains the scripts and configurations necessary to run parameter sweeps, One-Factor-At-a-Time (OFAT) experiments, and more complex sensitivity analyses (like Sobol/Saltelli) for REVPack.

This document outlines the standard workflow, what the main files do, and how to configure them for your own experiments.

---

## The Standard Workflow

A typical parameter sweep study consists of four main phases:

1. **Generate scenarios:** Creating the scenarios/parameter sets to test.
2. **Execution:** Running the scenarios either locally or distributed across an HPC cluster.
3. **Extraction:** Parsing the simulation outputs and compiling them into a workable dataset.
4. **Analysis:** Visualising the data or calculating sensitivities.

---

## 1. Generating Scenarios

Before running simulations, you must generate a dictionary of scenarios containing your varied parameter configurations.

### Key Files:

- `problemBounds.py` _(Requires setup)_: Defines the parameters you want to vary and their bounds (e.g. min/max values).
- `saltelli_scenarioGenerator.py`: Uses `SALib` to generate a Saltelli sequence of parameters (ideal for Sobol sensitivity analysis).
- `ofat_scenarioGenerator.py`: Generates scenarios based on the default, varying one parameter at a time (OFAT = One Factor At a Time).
- `XXX_scenarioGenerator.py`: Some other generator that works in whatever way you wish.

### How-To: Set up a new simulation sweep

1. **Define Bounds:** Edit `problemBounds.py` to include the names and bounds of the parameters you wish to sweep.
2. **Map Parameters:** In `XXX_scenarioGenerator.py`, update the `PARAM_MAPPING` dictionary. This tells the generator exactly _where_ in the nested configuration dictionary (e.g. `['oem', 'remanufacture_delay']`) each parameter should be inserted.
3. **Set Sample Size:** Adjust `N` (the sample size). For example in Sobol analysis, the total number of scenarios generated is $N \times (2D + 2)$, where $D$ is the number of parameters being varied.
4. **Generate:** Run the generator script. It will output a `.py` file (e.g. `saltelli_parameters_X_Y.py`) containing a massive dictionary of all scenarios.

---

## 2. Executing the Simulation

You can execute the generated scenarios locally (good for small runs or debugging) or on a High-Performance Computing (HPC) cluster (useful for avoiding FileZilla).

### Option A: Local Execution

**File:** `LocalScenarios.py`

- **How it works:** Uses Python's `multiprocessing.ProcessPoolExecutor` to run simulations in parallel using your machine's CPU cores.
- **Configuration:**
  - Update `SCENARIO_FILE` to point to the file you generated in Step 1.
  - Update `SEEDS` to run multiple stochastic variations per scenario.
  - Adjust `WORKERS` if you want to dedicate more or fewer CPU cores to the task.

### Option B: HPC Execution (SLURM)

**File:** `HPCScenarios.sh` (or `run_sobol.sh`)

- **How it works:** Submits a SLURM "Array Job". This splits your massive scenario dictionary into smaller "chunks" and runs them in parallel across multiple HPC nodes.

**Key HPC Commands & Configurations to Know:**

- `#SBATCH --array=1-328`: This is the most important command. It creates 328 parallel jobs. If you have 16,384 scenarios and run them in chunks of 50, you need 328 jobs ($16384 \div 50$).
- `SCENARIO_FILE="..."`: Point this to the Python file generated in Step 1.
- `MAX_SCENARIOS`: A failsafe to prevent the script from trying to run scenarios that don't exist. Must match the exact total output by your generator.
- `CHUNK_SIZE`: How many scenarios each HPC job will process. If tasks are timing out (hitting the `--time` limit), lower this number and increase the `--array` size, or increase the time limit.
- `SEEDS`: Determines how many random seeds to run per scenario to account for.
- `START_ID` & `END_ID`: Bash variables that calculate which part of the scenario dictionary the current array task is responsible for.

---

## 3. Extracting and Processing Results

Whether run locally or on an HPC, the outputs are typically dumped into text log files using a specific tag (`HPC_JSON_RESULT::`).

### Key File:

- `resultsSearch.py`

### How it works:

1. The script sweeps through a specified directory of `.txt` logs.
2. It scans line-by-line for the `HPC_JSON_RESULT::` prefix.
3. It unpacks the JSON payload, getting scenario IDs, seeds, and dynamically pulling all report metrics (Profit, Costs, Units Sold, etc).
4. **Averaging:** It groups the results by `Scenario` and calculates the `mean()` across all numeric columns. This averages out the randomness from different seeds.
5. Outputs a `.csv` file containing all the averages, ready for analysis.

### How to modify:

- **Adding Custom Metrics:** If you add new metrics to the `OEM.py` or simulation `report` dictionary, they will _automatically_ be picked up by `resultsSearch.py`. You only need to edit this file if you change the JSON tag format or want to calculate a derived metric (like the explicitly calculated `Profit` column).

---

## 4. Using the Results

Once you have the aggregated CSV, you can analyse the simulation's sensitivity to the input parameters.

### Option A: Sobol Sensitivity Analysis

**File:** `sobolAnalysis.py`

- **Purpose:** Calculates First-order ($S1$), Total-order ($S_T$), and Second-order ($S2$) sensitivity indices using `SALib`.
- **What it tells you:**
  - **$S1$ (First-order):** The direct effect a single parameter has on the variance of the output (e.g., Profit).
  - **$S_T$ (Total-order):** The total effect of a parameter, including its interactions with _all other_ parameters. If $S_T > S1$, interactions are occurring.
  - **$S2$ (Second-order):** Shows specifically which two parameters are interacting.
- **What it doesn't tell you:**
  - The nature of that interaction, whether they are positively or negatively correlated. All negative values are simulation artefacts and should be treated as though they were zero.
- **How to modify:**
  - Update the `target_params` list to choose which specific parameters to plot in the bar charts.
  - The script automatically generates a stacked bar chart (for $S1$ and Higher-order interactions) and a Heatmap (for $S2$ interactions).

### Option B: Rapid Data Profiling

**File:** `dataProfiler.py`

- **Purpose:** Uses `ydata_profiling` to generate an automated HTML report of your simulation dataset.
- **What it tells you:** Creates histograms, correlation matrices, and missing-value checks for every single input parameter and output metric. Good for sanity-checks.

---

## HPC Example

1. **Generate scenarios:**

   ```bash
   python3 examples/parameterSweepStudy/saltelli_scenarioGenerator.py
   ```

   _(Outputs to `saltelli_parameters_X.py`)_

2. **Submit HPC job:**
   Edit `HPCScenarios.sh` to match the generated file name and correct array size, then submit:

   ```bash
   sbatch examples/parameterSweepStudy/HPCScenarios.sh
   ```

3. **Wait for jobs to complete, then parse logs:**
   Edit `resultsSearch.py` to point to the correct output folder, then run:

   ```bash
   python3 examples/parameterSweepStudy/resultsSearch.py
   ```

   _(Outputs to `saltelli_outputs_X.csv`)_

4. **Run Analysis:**
   Edit `sobolAnalysis.py` to point to your new CSV:
   ```bash
   python3 examples/parameterSweepStudy/sobolAnalysis.py
   ```
