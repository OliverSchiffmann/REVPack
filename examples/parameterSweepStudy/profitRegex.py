import re
import glob
import csv
import matplotlib.pyplot as plt

if __name__ == "__main__":
        
    # 1. Define the Regex Pattern
    # \s+            : Matches any whitespace (including non-breaking spaces)
    # [+-]           : Matches the explicit + or - sign
    # \d{1,3}        : Matches 1 to 3 digits (before the first comma or decimal)
    # (?:,\d{3})* : Matches zero or more occurrences of a comma followed by 3 digits
    # \.\d{2}        : Matches the exact decimal point and 2 digits
    profit_pattern = re.compile(r"NET PROFIT \(\€\):\s+([+-]?\d{1,3}(?:,\d{3})*\.\d{2})")

    profits = []

    # 2. Fetch all log files from your directory (adjust the path and extension)
    log_files = glob.glob("examples/parameterSweepStudy/logs/*.txt")

    for file_path in log_files:
        # Use encoding='utf-8' to safely handle the € symbol and non-breaking spaces
        with open(file_path, 'r', encoding='cp1252') as file:
            content = file.read()
            
            # Find all occurrences in the current file
            matches = profit_pattern.findall(content)
            
            for match in matches:
                # 3. Clean and convert the string to a float
                # Remove the comma so Python can parse it into a float
                clean_str = match.replace(',', '')
                
                # Python's built-in float() automatically handles the leading '+' or '-'
                profit_value = float(clean_str)
                profits.append(profit_value)

    print(f"Successfully extracted {len(profits)} profit records.")

    # Save the profits to a csv
    with open('examples/parameterSweepStudy/profits.csv', 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Profit'])
        for profit in profits:
            writer.writerow([profit])
    

