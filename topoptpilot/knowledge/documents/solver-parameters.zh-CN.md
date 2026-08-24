# MATLAB 求解器参数与直接求解配置

`volfrac` 是目标材料体积分数；`penal` 控制中间密度惩罚；`rmin` 是滤波半径；`beta` 用于投影锐化；`max_iter` 是迭代上限。参数必须由 Policy 在安全范围内编译。

Research Contract 固定 2D 或 3D。Policy 根据问题、预算和机器能力选择实际网格、精度、变体、加速方式与迭代上限。COPILOT 模式等待用户确认；AUTONOMOUS 模式通过 Safety 与 Budget 后直接执行。正式实验只允许 MATLAB MCP，不允许 Python 求解回退。
