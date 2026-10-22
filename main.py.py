import pandas as pd
import matplotlib.pyplot as plt
import os

##Load input data
assets = pd.read_csv("data/assets.csv") 
liabilities = pd.read_csv("data/liabilities.csv")
market_rates = pd.read_csv("data/market_rates.csv")
cash_flows = pd.read_csv("data/cash_flow.csv")

def present_value(cash_flow, rate, tenor):
    return cash_flow / (1 + rate)**tenor

def get_discount_rate(tenor, market_rates):
    return market_rates.loc[market_rates["tenor_years"] == tenor, "base_rate"].iloc[0]

cash_flows["discount_rate"] = cash_flows["tenor_years"].apply(
    lambda tenor: get_discount_rate(tenor, market_rates))

##Procedure for NII
##Calculate total assets and liabilities
total_assets = assets["amount"].sum()
total_liabilities = liabilities["amount"].sum()

##Calculate initial equity
equity = total_assets - total_liabilities

##Calculate annual interest income and expense
assets["interest_income"] = assets["amount"] * assets["interest_rate"]
liabilities["interest_expense"] = liabilities["amount"] * liabilities["interest_rate"]

base_interest_income = assets["interest_income"].sum()
base_interest_expense = liabilities["interest_expense"].sum()

base_nii = base_interest_income - base_interest_expense

##Defining scenarios
scenarios = {
    "Base case": {"short": 0.00, "long": 0.00},
    "Rates up (+100 bps)": {"short": 0.03, "long": 0.03},
    "Rates down (-100 bps)": {"short": -0.03, "long": -0.03},
    "Steepener": {"short": -0.025, "long": 0.025},
    "Flattener": {"short": 0.025, "long": -0.025}
}
results = []

for scenario, shocks in scenarios.items():

    shocked_assets = assets["interest_rate"].copy()
    shocked_liabilities = liabilities["interest_rate"].copy()

    for term, shock in shocks.items():

        variable_assets = (
            (assets["rate_type"] == "Variable") &
            (assets["repricing_term"] == term.title())
        )

        variable_liabilities = (
            (liabilities["rate_type"] == "Variable") &
            (liabilities["repricing_term"] == term.title())
        )

        shocked_assets.loc[variable_assets] += shock
        shocked_liabilities.loc[variable_liabilities] += shock

    interest_income = (
        assets["amount"] * shocked_assets
    ).sum()

    interest_expense = (
        liabilities["amount"] * shocked_liabilities
    ).sum()

    nii = interest_income - interest_expense

    delta_nii = nii - base_nii

    results.append({
        "Scenario": scenario,
        "Interest Income": interest_income,
        "Interest Expense": interest_expense,
        "NII": nii,
        "Delta NII": delta_nii
    })
    
##Convert results to a DataFrame

results_df = pd.DataFrame(results)

##Procedure for EVE
capital = 100_000_000

eve_shocks = {
    "Base case": (0.00, 0.00),
    "Rates up (+100 bps)": (0.0225, 0.0225),
    "Rates down (-100 bps)": (-0.0225, -0.0225),
    "Steepener": (-0.035, 0.02),
    "Flattener": (0.035, -0.02)
}

eve_results = []

for scenario, shocks in eve_shocks.items():

    short_shock, long_shock = shocks

    scenario_shocks = cash_flows["tenor_years"].apply(
        lambda tenor: short_shock if tenor <= 1
        else long_shock
    )

    scenario_rates = cash_flows["discount_rate"] + scenario_shocks

    scenario_pv = cash_flows["cash_flow"] / (
        (1 + scenario_rates) ** cash_flows["tenor_years"]
    )

    asset_pv_scenario = scenario_pv[
        cash_flows["instrument_type"] == "Asset"
    ].sum()

    liability_pv_scenario = scenario_pv[
        cash_flows["instrument_type"] == "Liability"
    ].sum()

    eve_scenario = asset_pv_scenario - liability_pv_scenario

    eve_results.append({
        "Scenario": scenario,
        "EVE": eve_scenario
    })


eve_df = pd.DataFrame(eve_results)

base_eve = eve_df.loc[
    eve_df["Scenario"] == "Base case", "EVE"
].iloc[0]

eve_df["Delta EVE"] = eve_df["EVE"] - base_eve

eve_df["Delta EVE / Capital (%)"] = (
    eve_df["Delta EVE"] / capital * 100
)


##Display results
print("\n=== NII SENSITIVITY ANALYSIS ===")
print(results_df.to_string(index=False, formatters={
"Interest Income": "{:,.2f}".format,
"Interest Expense": "{:,.2f}".format,
"NII": "{:,.2f}".format,
"Delta NII": "{:,.2f}".format
}))


print("\n=== EVE SENSITIVITY ANALYSIS ===")
print("\nEVE Sensitivity Analysis:")
print(
    eve_df.to_string(
        index=False,
        formatters={
            "EVE": "{:,.2f}".format,
            "Delta EVE": "{:,.2f}".format,
            "Delta EVE / Capital (%)": "{:.2f}%".format
        }
    )
)

# Create charts folder
os.makedirs("charts", exist_ok=True)

# 1. NII Sensitivity Chart
nii_chart = results_df.set_index("Scenario")["NII"]

ax = nii_chart.plot(kind="bar", figsize=(9, 5))
ax.bar_label(ax.containers[0], labels=[f"{value / 1_000_000:.2f}mln" for value in nii_chart], padding=4)
plt.ylim(3_500_000, 4_700_000)
plt.title("NII Sensitivity Analysis")
plt.ylabel("Net Interest Income (mln)")
plt.xlabel("Scenario")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig("charts/nii_sensitivity.png", dpi=300)
plt.close()

# 2. EVE Sensitivity Chart
eve_chart = eve_df.set_index("Scenario")["EVE"]

ax = eve_chart.plot(kind="bar", figsize=(9, 5))
ax.bar_label(ax.containers[0], labels=[f"{value / 1_000_000:.2f}mln" for value in eve_chart], padding=4)
plt.title("EVE Sensitivity Analysis")
plt.ylabel("Economic Value of Equity")
plt.xlabel("Scenario")
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig("charts/eve_sensitivity.png", dpi=300)
plt.close()

# 3. Delta EVE / Capital Chart
delta_chart = eve_df.set_index("Scenario")[
    "Delta EVE / Capital (%)"
].drop("Base case")

ax = delta_chart.plot(kind="bar", figsize=(9, 5))
ax.bar_label(ax.containers[0], labels=[f"{value:.2f}%" for value in delta_chart], padding=4)
plt.title("Change in EVE as % of Capital")
plt.ylabel("Delta EVE / Capital (%)")
plt.xlabel("Scenario")
plt.axhline(0, linewidth=0.8)
plt.xticks(rotation=25, ha="right")
plt.tight_layout()
plt.savefig("charts/delta_eve_capital.png", dpi=300)
plt.close()

print("\nCharts saved successfully in the charts folder.")