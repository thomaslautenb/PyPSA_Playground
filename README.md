# PyPSA_Playground

PyPSA_Playground is a project designed for exploring and experimenting with PyPSA (Python for Power System Analysis). This repository contains various scripts, models, and tutorials to help users learn and apply PyPSA for power system analysis and simulation.

## Features

- **Power System Modeling**: Examples and templates for building power system models using PyPSA.
- **Analysis Tools**: Scripts to analyze and visualize results from power system simulations.
- **Sensitivity Analysis**: Specific tools to conduct sensitivity analysis, enabling the assessment of how different parameters affect the system's performance and cost.
- **Capacity Expansion Modeling**: Models to explore how different factors influence the expansion of power generation capacity over time.

## Usage

### Sensitivity Analysis

The `sensitivity_analysis.py` script is designed to analyze the impact of various parameters on the overall system cost. The analysis can be performed on different parameters such as CO2 emissions limits, solar capital costs, and offshore wind potential. The results are visualized using area plots to show how changes in these parameters affect the system cost.

### Capacity Expansion Model

The `capacity_expansion_model.py` script handles the creation and optimization of network models to simulate capacity expansion. It includes functionalities to:
- Load cost data and time series.
- Create a network model.
- Add storage units.
- Optimize the network for minimum cost.
- Apply CO2 emission constraints.


## Acknowledgements

- [PyPSA](https://pypsa.org/) - The primary tool used in this project.
- [Thomas Lautenbacher](https://github.com/thomaslautenb) - Creator and maintainer of the PyPSA_Playground repository.
