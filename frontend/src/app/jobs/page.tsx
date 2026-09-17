"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  Briefcase,
  Search,
  ExternalLink,
  Bookmark,
  BookmarkCheck,
  ThumbsDown,
  MapPin,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  X,
  RefreshCw,
  RotateCcw,
  Check,
  Ban,
  Sliders,
  Activity,
} from "lucide-react";
import { SyncProgressModal } from "@/components/SyncProgressModal";
import JobDetailDrawer from "@/components/jobs/JobDetailDrawer";
import { loadUserPreferences, saveUserPreferences } from "@/lib/preferences";

interface SkillPartition {
  matched: string[];
  missing: string[];
}

interface TransferableDetail {
  candidate_skill: string;
  job_skill: string;
  credit: number;
}

interface MatchBreakdown {
  overall_score: number;
  skill_score: number;
  semantic_score: number;
  experience_score: number;
  role_score: number;
  location_score: number;
  preference_score: number;
  matched_skills: string[];
  missing_skills: string[];
  transferable_skills: string[];
  required_skills?: SkillPartition;
  preferred_skills?: SkillPartition;
  transferable_details?: TransferableDetail[];
  experience_eligible?: boolean;
  location_eligible?: boolean;
  confidence?: number;
  confidence_label?: string;
  explanation: string;
  recommendation: string;
}

interface OtherSource {
  source: string;
  url?: string;
  application_url?: string;
}

interface JobItem {
  id: string;
  title: string;
  company: string;
  company_logo_url?: string | null;
  location: string;
  normalized_location?: string;
  remote_type: string;
  employment_type?: string;
  salary: string;
  salary_min?: number | null;
  salary_max?: number | null;
  experience: string;
  experience_min?: number | null;
  experience_max?: number | null;
  experience_confidence?: string;
  description_confidence?: string;
  posted_at?: string;
  age_hours: number;
  source: string;
  application_url: string;
  required_skills: string[];
  quality_score?: number;
  match?: MatchBreakdown;
  saved_status?: string;
  other_sources?: OtherSource[];
}



const getMonogram = (name: string) => {
  if (!name) return "CO";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [loading, setLoading] = useState(true);



  // Phase 46: Job Detail Drawer State
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [detailDrawerOpen, setDetailDrawerOpen] = useState(false);

  // Search & Filters state
  const [query, setQuery] = useState("");
  const [selectedSkills, setSelectedSkills] = useState<string[]>([]);
  const [selectedLocations, setSelectedLocations] = useState<string[]>([]);
  const [availableLocations, setAvailableLocations] = useState<string[]>([]);
  const [locationDropdownOpen, setLocationDropdownOpen] = useState(false);
  const [locationSearch, setLocationSearch] = useState("");
  const locationDropdownRef = useRef<HTMLDivElement>(null);
  const [typeFilter, setTypeFilter] = useState<"ALL" | "JOBS" | "INTERNSHIPS">("ALL");
  const [sourceFilter, setSourceFilter] = useState<"ALL" | "INTERNSHALA" | "NAUKRI" | "LINKEDIN">("ALL");
  const [freshnessHours, setFreshnessHours] = useState(24);
  const [sortBy, setSortBy] = useState<"match" | "freshness">("match");
  const [experienceFilter, setExperienceFilter] = useState<string>("ALL");
  const [matchThreshold, setMatchThreshold] = useState<number | null>(null);
  const [excludedCompanies, setExcludedCompanies] = useState<string[]>([]);
  const [applyingPrefs, setApplyingPrefs] = useState(false);
  const [prefToast, setPrefToast] = useState<string | null>(null);
  const [activeCardIndex, setActiveCardIndex] = useState<number>(0);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const pageSize = 50;
  const [totalCount, setTotalCount] = useState(0);

  // Global facet counts from database
  const [facets, setFacets] = useState<{
    total: number;
    types: Record<string, number>;
    sources: Record<string, number>;
    locations: Record<string, number>;
    experience: Record<string, number>;
  } | null>(null);

  // Live sync states
  const [syncing, setSyncing] = useState(false);
  const [syncSource, setSyncSource] = useState<string>("all");
  const [syncFreshness, setSyncFreshness] = useState<number>(24);
  const [syncNotification, setSyncNotification] = useState<{ type: "success" | "error"; message: string } | null>(null);
  const [syncJobId, setSyncJobId] = useState<string | null>(null);
  const [syncModalOpen, setSyncModalOpen] = useState(false);

  // Action notification (Save, Reject, Applied, or Reject All) with Undo
  const [actionNotification, setActionNotification] = useState<{
    type: "save" | "reject" | "applied" | "reject_all";
    message: string;
    jobIds: string[];
    jobs: JobItem[];
  } | null>(null);
  const [rejectingAll, setRejectingAll] = useState(false);

  const handleSyncLive = async (targetSource?: string) => {
    const src = targetSource || syncSource;
    setSyncing(true);
    setSyncNotification(null);
    setSyncJobId(null);
    setSyncModalOpen(true);
    try {
      const payload = {
        source: src,
        freshness_hours: syncFreshness,
      };

      const res = await fetch("http://localhost:8000/api/v1/jobs/sync", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        setSyncNotification({ type: "error", message: `Failed to sync with ${src}.` });
        setSyncing(false);
        return;
      }

      const initialData = await res.json();
      if (res.status === 202 && initialData.job_id) {
        setSyncJobId(initialData.job_id);
        setSyncNotification({
          type: "success",
          message: `Sync job enqueued (${initialData.source || src}). Background sync running...`,
        });
      } else {
        // Synchronous fallback response
        const result = initialData;
        const saved = result.canonical_saved || 0;
        const refreshed = result.updated_existing || 0;
        const srcNames = result.sources_synced?.join(", ") || src;
        setSyncNotification({
          type: "success",
          message: `Sync complete (${srcNames}): ${result.total_discovered || 0} scanned, ${result.fresh_jobs || 0} fresh, ${saved} new saved, ${refreshed} refreshed.`,
        });
        await fetchJobs(1);
        setSyncing(false);
      }
    } catch (e: unknown) {
      const err = e instanceof Error ? e.message : "Sync error";
      setSyncNotification({ type: "error", message: `Error: ${err}` });
      setSyncing(false);
    }
  };

  const fetchJobs = async (targetPage = currentPage) => {
    setLoading(true);
    const params = new URLSearchParams();
    if (query.trim()) params.set("query", query.trim());
    if (sourceFilter !== "ALL") params.set("source", sourceFilter.toLowerCase());
    if (selectedLocations.length > 0) {
      selectedLocations.forEach((loc) => params.append("location", loc));
    }
    params.set("freshness_hours", freshnessHours.toString());
    params.set("sort_by", sortBy);
    if (experienceFilter === "FRESHER") {
      params.set("experience_max", "0");
    } else if (experienceFilter === "0_1") {
      params.set("experience_max", "1");
    } else if (experienceFilter === "1_2") {
      params.set("experience_min", "1");
      params.set("experience_max", "2");
    } else if (experienceFilter === "2_3") {
      params.set("experience_min", "2");
      params.set("experience_max", "3");
    } else if (experienceFilter === "3_PLUS") {
      params.set("experience_min", "3");
    }
    if (typeFilter !== "ALL") {
      params.set("employment_type", typeFilter);
    }

    params.set("page", targetPage.toString());
    params.set("page_size", pageSize.toString());

    try {
      // Parallel fetch: current page jobs + contextual database facets
      const facetParams = new URLSearchParams();
      if (query.trim()) facetParams.set("query", query.trim());
      facetParams.set("freshness_hours", freshnessHours.toString());
      if (sourceFilter !== "ALL") facetParams.set("source", sourceFilter.toLowerCase());
      if (selectedLocations.length > 0) {
        selectedLocations.forEach((loc) => facetParams.append("location", loc));
      }
      if (typeFilter !== "ALL") {
        facetParams.set("employment_type", typeFilter);
      }
      if (experienceFilter === "FRESHER") {
        facetParams.set("experience_max", "0");
      } else if (experienceFilter === "0_1") {
        facetParams.set("experience_max", "1");
      } else if (experienceFilter === "1_2") {
        facetParams.set("experience_min", "1");
        facetParams.set("experience_max", "2");
      } else if (experienceFilter === "2_3") {
        facetParams.set("experience_min", "2");
        facetParams.set("experience_max", "3");
      } else if (experienceFilter === "3_PLUS") {
        facetParams.set("experience_min", "3");
      }

      const [res, facetRes] = await Promise.all([
        fetch(`http://localhost:8000/api/v1/jobs?${params.toString()}`),
        fetch(`http://localhost:8000/api/v1/jobs/facets?${facetParams.toString()}`).catch(() => null),
      ]);

      if (facetRes && facetRes.ok) {
        const facetData = await facetRes.json();
        setFacets(facetData);
        if (facetData.locations) {
          const dbLocs = Object.keys(facetData.locations).sort((a, b) => a.localeCompare(b));
          setAvailableLocations(dbLocs);
        }
      }

      if (res.ok) {
        const countHeader = res.headers.get("X-Total-Count") || res.headers.get("x-total-count");
        const data: JobItem[] = await res.json();
        setJobs(data);
        if (!facetRes || !facetRes.ok) {
          const extracted = [
            ...new Set(
              data
                .map((j) => (j.location ?? "").trim())
                .filter((loc) => loc.length > 0)
            ),
          ].sort((a, b) => a.localeCompare(b));
          setAvailableLocations((prev) => {
            if (prev.length === 0) return extracted;
            return [...new Set([...prev, ...extracted])].sort((a, b) => a.localeCompare(b));
          });
        }
        if (countHeader) {
          setTotalCount(parseInt(countHeader, 10));
        } else {
          setTotalCount(data.length);
        }
        setCurrentPage(targetPage);
      }
    } catch {
      // Backend offline
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUserPreferences().then((prefs) => {
      if (prefs.excluded_companies && prefs.excluded_companies.length > 0) {
        setExcludedCompanies(prefs.excluded_companies);
      }
    }).catch(() => {});
  }, []);

  useEffect(() => {
    fetchJobs(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sourceFilter, freshnessHours, sortBy, selectedLocations, experienceFilter, typeFilter]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchJobs(1);
  };

  const clearQuery = () => {
    setQuery("");
    fetchJobs(1);
  };

  const resetAllFilters = () => {
    setSelectedLocations([]);
    setSelectedSkills([]);
    setLocationSearch("");
    setLocationDropdownOpen(false);
    setTypeFilter("ALL");
    setSourceFilter("ALL");
    setFreshnessHours(24);
    setSyncFreshness(24);
    setSortBy("match");
    setExperienceFilter("ALL");
    setMatchThreshold(null);
    setExcludedCompanies([]);
    clearQuery();
  };

  const handleApplyMyPreferences = async () => {
    setApplyingPrefs(true);
    try {
      const prefs = await loadUserPreferences();

      // 1. Freshness
      setFreshnessHours(prefs.freshness_hours);
      setSyncFreshness(prefs.freshness_hours);

      // 2. Experience level
      setExperienceFilter(prefs.experience_level || "ALL");

      // 3. Role type
      setTypeFilter(prefs.role_type || "ALL");

      // 4. Source board
      if (prefs.source_boards && prefs.source_boards.length === 1) {
        const board = prefs.source_boards[0].toUpperCase();
        if (board === "LINKEDIN" || board === "NAUKRI" || board === "INTERNSHALA") {
          setSourceFilter(board);
        } else {
          setSourceFilter("ALL");
        }
      } else {
        setSourceFilter("ALL");
      }

      // 5. Preferred locations
      setSelectedLocations(prefs.preferred_locations || []);

      // 6. Minimum match threshold & excluded companies
      setMatchThreshold(typeof prefs.match_threshold === "number" ? prefs.match_threshold : null);
      setExcludedCompanies(prefs.excluded_companies || []);

      // 7. Reset to page 1 and fetch jobs
      setCurrentPage(1);
      fetchJobs(1);

      setPrefToast("Preferences applied to filters");
      setTimeout(() => setPrefToast(null), 3500);
    } catch (err) {
      console.error("Failed to load user preferences:", err);
    } finally {
      setApplyingPrefs(false);
    }
  };

  const handleSave = async (job: JobItem) => {
    const remaining = jobs.filter((j) => j.id !== job.id);
    setJobs(remaining);
    const newTotal = Math.max(0, totalCount - 1);
    setTotalCount(newTotal);

    setActionNotification({
      type: "save",
      message: `Saved "${job.title}" to your tracking pipeline.`,
      jobIds: [job.id],
      jobs: [job],
    });

    try {
      await fetch(`http://localhost:8000/api/v1/jobs/${job.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "SAVED" }),
      });
    } catch {
      // Handle error
    }

    // Auto-advance / replenish if page has no more jobs left and database still has more
    if (remaining.length === 0 && newTotal > 0) {
      const maxPages = Math.ceil(newTotal / pageSize);
      const nextTargetPage = Math.min(currentPage, Math.max(1, maxPages));
      fetchJobs(nextTargetPage);
    }
  };

  const handleReject = async (job: JobItem) => {
    const remaining = jobs.filter((j) => j.id !== job.id);
    setJobs(remaining);
    const newTotal = Math.max(0, totalCount - 1);
    setTotalCount(newTotal);

    setActionNotification({
      type: "reject",
      message: `Hidden "${job.title}" from future discovery.`,
      jobIds: [job.id],
      jobs: [job],
    });

    try {
      await fetch(`http://localhost:8000/api/v1/jobs/${job.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "REJECTED" }),
      });
    } catch {
      // Handle error
    }

    // Auto-advance / replenish if page has no more jobs left and database still has more
    if (remaining.length === 0 && newTotal > 0) {
      const maxPages = Math.ceil(newTotal / pageSize);
      const nextTargetPage = Math.min(currentPage, Math.max(1, maxPages));
      fetchJobs(nextTargetPage);
    }
  };

  const handleMarkApplied = async (job: JobItem) => {
    const remaining = jobs.filter((j) => j.id !== job.id);
    setJobs(remaining);
    const newTotal = Math.max(0, totalCount - 1);
    setTotalCount(newTotal);

    setActionNotification({
      type: "applied",
      message: `Marked "${job.title}" as Applied ✓ in tracking pipeline.`,
      jobIds: [job.id],
      jobs: [job],
    });

    try {
      await fetch(`http://localhost:8000/api/v1/jobs/${job.id}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "APPLIED" }),
      });
    } catch {
      // Handle error
    }

    if (remaining.length === 0 && newTotal > 0) {
      const maxPages = Math.ceil(newTotal / pageSize);
      const nextTargetPage = Math.min(currentPage, Math.max(1, maxPages));
      fetchJobs(nextTargetPage);
    }
  };

  const handleBanCompany = async (companyName: string) => {
    const trimmed = (companyName || "").trim();
    if (!trimmed) return;

    // 1. Update excludedCompanies state immediately
    const updated = Array.from(new Set([...excludedCompanies, trimmed]));
    setExcludedCompanies(updated);

    // 2. Remove all jobs from this company from current jobs list
    const norm = trimmed.toLowerCase();
    const remaining = jobs.filter((j) => {
      const comp = (j.company ?? "").toLowerCase().trim();
      return !(comp === norm || comp.includes(norm) || norm.includes(comp));
    });
    const removedCount = jobs.length - remaining.length;
    setJobs(remaining);
    const newTotal = Math.max(0, totalCount - removedCount);
    setTotalCount(newTotal);

    // 3. Show confirmation feedback
    setPrefToast(`Banned "${trimmed}" & added to excluded companies.`);
    setTimeout(() => setPrefToast(null), 4000);

    // 4. Save to dual-layer persistence (localStorage + backend)
    try {
      const currentPrefs = await loadUserPreferences();
      const newExcluded = Array.from(new Set([...(currentPrefs.excluded_companies || []), trimmed]));
      await saveUserPreferences({
        ...currentPrefs,
        excluded_companies: newExcluded,
      });
    } catch (err) {
      console.error("Failed to save banned company preference:", err);
    }

    // 5. Replenish if empty
    if (remaining.length === 0 && newTotal > 0) {
      const maxPages = Math.ceil(newTotal / pageSize);
      const nextTargetPage = Math.min(currentPage, Math.max(1, maxPages));
      fetchJobs(nextTargetPage);
    }
  };

  const handleRejectAllOnPage = async () => {
    if (filteredJobs.length === 0 || rejectingAll) return;
    const confirmed = window.confirm(`Dismiss all ${filteredJobs.length} jobs on this page? You can undo this action from the toast notification.`);
    if (!confirmed) return;
    setRejectingAll(true);

    const targetJobs = [...filteredJobs];
    const targetIds = targetJobs.map((j) => j.id);

    const remaining = jobs.filter((j) => !targetIds.includes(j.id));
    setJobs(remaining);
    const newTotal = Math.max(0, totalCount - targetIds.length);
    setTotalCount(newTotal);

    setActionNotification({
      type: "reject_all",
      message: `Rejected all ${targetIds.length} listings from page ${currentPage}.`,
      jobIds: targetIds,
      jobs: targetJobs,
    });

    try {
      await fetch("http://localhost:8000/api/v1/jobs/batch-status", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ job_ids: targetIds, status: "REJECTED" }),
      });
    } catch {
      // Handle error
    } finally {
      setRejectingAll(false);
    }

    // Auto-advance / replenish with next page of jobs
    if (newTotal > 0) {
      const maxPages = Math.ceil(newTotal / pageSize);
      const nextTargetPage = Math.min(currentPage, Math.max(1, maxPages));
      fetchJobs(nextTargetPage);
    }
  };

  const handleUndoAction = async () => {
    if (!actionNotification) return;
    const { jobIds, jobs: restoredJobs } = actionNotification;
    setActionNotification(null);

    setJobs((prev) => [...restoredJobs, ...prev]);
    setTotalCount((prev) => prev + jobIds.length);

    try {
      if (jobIds.length === 1) {
        await fetch(`http://localhost:8000/api/v1/jobs/${jobIds[0]}/status`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ status: "DISCOVERED" }),
        });
      } else if (jobIds.length > 1) {
        await fetch("http://localhost:8000/api/v1/jobs/batch-status", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ job_ids: jobIds, status: "DISCOVERED" }),
        });
      }
    } catch {
      // Handle error
    }
  };

  useEffect(() => {
    const onPointerDown = (e: MouseEvent) => {
      if (!locationDropdownRef.current?.contains(e.target as Node)) {
        setLocationDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, []);

  const locationCounts = useMemo(() => {
    if (facets?.locations) {
      return facets.locations;
    }
    const map: Record<string, number> = {};
    for (const job of jobs) {
      const loc = (job.location ?? "").trim();
      if (!loc) continue;
      map[loc] = (map[loc] || 0) + 1;
    }
    return map;
  }, [facets, jobs]);

  const TOP_HUBS = useMemo(() => [
    "Bengaluru",
    "Delhi NCR",
    "Mumbai",
    "Hyderabad",
    "Pune",
    "Chennai",
    "Kolkata",
    "Gurugram",
    "Noida",
    "Remote",
    "Remote (India)",
  ], []);

  const visibleLocations = useMemo(() => {
    const q = locationSearch.trim().toLowerCase();
    const source = availableLocations.length > 0 ? availableLocations : TOP_HUBS;
    if (!q) {
      // Prioritize top tech hubs first, then alphabetical
      const topSet = new Set(TOP_HUBS.map(h => h.toLowerCase()));
      const hubsInList = source.filter(l => topSet.has(l.toLowerCase()));
      const others = source.filter(l => !topSet.has(l.toLowerCase())).sort((a, b) => a.localeCompare(b));
      return [...new Set([...hubsInList, ...others])];
    }
    return source.filter((loc) => loc.toLowerCase().includes(q));
  }, [availableLocations, locationSearch, TOP_HUBS]);

  const counts = {
    all: facets?.total ?? totalCount ?? jobs.length,
    jobsCount: facets?.types?.JOBS ?? jobs.filter(
      (j) => j.employment_type !== "INTERNSHIP" && !j.experience?.toLowerCase().includes("internship")
    ).length,
    internCount: facets?.types?.INTERNSHIPS ?? jobs.filter(
      (j) => j.employment_type === "INTERNSHIP" || j.experience?.toLowerCase().includes("internship")
    ).length,
    internshalaCount: facets?.sources?.internshala ?? jobs.filter((j) => j.source === "internshala").length,
    naukriCount: facets?.sources?.naukri ?? jobs.filter((j) => j.source === "naukri").length,
    linkedinCount: facets?.sources?.linkedin ?? jobs.filter((j) => j.source === "linkedin").length,
    fresherCount: facets?.experience?.FRESHER ?? jobs.filter(
      (j) =>
        j.employment_type === "INTERNSHIP" ||
        j.experience_min === 0 ||
        j.experience?.toLowerCase().includes("fresher") ||
        j.experience?.toLowerCase().includes("intern")
    ).length,
    exp01Count: facets?.experience?.["0_1"] ?? jobs.filter(
      (j) =>
        (j.experience_min !== null && j.experience_min !== undefined && j.experience_min <= 1) ||
        (j.experience_max !== null && j.experience_max !== undefined && j.experience_max <= 1) ||
        j.employment_type === "INTERNSHIP"
    ).length,
    exp12Count: facets?.experience?.["1_2"] ?? jobs.filter((j) => {
      const min = j.experience_min ?? 0;
      const max = j.experience_max ?? (j.experience_min ?? 99);
      return (min <= 2 && max >= 1) || j.experience?.includes("1-2") || j.experience?.includes("0-2");
    }).length,
    exp23Count: facets?.experience?.["2_3"] ?? jobs.filter((j) => {
      const min = j.experience_min ?? 0;
      const max = j.experience_max ?? 99;
      return (min <= 3 && max >= 2) || j.experience?.includes("2-3") || j.experience?.includes("1-3");
    }).length,
    strong: jobs.filter((j) => j.match?.recommendation === "STRONG_MATCH").length,
    good: jobs.filter((j) => j.match?.recommendation === "GOOD_MATCH").length,
    consider: jobs.filter((j) => j.match?.recommendation === "CONSIDER").length,
  };

  const filteredJobs = jobs.filter((job) => {
    // Location is already authoritatively filtered by the backend with taxonomy expansion.
    // Client-side fallback only applies if backend returned jobs without location filtering (e.g. offline).

    // Employment type filtering
    if (typeFilter === "JOBS") {
      if (job.employment_type === "INTERNSHIP" || job.experience?.toLowerCase().includes("internship")) return false;
    } else if (typeFilter === "INTERNSHIPS") {
      if (job.employment_type !== "INTERNSHIP" && !job.experience?.toLowerCase().includes("internship")) return false;
    }

    // Experience tier filtering
    if (experienceFilter === "FRESHER") {
      const isIntern = job.employment_type === "INTERNSHIP" || job.experience?.toLowerCase().includes("intern");
      const isFresherMin = job.experience_min === 0;
      const isFresherText = job.experience?.toLowerCase().includes("fresher");
      const isUnspecified = job.experience_min == null && (job.experience_max == null || job.experience_max <= 1);
      if (!isIntern && !isFresherMin && !isFresherText && !isUnspecified) return false;
    } else if (experienceFilter === "0_1") {
      const min = job.experience_min ?? 0;
      const isIntern = job.employment_type === "INTERNSHIP";
      if (!isIntern && min > 1) return false;
    } else if (experienceFilter === "1_2") {
      const min = job.experience_min ?? 0;
      const max = job.experience_max ?? (job.experience_min ?? 99);
      if (min > 2 || max < 1) return false;
    } else if (experienceFilter === "2_3") {
      const min = job.experience_min ?? 0;
      const max = job.experience_max ?? 99;
      if (min > 3 || max < 2) return false;
    } else if (experienceFilter === "3_PLUS") {
      const max = job.experience_max ?? 99;
      const min = job.experience_min ?? 0;
      if (max < 3 && min < 3) return false;
    }

    // Selected skill filtering (Phase 46)
    if (selectedSkills.length > 0) {
      const jobSkills = (job.required_skills || []).map((s) => s.toLowerCase());
      const hasSkill = selectedSkills.every((sk) =>
        jobSkills.some((js) => js.includes(sk.toLowerCase()))
      );
      if (!hasSkill) return false;
    }

    // Excluded companies filtering (R1 & R2)
    if (excludedCompanies.length > 0) {
      const jobCompany = (job.company ?? "").toLowerCase().trim();
      const isExcluded = excludedCompanies.some((exc) => {
        const norm = exc.toLowerCase().trim();
        return norm.length > 0 && (jobCompany === norm || jobCompany.includes(norm) || norm.includes(jobCompany));
      });
      if (isExcluded) return false;
    }



    return true;
  });

  // Power user keyboard shortcuts (J = next, K = prev, S = save, X = dismiss, Enter = open drawer)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore keystrokes when typing inside inputs, textareas, or dropdowns
      const target = e.target as HTMLElement;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.isContentEditable ||
          target.tagName === "SELECT")
      ) {
        return;
      }

      if (detailDrawerOpen) {
        if (e.key === "Escape") {
          setDetailDrawerOpen(false);
        }
        return;
      }

      if (filteredJobs.length === 0) return;

      if (e.key === "j" || e.key === "J") {
        e.preventDefault();
        setActiveCardIndex((prev) => Math.min(prev + 1, filteredJobs.length - 1));
      } else if (e.key === "k" || e.key === "K") {
        e.preventDefault();
        setActiveCardIndex((prev) => Math.max(prev - 1, 0));
      } else if (e.key === "Enter") {
        e.preventDefault();
        const currentJob = filteredJobs[activeCardIndex];
        if (currentJob) {
          setSelectedJobId(currentJob.id);
          setDetailDrawerOpen(true);
        }
      } else if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        const currentJob = filteredJobs[activeCardIndex];
        if (currentJob) {
          handleSave(currentJob);
        }
      } else if (e.key === "x" || e.key === "X") {
        e.preventDefault();
        const currentJob = filteredJobs[activeCardIndex];
        if (currentJob) {
          handleReject(currentJob);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activeCardIndex, filteredJobs, detailDrawerOpen]);


  const getBadgeStyle = (rec: string) => {
    switch (rec) {
      case "STRONG_MATCH":
        return "bg-emerald-50 text-emerald-800 border-emerald-300 font-bold";
      case "GOOD_MATCH":
        return "bg-teal-50 text-teal-800 border-teal-300 font-bold";
      case "CONSIDER":
        return "bg-amber-50 text-amber-900 border-amber-300 font-bold";
      case "LOW_PRIORITY":
        return "bg-orange-50 text-orange-900 border-orange-300 font-bold";
      default:
        return "bg-slate-100 text-slate-800 border-slate-300 font-medium";
    }
  };


  const hasActiveFilters =
    selectedLocations.length > 0 ||
    selectedSkills.length > 0 ||
    typeFilter !== "ALL" ||
    sourceFilter !== "ALL" ||
    experienceFilter !== "ALL" ||
    matchThreshold !== null ||
    excludedCompanies.length > 0 ||
    query.trim().length > 0;

  const clearLocations = () => {
    setSelectedLocations([]);
    setLocationSearch("");
  };

  const toggleLocation = (loc: string) => {
    setSelectedLocations((prev) =>
      prev.includes(loc) ? prev.filter((l) => l !== loc) : [...prev, loc]
    );
  };

  const renderPaginationControls = () => {
    if (totalCount <= pageSize) return null;
    const totalPages = Math.ceil(totalCount / pageSize);

    return (
      <div className="flex flex-wrap items-center justify-between gap-4 pt-4 pb-2 border-t border-slate-100 text-xs">
        <div className="text-slate-500 font-medium">
          Showing <strong className="text-slate-900 font-tabular">{(currentPage - 1) * pageSize + 1}</strong> to{" "}
          <strong className="text-slate-900 font-tabular">{Math.min(currentPage * pageSize, totalCount)}</strong> of{" "}
          <strong className="text-slate-900 font-tabular">{totalCount}</strong> listings
        </div>

        <div className="flex items-center gap-1.5">
          <button
            onClick={() => {
              if (currentPage > 1) {
                fetchJobs(currentPage - 1);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }
            }}
            disabled={currentPage <= 1 || loading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 transition-colors shadow-xs"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Previous</span>
          </button>

          <div className="flex items-center gap-1 px-1">
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
              .map((p, idx, arr) => {
                const prev = arr[idx - 1];
                const showEllipsis = prev && p - prev > 1;
                return (
                  <div key={p} className="flex items-center gap-1">
                    {showEllipsis && <span className="text-slate-400 px-1">...</span>}
                    <button
                      onClick={() => {
                        fetchJobs(p);
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                      disabled={loading}
                      className={`min-w-[32px] h-8 px-2 rounded-lg text-xs font-semibold font-tabular transition-colors ${
                        currentPage === p
                          ? "bg-slate-900 text-white shadow-xs"
                          : "border border-slate-200 bg-white hover:bg-slate-50 text-slate-600 hover:text-slate-900"
                      }`}
                    >
                      {p}
                    </button>
                  </div>
                );
              })}
          </div>

          <button
            onClick={() => {
              if (currentPage < totalPages) {
                fetchJobs(currentPage + 1);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }
            }}
            disabled={currentPage >= totalPages || loading}
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-slate-200 bg-white hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed text-slate-700 transition-colors shadow-xs"
          >
            <span>Next</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 pb-20">
      {/* Top Command Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="space-y-1 relative">
          <div className="flex items-center gap-3">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-900">
              Job Discovery
            </h1>
          </div>
          <p className="text-xs sm:text-sm text-slate-500 font-medium">
            Real-time tech roles across India <span className="text-slate-300 mx-1.5">·</span>{" "}
            <strong className="text-slate-800 font-tabular font-bold">{totalCount}</strong> opportunities tracked
          </p>
        </div>

        {/* Sync Controls Dock matching reference screenshot */}
        <div className="flex items-center gap-2.5 self-start md:self-auto flex-wrap">
          <div className="relative">
            <select
              value={syncSource}
              onChange={(e) => setSyncSource(e.target.value)}
              disabled={syncing}
              className="appearance-none bg-white text-slate-700 font-medium text-xs border border-slate-200/90 rounded-xl pl-3.5 pr-8 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 hover:border-slate-300 shadow-xs cursor-pointer"
            >
              <option value="all">All Sources</option>
              <option value="linkedin">LinkedIn</option>
              <option value="naukri">Naukri</option>
              <option value="internshala">Internshala</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-3.5 pointer-events-none" />
          </div>

          <div className="relative">
            <select
              value={freshnessHours}
              onChange={(e) => {
                const val = Number(e.target.value);
                setSyncFreshness(val);
                setFreshnessHours(val);
              }}
              disabled={syncing}
              className="appearance-none bg-white text-slate-700 font-medium text-xs border border-slate-200/90 rounded-xl pl-3.5 pr-8 py-2.5 focus:outline-none focus:ring-2 focus:ring-blue-500/20 hover:border-slate-300 shadow-xs cursor-pointer"
              title="Freshness Window"
            >
              <option value={1}>Past 1h</option>
              <option value={4}>Past 4h</option>
              <option value={8}>Past 8h</option>
              <option value={12}>Past 12h</option>
              <option value={16}>Past 16h</option>
              <option value={24}>Past 24h</option>
            </select>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 absolute right-2.5 top-3.5 pointer-events-none" />
          </div>

          {syncJobId && (
            <button
              onClick={() => setSyncModalOpen(true)}
              className="flex items-center gap-1.5 px-3 py-2.5 bg-blue-50 hover:bg-blue-100 text-blue-700 border border-blue-200 rounded-xl text-xs font-semibold transition-all cursor-pointer shadow-xs"
              title="View Ingestion Progress"
            >
              <Activity className={`w-3.5 h-3.5 ${syncing ? "animate-pulse text-blue-600" : ""}`} />
              <span>Telemetry</span>
            </button>
          )}

          <button
            onClick={() => handleSyncLive()}
            disabled={syncing}
            className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-800 active:scale-[0.98] disabled:opacity-50 text-white rounded-xl text-xs font-semibold transition-all shadow-xs cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? "animate-spin" : ""}`} />
            <span>{syncing ? "Syncing..." : "Sync Feeds"}</span>
          </button>
        </div>
      </div>

      {/* Sync Notification Toast */}
      {syncNotification && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-center justify-between shadow-xs transition-all ${
            syncNotification.type === "success"
              ? "bg-emerald-50 border-emerald-200 text-emerald-800"
              : "bg-rose-50 border-rose-200 text-rose-800"
          }`}
        >
          <div className="flex items-center gap-2">
            <span className="font-semibold">{syncNotification.message}</span>
            {syncJobId && (
              <button
                onClick={() => setSyncModalOpen(true)}
                className="underline font-bold hover:opacity-80 ml-1 cursor-pointer"
              >
                View Telemetry
              </button>
            )}
          </div>
          <button
            onClick={() => setSyncNotification(null)}
            aria-label="Dismiss notification"
            className="p-1 hover:bg-black/5 rounded text-slate-400 hover:text-slate-700 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Action Notification Toast with Undo */}
      {actionNotification && (
        <div
          className={`p-3.5 rounded-xl border text-xs flex items-center justify-between gap-3 shadow-md transition-all ${
            actionNotification.type === "save"
              ? "bg-white border-emerald-300 text-emerald-900"
              : "bg-white border-rose-300 text-rose-900"
          }`}
        >
          <div className="flex items-center gap-2.5 min-w-0">
            {actionNotification.type === "save" ? (
              <BookmarkCheck className="w-4 h-4 text-emerald-600 shrink-0" />
            ) : actionNotification.type === "reject_all" ? (
              <Ban className="w-4 h-4 text-rose-600 shrink-0" />
            ) : (
              <ThumbsDown className="w-4 h-4 text-rose-600 shrink-0" />
            )}
            <span className="font-medium text-slate-800 truncate">{actionNotification.message}</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {actionNotification.type === "save" && (
              <Link
                href="/saved"
                className="px-3 py-1 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-lg text-xs font-semibold transition-colors"
              >
                View in Pipeline
              </Link>
            )}
            <button
              onClick={handleUndoAction}
              className="px-3 py-1 bg-slate-100 hover:bg-slate-200 text-slate-800 border border-slate-200 rounded-lg text-xs font-semibold transition-colors"
            >
              Undo
            </button>
            <button
              onClick={() => setActionNotification(null)}
              aria-label="Dismiss action notice"
              className="p-1 hover:bg-slate-100 rounded text-slate-400 hover:text-slate-700 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Streamlined Discovery Layout: Full-Width Focused Stream */}
      <div className="w-full space-y-4">
        {/* Command Dock: Search bar + Hubs + Dropdowns */}
        <div className="rounded-2xl border border-slate-200/90 bg-white p-4 space-y-3.5 shadow-sm">
          {/* Search Input Bar with Command-K indicator */}
          <form onSubmit={handleSearchSubmit} className="relative flex items-center rounded-xl bg-slate-50 border border-slate-200/90 focus-within:border-slate-400 focus-within:ring-2 focus-within:ring-slate-100 transition-all p-1">
            <Search className="w-4 h-4 text-slate-400 ml-3 shrink-0" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by role, company, skill or keyword..."
              className="bg-transparent text-slate-900 text-xs sm:text-sm font-medium focus:outline-none flex-1 px-3 py-2 placeholder:text-slate-400"
            />
            <div className="hidden sm:flex items-center gap-1 px-2 py-1 rounded-md bg-white border border-slate-200 text-[11px] font-mono text-slate-400 mr-2 shadow-xs">
              <span>⌘</span>
              <span>K</span>
            </div>
            {query && (
              <button
                type="button"
                onClick={clearQuery}
                className="p-1 mr-1 text-slate-400 hover:text-slate-700 transition-colors"
                title="Clear search"
              >
                <X className="w-4 h-4" />
              </button>
            )}
            <button
              type="submit"
              className="px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold transition-all shadow-xs active:scale-[0.98]"
            >
              Search
            </button>
          </form>

          {/* Hubs row: Clean subtle pills */}
          <div className="flex items-center gap-1.5 flex-wrap text-xs pt-0.5">
            <span className="text-xs text-slate-500 font-semibold mr-1 flex items-center gap-1 shrink-0">
              <MapPin className="w-3.5 h-3.5 text-slate-400" /> Hubs:
            </span>

            <button
              onClick={clearLocations}
              className={`px-2.5 py-1 rounded-lg text-xs transition-all border shrink-0 ${
                selectedLocations.length === 0
                  ? "bg-slate-900 text-white font-semibold border-slate-900 shadow-xs"
                  : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:text-slate-900"
              }`}
            >
              <span>All India</span>
              <span className={`ml-1.5 px-1.5 py-0.2 rounded-full text-[10px] font-tabular ${selectedLocations.length === 0 ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-600"}`}>
                {counts.all}
              </span>
            </button>

            {["Bengaluru", "Delhi NCR", "Hyderabad", "Pune", "Remote"].map((hub) => {
              const isSelected = selectedLocations.includes(hub);
              const count = locationCounts[hub] ?? 0;
              return (
                <button
                  key={hub}
                  onClick={() => toggleLocation(hub)}
                  className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-all border shrink-0 ${
                    isSelected
                      ? "bg-slate-900 border-slate-900 text-white font-semibold shadow-xs"
                      : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:text-slate-900"
                  }`}
                >
                  <span>{hub}</span>
                  <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-tabular ${isSelected ? "bg-slate-800 text-slate-200" : "bg-slate-100 text-slate-600"}`}>
                    {count}
                  </span>
                </button>
              );
            })}

            {/* Location Dropdown Trigger */}
            <div className="relative shrink-0" ref={locationDropdownRef}>
              {(() => {
                const extraSelectedCount = selectedLocations.filter(
                  (loc) => !["Bengaluru", "Delhi NCR", "Hyderabad", "Pune", "Remote"].includes(loc)
                ).length;
                const isExtraActive = locationDropdownOpen || extraSelectedCount > 0;
                return (
                  <button
                    onClick={() => setLocationDropdownOpen((prev) => !prev)}
                    className={`flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs transition-all border shrink-0 ${
                      isExtraActive
                        ? "bg-slate-900 border-slate-900 text-white font-semibold shadow-xs"
                        : "bg-white text-slate-600 border-slate-200 hover:border-slate-300 hover:text-slate-900"
                    }`}
                  >
                    <span>+ More</span>
                    {extraSelectedCount > 0 && (
                      <span className="px-1.5 py-0.2 rounded-full text-[10px] font-tabular bg-slate-800 text-slate-200">
                        {extraSelectedCount}
                      </span>
                    )}
                    <ChevronDown className={`w-3 h-3 ${isExtraActive ? "text-slate-300" : "text-slate-400"}`} />
                  </button>
                );
              })()}

              {locationDropdownOpen && (
                <div className="absolute left-0 top-full mt-1.5 w-64 bg-white rounded-xl border border-slate-200 shadow-lg z-50 p-2 space-y-2">
                  <input
                    type="text"
                    value={locationSearch}
                    onChange={(e) => setLocationSearch(e.target.value)}
                    placeholder="Filter cities..."
                    className="w-full px-2.5 py-1.5 bg-slate-50 border border-slate-200 rounded-lg text-xs focus:outline-none focus:border-slate-400"
                  />
                  <div className="max-h-48 overflow-y-auto space-y-1">
                    {visibleLocations.map((loc) => {
                        const checked = selectedLocations.includes(loc);
                        return (
                          <button
                            key={loc}
                            onClick={() => toggleLocation(loc)}
                            className="w-full flex items-center justify-between px-2 py-1 rounded text-xs hover:bg-slate-50 text-left"
                          >
                            <span className={checked ? "font-bold text-slate-900" : "text-slate-600"}>{loc}</span>
                            {checked && <Check className="w-3 h-3 text-slate-900" />}
                          </button>
                        );
                      })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Secondary Filter Row & Actions */}
          <div className="flex items-center justify-between gap-3 flex-wrap pt-1 border-t border-slate-100">
            <div className="flex items-center gap-2 flex-wrap">
              <div className="relative">
                <select
                  value={typeFilter}
                  onChange={(e) => setTypeFilter(e.target.value as "ALL" | "JOBS" | "INTERNSHIPS")}
                  className="appearance-none bg-white text-slate-700 font-medium border border-slate-200 rounded-xl pl-2.5 pr-6 py-1.5 text-xs focus:outline-none hover:border-slate-300 transition-colors cursor-pointer shadow-xs"
                >
                  <option value="ALL">Role: All ({counts.all})</option>
                  <option value="JOBS">Full-Time ({counts.jobsCount})</option>
                  <option value="INTERNSHIPS">Internships ({counts.internCount})</option>
                </select>
                <ChevronDown className="w-3 h-3 text-slate-400 absolute right-1.5 top-2.5 pointer-events-none" />
              </div>

              <div className="relative">
                <select
                  value={experienceFilter}
                  onChange={(e) => setExperienceFilter(e.target.value)}
                  className="appearance-none bg-white text-slate-700 font-medium border border-slate-200 rounded-xl pl-2.5 pr-6 py-1.5 text-xs focus:outline-none hover:border-slate-300 transition-colors cursor-pointer shadow-xs"
                >
                  <option value="ALL">Exp: Any</option>
                  <option value="FRESHER">Fresher / 0y</option>
                  <option value="0_1">0-1 Years</option>
                  <option value="1_2">1-2 Years</option>
                  <option value="2_3">2-3 Years</option>
                  <option value="3_PLUS">3+ Years</option>
                </select>
                <ChevronDown className="w-3 h-3 text-slate-400 absolute right-1.5 top-2.5 pointer-events-none" />
              </div>

              <div className="relative">
                <select
                  value={sourceFilter}
                  onChange={(e) => setSourceFilter(e.target.value as "ALL" | "INTERNSHALA" | "NAUKRI" | "LINKEDIN")}
                  className="appearance-none bg-white text-slate-700 font-medium border border-slate-200 rounded-xl pl-2.5 pr-6 py-1.5 text-xs focus:outline-none hover:border-slate-300 transition-colors cursor-pointer shadow-xs"
                >
                  <option value="ALL">Source: All</option>
                  <option value="LINKEDIN">LinkedIn</option>
                  <option value="NAUKRI">Naukri</option>
                  <option value="INTERNSHALA">Internshala</option>
                </select>
                <ChevronDown className="w-3 h-3 text-slate-400 absolute right-1.5 top-2.5 pointer-events-none" />
              </div>

              <div className="relative">
                <select
                  value={sortBy}
                  onChange={(e) => setSortBy(e.target.value as "match" | "freshness")}
                  className="appearance-none bg-white text-slate-700 font-medium border border-slate-200 rounded-xl pl-2.5 pr-6 py-1.5 text-xs focus:outline-none hover:border-slate-300 transition-colors cursor-pointer shadow-xs"
                >
                  <option value="match">Sort: Match Fit</option>
                  <option value="freshness">Sort: Freshness</option>
                </select>
                <ChevronDown className="w-3 h-3 text-slate-400 absolute right-1.5 top-2.5 pointer-events-none" />
              </div>

              <button
                onClick={handleApplyMyPreferences}
                disabled={applyingPrefs}
                className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl bg-white hover:bg-slate-50 text-slate-700 border border-slate-200 text-xs font-medium transition-all disabled:opacity-50 shadow-xs shrink-0"
                title="Apply saved preferences"
              >
                {applyingPrefs ? (
                  <RefreshCw className="w-3 h-3 animate-spin text-slate-700" />
                ) : (
                  <Sliders className="w-3 h-3 text-slate-500" />
                )}
                <span>My Preferences</span>
              </button>
            </div>

            {filteredJobs.length > 0 && (
              <button
                onClick={handleRejectAllOnPage}
                disabled={rejectingAll}
                className="flex items-center gap-1.5 text-xs text-rose-600 border border-rose-200 bg-rose-50/60 hover:bg-rose-100/80 px-3 py-1.5 rounded-xl transition-all disabled:opacity-50 font-semibold shrink-0 ml-auto whitespace-nowrap shadow-xs"
                title="Dismiss all jobs on this page and load next"
              >
                <Ban className="w-3.5 h-3.5" />
                <span>{rejectingAll ? "Dismissing..." : `Dismiss Page (${filteredJobs.length})`}</span>
              </button>
            )}
          </div>
        </div>

        {/* Result Count Bar */}
        <div className="flex items-center justify-between text-xs text-slate-500 px-1 flex-wrap gap-2">
          <div className="flex items-center gap-2 flex-wrap">
            <div>
              Showing <strong className="text-slate-900 font-tabular font-bold">{filteredJobs.length}</strong> of{" "}
              <strong className="text-slate-900 font-tabular font-bold">{totalCount > 0 ? totalCount : jobs.length}</strong>
              {totalCount > pageSize && (
                <span className="text-slate-400 ml-1.5">(Page {currentPage} of {Math.ceil(totalCount / pageSize)})</span>
              )}
            </div>

            {excludedCompanies.length > 0 && (
              <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] bg-slate-100 text-slate-600 border border-slate-200">
                <span>{excludedCompanies.length} companies excluded</span>
              </span>
            )}
          </div>

          {hasActiveFilters && (
            <button
              onClick={resetAllFilters}
              className="flex items-center gap-1 text-slate-500 hover:text-slate-900 transition-colors font-medium"
            >
              <RotateCcw className="w-3 h-3" />
              <span>Reset Filters</span>
            </button>
          )}
        </div>

        {/* Job Listings: Clean modern white cards */}
        {loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4].map((i) => (
              <div key={i} className="rounded-2xl border border-slate-200/90 bg-white p-5 animate-pulse space-y-3 shadow-sm">
                <div className="flex items-center gap-3.5">
                  <div className="w-12 h-12 rounded-xl bg-slate-100 shrink-0" />
                  <div className="space-y-2 flex-1">
                    <div className="h-4 bg-slate-100 rounded w-1/3" />
                    <div className="h-3 bg-slate-50 rounded w-1/2" />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : filteredJobs.length > 0 ? (
          <div className="space-y-3.5">
            {filteredJobs.map((job, idx) => {
              const match = job.match;
              const monogram = getMonogram(job.company);
              const isActive = activeCardIndex === idx;

              return (
                <div
                  key={job.id}
                  onClick={() => {
                    setActiveCardIndex(idx);
                    setSelectedJobId(job.id);
                    setDetailDrawerOpen(true);
                  }}
                  className={`group relative rounded-2xl border bg-white p-5 hover:border-slate-300 hover:shadow-md transition-all duration-200 cursor-pointer ${
                    isActive ? "border-slate-900 ring-1 ring-slate-900/10" : "border-slate-200/90 shadow-sm"
                  }`}
                >
                  <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-4">
                    {/* Left: Company Logo/Avatar + Main Details */}
                    <div className="flex items-start gap-4 min-w-0 flex-1">
                      {/* Company Logo Monogram Container */}
                      <div className="w-12 h-12 rounded-xl bg-slate-50 border border-slate-200/90 flex items-center justify-center font-bold text-sm text-slate-700 shrink-0 shadow-xs group-hover:border-slate-300 transition-all overflow-hidden relative">
                        {job.company_logo_url ? (
                          <img
                            src={job.company_logo_url}
                            alt={job.company}
                            className="w-full h-full object-contain p-1"
                            onError={(e) => {
                              (e.currentTarget as HTMLElement).style.display = "none";
                              const fallback = e.currentTarget.nextElementSibling as HTMLElement;
                              if (fallback) fallback.style.display = "flex";
                            }}
                          />
                        ) : null}
                        <span
                          className="items-center justify-center w-full h-full"
                          style={{ display: job.company_logo_url ? "none" : "flex" }}
                        >
                          {monogram}
                        </span>
                      </div>

                      <div className="min-w-0 flex-1 space-y-2">
                        {/* Row 1: Company Name + Source Badge + Match Badge + QS Badge + Time */}
                        <div className="flex items-center gap-2 flex-wrap text-xs">
                          <span className="text-slate-900 font-bold text-sm tracking-tight">{job.company}</span>

                          {/* Source icon badge */}
                          <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-md bg-slate-100 text-slate-700 border border-slate-200 font-semibold text-[10px] tracking-wide uppercase">
                            {job.source}
                          </span>

                          {match && (
                            <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${getBadgeStyle(match.recommendation)}`}>
                              <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                              <span className="font-tabular">{match.overall_score}%</span>
                              <span>{match.recommendation.replace("_", " ")}</span>
                            </span>
                          )}

                          {job.quality_score !== undefined && job.quality_score > 0 && (
                            <span className="px-2 py-0.5 rounded-md text-xs font-medium font-tabular bg-slate-50 text-slate-600 border border-slate-200">
                              QS {Math.round(job.quality_score)}%
                            </span>
                          )}

                          <span className="text-slate-400 font-tabular text-xs font-normal ml-auto lg:ml-1">
                            {job.age_hours !== null ? `${job.age_hours}h ago` : "Just now"}
                          </span>
                        </div>

                        {/* Row 2: Job Title (Large & Bold) */}
                        <h2
                          onClick={() => {
                            setSelectedJobId(job.id);
                            setDetailDrawerOpen(true);
                          }}
                          className="text-lg sm:text-xl font-bold text-slate-900 group-hover:text-blue-600 transition-colors cursor-pointer leading-snug tracking-tight"
                        >
                          {job.title}
                        </h2>

                        {/* Row 3: Metadata (Location, Exp, Comp) */}
                        <div className="flex items-center gap-3 text-xs sm:text-[13px] text-slate-600 flex-wrap pt-0.5 font-normal">
                          <div className="flex items-center gap-1.5 text-slate-800 font-medium">
                            <MapPin className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span>{job.location}</span>
                            <span className="text-slate-500 uppercase text-[11px] font-semibold">({job.remote_type})</span>
                          </div>

                          <span className="text-slate-300">·</span>
                          <div className="flex items-center gap-1.5">
                            <Briefcase className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                            <span>Exp: <strong className="text-slate-900 font-semibold">{job.experience}</strong></span>
                          </div>

                          <span className="text-slate-300">·</span>
                          <div className="flex items-center gap-1">
                            <span className="text-slate-500">Comp:</span>
                            <strong className={job.salary ? "text-slate-900 font-semibold" : "text-slate-500 font-normal"}>
                              {job.salary || "Not disclosed"}
                            </strong>
                          </div>
                        </div>

                        {/* Row 4: Skill Tags */}
                        {job.required_skills && job.required_skills.length > 0 && (
                          <div className="flex items-center gap-1.5 flex-wrap pt-1">
                            {job.required_skills.slice(0, 5).map((s) => (
                              <span
                                key={s}
                                className="text-xs font-medium px-2 py-0.5 rounded-md bg-slate-50 text-slate-700 border border-slate-200/80"
                              >
                                {s}
                              </span>
                            ))}
                            {job.required_skills.length > 5 && (
                              <span className="text-xs text-slate-400 font-medium ml-1">
                                +{job.required_skills.length - 5} more
                              </span>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Right: Clean Actions Toolbar */}
                    <div className="flex items-center gap-2 shrink-0 self-start lg:self-center pt-2 lg:pt-0">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleSave(job);
                        }}
                        aria-label={`Save ${job.title} to pipeline`}
                        className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-all shadow-xs active:scale-[0.98] bg-white hover:bg-slate-50 text-slate-700 border-slate-200 hover:border-slate-300"
                        title="Save to pipeline"
                      >
                        <Bookmark className="w-3.5 h-3.5 text-slate-500" />
                        <span>Save</span>
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleMarkApplied(job);
                        }}
                        aria-label={`Mark ${job.title} as applied`}
                        className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-emerald-50 text-slate-400 hover:text-emerald-600 hover:border-emerald-200 transition-colors shadow-xs"
                        title="Mark as applied"
                      >
                        <Check className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleReject(job);
                        }}
                        aria-label={`Dismiss ${job.title} at ${job.company}`}
                        className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-rose-50 text-slate-400 hover:text-rose-600 hover:border-rose-200 transition-colors shadow-xs"
                        title="Dismiss job"
                      >
                        <ThumbsDown className="w-3.5 h-3.5" />
                      </button>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleBanCompany(job.company);
                        }}
                        aria-label={`Ban ${job.company} from all future results`}
                        className="p-2 rounded-xl border border-slate-200 bg-white hover:bg-rose-50 text-slate-400 hover:text-rose-600 hover:border-rose-200 transition-colors shadow-xs"
                        title={`Ban ${job.company}`}
                      >
                        <Ban className="w-3.5 h-3.5" />
                      </button>

                      <a
                        href={job.application_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="flex items-center gap-1.5 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-xl text-xs font-semibold transition-all shadow-xs active:scale-[0.98]"
                      >
                        <span>Apply</span>
                        <ExternalLink className="w-3 h-3 text-slate-300" />
                      </a>
                    </div>
                  </div>
                </div>
              );
            })}

            {/* Unified pagination inside bottom white container */}
            <div className="p-4 bg-white rounded-2xl border border-slate-200/90 shadow-sm">
              {renderPaginationControls()}
            </div>
          </div>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-200 p-12 text-center bg-white space-y-3 shadow-sm">
            <Briefcase className="w-8 h-8 text-slate-400 mx-auto" />
            <p className="text-base font-semibold text-slate-800">
              {totalCount > 0 ? "No signals matching active filter parameters on this page" : "No radar signals detected matching your filters"}
            </p>
            <p className="text-xs text-slate-500 max-w-sm mx-auto">
              {totalCount > 0
                ? "Check other page indices, adjust hub filters, or trigger a feed sync."
                : "Widen your freshness window, reset excluded companies, or sync fresh radar feeds."}
            </p>
            <div className="flex items-center justify-center gap-2 pt-2">
              {hasActiveFilters && (
                <button
                  onClick={resetAllFilters}
                  className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs font-semibold transition-colors"
                >
                  Reset All Filters
                </button>
              )}
              <Link
                href="/preferences"
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-800 rounded-xl text-xs font-semibold transition-colors border border-slate-200"
              >
                Configure Radar Settings
              </Link>
            </div>
          </div>
        )}
      </div>

      {/* Sync Telemetry Modal */}
      <SyncProgressModal
        isOpen={syncModalOpen}
        onClose={() => {
          setSyncModalOpen(false);
          // Don't reset syncJobId so user can re-open modal via "View Progress"
        }}
        jobId={syncJobId}
        source={syncSource}
        onCancelSync={() => {
          setSyncing(false);
          setSyncNotification({
            type: "error",
            message: "Sync was stopped by user.",
          });
        }}
        onSyncComplete={(summary) => {
          fetchJobs(1);
          setSyncing(false);
          if (summary) {
            if (summary.status === "completed" || summary.status === "partial_success") {
              const srcNames = summary.sources_synced?.join(", ") || syncSource;
              setSyncNotification({
                type: "success",
                message: `Sync completed: ${summary.total_discovered ?? 0} discovered, ${summary.canonical_saved ?? 0} added via ${srcNames}.`,
              });
            } else if (summary.status === "cancelled") {
              setSyncNotification({
                type: "error",
                message: "Sync stopped by user.",
              });
            } else if (summary.status === "failed" || summary.status === "blocked") {
              setSyncNotification({
                type: "error",
                message: summary.error || "Sync completed with warnings or no response.",
              });
            }
          }
        }}
      />

      {/* Job Detail Drawer */}
      <JobDetailDrawer
        jobId={selectedJobId}
        isOpen={detailDrawerOpen}
        onClose={() => {
          setDetailDrawerOpen(false);
          setSelectedJobId(null);
        }}
        onSave={(j) => {
          handleSave(j as JobItem);
        }}
        onUnsave={async (j) => {
          try {
            await fetch(`/api/saved-jobs/${j.id}`, {
              method: "DELETE",
            });
          } catch {
            // ignore
          }
        }}
        onReject={(j) => {
          handleReject(j as JobItem);
        }}
        onMarkApplied={(j) => {
          handleMarkApplied(j as JobItem);
        }}
        onBanCompany={(comp) => {
          handleBanCompany(comp);
        }}
      />

      {/* Preferences Applied Toast Feedback */}
      {prefToast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white border border-emerald-200 text-emerald-800 text-xs font-mono shadow-card-subtle animate-fade-in">
          <Check className="w-3.5 h-3.5 text-emerald-600" />
          <span>{prefToast}</span>
        </div>
      )}
    </div>
  );
}
