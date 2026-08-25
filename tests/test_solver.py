"""solver 模块物理验证 + 全链路集成测试

覆盖（与缺口分析 #3 ——"真实求解替代随机模拟" 对应）：
  T1 参数规范化      normalize_task 幂等 / 别名 / 网格映射 / 投影→控制器约束
  T2 OC 更新移植     体积守恒、上下界、收敛（对照 OC_solver.m 行为）
  T3 经典路径真值     60×30 MBB volfrac=0.5 对照 MATLAB top99（391.91/148.83/127.69）
  T4 Heaviside 物理   无投影灰度高 → 周期调度后灰度低、单连通、柔度降
  T5 四种控制器       全部可跑且柔度正有限
  T6 结果契约字段      build_result 顶层字段 / quality / solver / artifacts 完整性
  T7 队列端到端       ExperimentQueue 四组（B0/B1/A1/Ours）成效趋势
  T8 持久化           SolverRunner.run_sync 输出 density/history/log

运行：python tests/test_solver.py
"""

import json
import os
import sys
import time

# 强制 UTF-8 输出（Windows GBK 控制台无法渲染 ✅/❌）
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

import numpy as np

# 允许从项目根导入
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        passed += 1
        print(f"  ✅ PASS: {name}")
    else:
        failed += 1
        print(f"  ❌ FAIL: {name}")
        if detail:
            print(f"       {detail}")


def _classic_task(task_id="t", mesh="medium", max_iter=60, volfrac=0.5, **kw):
    """经典路径任务模板（sensitivity filter + 无投影）。"""
    task = {
        "task_id": task_id, "experiment_group": "B0", "hypothesis_id": "H0",
        "load_case": "vertical", "mesh_level": mesh,
        "projection": "none", "controller": "fixed_controller",
        "filter": "sensitivity_filter",
        "params": {"volfrac": volfrac, "rmin": 1.5, "max_iter": max_iter, **kw},
    }
    return task


print("=" * 62)
print("  TopOptPilot Solver 物理验证 + 集成测试")
print("=" * 62)

# ===== T1: 参数规范化 =====
print("\n--- T1: normalize_task 参数规范化 ---")
from solver.params import normalize_task

spec = normalize_task({"load_case": "vertical", "mesh_level": "medium", "params": {}})
test("默认 volfrac=0.40", abs(spec["volfrac"] - 0.40) < 1e-12, f"volfrac={spec['volfrac']}")
test("默认 bc_type=MBB", spec["bc_type"] == "MBB", f"bc={spec['bc_type']}")
test("默认 投影/控制器/滤波",
     spec["projection"] == "none" and spec["controller"] == "fixed_controller"
     and spec["filter"] == "sensitivity_filter",
     f"{spec['projection']}/{spec['controller']}/{spec['filter']}")
test("网格映射 medium=60x30", (spec["nelx"], spec["nely"]) == (60, 30),
     f"{spec['nelx']}x{spec['nely']}")
test("网格映射 coarse=30x15", normalize_task({"mesh_level": "coarse"})["nelx"] == 30)

spec2 = normalize_task(spec)
test("规范化幂等（volfrac/网格不丢）",
     abs(spec2["volfrac"] - spec["volfrac"]) < 1e-12 and spec2["nelx"] == 60)

spec3 = normalize_task({
    "load_case": "mbb", "filter": "PDE_filter", "projection": "Heaviside_projection",
    "controller": "periodic_controller",
})
test("别名归一化（mbb/PDE_filter/Heaviside）",
     spec3["bc_type"] == "MBB" and spec3["filter"] == "sensitivity_filter"
     and spec3["projection"] == "heaviside_projection"
     and spec3["controller"] == "periodic_controller",
     f"bc={spec3['bc_type']} filter={spec3['filter']} proj={spec3['projection']}")

spec4 = normalize_task({"projection": "none", "controller": "joint_feedback_controller"})
test("投影 none 强制 fixed 控制器", spec4["controller"] == "fixed_controller",
     f"controller={spec4['controller']}")

# ===== T2: OC 更新移植 =====
print("\n--- T2: OC 更新（对照 OC_solver.m） ---")
from solver.oc_solver import oc_update

rng = np.random.default_rng(0)
x0 = np.full((30, 15), 0.4)
dc = rng.uniform(-3.0, -0.5, x0.shape)
xnew, info = oc_update(x0, dc, 0.4, {})
test("OC 更新体积守恒", abs(xnew.mean() - 0.4) < 1e-4, f"mean={xnew.mean():.6f}")
test("OC 更新在 [xmin,1] 界内", xnew.min() >= 1e-3 - 1e-9 and xnew.max() <= 1.0 + 1e-9,
     f"[{xnew.min():.4f}, {xnew.max():.4f}]")
test("OC 更新全有限", np.all(np.isfinite(xnew)))
test("OC 双分收敛", info["converged"] is True, f"l2-l1={info.get('l2', 0) - info.get('l1', 0):.2e}")

# ===== T3: 经典路径 vs MATLAB 地面真值 =====
print("\n--- T3: 经典路径（sensitivity filter）对照 MATLAB top99 ---")
from solver.topopt_engine import run_topopt

res = run_topopt(_classic_task("gt", "medium", max_iter=60, volfrac=0.5))
test("状态完成", res["status"] in ("converged", "failed", "timeout"), f"status={res['status']}")
hist = {h["iteration"]: h for h in res["artifacts"]["history"]}
test("history 含 iter1", 1 in hist, f"len={len(hist)}")
for it, gt in [(1, 391.9097), (10, 148.8253), (60, 127.6915)]:
    if it in hist:
        rel = abs(hist[it]["compliance"] - gt) / gt
        test(f"iter{it} C≈{gt} (±2%)", rel < 0.02,
             f"py={hist[it]['compliance']:.3f} gt={gt} rel={rel:.2%}")
    else:
        test(f"iter{it} 存在", False, f"history 缺少迭代 {it}")
test("最终体积≈0.5", abs(res["constraints"]["volume_fraction"] - 0.5) < 0.02,
     f"vf={res['constraints']['volume_fraction']:.4f}")
test("物理密度有限", np.all(np.isfinite(res["artifacts"]["density"])))
test("残差可信", res["solver"]["relative_residual"] < 1e-3,
     f"res={res['solver']['relative_residual']:.2e}")

# 确定性：同参数两次运行柔度一致
res2 = run_topopt(_classic_task("gt2", "medium", max_iter=60, volfrac=0.5))
test("引擎确定性（两次运行一致）",
     abs(res2["objective"]["compliance"] - res["objective"]["compliance"]) < 1e-6,
     f"C1={res['objective']['compliance']:.4f} C2={res2['objective']['compliance']:.4f}")

# ===== T4: Heaviside 投影物理 =====
print("\n--- T4: Heaviside 投影物理（B0 vs B1） ---")
b0 = run_topopt(_classic_task("B0", "medium", max_iter=150, volfrac=0.4))
b1 = run_topopt({
    "task_id": "B1", "experiment_group": "B1", "hypothesis_id": "H3",
    "load_case": "vertical", "mesh_level": "medium",
    "projection": "heaviside_projection", "controller": "periodic_controller",
    "filter": "density_filter",
    "params": {"volfrac": 0.4, "rmin": 1.5, "max_iter": 100, "beta_max": 16},
})
test("B0 无投影灰度显著", b0["quality"]["gray_ratio"] > 0.3,
     f"gray={b0['quality']['gray_ratio']}")
test("B1 投影后灰度大幅下降", b1["quality"]["gray_ratio"] < 0.10,
     f"gray={b1['quality']['gray_ratio']}")
test("B1 灰度 < B0 灰度（投影有效）",
     b1["quality"]["gray_ratio"] < b0["quality"]["gray_ratio"],
     f"{b1['quality']['gray_ratio']} vs {b0['quality']['gray_ratio']}")
test("B1 单连通", b1["quality"]["connected_components"] == 1,
     f"conn={b1['quality']['connected_components']}")
test("B1 柔度优于 B0", b1["objective"]["compliance"] < b0["objective"]["compliance"],
     f"C_B0={b0['objective']['compliance']:.1f} C_B1={b1['objective']['compliance']:.1f}")

# ===== T5: 四种控制器 =====
print("\n--- T5: 四种控制器可运行 ---")
controllers = ["fixed_controller", "periodic_controller",
               "gray_feedback_controller", "joint_feedback_controller"]
for ctrl in controllers:
    is_heav = ctrl != "fixed_controller"
    r = run_topopt({
        "task_id": f"T5_{ctrl}", "experiment_group": ctrl, "hypothesis_id": "H0",
        "load_case": "vertical", "mesh_level": "coarse",
        "projection": "heaviside_projection" if is_heav else "none",
        "controller": ctrl,
        "filter": "density_filter" if is_heav else "sensitivity_filter",
        "params": {"volfrac": 0.4, "rmin": 1.5, "max_iter": 30, "beta_max": 16},
    })
    test(f"{ctrl} 可运行", r["status"] in ("converged", "failed", "timeout"),
         f"status={r['status']}")
    test(f"{ctrl} 柔度正有限",
         np.isfinite(r["objective"]["compliance"]) and r["objective"]["compliance"] > 0,
         f"C={r['objective']['compliance']}")

# ===== T6: 结果契约字段 =====
print("\n--- T6: 结果契约（ExperimentResult 兼容） ---")
r = run_topopt(_classic_task("T6", "coarse", max_iter=20, volfrac=0.4))
for key in ["run_id", "task_id", "hypothesis_id", "experiment_group", "status",
            "objective", "constraints", "quality", "solver", "artifacts"]:
    test(f"顶层字段 {key}", key in r)
test("objective.compliance 有限", np.isfinite(r["objective"]["compliance"]))
for key in ["gray_ratio", "connected_components", "max_displacement_mm"]:
    test(f"quality.{key}", key in r["quality"])
test("gray_ratio ∈ [0,1]", 0 <= r["quality"]["gray_ratio"] <= 1,
     f"gray={r['quality']['gray_ratio']}")
test("solver.backend=python", r["solver"]["backend"] == "python")
test("artifacts.density 形状=(nely,nelx)", r["artifacts"]["density"].shape == (15, 30),
     f"shape={r['artifacts']['density'].shape}")
test("artifacts.history 非空", len(r["artifacts"]["history"]) > 0)
test("history 条目含 compliance/beta/penal",
     all(k in r["artifacts"]["history"][0]
         for k in ["iteration", "compliance", "change", "beta", "penal", "gray_ratio"]),
     f"keys={list(r['artifacts']['history'][0].keys())}")

# ===== T7: ExperimentQueue 端到端四组 =====
print("\n--- T7: ExperimentQueue 四组实验（B0/B1/A1/Ours） ---")
from experiments.experiment_queue import ExperimentQueue
from agent.roles.experiment_agent import ExperimentTask

GROUPS = [
    ("B0", "none", "fixed_controller", "sensitivity_filter", {}),
    ("B1", "heaviside_projection", "periodic_controller", "density_filter", {"beta_max": 16}),
    ("A1", "heaviside_projection", "gray_feedback_controller", "density_filter",
     {"beta_max": 32, "beta_step": 4}),
    ("Ours", "heaviside_projection", "joint_feedback_controller", "density_filter",
     {"beta_max": 24, "rmin": 2.0, "p_end": 4.0, "p_interval": 40}),
]
eq = ExperimentQueue()  # backend="python"：真实求解
t0 = time.time()
for g, proj, ctrl, filt, extra in GROUPS:
    task = ExperimentTask(
        task_id=f"grp_{g}", experiment_group=g, hypothesis_id=f"H_{g}",
        load_case="vertical", mesh_level="medium",
        projection=proj, controller=ctrl, filter=filt,
        params={"volfrac": 0.4, "max_iter": 120, **extra},
        work_package={"volume_fraction": 0.4},
    )
    eq.submit(task)
dt = time.time() - t0
test("四组全部完成", eq.get_status_summary()["by_status"].get("completed", 0) == 4,
     f"{eq.get_status_summary()['by_status']}")
test(f"四组实时求解耗时合理（{dt:.1f}s < 60s）", dt < 60, f"dt={dt:.1f}s")

by_group = {r.experiment_group: r for r in eq.get_all_results()}
test("B0/B1/A1/Ours 均有结果", all(g in by_group for g in ["B0", "B1", "A1", "Ours"]),
     f"got={sorted(by_group)}")

def _c(r):
    return r.objective.get("compliance", float("inf"))

def _g(r):
    return r.quality.get("gray_ratio", 1.0)

def _k(r):
    return r.quality.get("connected_components", 0)

if all(g in by_group for g in ["B0", "B1", "A1", "Ours"]):
    b0r, b1r, a1r, ours = (by_group[g] for g in ["B0", "B1", "A1", "Ours"])
    test("成效1: B1 柔度 < B0", _c(b1r) < _c(b0r), f"C_B0={_c(b0r):.1f} C_B1={_c(b1r):.1f}")
    test("成效2: B1 灰度 < B0", _g(b1r) < _g(b0r), f"g_B0={_g(b0r)} g_B1={_g(b1r)}")
    test("成效3: B1 单连通", _k(b1r) == 1, f"conn_B1={_k(b1r)}")
    test("成效4: Ours 柔度最优（< B0 且 ≤ B1）",
         _c(ours) < _c(b0r) and _c(ours) <= _c(b1r) * 1.05,
         f"C_Ours={_c(ours):.1f} vs C_B0={_c(b0r):.1f} C_B1={_c(b1r):.1f}")
    test("成效5: Ours 灰度低且单连通", _g(ours) < 0.10 and _k(ours) == 1,
         f"g={_g(ours)} conn={_k(ours)}")
    test("成效6: A1 反馈调度保持健康", _g(a1r) < 0.10,
         f"g_A1={_g(a1r)} conn_A1={_k(a1r)}")

# ===== T8: SolverRunner.run_sync 持久化 =====
print("\n--- T8: SolverRunner 持久化 ---")
from experiments.solver_runner import SolverRunner
import tempfile

outdir = tempfile.mkdtemp(prefix="topopt_solver_test_")
sr = SolverRunner(backend="python")
sync = sr.run_sync(_classic_task("sync", "coarse", max_iter=20, volfrac=0.4),
                   run_id="sync_test", output_dir=outdir)
files = os.listdir(outdir)
test("run_sync 生成 3 个 artifact 文件", len(files) >= 3, f"files={files}")
test("artifacts 指向文件路径",
     all(k in sync["artifacts"] for k in ["density", "history", "log"]),
     f"keys={list(sync['artifacts'])}")
try:
    dens = np.load(sync["artifacts"]["density"])
    test("density.npy 可读且形状正确", dens.shape == (15, 30), f"shape={dens.shape}")
except Exception as e:
    test("density.npy 可读", False, str(e))
with open(sync["artifacts"]["history"], encoding="utf-8") as f:
    s_hist = json.load(f)
test("history.json 有迭代记录", len(s_hist) > 0, f"len={len(s_hist)}")
with open(sync["artifacts"]["log"], encoding="utf-8") as f:
    logtxt = f.read()
test("log.txt 含 compliance", "compliance" in logtxt)

print("\n" + "=" * 62)
print("  Solver 模块测试报告")
print("=" * 62)
total = passed + failed
print(f"  通过: {passed}/{total}")
if total > 0:
    print(f"  通过率: {passed/total*100:.1f}%")
if failed > 0:
    print("\n  ⚠️  有失败测试项，请检查上方的 ❌ 标记。")
else:
    print("\n  ✅ 全部通过！")
print("=" * 62)
sys.exit(1 if failed > 0 else 0)
