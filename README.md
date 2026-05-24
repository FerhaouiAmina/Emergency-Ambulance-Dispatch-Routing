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
python map_animation.py --data data/map.json
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
ª   README.md
ª   
+---ambulance-dispatch
    ª   .gitignore
    ª   main.py
    ª   map_animation.py
    ª   requirements.txt
    ª   
    +---__pycache__
    ª       map_animation.cpython-313.pyc
    ª       
    +---cache
    ª       c865b435e61cfbf46ba18e6d87d28ef8e0147cbe.json
    ª       9b31a4d40740a8e0ce55dd88622f35b99fd6f860.json
    ª       
    +---data
    ª       map.json
    ª       extract_osm.py
    ª       data.json
    ª       
    +---notebooks
    ª       Main_Project.py
    ª       Main_Project.ipynb
    ª       
    +---report
    ª       Report.pdf
    ª       
    +---scripts
    ª       verify_integration.py
    ª       patch_notebook.py
    ª       
    +---src
    ª   ª   __init__.py
    ª   ª   
    ª   +---algorithms
    ª   ª   ª   astar.py
    ª   ª   ª   astar_dispatch.py
    ª   ª   ª   greedy_dispatch.py
    ª   ª   ª   hill_climbing.py
    ª   ª   ª   realtime_astar.py
    ª   ª   ª   simple_path.py
    ª   ª   ª   standby_manager.py
    ª   ª   ª   
    ª   ª   +---__pycache__
    ª   ª           standby_manager.cpython-313.pyc
    ª   ª           hill_climbing.cpython-313.pyc
    ª   ª           astar.cpython-313.pyc
    ª   ª           realtime_astar.cpython-313.pyc
    ª   ª           greedy_dispatch.cpython-313.pyc
    ª   ª           astar_dispatch.cpython-313.pyc
    ª   ª           
    ª   +---core
    ª   ª   ª   ambulance.py
    ª   ª   ª   depot_utils.py
    ª   ª   ª   edge.py
    ª   ª   ª   emergency.py
    ª   ª   ª   graph.py
    ª   ª   ª   hospital.py
    ª   ª   ª   node.py
    ª   ª   ª   simulation_engine.py
    ª   ª   ª   __init__.py
    ª   ª   ª   
    ª   ª   +---__pycache__
    ª   ª           __init__.cpython-313.pyc
    ª   ª           graph.cpython-313.pyc
    ª   ª           node.cpython-313.pyc
    ª   ª           edge.cpython-313.pyc
    ª   ª           hospital.cpython-313.pyc
    ª   ª           ambulance.cpython-313.pyc
    ª   ª           depot_utils.cpython-313.pyc
    ª   ª           emergency.cpython-313.pyc
    ª   ª           simulation_engine.cpython-313.pyc
    ª   ª           
    ª   +---evaluation
    ª   ª   ª   algorithm_comparison.py
    ª   ª   ª   comparison_runner.py
    ª   ª   ª   metrics.py
    ª   ª   ª   response_time_analysis.py
    ª   ª   ª   simulation_benchmark.py
    ª   ª   ª   static_vs_dynamic.py
    ª   ª   ª   
    ª   ª   +---__pycache__
    ª   ª           metrics.cpython-313.pyc
    ª   ª           response_time_analysis.cpython-313.pyc
    ª   ª           static_vs_dynamic.cpython-313.pyc
    ª   ª           algorithm_comparison.cpython-313.pyc
    ª   ª           comparison_runner.cpython-313.pyc
    ª   ª           simulation_benchmark.cpython-313.pyc
    ª   ª           
    ª   +---simulation
    ª   ª   ª   dispatcher.py
    ª   ª   ª   dynamic_strategy.py
    ª   ª   ª   event_queue.py
    ª   ª   ª   poisson_generator.py
    ª   ª   ª   static_strategy.py
    ª   ª   ª   surge_scenarios.py
    ª   ª   ª   
    ª   ª   +---__pycache__
    ª   ª           dispatcher.cpython-313.pyc
    ª   ª           event_queue.cpython-313.pyc
    ª   ª           poisson_generator.cpython-313.pyc
    ª   ª           surge_scenarios.cpython-313.pyc
    ª   ª           dynamic_strategy.cpython-313.pyc
    ª   ª           static_strategy.cpython-313.pyc
    ª   ª           
    ª   +---traffic
    ª   ª   ª   traffic_model.py
    ª   ª   ª   
    ª   ª   +---__pycache__
    ª   ª           traffic_model.cpython-313.pyc
    ª   ª           
    ª   +---visualization
    ª   ª   ª   dashboard.py
    ª   ª   ª   heatmap.py
    ª   ª   ª   histograms.py
    ª   ª   ª   histogram_astar_greedy.py
    ª   ª   ª   traffic_heatmap_enhanced.png
    ª   ª   ª   __init__.py
    ª   ª   ª   
    ª   ª   +---__pycache__
    ª   ª           histogram_astar_greedy.cpython-313.pyc
    ª   ª           __init__.cpython-313.pyc
    ª   ª           histograms.cpython-313.pyc
    ª   ª           heatmap.cpython-313.pyc
    ª   ª           dashboard.cpython-313.pyc
    ª   ª           
    ª   +---__pycache__
    ª           __init__.cpython-313.pyc
    ª           
    +---visualization
        ª   control_panel.py
        ª   entity_renderer.py
        ª   fake_simulation.py
        ª   main_window.py
        ª   map_renderer.py
        ª   map_widget.py
        ª   real_simulation.py
        ª   stats_panel.py
        ª   ui_theme.py
        ª   __init__.py
        ª   
        +---__pycache__
                control_panel.cpython-314.pyc
                entity_renderer.cpython-313.pyc
                fake_simulation.cpython-313.pyc
                fake_simulation.cpython-314.pyc
                main_window.cpython-314.pyc
                map_bridge.cpython-313.pyc
                map_renderer.cpython-313.pyc
                map_widget.cpython-314.pyc
                real_simulation.cpython-314.pyc
                stats_panel.cpython-314.pyc
                ui_theme.cpython-314.pyc
                __init__.cpython-314.pyc
                __init__.cpython-313.pyc
                main_window.cpython-313.pyc
                ui_theme.cpython-313.pyc
                control_panel.cpython-313.pyc
                map_widget.cpython-313.pyc
                stats_panel.cpython-313.pyc
                real_simulation.cpython-313.pyc
                

```

