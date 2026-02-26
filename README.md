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
- Dijkstra routing
- Reinforcement learning dispatcher
### src/evaluation
Performance measurement:
- Average response time
- Maximum delay
- Utilization rate
- Comparative analysis
### src/utils
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
Clone the repository:
```
git clone https://github.com/FerhaouiAmina/Emergency-Ambulance-Dispatch-Routing.git
cd ambulance-dispatch
```
Install dependencies:
```
pip install -r requirements.txt
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
ambulance-dispatch/
│
├── report/
│   └── Mini_Project_Report.pdf
│
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   └── processed/
│       └── .gitkeep
│
├── src/
│   ├── __init__.py
│   │
│   ├── simulation/
│   │   ├── __init__.py
│   │   ├── city_map.py
│   │   ├── ambulance.py
│   │   ├── environment.py
│   │   ├── dispatcher.py
│   │   └── traffic_model.py
│   │
│   ├── algorithms/
│   │   ├── __init__.py
│   │   ├── base_algorithm.py
│   │   ├── greedy_dispatch.py
│   │   ├── a_star_routing.py
│   │   ├── dijkstra_routing.py
│   │   └── reinforcement_learning.py
│   │
│   ├── evaluation/
│   │   ├── __init__.py
│   │   ├── metrics.py
│   │   └── performance_tracker.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── data_loader.py
│   │   ├── distance.py
│   │   └── logger.py
│   │
│   └── main.py
│
├── notebooks/
│   └── Main_Project.ipynb
│
├── tests/
│   ├── __init__.py
│   ├── test_city_map.py
│   ├── test_dispatcher.py
│   ├── test_algorithms.py
│   └── test_metrics.py
│
├── requirements.txt
├── README.md
└── .gitignore
```

