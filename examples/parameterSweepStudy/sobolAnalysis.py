from SALib.analyze import sobol
import pandas as pd

from problemBounds import problem

if __name__ == "__main__":

    HPCResults = pd.read_csv("examples/parameterSweepStudy/saltelli_outputs_big.csv")

    # Print the Sobol analysis results to the terminal.
    Si = sobol.analyze(problem, HPCResults["Profit"].to_numpy(), print_to_console=True)