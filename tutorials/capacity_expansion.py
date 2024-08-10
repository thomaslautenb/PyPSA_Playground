
import pypsa
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use("bmh")

# Load technology data and costs
year = 2030
url = f"https://raw.githubusercontent.com/PyPSA/technology-data/master/outputs/costs_{year}.csv"
costs = pd.read_csv(url, index_col=[0, 1])
costs.loc[costs.unit.str.contains("/kW"), "value"] *= 1e3
costs.unit = costs.unit.str.replace("/kW", "/MW")

defaults = {
    "FOM": 0,
    "VOM": 0,
    "efficiency": 1,
    "fuel": 0,
    "investment": 0,
    "lifetime": 25,
    "CO2 intensity": 0,
    "discount rate": 0.07,
}
costs = costs.value.unstack().fillna(defaults)

costs.at["OCGT", "fuel"] = costs.at["gas", "fuel"]
costs.at["CCGT", "fuel"] = costs.at["gas", "fuel"]
costs.at["OCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]
costs.at["CCGT", "CO2 intensity"] = costs.at["gas", "CO2 intensity"]

def annuity(r, n):
    return r / (1.0 - 1.0 / (1.0 + r) ** n)

# Calculate short-term marginal generation costs
costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]

# Calculate annualised investment costs
annuity = costs.apply(lambda x: annuity(x["discount rate"], x["lifetime"]), axis=1)
costs["capital_cost"] = (annuity + costs["FOM"] / 100) * costs["investment"]

# Load time series data for Germany in 2015
url = "https://tubcloud.tu-berlin.de/s/pKttFadrbTKSJKF/download/time-series-lecture-2.csv"
ts = pd.read_csv(url, index_col=0, parse_dates=True)
ts.load *= 1e3  # Convert load from GW to MW
resolution = 4
ts = ts.resample(f"{resolution}h").first()

# Initialize the network
n = pypsa.Network()

# Add bus and set snapshots
n.add("Bus", "electricity")
n.set_snapshots(ts.index)
n.snapshot_weightings.loc[:, :] = resolution

# Add carriers
carriers = ["onwind", "offwind", "solar", "OCGT", "hydrogen storage underground", "battery storage"]
n.madd("Carrier", carriers, 
       color=["dodgerblue", "aquamarine", "gold", "indianred", "magenta", "yellowgreen"], 
       co2_emissions=[costs.at[c, "CO2 intensity"] for c in carriers])

# Add load
n.add("Load", "demand", bus="electricity", p_set=ts.load)

# Add OCGT generator
n.add("Generator", "OCGT", bus="electricity", carrier="OCGT", 
       capital_cost=costs.at["OCGT", "capital_cost"], 
       marginal_cost=costs.at["OCGT", "marginal_cost"], 
       efficiency=costs.at["OCGT", "efficiency"], 
       p_nom_extendable=True)

# Add variable renewable generators
for tech in ["onwind", "offwind", "solar"]:
    n.add("Generator", tech, bus="electricity", carrier=tech, 
          p_max_pu=ts[tech], 
          capital_cost=costs.at[tech, "capital_cost"], 
          marginal_cost=costs.at[tech, "marginal_cost"], 
          efficiency=costs.at[tech, "efficiency"], 
          p_nom_extendable=True)

# Optimize the network
n.optimize(solver_name="highs")

# Add battery storage
n.add("StorageUnit", "battery storage", bus="electricity", carrier="battery storage", 
       max_hours=6, 
       capital_cost=costs.at["battery inverter", "capital_cost"] + 6 * costs.at["battery storage", "capital_cost"], 
       efficiency_store=costs.at["battery inverter", "efficiency"], 
       efficiency_dispatch=costs.at["battery inverter", "efficiency"], 
       p_nom_extendable=True, 
       cyclic_state_of_charge=True)

# Add hydrogen storage
capital_costs = (costs.at["electrolysis", "capital_cost"] + 
                 costs.at["fuel cell", "capital_cost"] + 
                 168 * costs.at["hydrogen storage underground", "capital_cost"])
n.add("StorageUnit", "hydrogen storage underground", bus="electricity", 
       carrier="hydrogen storage underground", max_hours=168, 
       capital_cost=capital_costs, 
       efficiency_store=costs.at["electrolysis", "efficiency"], 
       efficiency_dispatch=costs.at["fuel cell", "efficiency"], 
       p_nom_extendable=True, 
       cyclic_state_of_charge=True)

# Re-optimize the network
n.optimize(solver_name="highs")

# Add CO2 emission limit for a 100% renewable system
n.add("GlobalConstraint", "CO2Limit", carrier_attribute="co2_emissions", sense="<=", constant=0)

# Re-optimize the network
n.optimize(solver_name="highs")

# Plotting optimal dispatch
def plot_dispatch(n, time="2015-07"):
    p_by_carrier = n.generators_t.p.groupby(n.generators.carrier, axis=1).sum().div(1e3)
    if not n.storage_units.empty:
        sto = n.storage_units_t.p.T.groupby(n.storage_units.carrier).sum().T.div(1e3)
        p_by_carrier = pd.concat([p_by_carrier, sto], axis=1)
    fig, ax = plt.subplots(figsize=(6, 3))
    color = p_by_carrier.columns.map(n.carriers.color)
    p_by_carrier.where(p_by_carrier > 0).loc[time].plot.area(ax=ax, linewidth=0, color=color)
    charge = p_by_carrier.where(p_by_carrier < 0).dropna(how="all", axis=1).loc[time]
    if not charge.empty:
        charge.plot.area(ax=ax, linewidth=0, color=charge.columns.map(n.carriers.color))
    n.loads_t.p_set.sum(axis=1).loc[time].div(1e3).plot(ax=ax, c="k")
    plt.legend(loc=(1.05, 0))
    ax.set_ylabel("GW")
    ax.set_ylim(-200, 200)

plot_dispatch(n)

# Save the network
n.export_to_netcdf("network-new.nc")

# Sensitivity analysis
def system_cost(n):
    tsc = n.statistics.capex() + n.statistics.opex()
    return tsc.droplevel(0).div(1e6)  # million €/a

# Sensitivity on CO2 emissions
sensitivity = {}
for co2 in [150, 100, 50, 25, 0]:
    n.global_constraints.loc["CO2Limit", "constant"] = co2 * 1e6
    n.optimize(solver_name="highs")
    sensitivity[co2] = system_cost(n)
df = pd.DataFrame(sensitivity).T.div(1e3)  # billion Euro/a
df.plot.area(stacked=True, linewidth=0, color=df.columns.map(n.carriers.color), figsize=(4, 4), xlim=(0, 150), xlabel=r"CO$_2$ emissions [Mt/a]", ylabel="System cost [bn€/a]", ylim=(0, 100))
plt.legend(frameon=False, loc=(1.05, 0))

# Sensitivity on solar capital cost
sensitivity = {}
for solar_cost in [0, 20, 40, 60, 80, 100, 150]:
    n.generators.loc["solar", "capital_cost"] = solar_cost * 1e3
    n.optimize(solver_name="highs")
    sensitivity[solar_cost] = system_cost(n)
n.generators.loc["solar", "capital_cost"] = 40 * 1e3
df = pd.DataFrame(sensitivity).T.div(1e3)  # billion Euro/a
df.plot.area(stacked=True, linewidth=0, color=df.columns.map(n.carriers.color), figsize=(4, 4), xlim=(0, 150), xlabel="Solar Capital Cost [€/MW/a]", ylabel="System cost [bn€/a]", ylim=(0, 100))

# Sensitivity on offshore wind potential
sensitivity = {}
for offwind_potential in [0, 50, 100, 150]:
    n.generators.loc["offwind", "p_nom_max"] = offwind_potential * 1e3
    n.optimize(solver_name="highs")
    sensitivity[offwind_potential] = system_cost(n)
df = pd.DataFrame(sensitivity).T.div(1e3) # billion Euro/a
df.plot.area(stacked=True, linewidth=0, color=df.columns.map(n.carriers.color), figsize=(4, 4), xlim=(0, 150), xlabel="Offshore Wind Potential [GW]", ylabel="System cost [bn€/a]", ylim=(0, 100))
