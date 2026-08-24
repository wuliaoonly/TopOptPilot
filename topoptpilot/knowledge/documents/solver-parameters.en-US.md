# MATLAB solver parameters and direct profiles

`volfrac`, `penal`, `rmin`, `beta` and `max_iter` are compiled by Policy. The Research Contract fixes 2D or 3D. Policy selects the actual grid, accuracy, variant, acceleration and iteration limit from the question, budget and machine capabilities. COPILOT waits for confirmation; AUTONOMOUS runs after Safety and Budget pass. Production experiments use MATLAB MCP and never fall back to Python.
