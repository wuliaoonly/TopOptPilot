# TopOptPilot V6.3

面向结构拓扑优化的桌面智能工作台：把工程代码、真实 MATLAB 求解、实验评价、Agent 协作、独立终审和可追溯报告放进同一条证据链。

> V6.3 只提供 Windows Tauri 桌面应用，不提供 Streamlit 或独立网页端。React/Vite 仅用于构建桌面 WebView 界面。

## 当前交付状态

| 项目 | 状态 | 说明 |
|---|---|---|
| 版本 | `6.3.0` | Git 标签 `v6.3.0` 已指向当前候选代码 |
| 桌面安装包 | 已生成 | `TopOptPilot_6.3.0_x64-setup.exe`，当前未签名 |
| 离线发布审计 | 通过 | MATLAB MCP 2D、3D、等价性和资源哈希均通过 |
| 在线 Deep campaign | 通过 | 覆盖 Research Lead、SCIENTIST、Reviewer `REVISE/APPROVE` |
| GitHub Release | 已创建 | https://github.com/wuliaoonly/TopOptPilot/releases/tag/v6.3.0 ，安装包与 SHA-256 已上传 |
| 独立环境验收 | 待完成 | 干净 Windows 安装/升级/卸载、人工 UI 视觉检查、代码签名 |

权威证据见 [在线 campaign 记录](docs/validation/2026-08-25-v6.3-online-campaign.md)、[待测试清单](docs/validation/V6.3-待测试清单.md) 和仓库根目录的 `release_audit.json`。

## 产品解决什么问题

传统拓扑优化工作往往分散在代码编辑器、MATLAB、结果目录、表格和聊天工具中。参数为什么改变、某次结果是否可行、Agent 是否越权、报告是否经过独立审查，很难在同一个上下文里回答。

TopOptPilot 将工作拆成两条共享 Workspace 的链路：

| 链路 | 适合场景 | Agent 行为 | 结果裁决 |
|---|---|---|---|
| 快速实现 Quick | 修改代码、配置参数、快速运行 2D/3D MATLAB、比较真实运行 | 工程问答与 Patch Proposal；不主动反思，不接触 Deep ToolGateway | `completed` 仅表示执行完成，不等于可行或成功 |
| 深度优化 Deep | 形成假设、受控实验、评价、反思、复审和报告 | Research Lead 调度隔离 Subagent；最终 Reviewer 独立审阅 | Evaluator 判断可行性；Reviewer 只有 `APPROVE` 才放行正式报告 |

两条链路共用项目文件、工作区授权、代码/结果/迭代/参数视图和 Agent 工作流面板，但 Quick Run 与 Deep Experiment 使用不同状态机。

## 核心能力

### 统一桌面工作台

- 左栏：Workspace 文件，以及当前模式的 Quick Runs 或 Research → Experiments。
- 中央：代码、结果、迭代可视化、参数与对比四个固定页签。
- 右栏：Agent 工作流与检查器；只显示脱敏后的任务、工具摘要、审批和证据引用。
- Quick → Deep 晋升采用不可变 `SourceSnapshot`；Deep 修改进入 Experiment Overlay，不自动改写项目主文件。

### 真实求解与可验证结果

- Quick 本机 MATLAB：2D 路由到 `TopOpt_2D/topopt_main.m`，3D 路由到 `TopOpt-3D/topopt3d_main.m`。
- Quick 可选已验证的 MATLAB Runtime；标准安装包不冒充包含 Runtime。
- Deep 通过 MATLAB MCP 的受控工具运行 Direct Solver，不向 Agent 暴露任意 shell、terminal 或直接数据库访问。
- 密度场、历史、日志、图像和求解证据均带 SHA-256、owner 和 lineage。
- 失败实验是有效证据；基础设施失败不会回退成 Python 并宣称 MATLAB 成功。

### Deep Agent 与最终审阅门禁

```text
Research Goal
  → Research Lead 读取权威 Research State
  → 精确 ExperimentDraft 校验与预算预览
  → Agent Proposal + 人工批准
  → MATLAB MCP 异步实验
  → Deterministic Evaluator
  → 反思 / 受控后续实验
  → FINAL_REVIEW: Independent Reviewer
      ├─ APPROVE → 生成正式报告
      └─ REVISE/REJECT → 撤销终止或暂停，禁止正式报告
```

当研究包含假设时，至少需要两个成功实验才能判定 `GOAL_ACHIEVED`。因果结论只允许来自单一受控变量差异。

### 安全边界

- Tauri 对用户选择的项目签发 Workspace Grant；路径不能越过授权根目录。
- 项目写入必须经过 unified diff、预览令牌和人工 Patch Approval。
- Quick 工程 Agent 不拥有 terminal、Deep 实验工具或 Research ToolGateway。
- 每个 Pi 进程使用绑定 research、role、allowed tools 和 expiry 的 capability token。
- WebSocket 使用短期、单次消费 ticket，不把长期 Desktop token 放入 query。
- API key 不写入 SQLite、报告、日志或前端状态。

## 快速开始

### 使用安装包

系统要求：Windows 10/11 x64。MATLAB R2024a 是当前真实求解验证环境；MATLAB 本体不随安装包分发。

```text
desktop/src-tauri/target/release/bundle/nsis/TopOptPilot_6.3.0_x64-setup.exe
SHA-256: E0EF7591D48CCCC2F6BE025EE52BF4E6730AE38DE74646707279A39859B33CC0
```

安装包当前未进行 Authenticode 签名。首次使用时在设置页探测 MATLAB，再打开或创建 Workspace。

### 从源码启动桌面 App

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
npm install
npm --prefix desktop install
python launch.py
```

`python launch.py` 只启动已构建的桌面程序或 `tauri dev`。`--web` 已移除。
在线 Agent 凭据可通过桌面设置的专用凭据接口配置；开发环境也可在启动进程前设置
`DASHSCOPE_API_KEY`。密钥不得写进仓库、源码、SQLite、日志或报告。

## 八分钟评审演示

演示前先执行只读证据预检：

```powershell
python demo/demo_runner.py --check
```

正式演示使用 Tauri App，不使用浏览器：

1. 打开已授权的 Workspace，展示相同左栏、四个中央页签和 Agent 工作流。
2. 在 Quick 中配置小网格 2D MBB，提交本机 MATLAB 运行。
3. 展示真实迭代、密度/日志制品与 SHA-256；解释 `completed ≠ feasible`。
4. 将 Quick Run 晋升到 Deep，展示不可变 SourceSnapshot 和 lineage。
5. 展示受控 Experiment Proposal、预算检查、人工批准和 MATLAB MCP 实验。
6. 展示 Evaluator 的执行/评价/可行性分轴状态。
7. 展示已验证 campaign 中 Reviewer `REVISE` 与 `APPROVE` 两条路径。
8. 证明 `APPROVE` 前正式报告不可下载，随后打开报告与复现证据。

完整讲稿、现场/录屏切换规则和故障预案见 [示范案例说明](示范案例说明.md) 与 [demo 演示手册](demo/README.md)。

## 已验证证据

| 门禁 | 最近记录 |
|---|---|
| Python | 163 passed |
| React/Vitest | 65 passed / 23 files |
| 前端生产构建 | TypeScript + Vite build 通过 |
| Rust/Tauri | 32 passed |
| Quick MATLAB | 本机 2D、3D 真实运行通过 |
| Deep MATLAB MCP | 2D、3D 真实运行通过 |
| 等价性 | 2D reference/optimized/re-run compliance 一致，密度一致 |
| 在线 Agent | Deep Research campaign 覆盖 Lead、SCIENTIST、REVISE、APPROVE |
| 报告门禁 | Reviewer `APPROVE` 前返回 `FINAL_REPORT_NOT_READY` |

这些数字是特定提交和环境的验证记录，不代表所有硬件上的性能保证。运行新的测试后应生成新的记录，不能覆盖历史结果含义。

## 开发与验证

```powershell
git diff --check
python -m compileall topoptpilot idesktop_v2 mcp solver demo
python scripts/generate_contracts.py --check
python -m pytest tests -q
npm --prefix desktop test -- --run
npm --prefix desktop run build
cargo test --manifest-path desktop/src-tauri/Cargo.toml
cargo check --manifest-path desktop/src-tauri/Cargo.toml
python -m topoptpilot.release_audit --offline
```

在线发布审计会读取独立 campaign 证据。重新运行真实在线 campaign 会消耗模型和 MATLAB 资源：

```powershell
python scripts/run_v63_online_campaign.py
python -m topoptpilot.release_audit
```

打包：

```powershell
powershell -ExecutionPolicy Bypass -File scripts/build_desktop.ps1
```

## 关键目录

```text
desktop/                         Tauri + React 桌面应用
idesktop_v2/                     Quick 工程运行、助手、制品和 sidecar
topoptpilot/api/                 Desktop REST/WS 适配层
topoptpilot/agent_runtime/       Research Lead、Subagent、Reviewer 与 Pi bridge
topoptpilot/service/             ResearchService 与研究状态操作
topoptpilot/tools/               16 个 Deep Agent 工具契约与实现
mcp/matlab_mcp/                  MATLAB MCP worker 与受控工具
matlab/engineering/              Quick 2D/3D MATLAB 入口和求解清单
topoptpilot/memory/              Research/Workspace 权威状态与迁移
demo/                            评审演示预检和讲稿
docs/validation/                 实测证据与待测试清单
```

## 当前已知边界

- Quick Agent 的统一任务、会话和工作流投影已经落库，但完整“两轮代码生成→预检→修正→Patch 审批”执行器仍需补齐；正式演示使用现有工程 Chat/Patch Proposal 能力，不宣称该队列已经自主执行。
- Paper-to-Plugin 不是 V6.3 已交付能力，旧固定成功示例已从正式演示移除。
- 标准安装包不包含 MATLAB 本体或完整 Runtime。
- 尚未完成独立干净 Windows 安装/升级/卸载矩阵与代码签名。
- GitHub Release 页面与安装包资产已发布（`v6.3.0`）；代码签名仍未完成。

## 评审自评

按“科学价值 40% + 技术深度 30% + 应用潜力 30%”的证据化自评为 **86/100**。主要失分来自 Quick Agent 执行器尚未闭环、干净机交付与签名未完成，以及案例仍集中于 MBB 2D/基础 3D 通路。详细分项、扣分依据和提升优先级见 [V6.3 评审标准自评与改进建议](docs/V6.3-评审标准自评与改进建议.md)。

## 文档索引

- [示范案例说明](示范案例说明.md)
- [V6.3 Release Notes](release_notes_v6.3.0.md)
- [在线 Deep Research campaign 实测](docs/validation/2026-08-25-v6.3-online-campaign.md)
- [V6.3 待测试清单](docs/validation/V6.3-待测试清单.md)
- [评审标准自评与改进建议](docs/V6.3-评审标准自评与改进建议.md)

## 许可证与结果责任

项目包含基于 BSD-2-Clause 资源扩展的拓扑优化实现。工程材料、载荷、边界条件和安全结论必须由有资质的工程人员复核；TopOptPilot 的评价结果不能替代工程签字、法规认证或独立安全验证。
