import re
import glob
import csv
import matplotlib.pyplot as plt
import pandas as pd

if __name__ == "__main__":
    
    # First check that all of the logged error files are empty
    
    log_files = glob.glob("examples/parameterSweepStudy/logs/*.txt")
    
    for log in log_files:
        with open(log, 'r') as file:
            content = file.read()
            if content.strip():
                raise ValueError(f"Error log file {log} is not empty. Simulation may have failed.")

        
    # 1. Define the Regex Pattern
    # \s+            : Matches any whitespace (including non-breaking spaces)
    # [+-]           : Matches the explicit + or - sign
    # \d{1,3}        : Matches 1 to 3 digits (before the first comma or decimal)
    # (?:,\d{3})* : Matches zero or more occurrences of a comma followed by 3 digits
    # \.\d{2}        : Matches the exact decimal point and 2 digits
    profit_pattern = re.compile(r"NET PROFIT \(\€\):\s+([+-]?\d{1,3}(?:,\d{3})*\.\d{2})")
    virgin_sales_pattern = re.compile(r"Sale of virgin products:\s+€(\d{1,3}(?:,\d{3})*\.\d{2})")
    reman_sales_pattern = re.compile(r"Sale of reman products:\s+€(\d{1,3}(?:,\d{3})*\.\d{2})")


    resultsDf = pd.DataFrame(columns=["Scenario", "Seed", "Profit", "Virgin Sales", "Reman Sales"])
    
    # 2. Fetch all log files from your directory (adjust the path and extension)
    results_files = glob.glob("examples/parameterSweepStudy/results/*.txt")

    for file_path in results_files:
        
        # Extract scenario and seed numbers from filename
        filename = file_path.split('/')[-1]  # Get just the filename
        scenario_match = re.search(r'scenario_(\d+)', filename)
        seed_match = re.search(r'seed_(\d+)', filename)
        scenario_num = int(scenario_match.group(1)) if scenario_match else None
        seed_num = int(seed_match.group(1)) if seed_match else None
        
        resultsDf.loc[len(resultsDf), "Scenario"] = scenario_num
        resultsDf.loc[len(resultsDf)-1, "Seed"] = seed_num
        
        # Use encoding='utf-8' to safely handle the € symbol and non-breaking spaces
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
            
            # Find all occurrences in the current file
            profit_matches = profit_pattern.findall(content)
            virgin_sales_matches = virgin_sales_pattern.findall(content)
            reman_sales_matches = reman_sales_pattern.findall(content)
            
            
            for match in profit_matches:
                # 3. Clean and convert the string to a float
                # Remove the comma so Python can parse it into a float
                clean_str = match.replace(',', '')
                
                # Python's built-in float() automatically handles the leading '+' or '-'
                profit_value = float(clean_str)
                resultsDf.loc[len(resultsDf)-1, "Profit"] = profit_value
            
            for match in virgin_sales_matches:
                clean_str = match.replace(',', '')
                virgin_sales_value = float(clean_str)
                resultsDf.loc[len(resultsDf)-1, "Virgin Sales"] = virgin_sales_value
            
            for match in reman_sales_matches:
                clean_str = match.replace(',', '')  
                reman_sales_value = float(clean_str)
                resultsDf.loc[len(resultsDf)-1, "Reman Sales"] = reman_sales_value

    
    print(f"Successfully extracted {len(resultsDf.dropna()['Profit'])} profit records.")


    # Save the results
    resultsDf.to_csv("examples/parameterSweepStudy/saltelli_outputs_big.csv", index=False)
   
