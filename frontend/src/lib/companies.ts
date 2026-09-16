import { API_BASE } from "@/lib/api";

export async function fetchCompanySuggestions(q: string, signal?: AbortSignal): Promise<string[]> {
  if (!q.trim()) return [];
  try {
    const res = await fetch(`${API_BASE}/api/v1/companies/suggest?q=${encodeURIComponent(q.trim())}`, {
      signal,
      headers: { Accept: "application/json" },
      cache: "no-store",
    });
    if (!res.ok) return [];
    const data = (await res.json()) as string[];
    return Array.isArray(data) ? data : [];
  } catch {
    return [];
  }
}
