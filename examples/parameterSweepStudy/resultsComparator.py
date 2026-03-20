import pandas as pd
import matplotlib.pyplot as plt
from ydata_profiling import ProfileReport

from examples.parameterSweepStudy.saltelli_parameters import SCENARIOS

resultsDf = pd.read_csv("examples/parameterSweepStudy/saltelli_outputs.csv")

scenariosDf = pd.DataFrame(SCENARIOS).T

# Unwrap the nested dictionaries in the customer, main and oem columns
scenariosDf = pd.concat(
    [
        scenariosDf.drop(["b2b_customer", "b2c_customer", "main", "oem"], axis=1),
        pd.json_normalize(scenariosDf["b2b_customer"].tolist()).add_prefix("b2b_"),
        pd.json_normalize(scenariosDf["b2c_customer"].tolist()).add_prefix("b2c_"),
        pd.json_normalize(scenariosDf["main"].tolist()).add_prefix("main_"),
        pd.json_normalize(scenariosDf["oem"].tolist()).add_prefix("oem_"),
    ],
    axis=1,
)

fullDF = pd.concat([scenariosDf, resultsDf], axis=1).drop(["description"], axis=1).dropna()

negativesDf = fullDF[fullDF["Profit"] < 0]

# negativesDf.to_csv("examples/parameterSweepStudy/negatives.csv")

positivesDf = fullDF[fullDF["Profit"] > 0]

# positivesDf.to_csv("examples/parameterSweepStudy/positives.csv")

# Generate the profile report
profile = ProfileReport(fullDF, title="Statistical Profiling Report", explorative=True)

# Export to HTML
profile.to_file("examples/parameterSweepStudy/Data_report.html")