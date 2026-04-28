from SALib.analyze import sobol
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from problemBounds import problem

if __name__ == "__main__":

    HPCResults = pd.read_csv("examples/parameterSweepStudy/saltelli_outputs_final.csv")

    # Group the results by scenario and get the mean of the 10 seeds
    mean_results = HPCResults.groupby("Scenario").mean()

    Si = sobol.analyze(problem, mean_results["Profit"].to_numpy(), print_to_console=True)

    # Extract the Second-order indices (S2) matrix
    s2 = Si['S2'].copy()
    
    # Negative Sobol indices are numerical artifacts, so we cap them at 0
    s2[s2 < 0] = 0.0

    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot heatmap
    cax = ax.imshow(s2, cmap='viridis', vmin=0)
    fig.colorbar(cax, label='Second-order Sobol Index (S2)')

    ax.set_xticks(np.arange(len(problem['names'])))
    ax.set_yticks(np.arange(len(problem['names'])))
    ax.set_xticklabels(problem['names'], rotation=45, ha='right')
    ax.set_yticklabels(problem['names'])

    for i in range(len(problem['names'])):
        for j in range(len(problem['names'])):
            if not np.isnan(s2[i, j]):
                ax.text(j, i, f"{s2[i, j]:.3f}", ha="center", va="center", color="w" if s2[i, j] < np.nanmax(s2)/2 else "k")

    ax.set_title("Second-Order Parameter Interactions (S2)")
    plt.tight_layout()
    plt.show()