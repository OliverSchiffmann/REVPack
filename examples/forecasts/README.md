# Example forecast files

Simplan forecast outputs used by the "Forecast" example scenario and for testing
the forecast-to-advertising-rate calibration (`reuman/demand_inputs.py`).

These are **synthetic** data for the Olimpia Splendid case, not real sales.

| File | Contents |
| --- | --- |
| `forecast_virgin.json` | Simplan forecast of `source/synthetic-sales-OS-virgin.csv` (default dashboard settings) |
| `forecast_reman.json` | Simplan forecast of `source/synthetic-sales-OS-reman.csv` (default dashboard settings) |

## How the source data was made

`source/gen_synthetic_OS.py` (fixed seed, re-run to reproduce):

- Market size 1,000 customers, 200 already owning the product (pool starts at 800)
- 180 days, 01/01/2025 to 06/29/2025
- Virgin rate rises linearly from 0.0003 to 0.0009 per day
- Reman = 3% of new customers
- Values are new customers per day (whole numbers), drawn the same way as
  `World.generate_demand()`

Use these with `B2B_population = 1000`, `B2C_population = 0` and
`starting_customers = 200`. Expected calibrated rates from the raw data alone are
about V = 5.95e-4 and R = 2.2e-5. The Simplan files add forecast days, so the
values from them differ slightly.