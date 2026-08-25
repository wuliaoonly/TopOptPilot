# V6.3.0 候选发布说明 — 统一工作台与桌面专用版本

> **桌面端专用候选版本**。V6.3 将"快速实现 / 深度优化"统一到同一个 Tauri 原生工作台：
> 共用左栏项目文件、中央四页签（代码 / 结果 / 迭代 / 参数）与右侧工作流面板，
> Quick Run 与 Deep Experiment 共用同一套 Workspace、Agent 工作流与制品血缘。
> 本版本**不再提供** Streamlit 或独立浏览器版入口（`launch.py --web` 已被拒绝）。

---

## ✨ 新增功能

### 🧩 统一优化工作台（Quick / Deep 同台）
- **快速实现 / 深度优化**在同一原生窗口中切换，共用左栏、中央四页签与右侧工作流面板
- Quick Run 与 Deep Experiment 切换后，代码、结果、迭代可视化、参数与对比同步更新
- 新的 Workspace 抽象统一承载工程 Quick Run 与科研 Deep Experiment 的上下文与制品

### ⚡ Quick 快速实现 Workspace
- 紧凑的快速实现工作台：直接配置本机 MATLAB / 编译 Runtime，发起真实 2D/3D 求解
- Quick 运行限定在统一 Workspace 内，运行与结果持久化、可回放
- 从 Quick 2D/3D 可一键晋升为 Deep 科研实验（Quick → Deep promotion）

### 🧭 Deep 深度科研 Workspace
- 统一的 Workspace 上下文、Agent 工作流条目与对话，全部持久化并可恢复
- **可逆深度研究归档**：归档可恢复，研究记录不被破坏
- Workspace 有未保存文件时阻止切换，后台 Run / Experiment / Agent 任务持续运行

### 🔐 权限与隔离
- Workspace 授权机制：实验 overlay 隔离在受控目录，不可越权读写
- 工程 MATLAB / Runtime 链路与科研 F3 MATLAB MCP 权限保持隔离

### 🏗️ 工程链路（已验证 MATLAB 2D/3D）
- 工程 MATLAB 2D/3D 路由：参数选择"二维/三维"后调用 `TopOpt_2D/topopt_main.m` 或
  `TopOpt-3D/topopt3d_main.m`；失败记为 `MATLAB_INFRASTRUCTURE`，不回退 Python
- 只读工程问答与已验证对比：结果对比只基于真实 solver provenance
- 工程求解清单 `matlab/engineering/solver-sources.json` 随包提供，哈希逐文件校验

### 📦 发布与运行
- **网页入口移除**：`python launch.py --web` 被参数解析拒绝，产品只提供 Tauri 原生桌面端
- 发布审计与运行时品牌对齐；离线发布门禁通过（`offline_release_ready=true`）

---

## 🔬 测试证据

### 本机离线门禁（2026-08-25 复验）
| 项目 | 结果 | 证据 |
|---|---|---|
| Python 回归 | 163 passed | `python -m pytest tests -q` |
| 前端组件与显示逻辑 | 65 passed / 23 files | `npm --prefix desktop test -- --run` |
| 前端生产构建 | 通过 | `npm --prefix desktop run build` |
| Tauri Rust 测试 | 32 passed | `cargo test --manifest-path desktop/src-tauri/Cargo.toml` |
| 快速实现 MATLAB | 2D、3D 本机真实运行通过 | 本机 MATLAB R2024a 冒烟 |
| 深度研究 MATLAB MCP | 2D、3D 与 2D 等价性门禁通过 | `python -m topoptpilot.release_audit --offline` |
| 安装包启动 | 已打包 Tauri App 启动并拉起 sidecar | 隔离数据目录启动冒烟 |

### 在线 Agent Campaign（P0）— 通过
以已配置的在线 Agent 服务（`api.ai-pixel.online` / `deepseek-v4-flash`，Windows
Credential Manager 凭据）完成受控 Deep Research campaign。实际结果：

- **Research A · MBB-001 — `FINAL_REVIEW: APPROVE`**：
  E01（β=16，compliance 796.652，gray 0.0833）→ E02（β=32 受控对比，
  compliance 125.657，gray 0.0）；SCIENTIST Subagent 产出假设 `H-F928A413EF`；
  在线终审 Reviewer `SA-DC9BF7B9ED` 确认受控单变量对比后 **APPROVE**，
  正式最终报告才生成。
- **Research B · MBB-002 — `FINAL_REVIEW: REVISE`**：
  单次无对照可行运行被确认（GOAL_ACHIEVED 成立），但因果假设
  「投影强度导致拓扑完全离散」不被证据支持；在线终审 Reviewer
  `SA-A6B2716F76` 返回 **REVISE**，终止被撤回、正式报告保持阻塞。
- **Reviewer Gate 验证**：两个研究在终审 `APPROVE` 前，`report_path` 均抛
  `FINAL_REPORT_NOT_READY`；`APPROVE` 后正式报告才可下载。
- 实际 Research / Experiment / Evaluator / Reviewer / 制品 ID 见独立测试记录
  `docs/validation/2026-08-25-v6.3-online-campaign.md`。
- `release_audit.json`：`online_agent.pass=true`，`release_ready=true`。

---

## 📦 安装包

- **TopOptPilot_6.3.0_x64-setup.exe**（NSIS）— `desktop/src-tauri/target/release/bundle/nsis/`
- **SHA-256**：`E0EF7591D48CCCC2F6BE025EE52BF4E6730AE38DE74646707279A39859B33CC0`
- **代码签名**：未签名（本发布不暗示已签名）

## 🔄 兼容性

- 旧 Research、旧 Quick/Deep 记录与旧报告保持可读，不改写 provenance
- Windows 10/11 x64；MATLAB R2024a 为本机验证环境
- `vendor/` 第三方二进制（Node runtime、MATLAB MCP Server）随安装包提供，不入库

## ⚠️ 发布范围声明

- **桌面端专用**：本版本不提供浏览器/Streamlit 入口
- **发布状态**：`v6.3.0` 标签已存在，GitHub Release 页面与安装包 asset 已发布
  （https://github.com/wuliaoonly/TopOptPilot/releases/tag/v6.3.0）
- **未完成门禁如实声明**：干净 Windows 虚拟机安装/卸载矩阵、代码签名仍需独立环境完成；
  不以其缺失掩盖任何未验证功能
