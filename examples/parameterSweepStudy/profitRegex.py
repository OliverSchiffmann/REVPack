# It doesnt regex any more its using json since that will have all the results in it.

import glob
import json
import csv
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
        
    # 1. Fetch all log files from your directory (adjust the path and extension)
        with open(file_path, 'r', encoding='utf-8') as file:
            for line in file:
                # 2. Scan line-by-line for our unique JSON payload tag
                if line.startswith("HPC_JSON_RESULT::"):
                    json_str = line.split("HPC_JSON_RESULT::", 1)[1].strip()
                    
                    try:
                        data = json.loads(json_str)
                        
                        scenario_num = int(data["metadata"]["scenario_id"])
                        seed_num = int(data["metadata"]["seed"])
                        
                        report = data.get("report", {})
                        breakdown = report.get("Breakdown", {})
                        
                        profit = float(report.get("Total Revenue", 0) - report.get("Total Cost", 0))
                        v_sales = float(breakdown.get("Sale of virgin products", 0))
                        r_sales = float(breakdown.get("Sale of reman products", 0))
                        i_cost = float(breakdown.get("Reman implementation cost", 0))
                        
                        results_list.append({
                            "Scenario": scenario_num,
                            "Seed": seed_num,
                            "Profit": profit,
                            "Virgin Sales": v_sales,
                            "Reman Sales": r_sales,
                            "Implementation Cost": i_cost
                        })
                        
                    except json.JSONDecodeError as e:
                        print(f"Failed to parse JSON in {file_path}: {e}")
                        continue
     

    if results_list:
        resultsDf = pd.DataFrame(results_list)
    else:
        resultsDf = pd.DataFrame(columns=["Scenario", "Seed", "Profit", "Virgin Sales", "Reman Sales", "Implementation Cost"])
    
    print(f"Successfully extracted {len(resultsDf.dropna()['Profit'])} profit records.")


    # Save the results
    resultsDf.to_csv("examples/parameterSweepStudy/saltelli_outputs_11_5.csv", index=False)
   
