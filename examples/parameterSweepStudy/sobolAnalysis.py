from SALib.analyze import sobol
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from problemBounds import problem

if __name__ == "__main__":

    Results = pd.read_csv("examples/parameterSweepStudy/saltelli_outputs_1_5.csv")

    Si = sobol.analyze(problem, Results["Profit"].to_numpy(), print_to_console=True)

    # Define the parameters to plot
    target_params = [
        "remanufacture_delay",
        "unit_production_cost_R",
        "core_acceptance_rate",
        "core_return_rate",
        "mean_lifetime",
        "cores_consumed",
        "core_storage_limit",
    ]

    s1_vals = []
    st_vals = []
    plot_params = []

    # Extract indices for the specified parameters, capping negative numerical artifacts to 0
    for param in target_params:
        if param in problem["names"]:
            idx = problem["names"].index(param)
            s1_vals.append(max(0.0, Si["S1"][idx]))
            st_vals.append(max(0.0, Si["ST"][idx]))
            plot_params.append(param)
        else:
            print(f"Warning: Parameter '{param}' not found in problem definition.")

    # Calculate higher-order effects (ST - S1) for the stacked bar chart.
    # This ensures the total height of the stacked bar equals the Total-order index (ST).
    higher_order_vals = [max(0.0, st - s1) for st, s1 in zip(st_vals, s1_vals)]

    fig, ax = plt.subplots(figsize=(10, 8))
    x = np.arange(len(plot_params))

    ax.bar(x, s1_vals, label="First-order (S1)", color="skyblue")
    ax.bar(
        x,
        higher_order_vals,
        bottom=s1_vals,
        label="Higher-order interactions (ST - S1)",
        color="orange",
    )

    ax.set_xticks(x)
    ax.set_xticklabels(plot_params, rotation=45, ha="right")
    ax.set_ylabel("Sobol Index")
    ax.set_title("First-Order (S1) and Total-Order (ST) Sobol Indices")
    ax.legend()

    plt.tight_layout()
    plt.show()

    # Extract the Second-order indices (S2) matrix
    s2 = Si["S2"].copy()

    # Negative Sobol indices are numerical artifacts, so we cap them at 0
    s2[s2 < 0] = 0.0

    # Make the S2 matrix symmetrical (SALib only populates the upper triangle)
    for i in range(s2.shape[0]):
        for j in range(s2.shape[1]):
            if np.isnan(s2[i, j]) and not np.isnan(s2[j, i]):
                s2[i, j] = s2[j, i]

    fig, ax = plt.subplots(figsize=(10, 8))

    # Plot heatmap
    cax = ax.imshow(s2, cmap="viridis", vmin=0)
    fig.colorbar(cax, label="Second-order Sobol Index (S2)")

    ax.set_xticks(np.arange(len(problem["names"])))
    ax.set_yticks(np.arange(len(problem["names"])))
    ax.set_xticklabels(problem["names"], rotation=45, ha="right")
    ax.set_yticklabels(problem["names"])

    for i in range(len(problem["names"])):
        for j in range(len(problem["names"])):
            if not np.isnan(s2[i, j]):
                ax.text(
                    j,
                    i,
                    f"{s2[i, j]:.3f}",
                    ha="center",
                    va="center",
                    color="w" if s2[i, j] < np.nanmax(s2) / 2 else "k",
                )

    ax.set_title("Second-Order Parameter Interactions (S2)")
    plt.tight_layout()
    plt.show()
