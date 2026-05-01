import re
import glob
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

        
    # 1. Define the Regex Pattern
    # \s+            : Matches any whitespace (including non-breaking spaces)
    # [+-]           : Matches the explicit + or - sign
    # \d{1,3}        : Matches 1 to 3 digits (before the first comma or decimal)
    # (?:,\d{3})* : Matches zero or more occurrences of a comma followed by 3 digits
    # \.\d{2}        : Matches the exact decimal point and 2 digits
    profit_pattern = re.compile(r"NET PROFIT \(\€\):\s+([+-]?\d{1,3}(?:,\d{3})*\.\d{2})")
    virgin_sales_pattern = re.compile(r"Sale of virgin products:\s+€(\d{1,3}(?:,\d{3})*\.\d{2})")
    reman_sales_pattern = re.compile(r"Sale of reman products:\s+€(\d{1,3}(?:,\d{3})*\.\d{2})")

    results_list = []
    
    # 2. Fetch all log files from your directory (adjust the path and extension)
    results_files = glob.glob("examples/parameterSweepStudy/Outputs/may_5/results/*.txt")

    for file_path in results_files:
        
        # Use encoding='utf-8' to safely handle the € symbol and non-breaking spaces
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
            # Split the content by the header printed in the HPC shell script
            blocks = re.split(r'===\s+SCENARIO_(\d+)\s+SEED_(\d+)\s+===', content)
            
            # Find the profit, virgin/reman sales for each chunk (simulation run)
            for i in range(1, len(blocks), 3):
                scenario_num = int(blocks[i])
                seed_num = int(blocks[i+1])
                run_content = blocks[i+2]
                
                p_match = profit_pattern.search(run_content)
                v_match = virgin_sales_pattern.search(run_content)
                r_match = reman_sales_pattern.search(run_content)
                
                if p_match and v_match and r_match:
                    results_list.append({
                        "Scenario": scenario_num,
                        "Seed": seed_num,
                        "Profit": float(p_match.group(1).replace(',', '')),
                        "Virgin Sales": float(v_match.group(1).replace(',', '')),
                        "Reman Sales": float(r_match.group(1).replace(',', ''))
                    })

    if results_list:
        resultsDf = pd.DataFrame(results_list)
    else:
        resultsDf = pd.DataFrame(columns=["Scenario", "Seed", "Profit", "Virgin Sales", "Reman Sales"])
    
    print(f"Successfully extracted {len(resultsDf.dropna()['Profit'])} profit records.")


    # Save the results
    resultsDf.to_csv("examples/parameterSweepStudy/saltelli_outputs_1_5.csv", index=False)
   
