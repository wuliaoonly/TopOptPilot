import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";
import { Type } from "typebox";
import { TOOL_CONTRACTS, TOOL_NAMES } from "../generated/topopt-tools";

async function invoke(tool: string, args: unknown, signal: AbortSignal) {
  const baseUrl = process.env.TOPPILOT_TOOL_URL;
  const researchId = process.env.TOPPILOT_RESEARCH_ID;
  const token = process.env.TOPPILOT_TOOL_TOKEN;
  const role = process.env.TOPPILOT_AGENT_ROLE || "RESEARCH_LEAD";
  if (!baseUrl || !researchId || !token) throw new Error("TopOptPilot tool gateway is not configured");
  const response = await fetch(`${baseUrl}/tool`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-topopt-token": token,
      "x-topopt-agent-role": role },
    body: JSON.stringify({ research_id: researchId, tool, arguments: args }),
    signal,
  });
  const data = await response.json();
  if (!response.ok || !data.ok) throw new Error(data.error || `Tool gateway returned ${response.status}`);
  return data.result;
}

function register(pi: ExtensionAPI, name: string, description: string, parameters: any) {
  pi.registerTool({
    name,
    label: name,
    description,
    parameters,
    async execute(_toolCallId, params, signal) {
      const result = await invoke(name, params, signal);
      return { content: [{ type: "text", text: JSON.stringify(result) }], details: result };
    },
  });
}

export default function (pi: ExtensionAPI) {
  pi.on("tool_call", async (event) => {
    if (!TOOL_NAMES.has(event.toolName)) {
      return { block: true, reason: `Tool ${event.toolName} is outside the research sandbox` };
    }
  });

  for (const [name, contract] of Object.entries(TOOL_CONTRACTS)) {
    register(pi, name, contract.description, Type.Unsafe(contract.parameters));
  }
}
