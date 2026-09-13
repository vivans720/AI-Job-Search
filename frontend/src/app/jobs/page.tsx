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
  Eye,
  Sliders,
} from "lucide-react";
import { SyncProgressModal } from "@/components/SyncProgressModal";
import JobDetailDrawer from "@/components/jobs/JobDetailDrawer";
import { loadUserPreferences } from "@/lib/preferences";

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
      const res = await fetch(`http://localhost:8000/api/v1/jobs/sync?source=${encodeURIComponent(src)}&freshness_hours=${syncFreshness}`, {
        method: "POST",
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
          message: `Sync job enqueued (${initialData.source || src}). Waiting for background worker...`,
        });

        // Poll for completion
        const jobId = initialData.job_id;
        let attempts = 0;
        const maxAttempts = 60; // 60 * 1.5s = 90s
        const pollInterval = setInterval(async () => {
          attempts += 1;
          try {
            const pollRes = await fetch(`http://localhost:8000/api/v1/jobs/sync/status/${jobId}`);
            if (pollRes.ok) {
              const statusData = await pollRes.json();
              if (statusData.status === "completed") {
                clearInterval(pollInterval);
                setSyncing(false);
                const stats = statusData.result || {};
                const saved = stats.canonical_saved || 0;
                const refreshed = stats.updated_existing || 0;
                const srcNames = stats.sources_synced?.join(", ") || src;
                setSyncNotification({
                  type: "success",
                  message: `Worker sync complete (${srcNames}): ${stats.total_discovered || 0} scanned, ${stats.fresh_jobs || 0} fresh, ${saved} new saved, ${refreshed} refreshed.`,
                });
                await fetchJobs(1);
              } else if (statusData.status === "failed") {
                clearInterval(pollInterval);
                setSyncing(false);
                setSyncNotification({
                  type: "error",
                  message: `Background worker sync failed: ${statusData.error || "Unknown error"}`,
                });
              } else {
                setSyncNotification({
                  type: "success",
                  message: `Worker state: ${statusData.status}... (${attempts * 1.5}s)`,
                });
              }
            }
          } catch {
            // keep polling
          }

          if (attempts >= maxAttempts) {
            clearInterval(pollInterval);
            setSyncing(false);
            setSyncNotification({
              type: "error",
              message: "Sync job polling timed out. Worker may still be running in background.",
            });
          }
        }, 1500);
      } else {
        // Synchronous fallback response
        const result = initialData;
        const saved = result.canonical_saved || 0;
        const refreshed = result.updated_existing || 0;
        const srcNames = result.sources_synced?.join(", ") || src;
        setSyncNotification({
          type: "success",
          message: `Sync complete (${srcNames}): ${result.total_discovered} scanned, ${result.fresh_jobs} fresh, ${saved} new saved, ${refreshed} refreshed.`,
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

  const handleRejectAllOnPage = async () => {
    if (filteredJobs.length === 0 || rejectingAll) return;
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

    // Minimum match threshold filtering (R1 & R2)
    if (matchThreshold !== null && matchThreshold > 0) {
      const rawScore = job.match?.overall_score ?? job.quality_score;
      if (rawScore !== undefined && rawScore !== null) {
        const normalizedScore = rawScore <= 1.0 && rawScore > 0 ? rawScore * 100 : rawScore;
        if (normalizedScore < matchThreshold) return false;
      }
    }

    return true;
  });

  const getBadgeStyle = (rec: string) => {
    switch (rec) {
      case "STRONG_MATCH":
        return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
      case "GOOD_MATCH":
        return "bg-teal-500/10 text-teal-400 border-teal-500/30";
      case "CONSIDER":
        return "bg-amber-500/10 text-amber-400 border-amber-500/30";
      case "LOW_PRIORITY":
        return "bg-orange-500/10 text-orange-400 border-orange-500/30";
      default:
        return "bg-zinc-500/10 text-zinc-400 border-zinc-500/20";
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
      <div className="flex flex-wrap items-center justify-between gap-4 pt-6 pb-4 border-t border-white/[0.06] text-xs">
        <div className="text-zinc-400">
          Showing <strong className="text-zinc-100 font-tabular">{(currentPage - 1) * pageSize + 1}</strong> to{" "}
          <strong className="text-zinc-100 font-tabular">{Math.min(currentPage * pageSize, totalCount)}</strong> of{" "}
          <strong className="text-zinc-100 font-tabular">{totalCount}</strong> listings
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
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-white/[0.08] bg-obsidian-900/60 hover:bg-obsidian-900 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
            <span>Previous</span>
          </button>

          <div className="flex items-center gap-1 px-2">
            {Array.from({ length: totalPages }, (_, i) => i + 1)
              .filter((p) => p === 1 || p === totalPages || Math.abs(p - currentPage) <= 1)
              .map((p, idx, arr) => {
                const prev = arr[idx - 1];
                const showEllipsis = prev && p - prev > 1;
                return (
                  <div key={p} className="flex items-center gap-1">
                    {showEllipsis && <span className="text-zinc-600 px-1">...</span>}
                    <button
                      onClick={() => {
                        fetchJobs(p);
                        window.scrollTo({ top: 0, behavior: "smooth" });
                      }}
                      disabled={loading}
                      className={`min-w-[32px] h-8 px-2 rounded-lg text-xs font-medium font-tabular transition-colors ${
                        currentPage === p
                          ? "bg-emerald-600 text-white font-semibold shadow-sm"
                          : "border border-white/[0.08] bg-obsidian-900/40 hover:bg-obsidian-900 text-zinc-400 hover:text-white"
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
            className="flex items-center gap-1 px-3 py-1.5 rounded-lg border border-white/[0.08] bg-obsidian-900/60 hover:bg-obsidian-900 disabled:opacity-40 disabled:cursor-not-allowed text-zinc-300 transition-colors"
          >
            <span>Next</span>
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6 pb-16">
      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-6 border-b border-white/[0.07]">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              DISCOVERY ENGINE
            </span>
            <span className="text-xs text-zinc-500">·</span>
            <span className="text-xs text-zinc-400 font-mono">≤{freshnessHours}h Freshness Window</span>
          </div>
          <h2 className="text-2xl font-bold tracking-tight text-zinc-100">Job Discovery Radar</h2>
          <p className="text-xs text-zinc-400">
            Search, evaluate, and track verified fresh tech opportunities with deterministic 6-dimension match analysis.
          </p>
        </div>

        {/* Sync Controls */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center rounded-xl bg-obsidian-900 border border-white/[0.08] p-1 shadow-sm text-xs">
            <select
              value={syncSource}
              onChange={(e) => setSyncSource(e.target.value)}
              disabled={syncing}
              className="bg-transparent text-zinc-300 px-2.5 py-1.5 rounded-lg focus:outline-none text-xs font-medium cursor-pointer border-none"
            >
              <option value="all" className="bg-obsidian-950 text-zinc-200">All Sources</option>
              <option value="linkedin" className="bg-obsidian-950 text-zinc-200">LinkedIn</option>
              <option value="naukri" className="bg-obsidian-950 text-zinc-200">Naukri</option>
              <option value="internshala" className="bg-obsidian-950 text-zinc-200">Internshala</option>
            </select>
            <select
              value={freshnessHours}
              onChange={(e) => {
                const val = Number(e.target.value);
                setSyncFreshness(val);
                setFreshnessHours(val);
              }}
              disabled={syncing}
              className="bg-transparent text-zinc-300 px-2 py-1.5 rounded-lg focus:outline-none text-xs font-medium cursor-pointer border-l border-white/[0.08]"
              title="Freshness Window"
            >
              <option value={1} className="bg-obsidian-950 text-zinc-200">1h fresh</option>
              <option value={4} className="bg-obsidian-950 text-zinc-200">4h fresh</option>
              <option value={8} className="bg-obsidian-950 text-zinc-200">8h fresh</option>
              <option value={12} className="bg-obsidian-950 text-zinc-200">12h fresh</option>
              <option value={16} className="bg-obsidian-950 text-zinc-200">16h fresh</option>
              <option value={24} className="bg-obsidian-950 text-zinc-200">24h fresh</option>
            </select>
            <button
              onClick={() => handleSyncLive()}
              disabled={syncing}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-white/[0.08] hover:bg-white/[0.12] active:scale-[0.98] disabled:opacity-50 text-zinc-200 rounded-lg text-xs font-medium transition-all shadow-surface-inset"
            >
              <RefreshCw className={`w-3.5 h-3.5 text-emerald-400 ${syncing ? "animate-spin" : ""}`} />
              <span>{syncing ? "Syncing..." : "Sync Radar"}</span>
            </button>
          </div>
        </div>
      </div>

      {/* Sync Notification Toast */}
      {syncNotification && (
        <div
          className={`p-3 rounded-xl border text-xs flex items-center justify-between shadow-lg ${
            syncNotification.type === "success"
              ? "bg-emerald-950/40 border-emerald-500/30 text-emerald-300"
              : "bg-rose-950/40 border-rose-500/30 text-rose-300"
          }`}
        >
          <span>{syncNotification.message}</span>
          <button
            onClick={() => setSyncNotification(null)}
            className="p-1 hover:bg-white/10 rounded text-zinc-400 hover:text-white transition-colors"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* Action Notification Toast (Save / Reject) with Undo */}
      {actionNotification && (
        <div
          className={`p-3.5 rounded-2xl border text-xs flex items-center justify-between shadow-xl backdrop-blur-xl ${
            actionNotification.type === "save"
              ? "border-emerald-500/30 bg-obsidian-900/90 text-emerald-300 shadow-surface-glow"
              : "border-rose-500/30 bg-obsidian-900/90 text-rose-300 shadow-rose-950/20"
          }`}
        >
          <div className="flex items-center gap-2.5">
            {actionNotification.type === "save" ? (
              <BookmarkCheck className="w-4 h-4 text-emerald-400 shrink-0" />
            ) : actionNotification.type === "reject_all" ? (
              <Ban className="w-4 h-4 text-rose-400 shrink-0" />
            ) : (
              <ThumbsDown className="w-4 h-4 text-rose-400 shrink-0" />
            )}
            <span className="font-medium text-zinc-200">{actionNotification.message}</span>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            {actionNotification.type === "save" && (
              <Link
                href="/saved"
                className="px-2.5 py-1 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/30 rounded-lg font-semibold text-xs transition-colors"
              >
                View in Pipeline
              </Link>
            )}
            <button
              onClick={handleUndoAction}
              className="px-2.5 py-1 bg-white/[0.08] hover:bg-white/[0.14] text-zinc-100 border border-white/[0.12] rounded-lg font-semibold text-xs transition-colors"
            >
              Undo
            </button>
            <button
              onClick={() => setActionNotification(null)}
              className="p-1 hover:bg-white/10 rounded-lg text-zinc-400 hover:text-white transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}



      {/* Search Input */}
      <div className="p-4 rounded-2xl bg-obsidian-900/70 border border-white/[0.08] shadow-surface-inset">
        <form onSubmit={handleSearchSubmit} className="flex items-center gap-2 p-1.5 rounded-xl bg-obsidian-950 border border-white/[0.08] focus-within:border-emerald-500/40 focus-within:ring-1 focus-within:ring-emerald-500/30 transition-all">
          <Search className="w-4 h-4 text-zinc-500 ml-2.5 shrink-0" />
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by role, tech stack, company, or keyword..."
            className="bg-transparent text-zinc-100 text-xs focus:outline-none flex-1 px-2.5 py-1.5 placeholder:text-zinc-500"
          />
          {query && (
            <button
              type="button"
              onClick={clearQuery}
              className="p-1 rounded-md text-zinc-400 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            type="submit"
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white rounded-lg text-xs font-semibold transition-all shadow-sm shrink-0"
          >
            Search
          </button>
        </form>
      </div>

      {/* Streamlined Faceted Filter Control Bar (Clean Architecture) */}
      <div className="p-4 rounded-2xl bg-obsidian-900/70 border border-white/[0.08] shadow-surface-inset space-y-4">
        {/* Location quick actions + searchable multi-select */}
        <div className="space-y-2">
          <div className="flex items-center justify-between text-xs">
            <span className="text-[11px] font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
              <MapPin className="w-3.5 h-3.5 text-emerald-400" />
              <span>Location</span>
            </span>
            {selectedLocations.length > 0 && (
              <span className="text-[11px] text-emerald-400 font-medium">
                {selectedLocations.length} location{selectedLocations.length === 1 ? "" : "s"} selected
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 flex-wrap text-xs">
            <button
              onClick={clearLocations}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center gap-1.5 whitespace-nowrap ${
                selectedLocations.length === 0
                  ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm"
                  : "bg-obsidian-950 text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] border border-white/[0.05]"
              }`}
            >
              <span>All Locations</span>
              <span className={`px-1.5 py-0.2 rounded-full text-[10px] font-tabular font-semibold ${
                selectedLocations.length === 0 ? "bg-emerald-400/20 text-emerald-200" : "bg-white/[0.06] text-zinc-500"
              }`}>
                {counts.all}
              </span>
            </button>

            <div className="relative min-w-[220px] flex-1 max-w-md" ref={locationDropdownRef}>
              <button
                type="button"
                onClick={() => setLocationDropdownOpen((open) => !open)}
                className={`w-full px-3 py-1.5 rounded-lg text-xs font-medium transition-all flex items-center justify-between gap-2 ${
                  selectedLocations.length > 0
                    ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 shadow-sm"
                    : "bg-obsidian-950 text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.04] border border-white/[0.05]"
                }`}
              >
                <span className="truncate">
                  {selectedLocations.length > 0
                    ? `${selectedLocations.length} selected`
                    : "Search locations"}
                </span>
                <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${locationDropdownOpen ? "rotate-180" : ""}`} />
              </button>

              {locationDropdownOpen && (
                <div className="absolute z-30 mt-1.5 w-full min-w-[260px] rounded-xl border border-white/[0.1] bg-obsidian-950 shadow-xl overflow-hidden">
                  <div className="p-2 border-b border-white/[0.06]">
                    <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-lg bg-obsidian-900 border border-white/[0.08]">
                      <Search className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
                      <input
                        type="text"
                        value={locationSearch}
                        onChange={(e) => setLocationSearch(e.target.value)}
                        placeholder="Filter locations..."
                        className="bg-transparent text-zinc-100 text-xs focus:outline-none flex-1 placeholder:text-zinc-500"
                      />
                    </div>
                  </div>
                  <div className="max-h-56 overflow-y-auto py-1">
                    {visibleLocations.length === 0 ? (
                      <p className="px-3 py-4 text-xs text-zinc-500 text-center">
                        {availableLocations.length === 0 ? "No locations in current results" : "No matching locations"}
                      </p>
                    ) : (
                      visibleLocations.map((loc) => {
                        const checked = selectedLocations.includes(loc);
                        const count = locationCounts[loc] ?? 0;
                        const isTopHub = TOP_HUBS.some(h => h.toLowerCase() === loc.toLowerCase());
                        return (
                          <button
                            key={loc}
                            type="button"
                            onClick={() => toggleLocation(loc)}
                            className="w-full flex items-center gap-2 px-3 py-1.5 text-left hover:bg-white/[0.04] transition-colors"
                          >
                            <span
                              className={`w-3.5 h-3.5 rounded border flex items-center justify-center shrink-0 ${
                                checked
                                  ? "bg-emerald-500/20 border-emerald-500/50 text-emerald-300"
                                  : "border-white/[0.15] text-transparent"
                              }`}
                            >
                              <Check className="w-2.5 h-2.5" />
                            </span>
                            <span className="flex-1 text-xs text-zinc-200 truncate" title={loc}>
                              {loc}
                            </span>
                            {isTopHub && (
                              <span className="px-1 py-0.2 rounded text-[9px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                                Hub
                              </span>
                            )}
                            <span className="px-1.5 py-0.2 rounded-full text-[10px] font-tabular font-semibold bg-white/[0.06] text-zinc-500">
                              {count}
                            </span>
                          </button>
                        );
                      })
                    )}
                  </div>
                  {selectedLocations.length > 0 && (
                    <div className="p-2 border-t border-white/[0.06]">
                      <button
                        type="button"
                        onClick={clearLocations}
                        className="w-full px-2 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-rose-400 hover:bg-white/[0.04] transition-colors"
                      >
                        Clear Selection
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Dropdown Filters & Controls Row */}
        <div className="pt-3 border-t border-white/[0.06] grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2.5 text-xs">
          {/* Role Type Dropdown */}
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block">Role Type</label>
            <select
              value={typeFilter}
              onChange={(e) => setTypeFilter(e.target.value as "ALL" | "JOBS" | "INTERNSHIPS")}
              className="w-full bg-obsidian-950 text-zinc-200 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-emerald-500/40"
            >
              <option value="ALL">All ({counts.all})</option>
              <option value="JOBS">Full-time ({counts.jobsCount})</option>
              <option value="INTERNSHIPS">Internships ({counts.internCount})</option>
            </select>
          </div>

          {/* Source Board Dropdown */}
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block">Source Board</label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value as "ALL" | "INTERNSHALA" | "NAUKRI" | "LINKEDIN")}
              className="w-full bg-obsidian-950 text-zinc-200 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-emerald-500/40"
            >
              <option value="ALL">All Sources</option>
              <option value="LINKEDIN">LinkedIn ({counts.linkedinCount})</option>
              <option value="NAUKRI">Naukri ({counts.naukriCount})</option>
              <option value="INTERNSHALA">Internshala ({counts.internshalaCount})</option>
            </select>
          </div>

          {/* Freshness Window */}
          <div className="space-y-1 col-span-2 sm:col-span-1 lg:col-span-2">
            <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block">Freshness</label>
            <div className="grid grid-cols-6 gap-1">
              {[1, 4, 8, 12, 16, 24].map((h) => (
                <button
                  key={h}
                  onClick={() => {
                    setFreshnessHours(h);
                    setSyncFreshness(h);
                  }}
                  className={`py-1.5 rounded-lg text-xs font-medium transition-all text-center ${
                    freshnessHours === h
                      ? "bg-white/[0.12] text-zinc-100 border border-white/[0.2] shadow-sm"
                      : "bg-obsidian-950 text-zinc-400 hover:text-zinc-200 border border-white/[0.06]"
                  }`}
                >
                  ≤{h}h
                </button>
              ))}
            </div>
          </div>

          {/* Experience Filter */}
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block">Experience</label>
            <select
              value={experienceFilter}
              onChange={(e) => setExperienceFilter(e.target.value)}
              className="w-full bg-obsidian-950 text-zinc-200 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-emerald-500/40"
            >
              <option value="ALL">Any Experience ({counts.all})</option>
              <option value="FRESHER">Freshers & Interns (0y) ({counts.fresherCount})</option>
              <option value="0_1">0-1 Years ({counts.exp01Count})</option>
              <option value="1_2">1-2 Years ({counts.exp12Count})</option>
              <option value="2_3">2-3 Years ({counts.exp23Count})</option>
              <option value="3_PLUS">3+ Years</option>
            </select>
          </div>

          {/* Sort By */}
          <div className="space-y-1">
            <label className="text-[10px] font-semibold text-zinc-500 uppercase tracking-wider block">Sort Ranking</label>
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as "match" | "freshness")}
              className="w-full bg-obsidian-950 text-zinc-200 border border-white/[0.08] rounded-lg px-2.5 py-1.5 text-xs focus:outline-none focus:border-emerald-500/40"
            >
              <option value="match">Best Match Fit</option>
              <option value="freshness">Most Recent</option>
            </select>
          </div>
        </div>

        {/* Filter Controls */}
        <div className="pt-3 border-t border-white/[0.06] flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 flex-wrap">
            {selectedSkills.map((sk) => (
              <span
                key={sk}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 text-xs font-medium"
              >
                <span>Skill: {sk}</span>
                <button
                  onClick={() => setSelectedSkills((prev) => prev.filter((s) => s !== sk))}
                  className="hover:text-white"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            ))}

            <button
              onClick={handleApplyMyPreferences}
              disabled={applyingPrefs}
              className="flex items-center gap-1.5 text-xs text-emerald-400 hover:text-emerald-300 border border-emerald-500/30 hover:border-emerald-500/50 bg-emerald-500/10 hover:bg-emerald-500/20 transition-all px-2.5 py-1 rounded-lg font-medium shadow-sm disabled:opacity-50"
              title="Apply saved search preferences to active filters"
            >
              {applyingPrefs ? (
                <RefreshCw className="w-3.5 h-3.5 animate-spin text-emerald-400" />
              ) : (
                <Sliders className="w-3.5 h-3.5 text-emerald-400" />
              )}
              <span>{applyingPrefs ? "Applying..." : "My Preferences"}</span>
            </button>

            {matchThreshold !== null && matchThreshold > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-300 border border-emerald-500/25 text-xs font-medium">
                <span>Min Match: {matchThreshold}%</span>
                <button
                  onClick={() => setMatchThreshold(null)}
                  className="hover:text-emerald-100"
                  title="Remove threshold filter"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {excludedCompanies.length > 0 && (
              <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-rose-500/10 text-rose-300 border border-rose-500/25 text-xs font-medium">
                <span>Excluded: {excludedCompanies.length} companies</span>
                <button
                  onClick={() => setExcludedCompanies([])}
                  className="hover:text-rose-100"
                  title="Clear excluded companies filter"
                >
                  <X className="w-3 h-3" />
                </button>
              </span>
            )}

            {hasActiveFilters && (
              <button
                onClick={resetAllFilters}
                className="flex items-center gap-1 text-xs text-zinc-400 hover:text-rose-400 transition-colors px-2 py-1 rounded hover:bg-white/[0.04]"
                title="Reset all search filters"
              >
                <RotateCcw className="w-3 h-3" />
                <span>Reset All Filters</span>
              </button>
            )}

            {filteredJobs.length > 0 && (
              <button
                onClick={handleRejectAllOnPage}
                disabled={rejectingAll}
                className="flex items-center gap-1.5 text-xs text-rose-400/90 hover:text-rose-300 border border-rose-500/20 hover:border-rose-500/40 bg-rose-500/10 hover:bg-rose-500/15 transition-all px-2.5 py-1 rounded-lg font-medium disabled:opacity-50"
                title="Reject all jobs on this page and advance"
              >
                <Ban className="w-3 h-3" />
                <span>{rejectingAll ? "Rejecting..." : `Reject All on Page (${filteredJobs.length})`}</span>
              </button>
            )}
          </div>

          <div className="text-xs text-zinc-400">
            Showing <strong className="text-zinc-100">{filteredJobs.length}</strong> of{" "}
            <strong className="text-zinc-100">{totalCount > 0 ? totalCount : jobs.length}</strong> listings
            {totalCount > pageSize && (
              <span> (Page {currentPage} of {Math.ceil(totalCount / pageSize)})</span>
            )}
          </div>
        </div>
      </div>

      {/* Jobs List */}
      {loading ? (
        <div className="py-20 text-center text-xs text-zinc-500 rounded-2xl bg-obsidian-900/40 border border-white/[0.06]">
          Loading fresh listings from database...
        </div>
      ) : filteredJobs.length > 0 ? (
        <div className="space-y-3.5">
          {filteredJobs.map((job) => {
            const match = job.match;
            const monogram = getMonogram(job.company);

            return (
              <div
                key={job.id}
                className="rounded-2xl bg-obsidian-900/60 border border-white/[0.08] shadow-surface-inset p-5 hover:border-white/[0.16] hover:bg-obsidian-900/90 transition-all duration-200 group space-y-4"
              >
                {/* Header Row */}
                <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                  {/* Left: Monogram, Title, Meta */}
                  <div className="flex items-start gap-3.5">
                    <div className="w-11 h-11 rounded-xl bg-gradient-to-br from-zinc-800 to-zinc-900 border border-white/[0.08] flex items-center justify-center font-bold text-sm text-zinc-200 shadow-sm shrink-0 mt-0.5">
                      {monogram}
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3
                          onClick={() => {
                            setSelectedJobId(job.id);
                            setDetailDrawerOpen(true);
                          }}
                          className="text-base font-semibold text-zinc-100 group-hover:text-emerald-400 transition-colors cursor-pointer hover:underline underline-offset-2"
                        >
                          {job.title}
                        </h3>

                        {job.source && (
                          <span
                            className={`px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider ${
                              job.source === "linkedin"
                                ? "bg-blue-500/10 text-blue-400 border border-blue-500/25"
                                : job.source === "naukri"
                                ? "bg-indigo-500/10 text-indigo-400 border border-indigo-500/25"
                                : job.source === "internshala"
                                ? "bg-sky-500/10 text-sky-400 border border-sky-500/25"
                                : "bg-emerald-500/10 text-emerald-400 border border-emerald-500/25"
                            }`}
                          >
                            {job.source}
                          </span>
                        )}

                        {job.employment_type === "INTERNSHIP" && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase tracking-wider bg-purple-500/10 text-purple-400 border border-purple-500/25">
                            Internship
                          </span>
                        )}

                        {job.quality_score !== undefined && job.quality_score > 0 && (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold font-tabular bg-white/[0.04] text-zinc-400 border border-white/[0.06]">
                            QS {Math.round(job.quality_score)}%
                          </span>
                        )}

                        {match && (
                          <div className="flex items-center gap-1.5 flex-wrap">
                            <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold font-tabular border ${getBadgeStyle(match.recommendation)}`}>
                              {match.overall_score}% {match.recommendation.replace("_", " ")}
                            </span>
                            {match.confidence_label && (
                              <span
                                className={`px-2 py-0.5 rounded text-[10px] font-semibold tracking-wider uppercase border ${
                                  match.confidence_label === "HIGH"
                                    ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/20"
                                    : match.confidence_label === "MEDIUM"
                                    ? "bg-amber-500/10 text-amber-400 border-amber-500/20"
                                    : "bg-rose-500/10 text-rose-400 border-rose-500/20"
                                }`}
                                title={`Matching Confidence: ${match.confidence !== undefined ? Math.round(match.confidence * 100) : 0}% (${match.confidence_label})`}
                              >
                                {match.confidence_label} Conf
                              </span>
                            )}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2 text-xs text-zinc-400 flex-wrap">
                        <span className="font-medium text-zinc-300">{job.company}</span>
                        <span className="text-zinc-600">·</span>
                        <span className="flex items-center gap-1">
                          <MapPin className="w-3 h-3 text-zinc-500" />
                          <span>{job.location}</span>
                          <span className="text-zinc-500">({job.remote_type})</span>
                        </span>
                        <span className="text-zinc-600">·</span>
                        <span>Exp: {job.experience}</span>
                        <span className="text-zinc-600">·</span>
                        <span className="text-emerald-400 font-medium">{job.salary || "Not disclosed"}</span>
                        <span className="text-zinc-600">·</span>
                        <span className="text-zinc-500 font-mono">
                          {job.age_hours !== null ? `${job.age_hours}h ago` : "Fresh"}
                        </span>
                      </div>

                      {/* Multi-source merged attribution */}
                      {job.other_sources && job.other_sources.length > 0 && (
                        <div className="flex items-center gap-1.5 text-xs text-zinc-500 pt-0.5">
                          <span className="text-[11px]">Also discovered on:</span>
                          {job.other_sources.map((os, idx) => (
                            <span
                              key={idx}
                              className="px-1.5 py-0.2 rounded bg-obsidian-950 border border-white/[0.06] text-[10px] text-zinc-400 capitalize"
                            >
                              {os.source}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Right Actions */}
                  <div className="flex items-center gap-2 shrink-0 self-end md:self-start">
                    <button
                      onClick={() => {
                        setSelectedJobId(job.id);
                        setDetailDrawerOpen(true);
                      }}
                      className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-obsidian-950 border border-white/[0.08] text-zinc-300 hover:text-white hover:border-white/[0.18] transition-colors text-xs font-medium"
                      title="Inspect full job description and match evidence"
                    >
                      <Eye className="w-3.5 h-3.5 text-zinc-400" />
                      <span>Details</span>
                    </button>
                    <button
                      onClick={() => handleSave(job)}
                      className="p-2 rounded-xl bg-obsidian-950 border border-white/[0.08] text-zinc-400 hover:text-emerald-400 hover:border-emerald-500/30 hover:bg-emerald-500/10 transition-colors"
                      title="Bookmark job (Save to Pipeline)"
                    >
                      <Bookmark className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleReject(job)}
                      className="p-2 rounded-xl bg-obsidian-950 border border-white/[0.08] text-zinc-400 hover:text-rose-400 hover:border-rose-500/30 hover:bg-rose-500/10 transition-colors"
                      title="Hide job (Will not show in discovery)"
                    >
                      <ThumbsDown className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => handleMarkApplied(job)}
                      className="flex items-center gap-1 px-2.5 py-2 rounded-xl bg-amber-500/10 hover:bg-amber-500/20 text-amber-300 border border-amber-500/25 transition-all text-xs font-semibold"
                      title="Mark as Applied ✓ directly"
                    >
                      <Check className="w-3.5 h-3.5" />
                      <span>Applied ✓</span>
                    </button>
                    <a
                      href={job.application_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1.5 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 active:scale-[0.98] text-white rounded-xl text-xs font-semibold transition-all shadow-sm"
                    >
                      <span>Apply</span>
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                </div>

                {/* Skills tags row */}
                <div className="flex flex-wrap gap-1.5 pt-1">
                  {job.required_skills.map((s) => {
                    const sLower = s.toLowerCase();
                    const isMatched = match?.matched_skills?.some((m) => m.toLowerCase() === sLower);

                    const isSelected = selectedSkills.includes(s);

                    return (
                      <span
                        key={s}
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedSkills((prev) =>
                            prev.includes(s) ? prev.filter((item) => item !== s) : [...prev, s]
                          );
                        }}
                        className={`px-2.5 py-0.5 rounded-lg text-xs font-medium transition-colors cursor-pointer hover:border-emerald-500/50 ${
                          isSelected
                            ? "bg-emerald-500 text-obsidian-950 font-bold border border-emerald-400"
                            : isMatched
                            ? "bg-emerald-500/15 text-emerald-300 border border-emerald-500/30 font-semibold"
                            : "bg-obsidian-950 text-zinc-400 border border-white/[0.06]"
                        }`}
                        title={isSelected ? "Click to remove skill filter" : "Click to filter listings by this skill"}
                      >
                        {s} {isMatched && !isSelected && "✓"}
                      </span>
                    );
                  })}
                </div>
              </div>
            );
          })}

          {/* Pagination Controls */}
          {renderPaginationControls()}
        </div>
      ) : (
        <div className="space-y-6">
          <div className="rounded-2xl border border-dashed border-white/[0.1] p-16 text-center bg-obsidian-900/30 space-y-3">
            <Briefcase className="w-8 h-8 text-zinc-500 mx-auto" />
            <p className="text-sm font-medium text-zinc-300">
              {totalCount > 0 ? "No opportunities match active filters on this page" : "No opportunities found matching your filters"}
            </p>
            <p className="text-xs text-zinc-500 max-w-sm mx-auto">
              {totalCount > 0
                ? "Try checking other pages, clearing some filters, or syncing new jobs."
                : "Try adjusting location segments, clearing skill tags, or resetting your filter criteria."}
            </p>
            <div className="flex items-center justify-center gap-2 pt-2">
              {hasActiveFilters && (
                <button
                  onClick={resetAllFilters}
                  className="px-4 py-2 bg-white/[0.08] hover:bg-white/[0.12] text-zinc-200 rounded-xl text-xs font-medium transition-colors border border-white/[0.08]"
                >
                  Reset All Filters
                </button>
              )}
              <Link
                href="/preferences"
                className="px-4 py-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium transition-colors border border-emerald-500/25"
              >
                Configure Preferences
              </Link>
            </div>
          </div>

          {/* Fallback pagination if listings exist on other pages */}
          {renderPaginationControls()}
        </div>
      )}

      {/* Sync Telemetry Modal */}
      <SyncProgressModal
        isOpen={syncModalOpen}
        onClose={() => setSyncModalOpen(false)}
        jobId={syncJobId}
        source={syncSource}
        onSyncComplete={() => {
          fetchJobs(1);
        }}
      />

      {/* Phase 46 & 47: Job Detail Drawer */}
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
            await fetch(`http://localhost:8000/api/v1/jobs/${j.id}/saved`, {
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
      />

      {/* Preferences Applied Toast Feedback (R2) */}
      {prefToast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 px-4 py-2.5 rounded-xl bg-obsidian-900/95 border border-emerald-500/40 text-emerald-300 text-xs font-medium shadow-2xl backdrop-blur-md animate-fade-in">
          <Check className="w-4 h-4 text-emerald-400" />
          <span>{prefToast}</span>
        </div>
      )}
    </div>
  );
}
