import { describe, expect, it } from "vitest";
import { solverLaneLabel, workspaceLabel } from "./workspace";

describe("TopOptPilot V6.3 workspace contract", () => {
  it("keeps the two user-facing workspaces explicit", () => {
    expect(workspaceLabel("engineering")).toBe("快速实现");
    expect(workspaceLabel("research")).toBe("深度优化");
  });
  it("does not collapse solver lanes into one MATLAB status", () => {
    expect(solverLaneLabel("local-matlab")).toBe("本机 MATLAB");
    expect(solverLaneLabel("matlab-mcp")).toBe("MATLAB MCP");
  });
});
