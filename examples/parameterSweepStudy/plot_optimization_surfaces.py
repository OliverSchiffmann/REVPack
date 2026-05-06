import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import griddata
import os

def plot_3d_surface(df, x_col, y_col, z_col, title, z_label, cmap='viridis'):
    """
    Generates a 3D surface plot from ungridded parameter sweep data.
    """
    fig = plt.figure(figsize=(12, 8))
    ax = fig.add_subplot(111, projection='3d')

    x = df[x_col].values
    y = df[y_col].values
    z = df[z_col].values

    # Create a grid to interpolate the ungridded sweep data onto
    xi = np.linspace(x.min(), x.max(), 100)
    yi = np.linspace(y.min(), y.max(), 100)
    X, Y = np.meshgrid(xi, yi)
    
    # Interpolate Z values onto the grid
    Z = griddata((x, y), z, (X, Y), method='cubic')

    # Plot the surface
    surf = ax.plot_surface(X, Y, Z, cmap=cmap, edgecolor='none', alpha=0.8)
    
    # Scatter the actual data points to show where the samples were taken
    ax.scatter(x, y, z, color='k', s=10, alpha=0.5, label='Sampled Points')

    ax.set_xlabel(x_col)
    ax.set_ylabel(y_col)
    ax.set_zlabel(z_label)
    ax.set_title(title)
    
    fig.colorbar(surf, shrink=0.5, aspect=0.5, pad=0.1, label=z_label)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # 1. Load the outputs parsed by profitRegex.py
    results_path = "saltelli_outputs_1_5.csv"
    
    # 2. Load the input parameters that correspond to each scenario
    # (Assume you saved the LHS/Saltelli samples to a CSV where row index or a column matches 'Scenario')
    params_path = "scenario_parameters.csv" 
    
    if not os.path.exists(results_path) or not os.path.exists(params_path):
        print("Please ensure both output results and input parameters CSVs exist.")
        exit()
        
    df_results = pd.read_csv(results_path)
    df_params = pd.read_csv(params_path)
    
    # Average the results across different random seeds for the same scenario
    df_agg = df_results.groupby('Scenario').mean().reset_index()
    
    # Merge inputs and outputs
    df = pd.merge(df_agg, df_params, on='Scenario')
    
    # --- Calculate Advanced Metrics ---
    # Assuming simulation length is 1000 days (approx 2.74 years). Adjust as needed.
    sim_years = 1000 / 365.0 
    
    # Annualize the profit
    df['Annual Profit'] = df['Profit'] / sim_years
    
    # Payback Period = Implementation Cost / Annual Profit
    # (If profit is negative, payback period is effectively infinite/undefined)
    df['Payback Period (Years)'] = np.where(
        df['Annual Profit'] > 0, 
        df['Implementation Cost'] / df['Annual Profit'], 
        np.nan # Use NaN for scenarios that never pay back
    )

    # --- Generate Plots ---
    # Example 1: Bounty Value vs Retail Price vs Profit
    plot_3d_surface(df, x_col='bounty_value', y_col='retail_price_R', z_col='Profit', title='Profit Optimization Surface', z_label='Net Profit (€)')

    # Example 2: Bounty Value vs Acceptance Rate vs Payback Period
    # Drop NaNs so the interpolation doesn't fail on unprofitable scenarios
    df_payback = df.dropna(subset=['Payback Period (Years)'])
    if not df_payback.empty:
        plot_3d_surface(df_payback, x_col='bounty_value', y_col='core_acceptance_rate', z_col='Payback Period (Years)', title='Payback Period Surface', z_label='Years', cmap='plasma_r')