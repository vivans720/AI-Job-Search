/**
 * Centralized API base URL resolver.
 * Defaults to process.env.NEXT_PUBLIC_API_URL or http://localhost:8000
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

export const getApiUrl = (path: string): string => {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
};

export interface AgentEvent {
  id: string;
  run_id: string;
  event_type: "status_update" | "tool_start" | "tool_complete" | "tool_error" | "milestone";
  tool_name?: string | null;
  action_summary: string;
  payload: Record<string, unknown>;
  duration_ms?: number | null;
  created_at: string;
}

export interface AgentRun {
  id: string;
  user_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  trigger: string;
  summary?: string | null;
  metrics: Record<string, unknown>;
  created_at: string;
  completed_at?: string | null;
  events?: AgentEvent[];
}

export async function fetchAgentRuns(limit = 10, offset = 0): Promise<AgentRun[]> {
  const res = await fetch(getApiUrl(`/v1/agent/runs?limit=${limit}&offset=${offset}`));
  if (!res.ok) throw new Error(`Failed to fetch agent runs: ${res.statusText}`);
  return res.json();
}

export async function fetchAgentRunDetail(runId: string): Promise<AgentRun> {
  const res = await fetch(getApiUrl(`/v1/agent/runs/${runId}`));
  if (!res.ok) throw new Error(`Failed to fetch agent run detail: ${res.statusText}`);
  return res.json();
}

export async function cancelAgentRun(runId: string): Promise<AgentRun> {
  const res = await fetch(getApiUrl(`/v1/agent/runs/${runId}/cancel`), { method: "POST" });
  if (!res.ok) throw new Error(`Failed to cancel agent run: ${res.statusText}`);
  return res.json();
}