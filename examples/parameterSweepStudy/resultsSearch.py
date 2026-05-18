# It doesnt regex any more its using json since that will have all the results in it.

import glob
import json
import pandas as pd

if __name__ == "__main__":

    results_list = []

    # 1. Fetch all log files from the relevant directory (adjust the path and extension)
    results_files = glob.glob("examples/parameterSweepStudy/Outputs/local/*.txt")

    for file_path in results_files:
        with open(file_path, "r", encoding="utf-8") as file:
            for line in file:
                # 2. Scan line-by-line for the JSON tag, should ignore errors and so on
                if line.startswith("HPC_JSON_RESULT::"):
                    json_str = line.split("HPC_JSON_RESULT::", 1)[1].strip()

                    try:
                        data = json.loads(json_str)

                        row_data = {}

                        # Add all the things tagged metadata
                        for k, v in data.get("metadata", {}).items():
                            row_data[f"{k}"] = v

                        report = data.get("report", {})

                        # Add all top-level metrics (e.g. Total Revenue, Total Cost)
                        for k, v in report.items():
                            if not isinstance(v, dict):
                                row_data[k] = v

                        # Extract all Breakdown and Statistics items
                        for section in ["Breakdown", "Statistics"]:
                            for k, v in report.get(section, {}).items():
                                row_data[k] = v

                        # Calculate derivative metrics
                        # Profit
                        row_data["Profit"] = float(
                            report.get("Total Revenue", 0) - report.get("Total Cost", 0)
                        )
                        # ...

                        results_list.append(row_data)

                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON in {file_path}: {e}")
                        continue

    if results_list:
        resultsDf = pd.DataFrame(results_list)

        # Group by Scenario to average across seeds
        # Only take the mean of the numerical values so a string doesn't break it
        numeric_cols = resultsDf.select_dtypes(include=["number"]).columns.tolist()
        if "Scenario" in numeric_cols:

            numeric_cols.remove("Scenario")

        # Take the mean of each Scenario.
        resultsDf = resultsDf.groupby("Scenario", as_index=False)[numeric_cols].mean()

        # Drop the seed column
        if "Seed" in resultsDf.columns:
            resultsDf = resultsDf.drop(columns=["Seed"])

        # Round all values to 2 decimal places
        resultsDf = resultsDf.round(2)
    else:
        raise ValueError(
            "No valid HPC_JSON_RESULT data found in the provided log files. Check your output directory and log content."
        )

    print(f"Successfully extracted and averaged {len(resultsDf)} scenario records.")

    # Save the results
    resultsDf.to_csv("examples/parameterSweepStudy/ofat_outputs_11_5.csv", index=False)
