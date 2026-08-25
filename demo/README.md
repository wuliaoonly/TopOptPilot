# V6.3 评审演示手册

## 正式入口

正式演示只使用 Tauri 桌面 App。`demo_runner.py` 是只读证据预检器，不启动求解器、不调用在线模型，也不会生成“成功”结果。

```powershell
python demo/demo_runner.py --check
python demo/demo_runner.py --timeline
python demo/demo_runner.py --json
```

返回码为 0 表示演示所需的仓库证据齐全；它不替代 MATLAB、在线 Agent 或桌面人工验收。

## 文件定位

| 文件 | 用途 |
|---|---|
| `demo_runner.py` | 校验 V6.3 版本、release audit、在线 campaign 记录、工具契约和安装包 |
| `run_solver_demo.py` | 旧 Python 求解器离线回归；不是 V6.3 Agent/桌面主演示 |
| `sample_inputs/mbb_2d_quick.json` | 主案例 Quick 请求模板；使用前替换 Workspace ID |
| `sample_inputs/mbb_2d_deep_draft.json` | 主案例 Deep Draft 模板；仍须经过 Research Contract 与预算校验 |
| `sample_inputs/bracket_task.json` | 历史示例输入，仅作 schema 参考，不代表已完成工程认证 |
| `../示范案例说明.md` | 八分钟现场讲稿、真实证据 ID 和故障预案 |

## 演示证据包

演示机器应提前准备：

- `TopOptPilot_6.3.0_x64-setup.exe` 及其 SHA-256。
- `release_audit.json`。
- `docs/validation/2026-08-25-v6.3-online-campaign.md`。
- 一个可授权的小型 MATLAB 项目目录。
- 一个隔离的 `TOPPILOT_DATA_DIR`。

不要把 `build/` 中的历史 campaign 数据直接当作现场新运行；展示历史记录时必须说出记录日期和 ID。

## 不进入正式演示的内容

- Paper-to-Plugin 固定返回值示例。
- CUDA/MEX 性能或 GPU 加速结论。
- 尚未闭环的 Quick Agent 两轮自主修正。
- 未经独立工程验证的应力、安全系数或工业可制造性结论。
