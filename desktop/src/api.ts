import { invoke } from "@tauri-apps/api/core";
import type { AppSettings, BackendInfo, EngineeringRun, GeometryPreview, KnowledgeEntry, Locale, MatlabHealth, Research, SettingsDiagnostics, SolverCapabilities, SubagentTask, SystemHealth } from "./types";
import type { EngineeringChatRequest, EngineeringChatResponse, EngineeringComparisonSchemeCreate } from "./generated/api-contract";

let backend: BackendInfo | null = null;

export async function initializeBackend(): Promise<BackendInfo> {
  if (backend) return backend;
  if (import.meta.env.VITE_API_URL) {
    backend = { port: Number(new URL(import.meta.env.VITE_API_URL).port), token: import.meta.env.VITE_API_TOKEN || "" };
    return backend;
  }
  // A cold PyInstaller one-file extraction can take >20 s while Defender scans it.
  for (let attempt = 0; attempt < 240; attempt++) {
    try {
      const value = await invoke<BackendInfo | null>("backend_info");
      if (value?.port) { backend = value; return value; }
    } catch { /* sidecar is still starting */ }
    await new Promise(resolve => setTimeout(resolve, 250));
  }
  throw new Error("Desktop backend did not become ready");
}

function base(): string { if (!backend) throw new Error("Backend not initialized"); return `http://127.0.0.1:${backend.port}`; }
function errorMessage(payload: unknown, fallback: string): string {
  if (payload && typeof payload === "object") {
    const envelope = payload as { message?: unknown; code?: unknown };
    if (typeof envelope.message === "string") return envelope.message;
    if (typeof envelope.code === "string") return envelope.code;
  }
  const detail = (payload as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const value = detail as { message?: unknown; code?: unknown };
    if (typeof value.message === "string") return value.message;
    if (typeof value.code === "string") return value.code;
  }
  return fallback;
}
async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  await initializeBackend();
  let lastError: unknown;
  // The handshake can precede Uvicorn's accept loop by a fraction of a second,
  // and Defender may briefly hold the extracted executable on a cold start.
  for (let attempt = 0; attempt < 20; attempt++) {
    try {
      const response = await fetch(base() + path, { ...init, headers: { "Content-Type": "application/json",
        "X-TopOptPilot-Token": backend!.token, ...(init.headers || {}) } });
      if (!response.ok) throw new Error(errorMessage(await response.json().catch(() => ({})), response.statusText));
      return response.json();
    } catch (reason) {
      lastError = reason;
      if (reason instanceof Error && !/Failed to fetch|NetworkError|Load failed/i.test(reason.message)) throw reason;
      await new Promise(resolve => setTimeout(resolve, Math.min(1000, 150 + attempt * 75)));
    }
  }
  throw lastError instanceof Error ? lastError : new Error("Desktop backend request failed");
}

async function download(path:string,filename:string):Promise<void>{
  await initializeBackend();
  const response=await fetch(base()+path,{headers:{"X-TopOptPilot-Token":backend!.token}});
  if(!response.ok)throw new Error(errorMessage(await response.json().catch(()=>({})),response.statusText));
  const url=URL.createObjectURL(await response.blob()),anchor=document.createElement("a");
  anchor.href=url;anchor.download=filename;document.body.appendChild(anchor);anchor.click();anchor.remove();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}

export const api = {
  projectPickFolder: () => invoke<string | null>("project_pick_folder"),
  projectOpen: (root: string) => invoke<import("./types").ProjectOpen>("project_open", { root }),
  projectList: (root: string) => invoke<import("./types").ProjectEntry[]>("project_list", { root }),
  projectRead: (root: string, relativePath: string) => invoke<import("./types").ProjectFile>("project_read", { root, relativePath }),
  projectSave: (root: string, relativePath: string, content: string, expectedSha256?: string) => invoke<import("./types").ProjectFile>("project_save", { root, relativePath, content, expectedSha256 }),
  projectCreate: (root: string, relativePath: string, content = "") => invoke<import("./types").ProjectFile>("project_create", { root, relativePath, content }),
  projectRename: (root: string, from: string, to: string) => invoke<void>("project_rename", { root, from, to }),
  projectSearch: (root: string, query: string) => invoke<import("./types").ProjectEntry[]>("project_search", { root, query }),
  patchPreview: (root: string, proposal: import("./types").PatchProposal) => invoke<import("./types").PatchPreviewResult>("patch_preview", { root, proposal }),
  patchApply: (root: string, proposal: import("./types").PatchProposal, approvalToken: string) => invoke<import("./types").ProjectFile[]>("patch_apply", { root, proposal, approvalToken }),
  engineeringPatch: (data: object) => request<import("./types").PatchProposal>("/api/engineering/assistant/patch", { method: "POST", body: JSON.stringify(data) }),
  engineeringChat: (data: EngineeringChatRequest) => request<EngineeringChatResponse>("/api/engineering/assistant/chat", { method: "POST", body: JSON.stringify(data) }),
  engineeringGenerate: (instruction: string) => request<{generatedEntrypoint:string;generatedFiles:Record<string,string>}>("/api/engineering/assistant/generate", { method: "POST", body: JSON.stringify({ instruction }) }),
  health: () => request<SystemHealth>("/api/health"),
  listResearch: () => request<Research[]>("/api/research"),
  getResearch: (id: string) => request<Research>(`/api/research/${id}`),
  researchArtifacts: (id: string) => request<{researchId:string; experiments:Array<{experimentId:string; status:string; dimension:number; solverProfile:Record<string,unknown>; legacyFidelity?:string; backend:string; provenance:Record<string,string>; files:Array<{relativePath:string; sha256:string; mediaType:string; sizeBytes:number}>; metrics:Record<string,number|null>}>}>(`/api/research/${id}/artifacts`),
  researchPareto: (id: string) => request<Array<Record<string,unknown>>>(`/api/research/${id}/pareto`),
  researchCompare: (id: string, a: string, b: string) => request<Record<string,unknown>>(`/api/research/${id}/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`),
  researchFromEngineeringRun: (runId: string, data: object) => request<{researchId:string; snapshot:Record<string,unknown>; research:Research}>(`/api/research/from-engineering-run/${encodeURIComponent(runId)}`, { method: "POST", body: JSON.stringify(data) }),
  createResearch: (data: object) => request<Research>("/api/research", { method: "POST", body: JSON.stringify(data) }),
  previewGuide: (text:string,locale:Locale) => request<Record<string,any>>("/api/guide", {method:"POST",body:JSON.stringify({text,locale})}),
  guide: (id:string,text:string) => request<Record<string,any>>(`/api/research/${id}/guide`, {method:"POST",body:JSON.stringify({text})}),
  agentTasks: (id:string) => request<SubagentTask[]>(`/api/research/${id}/agent-tasks`),
  knowledgeSearch: (query:string,locale:Locale,category?:string) => request<{items:KnowledgeEntry[];categories:Array<{category:string;count:number}>}>(`/api/knowledge/search?q=${encodeURIComponent(query)}&locale=${locale}${category?`&category=${encodeURIComponent(category)}`:""}`),
  knowledgeGet: (id:string,locale:Locale) => request<KnowledgeEntry>(`/api/knowledge/${encodeURIComponent(id)}?locale=${locale}`),
  solverCapabilities: () => request<SolverCapabilities>("/api/solvers/capabilities"),
  previewGeometry: (data:object,signal?:AbortSignal) => request<GeometryPreview>("/api/solvers/geometry-preview", {method:"POST",body:JSON.stringify(data),signal}),
  autonomous: (id: string) => request<Research>(`/api/research/${id}/autonomous`, { method: "POST" }),
  command: (id: string, text: string, selected_experiment?: string) => request<{ok:boolean;message:string;action:string;data:Record<string,unknown>}>(`/api/research/${id}/commands`, { method: "POST", body: JSON.stringify({ text, selected_experiment }) }),
  approve: (id: string) => request(`/api/decision/${id}/approve`, { method: "POST" }),
  reject: (id: string) => request(`/api/decision/${id}/reject`, { method: "POST" }),
  editDecision: (id: string, parameters: object) => request(`/api/decision/${id}/edit`, { method: "POST", body: JSON.stringify({ parameters }) }),
  why: (id: string) => request<{reason:string}>(`/api/decision/${id}/why`),
  setLocale: (id: string, locale: Locale) => request<Research>(`/api/research/${id}/locale`, { method: "PATCH", body: JSON.stringify({ locale }) }),
  matlabHealth: () => request<MatlabHealth>("/api/matlab/health"),
  restartMatlab: () => request<MatlabHealth>("/api/matlab/restart", { method: "POST" }),
  settings: () => request<AppSettings>("/api/settings"),
  saveSettings: (settings: object) => request<AppSettings>("/api/settings", { method: "PATCH", body: JSON.stringify({ settings }) }),
  setAgentKey: (apiKey: string) => request<{configured:boolean;source:string}>("/api/settings/agent-key", { method: "POST", body: JSON.stringify({ api_key: apiKey }) }),
  deleteAgentKey: () => request<{deleted:boolean;source:string}>("/api/settings/agent-key", { method: "DELETE" }),
  testAgent: () => request<{ok:boolean;status:string;model:string;error?:string}>("/api/settings/test-agent", { method: "POST" }),
  restartPi: () => request("/api/settings/restart-pi", { method: "POST" }),
  diagnostics: () => request<SettingsDiagnostics>("/api/settings/diagnostics"),
  engineeringHealth: () => request<{status:string; service:string; version:string; capabilities:{localMatlab:string; compiledRuntime:string}; python:{mode:"source"|"packaged";version:string;bundled:boolean}}>("/api/engineering/health"),
  engineeringInstallations: () => request<{preference:string; installations:Array<{executable?:string; release?:string; version?:string; source?:string; probeState?:string; diagnostic?:string|null}>}>("/api/engineering/matlab/installations"),
  engineeringRuntimeInstallations: () => request<{usable:boolean; runReady:boolean; installations:Array<{release?:string; version?:string; path?:string; source?:string; usable:boolean; reason?:string; runReady:boolean; runReason?:string; profileId?:string|null; solverExecutable?:string|null}>}>("/api/engineering/runtime/installations"),
  engineeringProbe: (executable: string, release = "") => request<{usable:boolean; version?:string; diagnostic:string; error?:Record<string, unknown>}>("/api/engineering/matlab/probe", { method: "POST", body: JSON.stringify({ executable, release }) }),
  engineeringPreference: (preference: "local-matlab" | "compiled-runtime") => request<{preference:string}>("/api/engineering/matlab/preference", { method: "POST", body: JSON.stringify({ preference }) }),
  engineeringRuntimeProbe: (root: string, solverExecutable: string) => request<{state:string; root:string; dllPath?:string; solverExecutable:string; profileId:string; usable:boolean; diagnostic:string}>("/api/engineering/runtime/probe", { method: "POST", body: JSON.stringify({ root, solverExecutable }) }),
  engineeringBundledRuntime: () => request<{state:string; root?:string; dllPath?:string; solverExecutable?:string; profileId:string|null; usable:boolean; diagnostic:string}>("/api/engineering/runtime/bundled"),
  engineeringRun: (data: object) => request<EngineeringRun>("/api/engineering/runs", { method: "POST", body: JSON.stringify(data) }),
  engineeringRunGet: (id: string) => request<EngineeringRun>(`/api/engineering/runs/${id}`),
  engineeringCancel: (id: string) => request<EngineeringRun>(`/api/engineering/runs/${id}/cancel`, { method: "POST" }),
  engineeringEvents: (id: string) => request<{runId:string; events:Array<Record<string,unknown>>}>(`/api/engineering/runs/${id}/events`),
  engineeringReport: (id: string) => request<{relativePath:string; sha256:string; mediaType:string; sizeBytes:number}>(`/api/engineering/runs/${id}/report`, { method: "POST" }),
  engineeringComparisonSchemes: () => request<import("./types").EngineeringComparisonScheme[]>("/api/engineering/comparison-schemes"),
  engineeringComparisonScheme: (id: string) => request<import("./types").EngineeringComparisonScheme>(`/api/engineering/comparison-schemes/${encodeURIComponent(id)}`),
  engineeringComparisonSchemeCreate: (data: EngineeringComparisonSchemeCreate) => request<import("./types").EngineeringComparisonScheme>("/api/engineering/comparison-schemes", { method: "POST", body: JSON.stringify(data) }),
  engineeringComparisonSchemeDelete: (id: string) => request<{deleted:boolean; id:string}>(`/api/engineering/comparison-schemes/${encodeURIComponent(id)}`, { method: "DELETE" }),
  terminalStart: (data: object) => request<{sessionId:string; status:string}>("/api/engineering/terminal/start", { method: "POST", body: JSON.stringify(data) }),
  terminalCommand: (sessionId: string, command: string) => request<{queued:boolean; id:number; command:string}>(`/api/engineering/terminal/command?session_id=${encodeURIComponent(sessionId)}`, { method: "POST", body: JSON.stringify({ command }) }),
  terminalPoll: (sessionId: string) => request<{sessionId:string; status:string; results:Array<Record<string,unknown>>}>(`/api/engineering/terminal/${encodeURIComponent(sessionId)}`),
  terminalStop: (sessionId: string) => request<{sessionId:string; status:string}>(`/api/engineering/terminal/stop?session_id=${encodeURIComponent(sessionId)}`, { method: "POST" }),
  webviewCreate: (url: string) => invoke<string>("webview_create", { url }),
  webviewNavigate: (url: string) => invoke<void>("webview_navigate", { url }),
  webviewClose: () => invoke<void>("webview_close"),
  engineeringStream: async (id: string, onEvent: (event: Record<string, unknown>) => void): Promise<WebSocket> => {
    if (!backend) throw new Error("Backend not initialized");
    const value = await request<{ticket:string}>(`/api/engineering/runs/${id}/stream-ticket`, {method:"POST"});
    const socket = new WebSocket(`ws://127.0.0.1:${backend.port}/api/engineering/runs/${id}/stream?ticket=${encodeURIComponent(value.ticket)}`);
    socket.onmessage = message => { try { onEvent(JSON.parse(message.data)); } catch { /* ignore malformed event */ } };
    return socket;
  },
  clearCache: () => request<{message:string}>("/api/settings/clear-cache", { method: "POST", body: JSON.stringify({confirm:true}) }),
  downloadReport:(id:string,format:"markdown"|"pdf")=>download(format==="pdf"?`/api/report/${id}/pdf`:`/api/report/${id}`,`${id}_report.${format==="pdf"?"pdf":"md"}`),
  async stream(id: string): Promise<WebSocket> {
    if (!backend) throw new Error("Backend not initialized");
    const value = await request<{ticket:string}>(`/api/research/${id}/stream-ticket`, {method:"POST"});
    return new WebSocket(`ws://127.0.0.1:${backend.port}/api/research/${id}/stream?ticket=${encodeURIComponent(value.ticket)}`);
  }
};

// Functional ownership exports. `api` remains the one-release compatibility
// aggregate while workspaces migrate to these narrower surfaces.
export const systemApi = {
  health: api.health, settings: api.settings, saveSettings: api.saveSettings,
  setAgentKey: api.setAgentKey, deleteAgentKey: api.deleteAgentKey,
  testAgent: api.testAgent, restartPi: api.restartPi,
  matlabHealth: api.matlabHealth, restartMatlab: api.restartMatlab,
  diagnostics: api.diagnostics, clearCache: api.clearCache,
};

export const projectApi = {
  pickFolder: api.projectPickFolder, open: api.projectOpen, list: api.projectList,
  read: api.projectRead, save: api.projectSave, create: api.projectCreate,
  rename: api.projectRename, search: api.projectSearch,
  patchPreview: api.patchPreview, patchApply: api.patchApply,
  webviewCreate: api.webviewCreate, webviewNavigate: api.webviewNavigate,
  webviewClose: api.webviewClose,
};

export const quickApi = {
  health: api.engineeringHealth, installations: api.engineeringInstallations,
  runtimeInstallations: api.engineeringRuntimeInstallations,
  probe: api.engineeringProbe, preference: api.engineeringPreference,
  runtimeProbe: api.engineeringRuntimeProbe, bundledRuntime: api.engineeringBundledRuntime,
  run: api.engineeringRun, getRun: api.engineeringRunGet, cancel: api.engineeringCancel,
  events: api.engineeringEvents, report: api.engineeringReport, stream: api.engineeringStream,
  patch: api.engineeringPatch, generate: api.engineeringGenerate, chat: api.engineeringChat,
  comparisonSchemes: api.engineeringComparisonSchemes,
  comparisonScheme: api.engineeringComparisonScheme,
  createComparisonScheme: api.engineeringComparisonSchemeCreate,
  deleteComparisonScheme: api.engineeringComparisonSchemeDelete,
  terminalStart: api.terminalStart, terminalCommand: api.terminalCommand,
  terminalPoll: api.terminalPoll, terminalStop: api.terminalStop,
};

export const deepApi = {
  list: api.listResearch, get: api.getResearch, create: api.createResearch,
  promote: api.researchFromEngineeringRun, artifacts: api.researchArtifacts,
  compare: api.researchCompare, pareto: api.researchPareto,
  autonomous: api.autonomous, command: api.command, guide: api.guide,
  approve: api.approve, reject: api.reject, editDecision: api.editDecision,
  why: api.why, agentTasks: api.agentTasks, setLocale: api.setLocale,
  stream: api.stream, downloadReport: api.downloadReport,
};
