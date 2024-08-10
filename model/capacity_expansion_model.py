import pypsa
import pandas as pd
import matplotlib.pyplot as plt

plt.style.use("bmh")

def load_cost_data(year=2030):
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

    annuity_values = costs.apply(lambda x: annuity(x["discount rate"], x["lifetime"]), axis=1)
    costs["capital_cost"] = (annuity_values + costs["FOM"] / 100) * costs["investment"]
    costs["marginal_cost"] = costs["VOM"] + costs["fuel"] / costs["efficiency"]

    return costs

def create_network(ts, costs):
    n = pypsa.Network()
    n.add("Bus", "electricity", carrier="electricity")  # Define the bus carrier explicitly
    n.set_snapshots(ts.index)
    n.snapshot_weightings.loc[:, :] = 4  # Set the resolution directly to 4 hours

    carriers = ["onwind", "offwind", "solar", "OCGT", "hydrogen storage underground", "battery storage"]
    n.madd("Carrier", carriers, 
           color=["dodgerblue", "aquamarine", "gold", "indianred", "magenta", "yellowgreen"], 
           co2_emissions=[costs.at[c, "CO2 intensity"] for c in carriers])

    n.add("Load", "demand", bus="electricity", p_set=ts.load)

    n.add("Generator", "OCGT", bus="electricity", carrier="OCGT", 
           capital_cost=costs.at["OCGT", "capital_cost"], 
           marginal_cost=costs.at["OCGT", "marginal_cost"], 
           efficiency=costs.at["OCGT", "efficiency"], 
           p_nom_extendable=True)

    for tech in ["onwind", "offwind", "solar"]:
        n.add("Generator", tech, bus="electricity", carrier=tech, 
              p_max_pu=ts[tech], 
              capital_cost=costs.at[tech, "capital_cost"], 
              marginal_cost=costs.at[tech, "marginal_cost"], 
              efficiency=costs.at[tech, "efficiency"], 
              p_nom_extendable=True)
    
    return n

def add_storage_units(n, costs):
    n.add("StorageUnit", "battery storage", bus="electricity", carrier="battery storage", 
           max_hours=6, 
           capital_cost=costs.at["battery inverter", "capital_cost"] + 6 * costs.at["battery storage", "capital_cost"], 
           efficiency_store=costs.at["battery inverter", "efficiency"], 
           efficiency_dispatch=costs.at["battery inverter", "efficiency"], 
           p_nom_extendable=True, 
           cyclic_state_of_charge=True)

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

def optimize_network(n, solver_name="highs"):
    n.optimize(solver_name=solver_name)

def apply_co2_limit(n, limit):
    n.add("GlobalConstraint", "CO2Limit", carrier_attribute="co2_emissions", sense="<=", constant=limit)
    optimize_network(n)

def save_network(n, filename="network-new.nc"):
    n.export_to_netcdf(filename)

def load_time_series():
    url = "https://tubcloud.tu-berlin.de/s/pKttFadrbTKSJKF/download/time-series-lecture-2.csv"
    ts = pd.read_csv(url, index_col=0, parse_dates=True)
    ts.load *= 1e3  # Convert load from GW to MW
    ts.resolution = 4
    ts = ts.resample(f"{ts.resolution}h").first()
    return ts

if __name__ == "__main__":
    costs = load_cost_data()
    ts = load_time_series()
    n = create_network(ts, costs)
    optimize_network(n)
    add_storage_units(n, costs)
    optimize_network(n)
    apply_co2_limit(n, 0)
    optimize_network(n)
    plot_dispatch(n)
    save_network(n)
