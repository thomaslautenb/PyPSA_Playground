
from model.capacity_expansion_model import load_cost_data, load_time_series, create_network, add_storage_units, optimize_network, apply_co2_limit, save_network
import pypsa
import pandas as pd
import matplotlib.pyplot as plt

def system_cost(n):
    tsc = n.statistics.capex() + n.statistics.opex()
    return tsc.droplevel(0).div(1e6)  # million €/a

def sensitivity_analysis(n, parameter, values, plot_title, xlabel):
    sensitivity = {}
    for value in values:
        if parameter == "CO2Limit":
            n.global_constraints.loc["CO2Limit", "constant"] = value * 1e6
        elif parameter == "solar_cost":
            n.generators.loc["solar", "capital_cost"] = value * 1e3
        elif parameter == "offwind_potential":
            n.generators.loc["offwind", "p_nom_max"] = value * 1e3
        
        print('optimizing network')
        optimize_network(n)
        
        sensitivity[value] = system_cost(n)
    df = pd.DataFrame(sensitivity).T.div(1e3)  # billion Euro/a
    df.plot.area(stacked=True, linewidth=0, color=df.columns.map(n.carriers.color), figsize=(4, 4), xlabel=xlabel, ylabel="System cost [bn€/a]", ylim=(0, 100))
    plt.title(plot_title)
    plt.legend(frameon=False, loc=(1.05, 0))
    plt.show()

if __name__ == "__main__":
    costs = load_cost_data()
    ts = load_time_series()
    n = create_network(ts, costs)
    optimize_network(n)
    add_storage_units(n, costs)
    apply_co2_limit(n, 0)
    
    # Sensitivity analysis on CO2 emissions
    sensitivity_analysis(n, "CO2Limit", [150, 0], "Sensitivity on CO2 emissions", r"CO$_2$ emissions [Mt/a]")
    
    # Sensitivity analysis on solar capital cost
    #sensitivity_analysis(n, "solar_cost", [0, 20, 40, 60, 80, 100, 150], "Sensitivity on Solar Capital Cost", "Solar Capital Cost [€/MW/a]")
    
    # Sensitivity analysis on offshore wind potential
    #sensitivity_analysis(n, "offwind_potential", [0, 50, 100, 150], "Sensitivity on Offshore Wind Potential", "Offshore Wind Potential [GW]")
