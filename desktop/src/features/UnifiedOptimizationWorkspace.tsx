import { useEffect, useMemo, useState } from "react";
import { Bot, Code2, FileCode2, FlaskConical, FolderOpen, GitCompare, LineChart, MessageCircle, Play, SlidersHorizontal } from "lucide-react";
import { api } from "../api";
import type { AgentWorkflowItem, Workspace, WorkspaceContextRef, WorkspaceConversationMessage } from "../generated/api-contract";
import type { Experiment, ProjectEntry, ProjectFile, Research } from "../types";
import type { WorkspaceMode } from "../workspace";
import ResizableWorkspaceLayout from "../components/ResizableWorkspaceLayout";

type Props = {
  mode: WorkspaceMode;
  researches: Research[];
  selectedResearch: Research | null;
  selectedExperiment: Experiment | null;
  onSelectResearch: (id: string) => void | Promise<void>;
  onSelectExperiment: (value: Experiment) => void;
  onCreateResearch: (workspaceId?: string) => void;
  onError: (message: string) => void;
};
type Tab = "code" | "result" | "iteration" | "parameters";
type RightTab = "workflow" | "inspector";

const languageFor = (path = "") => path.endsWith(".m") ? "MATLAB" : path.endsWith(".py") ? "Python" : path.endsWith(".ts") || path.endsWith(".tsx") ? "TypeScript" : "Text";

export default function UnifiedOptimizationWorkspace(props: Props) {
  const { mode, researches, selectedResearch, selectedExperiment, onSelectResearch, onSelectExperiment, onCreateResearch, onError } = props;
  const lane = mode === "engineering" ? "quick" : "deep";
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [contexts, setContexts] = useState<WorkspaceContextRef[]>([]);
  const [projectRoot, setProjectRoot] = useState("");
  const [files, setFiles] = useState<ProjectEntry[]>([]);
  const [selectedFile, setSelectedFile] = useState<ProjectFile | null>(null);
  const [tab, setTab] = useState<Tab>("code");
  const [rightTab, setRightTab] = useState<RightTab>("workflow");
  const [workflow, setWorkflow] = useState<AgentWorkflowItem[]>([]);
  const [messages, setMessages] = useState<WorkspaceConversationMessage[]>([]);
  const [message, setMessage] = useState("");
  const [switcherOpen, setSwitcherOpen] = useState(false);

  const activeContext = useMemo(() => {
    if (mode === "research" && selectedExperiment) return { type: "experiment", id: selectedExperiment.id };
    if (mode === "research" && selectedResearch) return { type: "research", id: selectedResearch.id };
    return { type: "workspace_draft", id: workspace?.id || "" };
  }, [mode, selectedExperiment, selectedResearch, workspace?.id]);

  const refreshWorkspace = async () => {
    const list = await api.listWorkspaces();
    setWorkspaces(list);
    const next = workspace ? list.find(item => item.id === workspace.id) || null : list[0] || null;
    setWorkspace(next);
  };
  useEffect(() => { void refreshWorkspace().catch(reason => onError(String(reason))); }, []);
  useEffect(() => {
    if (!workspace) { setContexts([]); setWorkflow([]); setMessages([]); return; }
    let cancelled = false;
    void Promise.all([
      api.workspaceContexts(workspace.id, lane),
      api.workspaceWorkflow(workspace.id),
      api.workspaceConversation(workspace.id),
    ]).then(([nextContexts, nextWorkflow, nextMessages]) => {
      if (!cancelled) { setContexts(nextContexts); setWorkflow(nextWorkflow); setMessages(nextMessages); }
    }).catch(reason => !cancelled && onError(String(reason)));
    return () => { cancelled = true; };
  }, [workspace?.id, lane, researches.length, selectedResearch?.id, selectedExperiment?.id]);

  async function openProject() {
    try {
      const root = await api.projectPickFolder();
      if (!root) return;
      const project = await api.projectOpen(root);
      setProjectRoot(project.root); setFiles(await api.projectList(project.root));
      const created = await api.createWorkspace({ projectId: project.projectId, name: project.projectId || "项目工作台" });
      setWorkspace(created); setWorkspaces(items => [created, ...items.filter(item => item.id !== created.id)]);
    } catch (reason) { onError(String(reason)); }
  }
  async function chooseFile(entry: ProjectEntry) {
    if (!projectRoot || entry.kind !== "file") return;
    try { setSelectedFile(await api.projectRead(projectRoot, entry.relative_path)); setTab("code"); }
    catch (reason) { onError(String(reason)); }
  }
  async function sendMessage() {
    if (!workspace || !message.trim()) return;
    const text = message.trim(); setMessage("");
    try {
      const stored = await api.workspaceMessage(workspace.id, { lane, role: "user", content: text, researchId: selectedResearch?.id });
      setMessages(items => [...items, stored]);
      if (lane === "quick") await api.quickAgentTask(workspace.id, text);
      else if (selectedResearch) await api.command(selectedResearch.id, text, selectedExperiment?.id);
      setWorkflow(await api.workspaceWorkflow(workspace.id));
    } catch (reason) { onError(String(reason)); }
  }
  const selectContext = (context: WorkspaceContextRef) => {
    if (context.type === "research" && context.researchId) void onSelectResearch(context.researchId);
    if (context.type === "experiment" && context.researchId && context.experimentId) {
      const research = researches.find(item => item.id === context.researchId);
      const experiment = research?.experiments.find(item => item.id === context.experimentId);
      if (experiment) { void onSelectResearch(context.researchId); onSelectExperiment(experiment); }
    }
  };

  const left = <div className="unified-left">
    <div className="sidebar-section-title"><FolderOpen size={14}/> 工作区文件 <button onClick={openProject} title="打开项目">+</button></div>
    {!projectRoot ? <button className="project-open-button" onClick={openProject}>打开项目目录</button> : null}
    <div className="unified-file-list">{files.filter(item => item.kind === "file").map(item =>
      <button key={item.relative_path} className={selectedFile?.relative_path === item.relative_path ? "active" : ""} onClick={() => void chooseFile(item)}><FileCode2 size={14}/>{item.relative_path}</button>)}</div>
    <div className="sidebar-section-title"><FlaskConical size={14}/>{lane === "quick" ? "快速运行" : "Research / Experiments"}</div>
    {lane === "quick" ? contexts.filter(item => item.type !== "workspace_draft").map(item => <button key={item.id} onClick={() => selectContext(item)}>{item.title}<small>{item.status}</small></button>)
      : contexts.filter(item => item.type !== "workspace_draft").map(item => <button key={item.id} className={activeContext.id === item.id ? "active" : ""} onClick={() => selectContext(item)}>{item.title}<small>{item.status}</small></button>)}
    {lane === "deep" ? <button className="project-open-button" onClick={() => onCreateResearch(workspace?.id)}>新建 Research</button> : null}
  </div>;

  const center = <div className="unified-center">
    <div className="unified-tabs">
      <button className={tab === "code" ? "active" : ""} onClick={() => setTab("code")}><Code2 size={14}/>代码</button>
      <button className={tab === "result" ? "active" : ""} onClick={() => setTab("result")}><Play size={14}/>结果</button>
      <button className={tab === "iteration" ? "active" : ""} onClick={() => setTab("iteration")}><LineChart size={14}/>迭代可视化</button>
      <button className={tab === "parameters" ? "active" : ""} onClick={() => setTab("parameters")}><GitCompare size={14}/>参数与对比</button>
    </div>
    <div className="unified-context-summary">上下文：{activeContext.type} · {activeContext.id || "未选择"} {mode === "research" && selectedExperiment ? " · SourceSnapshot → Experiment Overlay" : ""}</div>
    {tab === "code" ? <section className="unified-code"><header>{selectedFile?.relative_path || "选择项目文件"} <small>{languageFor(selectedFile?.relative_path)}</small></header><pre>{selectedFile?.content || "代码仅在用户打开的 Workspace 内显示。Deep Experiment 会在此处叠加只读 Overlay；项目主文件不会被 Agent 自动修改。"}</pre></section> : null}
    {tab === "result" ? <section className="unified-empty"><b>{lane === "quick" ? "Quick Run 执行结果" : "Deep Experiment 确定性评价"}</b><p>{lane === "quick" ? "completed 仅表示执行完成；可行性和优化成功由独立评价轴显示。" : (selectedExperiment?.result ? JSON.stringify(selectedExperiment.result, null, 2) : "选择一个 Experiment 查看真实结果。")}</p></section> : null}
    {tab === "iteration" ? <section className="unified-empty"><b>迭代可视化</b><p>选择 Run 或 Experiment 后加载该上下文的真实迭代证据；不以占位数据替代求解结果。</p></section> : null}
    {tab === "parameters" ? <section className="unified-empty"><b>参数与对比</b><p>{lane === "quick" ? "仅比较真实 Quick Runs。" : "可比较同一 Research 的 Experiment，并可引用带来源的 Quick 晋升基线。"}</p></section> : null}
  </div>;

  const right = <div className="unified-right">
    <div className="unified-tabs"><button className={rightTab === "workflow" ? "active" : ""} onClick={() => setRightTab("workflow")}><Bot size={14}/>Agent 工作流</button><button className={rightTab === "inspector" ? "active" : ""} onClick={() => setRightTab("inspector")}><SlidersHorizontal size={14}/>检查器</button></div>
    {rightTab === "workflow" ? <><div className="workflow-items">{workflow.map(item => <article key={item.workflowItemId}><b>{item.title}</b><small>{item.phase} · {item.status}</small><p>{item.summary}</p>{item.requiresHumanAction ? <em>需要人工操作</em> : null}</article>)}</div><div className="workflow-messages">{messages.slice(-8).map(item => <p key={item.id} data-role={item.role}>{item.content}</p>)}</div><div className="workflow-input"><input value={message} onChange={event => setMessage(event.target.value)} placeholder={lane === "quick" ? "让 Quick Agent 实现或修正代码…" : "与 Deep Agent 沟通研究调整…"} onKeyDown={event => event.key === "Enter" && void sendMessage()}/><button onClick={() => void sendMessage()}><MessageCircle size={15}/></button></div></> : <div className="unified-empty"><b>检查器</b><p>显示编译、预算、可行性和 Review 状态。Quick 与 Deep 状态分轴呈现。</p></div>}
  </div>;

  return <><ResizableWorkspaceLayout mode={mode} left={left} center={center} right={right} bottom={<div className="unified-bottom">Workspace 与后台 Run / Experiment / Agent 任务在模式切换后继续运行。</div>}/>
    {switcherOpen ? <div className="workspace-switcher-backdrop" onClick={() => setSwitcherOpen(false)}><section className="workspace-switcher" onClick={event => event.stopPropagation()}><header>切换 Workspace</header>{workspaces.map(item => <button key={item.id} onClick={() => { setWorkspace(item); setSwitcherOpen(false); }}>{item.name}<small>{item.projectId}</small></button>)}<button onClick={openProject}>打开或授权项目</button></section></div> : null}
    <button className="workspace-switcher-trigger" onClick={() => setSwitcherOpen(true)}>切换 Workspace</button></>;
}
