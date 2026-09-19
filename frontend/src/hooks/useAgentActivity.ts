"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { AgentEvent, AgentRun, fetchAgentRunDetail, getApiUrl } from "@/lib/api";

export function useAgentActivity(runId: string | null) {
  const [run, setRun] = useState<AgentRun | null>(null);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const loadRunDetail = useCallback(async (id: string) => {
    try {
      const data = await fetchAgentRunDetail(id);
      setRun(data);
      if (data.events) {
        setEvents(data.events);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load agent run";
      setError(msg);
    }
  }, []);

  useEffect(() => {
    if (!runId) {
      setRun(null);
      setEvents([]);
      return;
    }

    loadRunDetail(runId);

    // If run is already completed, no need to connect to live stream
    if (run?.status && ["completed", "failed", "cancelled"].includes(run.status)) {
      return;
    }

    const streamUrl = getApiUrl(`/v1/agent/runs/${runId}/stream`);
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    es.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    es.onerror = () => {
      setIsConnected(false);
    };

    const handleEvent = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        if (data.id) {
          setEvents((prev) => {
            if (prev.some((item) => item.id === data.id)) return prev;
            return [...prev, data];
          });
        }
      } catch (err) {
        console.error("Error parsing agent event SSE:", err);
      }
    };

    const handleStatus = (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        setRun((prev) => (prev ? { ...prev, ...data } : data));
        if (["completed", "failed", "cancelled"].includes(data.status)) {
          setIsConnected(false);
          es.close();
        }
      } catch (err) {
        console.error("Error parsing status SSE:", err);
      }
    };

    es.addEventListener("status_update", handleStatus);
    es.addEventListener("tool_complete", handleEvent);
    es.addEventListener("tool_start", handleEvent);
    es.addEventListener("tool_error", handleEvent);
    es.addEventListener("milestone", handleEvent);
    es.onmessage = handleEvent;

    return () => {
      es.close();
      eventSourceRef.current = null;
      setIsConnected(false);
    };
  }, [runId, loadRunDetail]);

  return { run, events, isConnected, error, refresh: () => runId && loadRunDetail(runId) };
}
