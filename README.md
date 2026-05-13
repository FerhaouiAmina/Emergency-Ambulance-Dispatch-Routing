# Emergency Ambulance Dispatch Routing
## Project Description
This project implements an AI-based ambulance dispatch simulation.
The system models:
- Emergency calls
- Ambulance locations and availability
- Traffic conditions
- Routing algorithms
- Dispatch strategies
Multiple algorithms are implemented and evaluated using performance metrics such as response time and ambulance utilization.
---
## Objectives
1. Model a realistic emergency response environment.
2. Implement multiple routing and dispatch algorithms.
3. Compare algorithm performance.
4. Analyze trade-offs between strategies.
---
## Project Architecture
### src/simulation
Models the emergency response environment:
- City map (graph-based)
- Ambulance objects
- Dispatcher logic
- Simulation time loop
- Traffic model
### src/algorithms
Contains dispatch and routing strategies:
- Greedy nearest ambulance
- A* routing
- Hill climbing
### src/evaluation
Performance measurement:
- Average response time
- Maximum delay
- Utilization rate
- Comparative analysis
### src/core
Shared utilities:
- Configuration
- Distance computation
- Data loading
- Logging
### data
- raw: Original datasets
- processed: Cleaned and transformed datasets
### report
Contains The final report of the project
---
## Installation
NB: it is recommended to be working with a linux cmd
Clone the repository:
```
git clone https://github.com/FerhaouiAmina/Emergency-Ambulance-Dispatch-Routing.git
cd ambulance-dispatch
```
Install dependencies:
```
pip install -r requirements.txt
```
if a message shows up it means you haven't activated a virtual environment:
Create the environment:
```
python -m venv .venv
```
Note: you can replace the ".venv" with any name you want for your environment
Activate it:
```
source .venv/bin/activate
```
---
## Running the Simulation
```
python -m src.main
```
---
## Evaluation Metrics
- Average response time
- Maximum response delay
- Ambulance utilization percentage
- Call coverage rate
---
## Team Members
- Allali Bouchra - G1 
- Bentata Ikram Amina - G8
- Ferhaoui Amina - G12
- Hamadach Thawriyya - G12
- Immessaoudene Malak Ikram - G1
- Moumani Malek Nourhene - G8
---
## Report
The final report is located in the /report directory and follows the given guidelines. Each member activity is found undere Appendix B

---
# Repository Structure
```
ambulance-dispatch-ai/
├── requirements.txt
├── .gitignore
├── notebooks/
│   ├── main_project.ipynb
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/
│   │   ├── graph.py
│   │   ├── node.py
│   │   ├── edge.py
│   │   ├── ambulance.py
│   │   ├── hospital.py
│   │   ├── emergency.py
│   │   └── simulation_engine.py
│   │
│   ├── algorithms/
│   │   ├── astar.py
│   │   ├── realtime_astar.py
│   │   ├── greedy_dispatch.py
│   │   ├── astar_dispatch.py
│   │   ├── hill_climbing.py
│   │   ├── simple_path.py
│   │   └── standby_manager.py
│   │
│   ├── traffic/
│   │   ├── traffic_model.py
│   │   ├── congestion_updates.py
│   │   └── rush_hour_rules.py
│   │
│   ├── simulation/
│   │   ├── event_queue.py
│   │   ├── poisson_generator.py
│   │   ├── surge_scenarios.py
│   │   └── dispatcher.py
│   │
│   ├── evaluation/
│   │   ├── metrics.py
│   │   ├── response_time_analysis.py
│   │   ├── static_vs_dynamic.py
│   │   └── algorithm_comparison.py
│   │
│   └── visualization/
│       ├── map_animation.py
│       ├── heatmap.py
│       ├── histograms.py
│       └── dashboard.py
│
├── data/
│   ├── raw/
│   │   ├── .gitkeep
│   │
│   ├── processed/
│       ├── .gitkeep
│
├── tests/
│   ├── test_astar.py
│   ├── test_realtime_astar.py
│   ├── test_hill_climbing.py
│   ├── test_dispatch.py
│   └── test_simulation.py
│
└── report/
│   ├── .gitkeep
│
└── README.md
```

