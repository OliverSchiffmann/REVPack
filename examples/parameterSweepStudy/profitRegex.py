# It doesnt regex any more its using json since that will have all the results in it.

import glob
import json
import csv
from logging import warn
import matplotlib.pyplot as plt
import pandas as pd

if __name__ == "__main__":
    
    # # First check that all of the logged error files are empty
    
    # log_files = glob.glob("examples/parameterSweepStudy/logs/*.txt")
    
    # for log in log_files:
    #     with open(log, 'r') as file:
    #         content = file.read()
    #         if content.strip():
    #             raise ValueError(f"Error log file {log} is not empty. Simulation may have failed.")

    results_list = []
    
    # 1. Fetch all log files from your directory (adjust the path and extension)
    results_files = glob.glob("examples/parameterSweepStudy/Outputs/may_6/results/*.txt")

    for file_path in results_files:
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                # 2. Scan line-by-line for our unique JSON payload tag
                if line.startswith("HPC_JSON_RESULT::"):
                    json_str = line.split("HPC_JSON_RESULT::", 1)[1].strip()
                    
                    try:
                        data = json.loads(json_str)
                        
                        row_data = {}
                        
                        # Dynamically add any extra metadata if present
                        for k, v in data.get("metadata", {}).items():
                            row_data[f"metadata_{k}"] = v
                        
                        report = data.get("report", {})
                        
                        # Add all top-level report metrics (e.g., Total Revenue, Total Cost)
                        for k, v in report.items():
                            if not isinstance(v, dict):
                                row_data[k] = v
                                
                        # Dynamically extract all Breakdown and Statistics items
                        for section in ["Breakdown", "Statistics"]:
                            for k, v in report.get(section, {}).items():
                                row_data[k] = v
                                
                        # Calculate explicitly named columns to maintain backwards compatibility 
                        # with downstream scripts (like plot_optimization_surfaces.py)
                        row_data["Profit"] = float(report.get("Total Revenue", 0) - report.get("Total Cost", 0))
                        
                        results_list.append(row_data)
                        
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON in {file_path}: {e}")
                        continue
     

    if results_list:
        resultsDf = pd.DataFrame(results_list)
        
        # Group by Scenario to average across seeds and greatly reduce the CSV size
        # We only apply mean to numeric columns, keeping the code robust against any string values
        numeric_cols = resultsDf.select_dtypes(include=['number']).columns.tolist()
        if "Scenario" in numeric_cols:
            
            numeric_cols.remove("Scenario")
            
        resultsDf = resultsDf.groupby("Scenario", as_index=False)[numeric_cols].mean()
        
        # We can drop 'Seed' as the averaged seed number is meaningless
        if "Seed" in resultsDf.columns:
            resultsDf = resultsDf.drop(columns=["Seed"])
    else:
        raise ValueError("No valid HPC_JSON_RESULT data found in the provided log files. Check your output directory and log content.")
    
    print(f"Successfully extracted and averaged {len(resultsDf)} scenario records.")


    # Save the results
    resultsDf.to_csv("examples/parameterSweepStudy/saltelli_outputs_11_5.csv", index=False)
   
