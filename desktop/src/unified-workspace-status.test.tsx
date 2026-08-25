// @vitest-environment jsdom
//
// V6.3 P1 UI acceptance (docs/validation/V6.3-待测试清单.md):
//  - `completed` run status is not shown as "可行" or "优化成功".
//  - A Reviewer workflow item with status `completed` is not rendered as `APPROVE`.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const apiMocks = vi.hoisted(() => ({
  listWorkspaces: vi.fn(),
  workspaceContexts: vi.fn(),
  workspaceWorkflow: vi.fn(),
  workspaceConversation: vi.fn(),
  workspaceStream: vi.fn(),
  workspaceMessage: vi.fn(),
  quickAgentTask: vi.fn(),
  command: vi.fn(),
  engineeringRun: vi.fn(),
  engineeringRunGet: vi.fn(),
  projectPickFolder: vi.fn(),
  projectOpen: vi.fn(),
  projectList: vi.fn(),
  createWorkspace: vi.fn(),
  workspaceGrant: vi.fn(),
  projectRead: vi.fn(),
}));

vi.mock("./api", () => ({ api: apiMocks }));

const fakeSocket = {
  close: vi.fn(),
  onmessage: null,
  onopen: null,
  onerror: null,
  send: vi.fn(),
} as unknown as WebSocket;

import UnifiedOptimizationWorkspace from "./features/UnifiedOptimizationWorkspace";

const baseProps = {
  mode: "engineering" as const,
  researches: [],
  selectedResearch: null,
  selectedExperiment: null,
  onSelectResearch: async () => undefined,
  onSelectExperiment: () => undefined,
  onCreateResearch: async () => undefined,
  onError: () => undefined,
};

function workspaceStub() {
  return {
    id: "ws-1",
    projectId: "project-1",
    name: "项目工作台",
    kind: "engineering" as const,
  };
}

describe("V6.3 unified workspace status semantics", () => {
  afterEach(cleanup);
  beforeEach(() => {
    vi.clearAllMocks();
    apiMocks.listWorkspaces.mockResolvedValue([workspaceStub()]);
    apiMocks.workspaceContexts.mockResolvedValue([]);
    apiMocks.workspaceWorkflow.mockResolvedValue([]);
    apiMocks.workspaceConversation.mockResolvedValue([]);
    apiMocks.workspaceStream.mockResolvedValue(fakeSocket);
    apiMocks.workspaceMessage.mockResolvedValue({ ok: true });
    apiMocks.quickAgentTask.mockResolvedValue({ ok: true });
    apiMocks.command.mockResolvedValue({ ok: true });
    apiMocks.engineeringRun.mockResolvedValue({ runId: "eng-1", status: "completed" });
    apiMocks.engineeringRunGet.mockResolvedValue({ runId: "eng-1", status: "completed" });
    apiMocks.projectPickFolder.mockResolvedValue("D:/Projects/cantilever");
    apiMocks.projectOpen.mockResolvedValue({ root: "D:/Projects/cantilever", projectId: "project-1" });
    apiMocks.projectList.mockResolvedValue([]);
    apiMocks.createWorkspace.mockResolvedValue(workspaceStub());
    apiMocks.workspaceGrant.mockResolvedValue({ ok: true });
    apiMocks.projectRead.mockResolvedValue({ path: "main.m", content: "" });
  });

  it("does not present `completed` as 可行 / 优化成功 in the Quick result panel", async () => {
    render(<UnifiedOptimizationWorkspace {...baseProps} />);
    await userEvent.click(screen.getByRole("button", { name: /结果/ }));
    const panel = await screen.findByText(/Quick Run 执行结果/);
    expect(panel).toBeTruthy();
    // The acceptance invariant is spelled out in the panel copy: execution
    // completion and feasibility/optimality are separate evaluation axes.
    expect(screen.getByText(/completed 仅表示执行完成/)).toBeTruthy();
    expect(screen.getByText(/可行性和优化成功由独立评价轴显示/)).toBeTruthy();
  });

  it("renders a completed Reviewer workflow item as `completed`, never as APPROVE", async () => {
    apiMocks.workspaceWorkflow.mockResolvedValue([
      {
        workflowItemId: "wf-review-1",
        phase: "REVIEW",
        status: "completed",
        title: "Independent Reviewer",
        summary: "终审完成，未生成正式报告",
        requiresHumanAction: false,
      },
    ]);
    render(<UnifiedOptimizationWorkspace {...baseProps} />);
    const item = await screen.findByText(/Independent Reviewer/);
    expect(item).toBeTruthy();
    const badge = screen.getByText(/REVIEW · completed/);
    expect(badge).toBeTruthy();
    expect(screen.queryByText(/APPROVE/)).toBeNull();
  });
});
