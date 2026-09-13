/**
 * Frontend Adversarial Stress-Test Suite for Preferences Configuration & Persistence (R1).
 * Tests validation, boundary clamping, corruption fallback, unicode preservation,
 * and localStorage dual-layer persistence resilience.
 */

import assert from "node:assert/strict";
import {
  validatePreferences,
  DEFAULT_PREFERENCES,
  FRESHNESS_OPTIONS,
  EXPERIENCE_OPTIONS,
  ROLE_TYPE_OPTIONS,
  SOURCE_BOARD_OPTIONS,
  getLocalPreferences,
  setLocalPreferences,
  loadUserPreferences,
  saveUserPreferences,
  PREFERENCES_STORAGE_KEY,
} from "../src/lib/preferences.ts";

let testsRun = 0;
let testsPassed = 0;

function runTest(name, fn) {
  testsRun++;
  try {
    fn();
    testsPassed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(err);
    throw err;
  }
}

async function runAsyncTest(name, fn) {
  testsRun++;
  try {
    await fn();
    testsPassed++;
    console.log(`  ✓ ${name}`);
  } catch (err) {
    console.error(`  ✗ ${name}`);
    console.error(err);
    throw err;
  }
}

console.log("\n=======================================================");
console.log("Running Frontend Adversarial Test Suite for Preferences");
console.log("=======================================================\n");

// -----------------------------------------------------------------------------
// 1. Freshness Boundary & Validation
// -----------------------------------------------------------------------------
console.log("Group 1: Freshness Boundary & Rejection/Fallback");

runTest("Preserves all valid discrete freshness values (1, 4, 8, 12, 16, 24)", () => {
  for (const h of [1, 4, 8, 12, 16, 24]) {
    const res = validatePreferences({ freshness_hours: h });
    assert.equal(res.freshness_hours, h);
  }
});

runTest("Normalizes string representation of valid freshness ('1', '4', '24')", () => {
  assert.equal(validatePreferences({ freshness_hours: "1" }).freshness_hours, 1);
  assert.equal(validatePreferences({ freshness_hours: "24" }).freshness_hours, 24);
  assert.equal(validatePreferences({ freshness_hours: "8" }).freshness_hours, 8);
});

runTest("Rejects invalid freshness values and falls back to default 24 (0, 25, -5, 100, etc.)", () => {
  const invalidValues = [0, 25, -5, -1, 100, 2, 3, 5, 7, 10, 48, 168, 999999, "invalid", null, undefined, NaN];
  for (const inv of invalidValues) {
    const res = validatePreferences({ freshness_hours: inv });
    assert.equal(
      res.freshness_hours,
      DEFAULT_PREFERENCES.freshness_hours,
      `Failed to fallback to default for freshness: ${inv}`
    );
  }
});

// -----------------------------------------------------------------------------
// 2. Match Threshold Boundary, Clamping & Validation
// -----------------------------------------------------------------------------
console.log("\nGroup 2: Match Threshold Boundaries & Clamping");

runTest("Preserves valid match threshold boundaries: 0% and 100%", () => {
  assert.equal(validatePreferences({ match_threshold: 0 }).match_threshold, 0);
  assert.equal(validatePreferences({ match_threshold: 100 }).match_threshold, 100);
  assert.equal(validatePreferences({ match_threshold: 50 }).match_threshold, 50);
});

runTest("Adversarial boundary: threshold 0 is not treated as falsy fallback", () => {
  const res = validatePreferences({ match_threshold: 0 });
  assert.equal(res.match_threshold, 0, "Threshold 0 was wrongly replaced by default 60!");
});

runTest("Clamps negative match threshold to 0 (-1, -5, -100)", () => {
  for (const neg of [-1, -5, -50, -100]) {
    assert.equal(validatePreferences({ match_threshold: neg }).match_threshold, 0);
  }
});

runTest("Clamps out-of-range match threshold to 100 (101, 150, 200, 100000)", () => {
  for (const over of [101, 150, 200, 100000]) {
    assert.equal(validatePreferences({ match_threshold: over }).match_threshold, 100);
  }
});

runTest("Rounds floating point thresholds cleanly (55.4 -> 55, 55.6 -> 56)", () => {
  assert.equal(validatePreferences({ match_threshold: 55.4 }).match_threshold, 55);
  assert.equal(validatePreferences({ match_threshold: 55.6 }).match_threshold, 56);
});

runTest("Falls back to default threshold (60) on non-numeric or NaN threshold", () => {
  for (const bad of [NaN, "high", null, undefined, {}, []]) {
    assert.equal(validatePreferences({ match_threshold: bad }).match_threshold, 60);
  }
});

// -----------------------------------------------------------------------------
// 3. Experience Levels: Tiers & Unknown Strings
// -----------------------------------------------------------------------------
console.log("\nGroup 3: Experience Level Tiers & Unknown Strings");

runTest("Preserves all valid experience tiers (FRESHER, 0_1, 1_2, 2_3, 3_PLUS, ALL)", () => {
  for (const tier of ["FRESHER", "0_1", "1_2", "2_3", "3_PLUS", "ALL"]) {
    assert.equal(validatePreferences({ experience_level: tier }).experience_level, tier);
  }
});

runTest("Normalizes lowercase and mixed-case experience level tiers", () => {
  assert.equal(validatePreferences({ experience_level: "fresher" }).experience_level, "FRESHER");
  assert.equal(validatePreferences({ experience_level: "0_1" }).experience_level, "0_1");
  assert.equal(validatePreferences({ experience_level: "3_plus" }).experience_level, "3_PLUS");
  assert.equal(validatePreferences({ experience_level: "FrEsHeR" }).experience_level, "FRESHER");
});

runTest("Rejects unknown experience level strings and falls back to 'ALL'", () => {
  const unknownTiers = ["SENIOR", "MID", "10_YEARS", "LEAD", "STAFF", "PRINCIPAL", "", "   ", "EXPERT", null, undefined, 123];
  for (const unk of unknownTiers) {
    assert.equal(
      validatePreferences({ experience_level: unk }).experience_level,
      DEFAULT_PREFERENCES.experience_level,
      `Failed to fallback to 'ALL' for experience_level: ${unk}`
    );
  }
});

// -----------------------------------------------------------------------------
// 4. Serialization: Empty Lists, Unicode, Long Lists & Injections
// -----------------------------------------------------------------------------
console.log("\nGroup 4: Lists, Unicode & Long Data Stress-Testing");

runTest("Handles empty arrays for preferred locations and excluded companies", () => {
  const res = validatePreferences({
    preferred_locations: [],
    excluded_companies: [],
  });
  assert.deepEqual(res.preferred_locations, []);
  assert.deepEqual(res.excluded_companies, []);
});

runTest("Trims whitespace and removes empty strings from locations and companies", () => {
  const res = validatePreferences({
    preferred_locations: ["  Bengaluru  ", "", "   ", "Remote  "],
    excluded_companies: ["  Revature  ", "", "Wipro"],
  });
  assert.deepEqual(res.preferred_locations, ["Bengaluru", "Remote"]);
  assert.deepEqual(res.excluded_companies, ["Revature", "Wipro"]);
});

runTest("Deduplicates identical entries in locations and companies", () => {
  const res = validatePreferences({
    preferred_locations: ["Bengaluru", "Bengaluru", "Remote", "Remote"],
    excluded_companies: ["SpamCorp", "SpamCorp"],
  });
  assert.deepEqual(res.preferred_locations, ["Bengaluru", "Remote"]);
  assert.deepEqual(res.excluded_companies, ["SpamCorp"]);
});

runTest("Preserves international unicode and emoji characters", () => {
  const unicodeLocs = ["München 🇩🇪", "東京 🇯🇵", "São Paulo 🇧🇷", "Zürich 🇨🇭", "القاهرة 🇪🇬"];
  const unicodeCos = ["Société Générale", "任天堂株式会社", "🚀 MoonCorp", "Häagen-Dazs"];
  const res = validatePreferences({
    preferred_locations: unicodeLocs,
    excluded_companies: unicodeCos,
  });
  assert.deepEqual(res.preferred_locations, unicodeLocs);
  assert.deepEqual(res.excluded_companies, unicodeCos);
});

runTest("Preserves malicious injection strings safely as string literals", () => {
  const injections = [
    "'; DROP TABLE preferences; --",
    "<script>alert(1)</script>",
    "\"}{\"json_inject\": true}",
  ];
  const res = validatePreferences({
    preferred_locations: [...injections, "\n\r\t"],
    excluded_companies: [...injections, "   "],
  });
  // The 3 valid injection strings are preserved verbatim; whitespace-only strings are stripped
  assert.equal(res.preferred_locations.length, 3);
  assert.equal(res.preferred_locations[0], injections[0]);
  assert.equal(res.preferred_locations[1], injections[1]);
  assert.equal(res.preferred_locations[2], injections[2]);
  assert.deepEqual(res.excluded_companies, injections);
});

runTest("Stress-tests 1,000 items in preferred_locations and excluded_companies", () => {
  const longLocs = Array.from({ length: 1000 }, (_, i) => `City_${i}`);
  const longCos = Array.from({ length: 1000 }, (_, i) => `Company_${i}`);
  const res = validatePreferences({
    preferred_locations: longLocs,
    excluded_companies: longCos,
  });
  assert.equal(res.preferred_locations.length, 1000);
  assert.equal(res.excluded_companies.length, 1000);
  assert.equal(res.preferred_locations[999], "City_999");
  assert.equal(res.excluded_companies[999], "Company_999");
});

// -----------------------------------------------------------------------------
// 5. Corrupted Data & Missing Payload Fallback Behavior
// -----------------------------------------------------------------------------
console.log("\nGroup 5: Corrupted & Missing Data Fallback");

runTest("Returns DEFAULT_PREFERENCES for null, undefined, primitive, or corrupted raw input", () => {
  for (const raw of [null, undefined, "", "corrupted-json-string", 12345, true, false]) {
    const res = validatePreferences(raw);
    assert.deepEqual(res, DEFAULT_PREFERENCES);
  }
});

runTest("Returns safe default structure when given empty object {}", () => {
  const res = validatePreferences({});
  assert.equal(res.freshness_hours, 24);
  assert.equal(res.experience_level, "ALL");
  assert.equal(res.match_threshold, 60);
  assert.deepEqual(res.preferred_locations, ["Bengaluru", "Remote"]);
  assert.equal(res.role_type, "ALL");
  assert.deepEqual(res.source_boards, ["LINKEDIN", "NAUKRI", "INTERNSHALA"]);
  assert.deepEqual(res.excluded_companies, []);
});

runTest("Sanitizes partially corrupted object with invalid types", () => {
  const corrupted = {
    freshness_hours: "not-a-number",
    experience_level: { object: "invalid" },
    match_threshold: [1, 2, 3],
    preferred_locations: "not-an-array",
    role_type: null,
    source_boards: ["INVALID_BOARD_XYZ"],
    excluded_companies: 9999,
  };
  const res = validatePreferences(corrupted);
  assert.equal(res.freshness_hours, 24);
  assert.equal(res.experience_level, "ALL");
  assert.equal(res.match_threshold, 60);
  assert.deepEqual(res.preferred_locations, ["Bengaluru", "Remote"]);
  assert.equal(res.role_type, "ALL");
  assert.deepEqual(res.source_boards, ["LINKEDIN", "NAUKRI", "INTERNSHALA"]);
  assert.deepEqual(res.excluded_companies, []);
});

// -----------------------------------------------------------------------------
// 6. LocalStorage Persistence & Error Resilience
// -----------------------------------------------------------------------------
console.log("\nGroup 6: LocalStorage Resilience & SSR Fallbacks");

runTest("getLocalPreferences returns DEFAULT_PREFERENCES when window is undefined", () => {
  const originalWindow = globalThis.window;
  try {
    delete globalThis.window;
    const res = getLocalPreferences();
    assert.deepEqual(res, DEFAULT_PREFERENCES);
  } finally {
    globalThis.window = originalWindow;
  }
});

runTest("getLocalPreferences gracefully handles corrupted JSON string in localStorage", () => {
  const mockStorage = new Map();
  mockStorage.set(PREFERENCES_STORAGE_KEY, "{corrupted_json_syntax: true, unclosed...");

  globalThis.window = {
    localStorage: {
      getItem: (key) => mockStorage.get(key) || null,
      setItem: (key, val) => mockStorage.set(key, val),
    },
  };

  const res = getLocalPreferences();
  assert.deepEqual(res, DEFAULT_PREFERENCES, "Did not fallback to DEFAULT_PREFERENCES on JSON.parse failure");
});

runTest("getLocalPreferences validates and normalizes corrupt/out-of-range values in localStorage", () => {
  const mockStorage = new Map();
  mockStorage.set(
    PREFERENCES_STORAGE_KEY,
    JSON.stringify({
      freshness_hours: 999,
      match_threshold: -50,
      experience_level: "ULTRA_SENIOR",
    })
  );

  globalThis.window = {
    localStorage: {
      getItem: (key) => mockStorage.get(key) || null,
      setItem: (key, val) => mockStorage.set(key, val),
    },
  };

  const res = getLocalPreferences();
  assert.equal(res.freshness_hours, 24);
  assert.equal(res.match_threshold, 0); // -50 clamped to 0
  assert.equal(res.experience_level, "ALL");
});

runTest("setLocalPreferences catches QuotaExceededError without crashing", () => {
  globalThis.window = {
    localStorage: {
      getItem: () => null,
      setItem: () => {
        throw new Error("QuotaExceededError: DOMException");
      },
    },
  };

  // Should not throw
  assert.doesNotThrow(() => {
    setLocalPreferences(DEFAULT_PREFERENCES);
  });
});

// -----------------------------------------------------------------------------
// 7. Dual-layer Persistence Network Failure Fallback
// -----------------------------------------------------------------------------
console.log("\nGroup 7: Dual-Layer Persistence Network Failure Fallback");

await runAsyncTest("loadUserPreferences falls back to local cache when backend fetch fails", async () => {
  const mockStorage = new Map();
  const cachedPrefs = {
    ...DEFAULT_PREFERENCES,
    freshness_hours: 8,
    match_threshold: 88,
  };
  mockStorage.set(PREFERENCES_STORAGE_KEY, JSON.stringify(cachedPrefs));

  globalThis.window = {
    localStorage: {
      getItem: (key) => mockStorage.get(key) || null,
      setItem: (key, val) => mockStorage.set(key, val),
    },
  };

  // Mock failing fetch
  globalThis.fetch = async () => {
    throw new Error("Failed to connect to backend: ECONNREFUSED");
  };

  const result = await loadUserPreferences();
  assert.equal(result.freshness_hours, 8);
  assert.equal(result.match_threshold, 88);
});

await runAsyncTest("saveUserPreferences saves to local cache and completes when backend fetch fails", async () => {
  const mockStorage = new Map();
  globalThis.window = {
    localStorage: {
      getItem: (key) => mockStorage.get(key) || null,
      setItem: (key, val) => mockStorage.set(key, val),
    },
  };

  globalThis.fetch = async () => {
    throw new Error("Backend server 500 Internal Server Error");
  };

  const newPrefs = {
    ...DEFAULT_PREFERENCES,
    freshness_hours: 16,
    experience_level: "2_3",
    match_threshold: 75,
  };

  const saved = await saveUserPreferences(newPrefs);
  assert.equal(saved.freshness_hours, 16);
  assert.equal(saved.experience_level, "2_3");
  assert.equal(saved.match_threshold, 75);

  // Check that localStorage cache was updated despite network failure
  const storedJson = mockStorage.get(PREFERENCES_STORAGE_KEY);
  assert.ok(storedJson);
  const parsed = JSON.parse(storedJson);
  assert.equal(parsed.freshness_hours, 16);
});

console.log("\n=======================================================");
console.log(`Summary: ${testsPassed} of ${testsRun} frontend adversarial tests passed!`);
console.log("=======================================================\n");
