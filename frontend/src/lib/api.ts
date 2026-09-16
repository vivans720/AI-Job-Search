/**
 * Centralized API base URL resolver.
 * Defaults to process.env.NEXT_PUBLIC_API_URL or http://localhost:8000
 */
export const API_BASE = process.env.NEXT_PUBLIC_API_URL?.replace(/\/+$/, "") || "http://localhost:8000";

export const getApiUrl = (path: string): string => {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${cleanPath}`;
};