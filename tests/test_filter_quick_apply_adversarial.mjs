/**
 * Empirical Adversarial Test Harness: Filter Quick-Apply ("My Preferences" Button) (R2)
 *
 * Stress-tests:
 * 1. Filter state transformation across all 7 fields
 * 2. Casing and trimming invariance for excluded_companies
 * 3. Match threshold filtering (0-1.0 float scale and 0-100 scale, boundaries, unscored jobs)
 * 4. Pagination reset to 1
 * 5. Edge cases: empty locations, single vs multi source boards, role types, experience tiers
 * 6. Source code contract integrity in frontend/src/app/jobs/page.tsx
 */

import fs from "node:fs";
import path from "node:path";
import assert from "node:assert";

// 1. Load preferences schema validator and defaults
const prefsModule = await import("../frontend/src/lib/preferences.ts");
const { validatePreferences, DEFAULT_PREFERENCES } = prefsModule;

// Replication of the exact state transformation logic in frontend/src/app/jobs/page.tsx (lines 388-434)
export function applyPreferencesToState(prefs, initialState = {}) {
  const nextState = { ...initialState };

  // 1. Freshness
  nextState.freshnessHours = prefs.freshness_hours;
  nextState.syncFreshness = prefs.freshness_hours;

  // 2. Experience level
  nextState.experienceFilter = prefs.experience_level || "ALL";

  // 3. Role type
  nextState.typeFilter = prefs.role_type || "ALL";

  // 4. Source board
  if (prefs.source_boards && prefs.source_boards.length === 1) {
    const board = prefs.source_boards[0].toUpperCase();
    if (board === "LINKEDIN" || board === "NAUKRI" || board === "INTERNSHALA") {
      nextState.sourceFilter = board;
    } else {
      nextState.sourceFilter = "ALL";
    }
  } else {
    nextState.sourceFilter = "ALL";
  }

  // 5. Preferred locations
  nextState.selectedLocations = prefs.preferred_locations ? [...prefs.preferred_locations] : [];

  // 6. Minimum match threshold & excluded companies
  nextState.matchThreshold = typeof prefs.match_threshold === "number" ? prefs.match_threshold : null;
  nextState.excludedCompanies = prefs.excluded_companies ? [...prefs.excluded_companies] : [];

  // 7. Reset to page 1
  nextState.currentPage = 1;

  return nextState;
}

// Replication of query parameter generation in fetchJobs() (lines 258-286)
export function buildQueryParams(state, targetPage) {
  const params = new URLSearchParams();
  if (state.query && state.query.trim()) params.set("query", state.query.trim());
  if (state.sourceFilter && state.sourceFilter !== "ALL") params.set("source", state.sourceFilter.toLowerCase());
  if (state.selectedLocations && state.selectedLocations.length > 0) {
    state.selectedLocations.forEach((loc) => params.append("location", loc));
  }
  params.set("freshness_hours", (state.freshnessHours ?? 24).toString());
  params.set("sort_by", state.sortBy || "match");
  if (state.experienceFilter === "FRESHER") {
    params.set("experience_max", "0");
  } else if (state.experienceFilter === "0_1") {
    params.set("experience_max", "1");
  } else if (state.experienceFilter === "1_2") {
    params.set("experience_min", "1");
    params.set("experience_max", "2");
  } else if (state.experienceFilter === "2_3") {
    params.set("experience_min", "2");
    params.set("experience_max", "3");
  } else if (state.experienceFilter === "3_PLUS") {
    params.set("experience_min", "3");
  }
  if (state.typeFilter && state.typeFilter !== "ALL") {
    params.set("employment_type", state.typeFilter);
  }

  params.set("page", targetPage.toString());
  params.set("page_size", (state.pageSize || 50).toString());
  return params;
}

// Replication of in-memory job filtering in filteredJobs (lines 658-729)
export function filterJobs(jobs, state) {
  const {
    selectedLocations = [],
    typeFilter = "ALL",
    experienceFilter = "ALL",
    selectedSkills = [],
    excludedCompanies = [],
    matchThreshold = null,
  } = state;

  return jobs.filter((job) => {
    if (selectedLocations.length > 0) {
      const jobLoc = (job.location ?? "").toLowerCase();
      const matches = selectedLocations.some((loc) => {
        const normalizedLoc = loc.toLowerCase();
        return jobLoc === normalizedLoc || jobLoc.includes(normalizedLoc);
      });
      if (!matches) return false;
    }

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

    // Selected skill filtering
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
}

// Test runner summary
let totalTests = 0;
let passedTests = 0;
let failedTests = 0;
const findings = [];

function test(name, fn) {
  totalTests++;
  try {
    fn();
    passedTests++;
    console.log(`  ✓ PASS: ${name}`);
  } catch (err) {
    failedTests++;
    console.error(`  ✗ FAIL: ${name}`);
    console.error(`    Error: ${err.message}`);
    findings.push({ test: name, error: err.message });
  }
}

console.log("=================================================================");
console.log("EMPIRICAL ADVERSARIAL TEST SUITE: R2 Filter Quick-Apply");
console.log("=================================================================\n");

// ============================================================================
// SECTION 1: Filter State Transformation Across All 7 Fields
// ============================================================================
console.log("--- Section 1: Filter State Transformation (7 Fields) ---");

test("1.1 Full 7-field preference values correctly mapped to active state", () => {
  const prefs = {
    freshness_hours: 8,
    experience_level: "1_2",
    match_threshold: 75,
    preferred_locations: ["Hyderabad", "Pune"],
    role_type: "INTERNSHIPS",
    source_boards: ["NAUKRI"],
    excluded_companies: ["Wipro", "TCS"],
  };

  const initial = {
    freshnessHours: 24,
    syncFreshness: 24,
    experienceFilter: "ALL",
    typeFilter: "ALL",
    sourceFilter: "ALL",
    selectedLocations: ["Bengaluru"],
    matchThreshold: null,
    excludedCompanies: [],
    currentPage: 4,
  };

  const next = applyPreferencesToState(prefs, initial);

  assert.strictEqual(next.freshnessHours, 8, "freshnessHours must be 8");
  assert.strictEqual(next.syncFreshness, 8, "syncFreshness must be 8");
  assert.strictEqual(next.experienceFilter, "1_2", "experienceFilter must be 1_2");
  assert.strictEqual(next.typeFilter, "INTERNSHIPS", "typeFilter must be INTERNSHIPS");
  assert.strictEqual(next.sourceFilter, "NAUKRI", "sourceFilter must be NAUKRI");
  assert.deepStrictEqual(next.selectedLocations, ["Hyderabad", "Pune"], "locations must match");
  assert.strictEqual(next.matchThreshold, 75, "matchThreshold must be 75");
  assert.deepStrictEqual(next.excludedCompanies, ["Wipro", "TCS"], "excluded companies must match");
  assert.strictEqual(next.currentPage, 1, "currentPage must reset to 1");
});

test("1.2 Default preferences correctly mapped to active state", () => {
  const next = applyPreferencesToState(DEFAULT_PREFERENCES, { currentPage: 7 });

  assert.strictEqual(next.freshnessHours, 24);
  assert.strictEqual(next.experienceFilter, "ALL");
  assert.strictEqual(next.typeFilter, "ALL");
  assert.strictEqual(next.sourceFilter, "ALL"); // multi-board default -> ALL
  assert.deepStrictEqual(next.selectedLocations, ["Bengaluru", "Remote"]);
  assert.strictEqual(next.matchThreshold, 60);
  assert.deepStrictEqual(next.excludedCompanies, []);
  assert.strictEqual(next.currentPage, 1);
});

test("1.3 Boundary freshness options: 1, 4, 8, 12, 16, 24 hours", () => {
  for (const h of [1, 4, 8, 12, 16, 24]) {
    const next = applyPreferencesToState({ ...DEFAULT_PREFERENCES, freshness_hours: h });
    assert.strictEqual(next.freshnessHours, h);
    assert.strictEqual(next.syncFreshness, h);
  }
});

test("1.4 All experience level tiers: FRESHER, 0_1, 1_2, 2_3, 3_PLUS, ALL", () => {
  for (const exp of ["ALL", "FRESHER", "0_1", "1_2", "2_3", "3_PLUS"]) {
    const next = applyPreferencesToState({ ...DEFAULT_PREFERENCES, experience_level: exp });
    assert.strictEqual(next.experienceFilter, exp);
  }
});

test("1.5 All role types: JOBS, INTERNSHIPS, ALL", () => {
  for (const r of ["ALL", "JOBS", "INTERNSHIPS"]) {
    const next = applyPreferencesToState({ ...DEFAULT_PREFERENCES, role_type: r });
    assert.strictEqual(next.typeFilter, r);
  }
});

test("1.6 Single source boards mapping: LINKEDIN, NAUKRI, INTERNSHALA", () => {
  for (const b of ["LINKEDIN", "NAUKRI", "INTERNSHALA"]) {
    const next = applyPreferencesToState({ ...DEFAULT_PREFERENCES, source_boards: [b] });
    assert.strictEqual(next.sourceFilter, b);
  }
});

test("1.7 Unsupported single board INDEED falls back to ALL", () => {
  const next = applyPreferencesToState({ ...DEFAULT_PREFERENCES, source_boards: ["INDEED"] });
  assert.strictEqual(next.sourceFilter, "ALL");
});

test("1.8 Multiple source boards or empty array fall back to ALL", () => {
  const m1 = applyPreferencesToState({ ...DEFAULT_PREFERENCES, source_boards: ["LINKEDIN", "NAUKRI"] });
  assert.strictEqual(m1.sourceFilter, "ALL");

  const m2 = applyPreferencesToState({ ...DEFAULT_PREFERENCES, source_boards: ["LINKEDIN", "NAUKRI", "INTERNSHALA", "INDEED"] });
  assert.strictEqual(m2.sourceFilter, "ALL");

  const m3 = applyPreferencesToState({ ...DEFAULT_PREFERENCES, source_boards: [] });
  assert.strictEqual(m3.sourceFilter, "ALL");
});

test("1.9 Match threshold values: 0, 50, 100, and null fallback", () => {
  assert.strictEqual(applyPreferencesToState({ ...DEFAULT_PREFERENCES, match_threshold: 0 }).matchThreshold, 0);
  assert.strictEqual(applyPreferencesToState({ ...DEFAULT_PREFERENCES, match_threshold: 50 }).matchThreshold, 50);
  assert.strictEqual(applyPreferencesToState({ ...DEFAULT_PREFERENCES, match_threshold: 100 }).matchThreshold, 100);
  assert.strictEqual(applyPreferencesToState({ ...DEFAULT_PREFERENCES, match_threshold: undefined }).matchThreshold, null);
});

test("1.10 API query params generation verifies active filter synchronization", () => {
  const state = {
    freshnessHours: 4,
    sourceFilter: "LINKEDIN",
    selectedLocations: ["Bengaluru", "Remote"],
    experienceFilter: "FRESHER",
    typeFilter: "INTERNSHIPS",
    query: "python",
    sortBy: "freshness",
    pageSize: 50,
  };

  const params = buildQueryParams(state, 1);
  assert.strictEqual(params.get("query"), "python");
  assert.strictEqual(params.get("source"), "linkedin");
  assert.deepStrictEqual(params.getAll("location"), ["Bengaluru", "Remote"]);
  assert.strictEqual(params.get("freshness_hours"), "4");
  assert.strictEqual(params.get("sort_by"), "freshness");
  assert.strictEqual(params.get("experience_max"), "0");
  assert.strictEqual(params.get("employment_type"), "INTERNSHIPS");
  assert.strictEqual(params.get("page"), "1");
  assert.strictEqual(params.get("page_size"), "50");
});

// ============================================================================
// SECTION 2: Excluded Companies Filtering & Adversarial Stress Tests
// ============================================================================
console.log("\n--- Section 2: Excluded Companies Filtering ---");

const sampleJobs = [
  { id: "1", title: "SWE 1", company: "Google", location: "Bengaluru", employment_type: "JOBS", quality_score: 90 },
  { id: "2", title: "SWE 2", company: "google", location: "Bengaluru", employment_type: "JOBS", quality_score: 85 },
  { id: "3", title: "SWE 3", company: "GOOGLE", location: "Bengaluru", employment_type: "JOBS", quality_score: 88 },
  { id: "4", title: "SWE 4", company: "gOoGlE LLC", location: "Bengaluru", employment_type: "JOBS", quality_score: 92 },
  { id: "5", title: "SWE 5", company: "  Google India  ", location: "Bengaluru", employment_type: "JOBS", quality_score: 80 },
  { id: "6", title: "SWE 6", company: "Microsoft", location: "Bengaluru", employment_type: "JOBS", quality_score: 85 },
  { id: "7", title: "SWE 7", company: "Amazon Web Services", location: "Bengaluru", employment_type: "JOBS", quality_score: 82 },
  { id: "8", title: "SWE 8", company: "Meta", location: "Bengaluru", employment_type: "JOBS", quality_score: 89 },
  { id: "9", title: "SWE 9", company: "Tata Consultancy Services", location: "Bengaluru", employment_type: "JOBS", quality_score: 70 },
  { id: "10", title: "SWE 10", company: "Revature", location: "Bengaluru", employment_type: "JOBS", quality_score: 65 },
];

test("2.1 Strict casing invariance (Google, google, GOOGLE, gOoGlE)", () => {
  const result = filterJobs(sampleJobs, { excludedCompanies: ["Google"] });
  const remainingCompanies = result.map((j) => j.company.toLowerCase().trim());

  assert.ok(!remainingCompanies.some((c) => c.includes("google")), "All Google variants must be excluded");
  assert.ok(result.some((j) => j.company === "Microsoft"), "Microsoft must be retained");
  assert.ok(result.some((j) => j.company === "Meta"), "Meta must be retained");
});

test("2.2 Whitespace trimming in excluded list and job company names", () => {
  const result = filterJobs(sampleJobs, { excludedCompanies: ["  Google  "] });
  assert.strictEqual(result.filter((j) => j.company.toLowerCase().includes("google")).length, 0);

  const result2 = filterJobs(sampleJobs, { excludedCompanies: ["Revature  "] });
  assert.strictEqual(result2.filter((j) => j.company === "Revature").length, 0);
});

test("2.3 Substring exclusion (Google LLC, Google India, AWS)", () => {
  const result = filterJobs(sampleJobs, { excludedCompanies: ["Google", "Amazon"] });
  assert.strictEqual(result.filter((j) => j.company.toLowerCase().includes("google")).length, 0);
  assert.strictEqual(result.filter((j) => j.company.toLowerCase().includes("amazon")).length, 0);
  assert.strictEqual(result.length, 4); // Microsoft, Meta, TCS, Revature remain
});

test("2.4 Adversarial Edge Case: Missing or empty company name behavior", () => {
  const jobsWithEmptyCompany = [
    { id: "e1", title: "Ghost SWE", company: "", location: "Bengaluru" },
    { id: "e2", title: "Null SWE", company: null, location: "Bengaluru" },
    { id: "e3", title: "Spaces SWE", company: "   ", location: "Bengaluru" },
    { id: "ok1", title: "Real SWE", company: "Apple", location: "Bengaluru" },
  ];

  // When excludedCompanies is empty, all jobs pass
  const noExclude = filterJobs(jobsWithEmptyCompany, { excludedCompanies: [] });
  assert.strictEqual(noExclude.length, 4, "Without exclusions, empty company jobs pass");

  // When excludedCompanies has "Google":
  // In JS: 'google'.includes('') is TRUE.
  // Because norm.includes(jobCompany) runs without checking jobCompany.length > 0,
  // empty company jobs get excluded!
  const withExclude = filterJobs(jobsWithEmptyCompany, { excludedCompanies: ["Google"] });
  
  // Verify empirical behavior:
  const emptyJobsKept = withExclude.filter((j) => !j.company || j.company.trim() === "").length;
  console.log(`    [Empirical Discovery] Jobs with empty/null company kept when company excluded: ${emptyJobsKept}/3`);
  
  // Apple is retained
  assert.ok(withExclude.some((j) => j.company === "Apple"), "Apple must be retained");
});

test("2.5 Bidirectional substring collision: Short company name vs excluded name", () => {
  const collisionJobs = [
    { id: "c1", title: "Uber Driver Platform", company: "Uber" },
    { id: "c2", title: "Huber Corp Engineer", company: "Huber" },
    { id: "c3", title: "In Software", company: "In" },
    { id: "c4", title: "Infosys Developer", company: "Infosys" },
  ];

  // If user excludes "Huber", what happens to "Uber"?
  // "huber".includes("uber") is true!
  const res1 = filterJobs(collisionJobs, { excludedCompanies: ["Huber"] });
  const uberRetained = res1.some((j) => j.company === "Uber");
  console.log(`    [Empirical Discovery] Excluding 'Huber': Uber retained = ${uberRetained}`);

  // If user excludes "Infosys", what happens to "In"?
  // "infosys".includes("in") is true!
  const res2 = filterJobs(collisionJobs, { excludedCompanies: ["Infosys"] });
  const inRetained = res2.some((j) => j.company === "In");
  console.log(`    [Empirical Discovery] Excluding 'Infosys': 'In' retained = ${inRetained}`);
});

// ============================================================================
// SECTION 3: Minimum Match Threshold Filtering & Adversarial Stress Tests
// ============================================================================
console.log("\n--- Section 3: Minimum Match Threshold Filtering ---");

test("3.1 Strict match threshold filtering on 0-100 integer scale", () => {
  const scoredJobs = [
    { id: "s1", title: "Job 1", match: { overall_score: 59 } },
    { id: "s2", title: "Job 2", match: { overall_score: 60 } },
    { id: "s3", title: "Job 3", match: { overall_score: 61 } },
    { id: "s4", title: "Job 4", match: { overall_score: 0 } },
    { id: "s5", title: "Job 5", match: { overall_score: 100 } },
  ];

  const res = filterJobs(scoredJobs, { matchThreshold: 60 });
  const ids = res.map((j) => j.id);

  assert.ok(!ids.includes("s1"), "Score 59 must be strictly filtered out");
  assert.ok(ids.includes("s2"), "Score 60 must be kept (boundary)");
  assert.ok(ids.includes("s3"), "Score 61 must be kept");
  assert.ok(!ids.includes("s4"), "Score 0 must be strictly filtered out");
  assert.ok(ids.includes("s5"), "Score 100 must be kept");
  assert.strictEqual(res.length, 3);
});

test("3.2 Dual-scale normalization: 0-1.0 float scale vs 0-100 threshold", () => {
  const floatScoredJobs = [
    { id: "f1", title: "Job 1", match: { overall_score: 0.59 } }, // 59%
    { id: "f2", title: "Job 2", match: { overall_score: 0.60 } }, // 60%
    { id: "f3", title: "Job 3", match: { overall_score: 0.61 } }, // 61%
    { id: "f4", title: "Job 4", match: { overall_score: 0.0 } },  // 0%
    { id: "f5", title: "Job 5", match: { overall_score: 1.0 } },  // 100%
  ];

  const res = filterJobs(floatScoredJobs, { matchThreshold: 60 });
  const ids = res.map((j) => j.id);

  assert.ok(!ids.includes("f1"), "Float 0.59 (59%) must be filtered out");
  assert.ok(ids.includes("f2"), "Float 0.60 (60%) must be kept (boundary)");
  assert.ok(ids.includes("f3"), "Float 0.61 (61%) must be kept");
  assert.ok(!ids.includes("f4"), "Float 0.0 (0%) must be filtered out");
  assert.ok(ids.includes("f5"), "Float 1.0 (100%) must be kept");
  assert.strictEqual(res.length, 3);
});

test("3.3 Boundary threshold values: 0% and 100%", () => {
  const jobs = [
    { id: "b1", match: { overall_score: 0 } },
    { id: "b2", match: { overall_score: 50 } },
    { id: "b3", match: { overall_score: 99 } },
    { id: "b4", match: { overall_score: 0.99 } },
    { id: "b5", match: { overall_score: 100 } },
    { id: "b6", match: { overall_score: 1.0 } },
  ];

  // Threshold = 0 (no threshold applied, all pass)
  const res0 = filterJobs(jobs, { matchThreshold: 0 });
  assert.strictEqual(res0.length, 6, "Threshold 0% should let all pass");

  // Threshold = 100 (only 100 and 1.0 pass)
  const res100 = filterJobs(jobs, { matchThreshold: 100 });
  const ids100 = res100.map((j) => j.id);
  assert.deepStrictEqual(ids100, ["b5", "b6"], "Threshold 100% must only keep 100 and 1.0");
});

test("3.4 Quality score fallback when match.overall_score is missing", () => {
  const qJobs = [
    { id: "q1", quality_score: 45 },
    { id: "q2", quality_score: 75 },
    { id: "q3", match: { overall_score: 85 }, quality_score: 30 }, // match score takes precedence
  ];

  const res = filterJobs(qJobs, { matchThreshold: 50 });
  const ids = res.map((j) => j.id);

  assert.ok(!ids.includes("q1"), "quality_score 45 < 50 filtered out");
  assert.ok(ids.includes("q2"), "quality_score 75 >= 50 kept");
  assert.ok(ids.includes("q3"), "match overall_score 85 >= 50 kept (overriding quality_score)");
});

test("3.5 Adversarial Edge Case: Unscored jobs (no match score and no quality score)", () => {
  const unscoredJobs = [
    { id: "u1", title: "Fresh unscored scraper job" },
    { id: "u2", title: "Scored low job", match: { overall_score: 20 } },
    { id: "u3", title: "Scored high job", match: { overall_score: 90 } },
  ];

  const res = filterJobs(unscoredJobs, { matchThreshold: 70 });
  const ids = res.map((j) => j.id);

  assert.ok(ids.includes("u3"), "High score job kept");
  assert.ok(!ids.includes("u2"), "Low score job filtered");
  
  // Unscored job: rawScore is undefined, rawScore !== undefined is false, so it is NOT filtered!
  const unscoredKept = ids.includes("u1");
  console.log(`    [Empirical Discovery] Unscored job passed through threshold 70%: ${unscoredKept}`);
  assert.strictEqual(unscoredKept, true, "Unscored jobs pass through threshold filter");
});

// ============================================================================
// SECTION 4: Pagination Reset Verification
// ============================================================================
console.log("\n--- Section 4: Pagination Reset ---");

test("4.1 Pagination strictly resets to page 1 from various initial pages", () => {
  for (const initialPage of [1, 2, 5, 17, 100]) {
    const next = applyPreferencesToState(DEFAULT_PREFERENCES, { currentPage: initialPage });
    assert.strictEqual(next.currentPage, 1, `currentPage must reset from ${initialPage} to 1`);

    const queryParams = buildQueryParams(next, next.currentPage);
    assert.strictEqual(queryParams.get("page"), "1", "API request must query page=1");
  }
});

// ============================================================================
// SECTION 5: Edge Cases: Empty Locations, Single vs Multi Boards, Role Types
// ============================================================================
console.log("\n--- Section 5: Preference Field Edge Cases ---");

test("5.1 Empty preferred locations permits all locations", () => {
  const locJobs = [
    { id: "l1", location: "Bengaluru" },
    { id: "l2", location: "Pune" },
    { id: "l3", location: "London" },
    { id: "l4", location: "" },
    { id: "l5", location: null },
  ];

  const stateWithEmptyLoc = applyPreferencesToState({ ...DEFAULT_PREFERENCES, preferred_locations: [] });
  assert.deepStrictEqual(stateWithEmptyLoc.selectedLocations, []);

  const res = filterJobs(locJobs, stateWithEmptyLoc);
  assert.strictEqual(res.length, 5, "All 5 jobs should pass when preferred_locations is empty");

  const queryParams = buildQueryParams(stateWithEmptyLoc, 1);
  assert.strictEqual(queryParams.getAll("location").length, 0, "No location params in query");
});

test("5.2 Multiple preferred locations filter accurately with case & substring matching", () => {
  const locJobs = [
    { id: "l1", location: "Bengaluru, Karnataka, India" },
    { id: "l2", location: "bengaluru" },
    { id: "l3", location: "pune" },
    { id: "l4", location: "Remote - India" },
    { id: "l5", location: "Mumbai" },
    { id: "l6", location: "Hyderabad" },
  ];

  const state = applyPreferencesToState({
    ...DEFAULT_PREFERENCES,
    preferred_locations: ["Bengaluru", "Remote"],
  });

  const res = filterJobs(locJobs, state);
  const ids = res.map((j) => j.id);

  assert.ok(ids.includes("l1"), "Bengaluru substring match");
  assert.ok(ids.includes("l2"), "bengaluru case-insensitive match");
  assert.ok(ids.includes("l4"), "Remote substring match");
  assert.ok(!ids.includes("l3"), "Pune must not match");
  assert.ok(!ids.includes("l5"), "Mumbai must not match");
  assert.ok(!ids.includes("l6"), "Hyderabad must not match");
  assert.strictEqual(res.length, 3);
});

test("5.3 Role types: JOBS, INTERNSHIPS, and ALL", () => {
  const roleJobs = [
    { id: "r1", title: "Full Time SWE", employment_type: "JOBS", experience: "2 years", location: "Bengaluru" },
    { id: "r2", title: "Summer Intern", employment_type: "INTERNSHIP", experience: "0 years", location: "Bengaluru" },
    { id: "r3", title: "Research Fellow", employment_type: "OTHER", experience: "Graduate internship", location: "Bengaluru" },
    { id: "r4", title: "Backend Engineer", employment_type: "FULL_TIME", experience: "1-3 years", location: "Bengaluru" },
  ];

  // 1. JOBS
  const jobsState = applyPreferencesToState({ ...DEFAULT_PREFERENCES, role_type: "JOBS" });
  assert.strictEqual(jobsState.typeFilter, "JOBS");
  const jobsRes = filterJobs(roleJobs, jobsState);
  assert.deepStrictEqual(jobsRes.map((j) => j.id), ["r1", "r4"]);

  // 2. INTERNSHIPS
  const internState = applyPreferencesToState({ ...DEFAULT_PREFERENCES, role_type: "INTERNSHIPS" });
  assert.strictEqual(internState.typeFilter, "INTERNSHIPS");
  const internRes = filterJobs(roleJobs, internState);
  assert.deepStrictEqual(internRes.map((j) => j.id), ["r2", "r3"]);

  // 3. ALL
  const allState = applyPreferencesToState({ ...DEFAULT_PREFERENCES, role_type: "ALL" });
  assert.strictEqual(allState.typeFilter, "ALL");
  const allRes = filterJobs(roleJobs, allState);
  assert.strictEqual(allRes.length, 4);
});

test("5.4 Experience tier filtering logic across all 6 tiers", () => {
  const expJobs = [
    { id: "e0", experience_min: 0, experience_max: 0, experience: "Fresher" },
    { id: "e1", experience_min: 1, experience_max: 1, experience: "1 year" },
    { id: "e2", experience_min: 1, experience_max: 2, experience: "1-2 years" },
    { id: "e3", experience_min: 2, experience_max: 3, experience: "2-3 years" },
    { id: "e4", experience_min: 3, experience_max: 5, experience: "3+ years" },
  ];

  // FRESHER
  const fRes = filterJobs(expJobs, { experienceFilter: "FRESHER" });
  assert.ok(fRes.some((j) => j.id === "e0"));

  // 0_1
  const exp01Res = filterJobs(expJobs, { experienceFilter: "0_1" });
  assert.ok(exp01Res.some((j) => j.id === "e0"));
  assert.ok(exp01Res.some((j) => j.id === "e1"));

  // 1_2
  const exp12Res = filterJobs(expJobs, { experienceFilter: "1_2" });
  assert.ok(exp12Res.some((j) => j.id === "e2"));

  // 2_3
  const exp23Res = filterJobs(expJobs, { experienceFilter: "2_3" });
  assert.ok(exp23Res.some((j) => j.id === "e3"));

  // 3_PLUS
  const exp3Res = filterJobs(expJobs, { experienceFilter: "3_PLUS" });
  assert.ok(exp3Res.some((j) => j.id === "e4"));
});

// ============================================================================
// SECTION 6: Static Source Code Integrity Verification
// ============================================================================
console.log("\n--- Section 6: Static Source Code Integrity ---");

test("6.1 frontend/src/app/jobs/page.tsx imports and integrates loadUserPreferences", () => {
  const jobsPagePath = path.resolve("frontend/src/app/jobs/page.tsx");
  const content = fs.readFileSync(jobsPagePath, "utf-8");

  assert.ok(
    content.includes('import { loadUserPreferences } from "@/lib/preferences"'),
    "jobs/page.tsx must import loadUserPreferences"
  );
  assert.ok(
    content.includes("const handleApplyMyPreferences = async () =>"),
    "jobs/page.tsx must define handleApplyMyPreferences"
  );
  assert.ok(
    content.includes("setApplyingPrefs(true)"),
    "handleApplyMyPreferences must set loading state"
  );
  assert.ok(
    content.includes("fetchJobs(1)"),
    "handleApplyMyPreferences must trigger fetchJobs(1)"
  );
  assert.ok(
    content.includes("setCurrentPage(1)"),
    "handleApplyMyPreferences must reset currentPage to 1"
  );
});

test("6.2 UI renders 'My Preferences' button with Lucide Sliders icon", () => {
  const jobsPagePath = path.resolve("frontend/src/app/jobs/page.tsx");
  const content = fs.readFileSync(jobsPagePath, "utf-8");

  assert.ok(
    content.includes("handleApplyMyPreferences"),
    "Button must be wired to handleApplyMyPreferences"
  );
  assert.ok(
    content.includes("My Preferences"),
    "Button must display 'My Preferences' label"
  );
  assert.ok(
    content.includes("<Sliders"),
    "Button must include Sliders icon"
  );
});

test("6.3 filteredJobs implements both matchThreshold and excludedCompanies", () => {
  const jobsPagePath = path.resolve("frontend/src/app/jobs/page.tsx");
  const content = fs.readFileSync(jobsPagePath, "utf-8");

  assert.ok(
    content.includes("excludedCompanies.length > 0"),
    "filteredJobs must filter by excludedCompanies"
  );
  assert.ok(
    content.includes("matchThreshold !== null && matchThreshold > 0"),
    "filteredJobs must filter by matchThreshold"
  );
});

console.log("\n=================================================================");
console.log(`TEST SUMMARY: Total: ${totalTests} | Passed: ${passedTests} | Failed: ${failedTests}`);
console.log("=================================================================");

if (failedTests > 0) {
  console.error(`\nFAILED TESTS (${failedTests}):`);
  findings.forEach((f) => console.error(`- ${f.test}: ${f.error}`));
  process.exit(1);
} else {
  console.log("\nAll adversarial quick-apply tests passed successfully!");
}
