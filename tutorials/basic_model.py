import pypsa
import pandas as pd
import matplotlib.pyplot as plt

# Initialize the network
n = pypsa.Network()

# Set snapshots (time steps)
n.set_snapshots(pd.date_range("2022-01-01", "2022-01-02", freq="H"))

# Add buses for each region
n.add("Bus", "SA", y=-30.5, x=25, v_nom=400, carrier="AC")
n.add("Bus", "MZ", y=-18.5, x=35.5, v_nom=400, carrier="AC")
n.add("Bus", "electricity", carrier="AC")  # Adding the electricity bus

# Add carriers with emissions data
emissions = {"coal": 0.34, "gas": 0.2, "oil": 0.26, "hydro": 0, "wind": 0}
n.madd("Carrier", ["coal", "gas", "oil", "hydro", "wind"], co2_emissions=emissions)

# Add generators
power_plants = {"SA": {"coal": 35000, "wind": 3000, "gas": 8000, "oil": 2000}, "MZ": {"hydro": 1200}}
for tech, p_nom in power_plants["SA"].items():
    n.add("Generator", f"SA {tech}", bus="SA", carrier=tech, p_nom=p_nom, marginal_cost=8 / 0.33)

n.add("Generator", "MZ hydro", bus="MZ", carrier="hydro", p_nom=1200, marginal_cost=0)

# Add loads
loads = {"SA": 42000, "MZ": 650}
n.add("Load", "SA electricity demand", bus="SA", p_set=loads["SA"])
n.add("Load", "MZ electricity demand", bus="MZ", p_set=loads["MZ"])

# Add line between South Africa and Mozambique
n.add("Line", "SA-MZ", bus0="SA", bus1="MZ", s_nom=500, x=1, r=1)

# Add hydrogen bus
n.add("Bus", "hydrogen")

# Add electrolysis link
n.add("Link", "electrolysis", bus0="electricity", bus1="hydrogen", carrier="electrolysis",
      p_nom_extendable=True, efficiency=0.7, capital_cost=50e3)

# Add fuel cell link
n.add("Link", "fuel cell", bus0="hydrogen", bus1="electricity", carrier="fuel cell",
      p_nom_extendable=True, efficiency=0.5, capital_cost=120e3)

# Add hydrogen storage
n.add("Store", "hydrogen storage", bus="hydrogen", carrier="hydrogen storage",
      capital_cost=140, e_nom_extendable=True, e_cyclic=True)

# Heat Demand and Heat Pumps
# Add heat bus and load
n.add("Bus", "heat")
heat_demand = pd.read_csv("https://tubcloud.tu-berlin.de/s/mSkHERH8fJCKNXx/download/heat-load-example.csv", 
                          index_col=0, parse_dates=True).squeeze()
n.add("Load", "heat demand", carrier="heat", bus="heat", p_set=heat_demand)

# Add heat pump
def cop(t_source, t_sink=55):
    delta_t = t_sink - t_source
    return 6.81 - 0.121 * delta_t + 0.000630 * delta_t**2

temp = pd.read_csv("https://tubcloud.tu-berlin.de/s/S4jRAQMP5Te96jW/download/ninja_weather_country_DE_merra-2_population_weighted.csv", 
                   skiprows=2, index_col=0, parse_dates=True).loc["2015", "temperature"][::4]
n.add("Link", "heat pump", carrier="heat pump", bus0="electricity", bus1="heat", 
      efficiency=cop(temp), p_nom_extendable=True, capital_cost=3e5)

# Add resistive heater as backup
n.add("Link", "resistive heater", carrier="resistive heater", bus0="electricity", bus1="heat", 
      efficiency=0.9, capital_cost=1e4, p_nom_extendable=True)

# Combined Heat-and-Power (CHP) and Gas Storage
# Add gas bus and storage
n.add("Bus", "gas", carrier="gas")
n.add("Store", "gas storage", carrier="gas storage", bus="gas", e_initial=100e6, 
      e_nom=100e6, marginal_cost=150)

# Add OCGT and CHP plants
n.add("Link", "OCGT", bus0="gas", bus1="electricity", carrier="OCGT", p_nom_extendable=True, 
      capital_cost=20000, efficiency=0.4)
n.add("Link", "CHP", bus0="gas", bus1="electricity", bus2="heat", carrier="CHP", 
      p_nom_extendable=True, capital_cost=40000, efficiency=0.4, efficiency2=0.4)

# Electric Vehicles
# Add EV bus and load
n.add("Bus", "EV", carrier="EV")
ev_demand = pd.read_csv("https://tubcloud.tu-berlin.de/s/9r5bMSbzzQiqG7H/download/electric-vehicle-profile-example.csv", 
                        index_col=0, parse_dates=True).squeeze()
n.add("Load", "EV demand", bus="EV", carrier="EV demand", p_set=ev_demand)

# Add EV charger and V2G link
availability_profile = pd.read_csv("https://tubcloud.tu-berlin.de/s/E3PBWPfYaWwCq7a/download/electric-vehicle-availability-example.csv", 
                                   index_col=0, parse_dates=True).squeeze()
number_cars = 40e6
bev_charger_rate = 0.011
p_nom = number_cars * bev_charger_rate

n.add("Link", "EV charger", bus0="electricity", bus1="EV", p_nom=p_nom, carrier="EV charger", 
      p_max_pu=availability_profile, efficiency=0.9)
n.add("Link", "V2G", bus0="EV", bus1="electricity", p_nom=p_nom, carrier="V2G", 
      p_max_pu=availability_profile, efficiency=0.9)

# Add DSM store for EVs
bev_energy = 0.05
bev_dsm_participants = 0.5
e_nom = number_cars * bev_energy * bev_dsm_participants
dsm_profile = pd.read_csv("https://tubcloud.tu-berlin.de/s/K62yACBRTrxLTia/download/dsm-profile-example.csv", 
                          index_col=0, parse_dates=True).squeeze()
n.add("Store", "EV DSM", bus="EV", carrier="EV battery", e_cyclic=True, e_nom=e_nom, e_min_pu=dsm_profile)

# Optimize the System
n.optimize(solver_name="highs")

# Analyze the Results
print(n.statistics())

# Plot capital expenditure
n.statistics()["Capital Expenditure"].div(1e9).sort_values().dropna().plot.bar(ylabel="bn€/a", 
                                                                              cmap="tab20c", 
                                                                              figsize=(7, 3))
plt.show()

# Plot the network
n.plot(bus_sizes=1, margin=1)
plt.show()
