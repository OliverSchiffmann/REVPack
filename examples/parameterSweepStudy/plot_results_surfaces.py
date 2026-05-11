import pandas as pd
import numpy as np
from scipy.interpolate import griddata
import os
import importlib.util
import plotly.graph_objects as go


def plot_3d_surface(
    df, x_col, y_col, z_col, title, z_label, colorscale="Viridis", resolution=50
):
    """
    Generates an interactive 3D surface plot from ungridded parameter sweep data using Plotly.
    """
    x = df[x_col].values
    y = df[y_col].values
    z = df[z_col].values

    # Create a grid to interpolate the ungridded sweep data onto
    xi = np.linspace(x.min(), x.max(), resolution)
    yi = np.linspace(y.min(), y.max(), resolution)
    X, Y = np.meshgrid(xi, yi)

    # Interpolate Z values onto the grid
    Z = griddata((x, y), z, (X, Y), method="linear")

    # Create Plotly figure
    fig = go.Figure()

    # Add the 3D surface
    fig.add_trace(
        go.Surface(
            x=xi,
            y=yi,
            z=Z,
            colorscale=colorscale,
            opacity=0.8,
            colorbar=dict(title=z_label),
        )
    )

    # # Add the scattered actual data points
    # fig.add_trace(go.Scatter3d(
    #     x=x, y=y, z=z,
    #     mode='markers',
    #     marker=dict(size=3, color='black', opacity=0.5),
    #     name='Sampled Points'
    # ))

    # Update layout for axes labels and title
    fig.update_layout(
        title=title,
        scene=dict(xaxis_title=x_col, yaxis_title=y_col, zaxis_title=z_label),
        margin=dict(l=0, r=0, b=0, t=40),
    )

    fig.show()


if __name__ == "__main__":
    # 1. Load the outputs parsed by profitRegex.py
    results_path = "examples/parameterSweepStudy/ofat_outputs_11_5.csv"

    # 2. Load the input parameters that correspond to each scenario
    # (Assume you saved the LHS/Saltelli samples to a CSV where row index or a column matches 'Scenario')
    params_path = "examples/parameterSweepStudy/ofat_parameters_v2.py"

    if not os.path.exists(results_path) or not os.path.exists(params_path):
        print("Please ensure both output results and input parameters CSVs exist.")
        exit()

    df_results = pd.read_csv(results_path)

    # Load the Python parameters file using importlib (since it's a .py file, not a .json file)
    spec = importlib.util.spec_from_file_location("scenario_module", params_path)
    if spec is None or spec.loader is None:
        print("Failed to load parameters file.")
        exit()
    scenario_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scenario_module)
    SCENARIOS = scenario_module.SCENARIOS

    # Flatten the scenarios dictionary into a list of parameters for the DataFrame
    scenario_params = []
    for scen_id, config in SCENARIOS.items():
        row = {"Scenario": int(scen_id)}
        for category_name, category_data in config.items():
            if isinstance(category_data, dict):
                for param_name, param_val in category_data.items():
                    if isinstance(param_val, dict):
                        for sub_name, sub_val in param_val.items():
                            if sub_name not in row:
                                row[sub_name] = sub_val
                    else:
                        if param_name not in row:
                            row[param_name] = param_val
        scenario_params.append(row)

    df_params = pd.DataFrame(scenario_params)

    # Average the results across different random seeds for the same scenario
    df_agg = df_results.groupby("Scenario").mean().reset_index()

    # Merge inputs and outputs
    df = pd.merge(df_agg, df_params, on="Scenario")

    # Assuming simulation length is 1000 days
    sim_years = 1000 / 365.0

    # Annualize the profit
    df["Annual Profit"] = df["Profit"] / sim_years

    # Payback Period = Implementation Cost / Annual Profit
    # (If profit is negative, payback period is effectively infinite/undefined)
    df["Payback Period (Years)"] = np.where(
        df["Annual Profit"] > 0,
        df["Reman implementation cost"] / df["Annual Profit"],
        np.nan,  # Use NaN for scenarios that never pay back
    )

    # --- Generate Plots ---
    # Example 1: Core Acceptance Rate vs Core Return Rate vs Profit
    plot_3d_surface(
        df,
        x_col="unit_production_cost_R",
        y_col="cores_consumed",
        z_col="Profit",
        title="Profit Surface",
        z_label="Net Profit (€)",
    )

    # Example 2: Unit Production Cost R vs Acceptance Rate vs Payback Period
    # Drop NaNs so the interpolation doesn't fail on unprofitable scenarios
    df_payback = df.dropna(subset=["Payback Period (Years)"])
    if not df_payback.empty:
        plot_3d_surface(
            df_payback,
            x_col="unit_production_cost_R",
            y_col="core_acceptance_rate",
            z_col="Payback Period (Years)",
            title="Payback Period Surface",
            z_label="Years",
            colorscale="Plasma",
        )
