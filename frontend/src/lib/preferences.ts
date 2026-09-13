/**
 * Shared preferences definitions, validation, and dual-layer persistence
 * (synchronous localStorage cache + asynchronous FastAPI backend sync).
 */

export type FreshnessOption = 1 | 4 | 8 | 12 | 16 | 24;
export type ExperienceOption = "ALL" | "FRESHER" | "0_1" | "1_2" | "2_3" | "3_PLUS";
export type RoleTypeOption = "ALL" | "JOBS" | "INTERNSHIPS";
export type SourceBoardOption = "LINKEDIN" | "NAUKRI" | "INTERNSHALA" | "INDEED";

export interface UserPreferences {
  freshness_hours: FreshnessOption;
  experience_level: ExperienceOption;
  match_threshold: number; // 0 - 100
  preferred_locations: string[];
  role_type: RoleTypeOption;
  source_boards: SourceBoardOption[];
  excluded_companies: string[];
  priority_companies?: string[];
  experience_max_years?: number;
}

export const PREFERENCES_STORAGE_KEY = "job_search_ai_preferences_v1";

export const FRESHNESS_OPTIONS: FreshnessOption[] = [1, 4, 8, 12, 16, 24];

export const EXPERIENCE_OPTIONS: { value: ExperienceOption; label: string; desc: string }[] = [
  { value: "ALL", label: "All Experience Levels", desc: "No experience tier filtering" },
  { value: "FRESHER", label: "Fresher / Entry Level", desc: "0 years or internship graduates" },
  { value: "0_1", label: "0 - 1 Years", desc: "Early career & associate roles" },
  { value: "1_2", label: "1 - 2 Years", desc: "Junior software developers" },
  { value: "2_3", label: "2 - 3 Years", desc: "Mid-junior developers" },
  { value: "3_PLUS", label: "3+ Years", desc: "Mid to senior engineers" },
];

export const ROLE_TYPE_OPTIONS: { value: RoleTypeOption; label: string }[] = [
  { value: "ALL", label: "All Role Types" },
  { value: "JOBS", label: "Full-Time Jobs" },
  { value: "INTERNSHIPS", label: "Internships" },
];

export const SOURCE_BOARD_OPTIONS: { value: SourceBoardOption; label: string }[] = [
  { value: "LINKEDIN", label: "LinkedIn" },
  { value: "NAUKRI", label: "Naukri" },
  { value: "INTERNSHALA", label: "Internshala" },
  { value: "INDEED", label: "Indeed" },
];

export const SUGGESTED_LOCATIONS: string[] = [
  "Bengaluru",
  "Pune",
  "Hyderabad",
  "Delhi NCR",
  "Mumbai",
  "Remote",
];

export const DEFAULT_PREFERENCES: UserPreferences = {
  freshness_hours: 24,
  experience_level: "ALL",
  match_threshold: 60,
  preferred_locations: ["Bengaluru", "Remote"],
  role_type: "ALL",
  source_boards: ["LINKEDIN", "NAUKRI", "INTERNSHALA"],
  excluded_companies: [],
  priority_companies: [],
  experience_max_years: 2,
};

const VALID_FRESHNESS = new Set<number>([1, 4, 8, 12, 16, 24]);
const VALID_EXPERIENCE = new Set<string>(["ALL", "FRESHER", "0_1", "1_2", "2_3", "3_PLUS"]);
const VALID_ROLE_TYPES = new Set<string>(["ALL", "JOBS", "INTERNSHIPS"]);
const VALID_BOARDS = new Set<string>(["LINKEDIN", "NAUKRI", "INTERNSHALA", "INDEED"]);

/**
 * Validates and normalizes raw preference data against strict schemas and defaults.
 */
export function validatePreferences(raw: unknown): UserPreferences {
  if (!raw || typeof raw !== "object") {
    return { ...DEFAULT_PREFERENCES };
  }

  const obj = raw as Record<string, unknown>;

  // Freshness
  let freshness: FreshnessOption = DEFAULT_PREFERENCES.freshness_hours;
  const numFreshness = Number(obj.freshness_hours);
  if (VALID_FRESHNESS.has(numFreshness)) {
    freshness = numFreshness as FreshnessOption;
  }

  // Experience level
  let expLevel: ExperienceOption = DEFAULT_PREFERENCES.experience_level;
  if (typeof obj.experience_level === "string" && VALID_EXPERIENCE.has(obj.experience_level.toUpperCase())) {
    expLevel = obj.experience_level.toUpperCase() as ExperienceOption;
  }

  // Match threshold (0 - 100)
  let threshold = DEFAULT_PREFERENCES.match_threshold;
  if (typeof obj.match_threshold === "number" && !isNaN(obj.match_threshold)) {
    threshold = Math.max(0, Math.min(100, Math.round(obj.match_threshold)));
  }

  // Preferred locations
  let locations: string[] = [...DEFAULT_PREFERENCES.preferred_locations];
  if (Array.isArray(obj.preferred_locations)) {
    locations = Array.from(
      new Set(
        obj.preferred_locations
          .map((loc) => (typeof loc === "string" ? loc.trim() : ""))
          .filter((loc) => loc.length > 0)
      )
    );
  }

  // Role type
  let roleType: RoleTypeOption = DEFAULT_PREFERENCES.role_type;
  if (typeof obj.role_type === "string" && VALID_ROLE_TYPES.has(obj.role_type.toUpperCase())) {
    roleType = obj.role_type.toUpperCase() as RoleTypeOption;
  }

  // Source boards
  let sourceBoards: SourceBoardOption[] = [...DEFAULT_PREFERENCES.source_boards];
  if (Array.isArray(obj.source_boards)) {
    const validProvided = obj.source_boards
      .map((b) => (typeof b === "string" ? b.trim().toUpperCase() : ""))
      .filter((b): b is SourceBoardOption => VALID_BOARDS.has(b));
    if (validProvided.length > 0) {
      sourceBoards = Array.from(new Set(validProvided));
    }
  }

  // Excluded companies
  let excluded: string[] = [];
  if (Array.isArray(obj.excluded_companies)) {
    excluded = Array.from(
      new Set(
        obj.excluded_companies
          .map((c) => (typeof c === "string" ? c.trim() : ""))
          .filter((c) => c.length > 0)
      )
    );
  }

  // Priority companies
  let priority: string[] = [];
  if (Array.isArray(obj.priority_companies)) {
    priority = Array.from(
      new Set(
        obj.priority_companies
          .map((c) => (typeof c === "string" ? c.trim() : ""))
          .filter((c) => c.length > 0)
      )
    );
  }

  // Max experience years fallback
  const expYears = typeof obj.experience_max_years === "number" ? obj.experience_max_years : 2;

  return {
    freshness_hours: freshness,
    experience_level: expLevel,
    match_threshold: threshold,
    preferred_locations: locations,
    role_type: roleType,
    source_boards: sourceBoards,
    excluded_companies: excluded,
    priority_companies: priority,
    experience_max_years: expYears,
  };
}

/**
 * Synchronous client-side cache getter from localStorage.
 * Guaranteed to never throw and returns DEFAULT_PREFERENCES in SSR / non-browser environments.
 */
export function getLocalPreferences(): UserPreferences {
  if (typeof window === "undefined" || !window.localStorage) {
    return { ...DEFAULT_PREFERENCES };
  }

  try {
    const stored = window.localStorage.getItem(PREFERENCES_STORAGE_KEY);
    if (!stored) {
      return { ...DEFAULT_PREFERENCES };
    }
    const parsed = JSON.parse(stored);
    return validatePreferences(parsed);
  } catch {
    return { ...DEFAULT_PREFERENCES };
  }
}

/**
 * Synchronous client-side cache setter into localStorage.
 */
export function setLocalPreferences(prefs: UserPreferences): void {
  if (typeof window === "undefined" || !window.localStorage) {
    return;
  }

  try {
    window.localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(prefs));
  } catch {
    // Ignore storage quota or disabled exceptions
  }
}

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * Loads user preferences using dual-layer persistence:
 * 1. Synchronously reads immediate cache from localStorage.
 * 2. Asynchronously synchronizes with the backend database.
 * 3. Updates localStorage with authoritative server response and returns.
 */
export async function loadUserPreferences(): Promise<UserPreferences> {
  const localPrefs = getLocalPreferences();

  try {
    const res = await fetch(`${API_BASE}/api/v1/preferences`, {
      method: "GET",
      headers: { Accept: "application/json" },
      cache: "no-store",
    });

    if (res.ok) {
      const serverData = await res.json();
      // Merge server data with local cache if server is missing newly added fields
      const merged = validatePreferences({
        ...localPrefs,
        ...serverData,
      });
      setLocalPreferences(merged);
      return merged;
    }
  } catch {
    // Offline or backend unavailable; safely fallback to localStorage cache
  }

  return localPrefs;
}

/**
 * Saves user preferences using dual-layer persistence:
 * 1. Immediately writes to localStorage cache.
 * 2. Asynchronously syncs to FastAPI backend via PUT /api/v1/preferences.
 * 3. Updates localStorage cache with server response if successful.
 */
export async function saveUserPreferences(prefs: UserPreferences): Promise<UserPreferences> {
  const validated = validatePreferences(prefs);

  // 1. Immediate synchronous local cache update
  setLocalPreferences(validated);

  // 2. Asynchronous backend sync
  try {
    const res = await fetch(`${API_BASE}/api/v1/preferences`, {
      method: "PUT",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(validated),
    });

    if (res.ok) {
      const data = await res.json();
      const updated = validatePreferences({
        ...validated,
        ...data,
      });
      setLocalPreferences(updated);
      return updated;
    }
  } catch {
    // Backend offline; local cache remains valid and persistent
  }

  return validated;
}
