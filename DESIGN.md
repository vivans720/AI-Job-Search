---
name: AI Job Agent India
description: Instrument-grade job discovery radar and triage console for early-career Indian tech talent.
colors:
  primary: "#10b981"
  primary-glow: "rgba(16, 185, 129, 0.15)"
  background: "#090a0f"
  surface-card: "#0f1118"
  surface-inset: "#141722"
  surface-elevated: "#1a1e2d"
  border-subtle: "rgba(255, 255, 255, 0.07)"
  border-active: "rgba(255, 255, 255, 0.14)"
  text-primary: "#f4f4f5"
  text-secondary: "#a1a1aa"
  text-tertiary: "#71717a"
  accent-sky: "#38bdf8"
  accent-purple: "#c084fc"
  accent-amber: "#fbbf24"
  accent-rose: "#f43f5e"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', 'Helvetica Neue', sans-serif"
    fontSize: "1.5rem"
    fontWeight: 700
    lineHeight: 1.2
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', 'Helvetica Neue', sans-serif"
    fontSize: "1.125rem"
    fontWeight: 600
    lineHeight: 1.3
    letterSpacing: "-0.015em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', 'Helvetica Neue', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', 'Helvetica Neue', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.011em"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Inter', 'Helvetica Neue', sans-serif"
    fontSize: "0.625rem"
    fontWeight: 600
    lineHeight: 1
    letterSpacing: "0.05em"
rounded:
  sm: "6px"
  md: "8px"
  lg: "12px"
  xl: "16px"
  full: "9999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "#ffffff"
    rounded: "{rounded.md}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "#059669"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.md}"
    padding: "8px 12px"
  card-base:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.xl}"
    padding: "16px"
  badge-freshness:
    backgroundColor: "rgba(16, 185, 129, 0.1)"
    textColor: "{colors.primary}"
    rounded: "{rounded.full}"
    padding: "2px 8px"
---

# Design System: AI Job Agent India

## Overview

**Creative North Star: "The Precision Radar"**

AI Job Agent India is built as an instrument-grade radar and high-velocity triage console for early-career software engineers in India. It treats job hunting not as a casual feed to browse, but as an active signal-detection mission where stale postings and noise are filtered out instantly, and every displayed opportunity is backed by transparent, deterministic data.

The aesthetic is anchored in an ultra-deep Obsidian dark space (`#090a0f`) punctuated by precise, luminous Emerald telemetry accents (`#10b981`) and fine hairline geometric structures (`rgba(255, 255, 255, 0.07)`). It balances compact density with scanability, using tabular typography for scores and timings to minimize cognitive load during triage.

**Key Characteristics:**
- **Instrument Density:** Information-dense layouts that let candidates evaluate 10+ signals (freshness age, match score, salary, location, tech stack, sources) in a single glance without overwhelming white space.
- **Luminous Telemetry:** Pure emerald highlights reserved specifically for fresh verified signals, active radar states, and high-confidence match metrics.
- **Glass & Obsidian Layering:** Subtle tonal steps from base space (`#090a0f`) up to interactive cards (`#0f1118`) with crisp inner highlight borders (`border-white/[0.07]`) rather than fuzzy drop shadows.

## Colors

The palette is tuned for prolonged nighttime screening with ultra-high contrast text and muted dark container surfaces.

### Primary
- **Radar Emerald** (`#10b981`): The primary signal color. Used strictly for verified freshness indicators, match score badges, active radar status, and primary action buttons.
- **Deep Emerald** (`#059669`): Hover and interactive active state for primary controls.

### Secondary
- **Telemetry Sky** (`#38bdf8`): Used for secondary platform telemetry (e.g. Internshala/LinkedIn source chips and transferable skill credits).
- **Signal Purple** (`#c084fc`): Denotes internships, educational qualifications, or special pipeline phases.

### Neutral
- **Deep Void Background** (`#090a0f`): The foundational background canvas (`obsidian-950`).
- **Surface Obsidian Base** (`#0f1118`): Standard background for cards, panels, and filter bars (`obsidian-900`).
- **Surface Inset / Well** (`#141722`): Recessed wells for search fields, dropdown inputs, and nested sub-panels (`obsidian-850`).
- **Surface Hover / Highlight** (`#1a1e2d`): Hover state for table rows, clickable list items, and action pills (`obsidian-800`).
- **Hairline Border** (`rgba(255, 255, 255, 0.07)`): The normative structural divider across all panels, drawers, and cards.
- **Text Primary** (`#f4f4f5`): High-clarity white-zinc text for titles, company names, and crucial metrics.
- **Text Secondary** (`#a1a1aa`): Muted zinc for descriptions, metadata labels, and timestamps.
- **Text Tertiary** (`#71717a`): De-emphasized zinc for micro-labels, dividers, and disabled states.

### Semantic Alerts
- **Warning Amber** (`#fbbf24`): Moderate match confidence (CONSIDER) and pending application states.
- **Destructive Rose** (`#f43f5e`): Missing critical skills, banned companies, and hard rejection actions.

### Named Rules
**The Rarity of Emerald Rule.** Radar Emerald is never used for decorative wallpaper or large surface fills. It is strictly reserved for high-signal telemetry: <= 24h freshness badges, strong match confirmation, and primary triage actions.
**The Ghost Border Rule.** Surfaces are demarcated with `1px border border-white/[0.07]` rather than opaque outlines or heavy shadows, maintaining a lightweight technical feel.

## Typography

**Display Font:** System Font Stack (`-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Inter", "Helvetica Neue", sans-serif`)
**Body Font:** System Font Stack with optical kerning
**Tabular Figures:** Dedicated `.font-tabular` (`font-variant-numeric: tabular-nums`) applied to scores, hours, percentages, and salaries.

**Character:** High-speed utilitarian clarity. Zero decorative typography; tight letter-spacing (`letter-spacing: -0.011em`) and OpenType feature settings (`"cv02", "cv03", "cv04", "cv11", "ss01"`) ensure clean rendering at compact 10px-12px sizes.

### Hierarchy
- **Display** (700 bold, `1.5rem` / `24px`, line-height 1.2): Section headers and dashboard hero titles (e.g. "Job Discovery Radar").
- **Headline** (600 semi-bold, `1.125rem` / `18px`, line-height 1.3): Modal drawer titles and primary job item titles.
- **Title** (600 semi-bold, `0.875rem` / `14px`, line-height 1.4): Card group headers and company names.
- **Body** (400 regular, `0.75rem` / `12px`, line-height 1.5): Standard job descriptions, location strings, and filter options.
- **Label** (600 semi-bold, uppercase, `0.625rem` / `10px`, letter-spacing `0.05em`): Telemetry category headers, freshness tags, source tags, and status pills.

### Named Rules
**The Tabular Score Rule.** Any dynamic numerical metric (match score percentage, age in hours, salary figures, count pills) must employ `.font-tabular` to prevent jitter during filtering and list re-renders.

## Layout

The layout uses a fixed desktop navigation sidebar (`w-64`) with a sticky viewport height (`h-[100dvh]`), framing a flexible main content canvas with standard horizontal constraints (`max-w-7xl`).

- **Base Rhythm:** 4px geometric scale (`4px`, `8px`, `12px`, `16px`, `24px`).
- **Card Spacing:** 12px (`gap-3`) to 16px (`gap-4`) vertical stacks between job cards in discovery feeds.
- **Filter Bar Container:** High-density command bar at the top of feeds grouping search inputs, location dropdowns, experience selectors, and quick-action chips.
- **Flyout Drawer:** Fixed slide-out drawer on the right (`w-full md:w-[600px] xl:w-[700px]`) for zero-context-loss deep dives into job descriptions and match explanations.

## Elevation & Depth

Surfaces are fundamentally layered flat at rest with structural depth established through lightness gradation (`#090a0f` -> `#0f1118` -> `#141722`) and 1px hairline inner borders.

### Shadow Vocabulary
- **Surface Inset:** `box-shadow: inset 0 1px 0 0 rgba(255, 255, 255, 0.07)` — Provides crisp top-edge lighting to dark cards and navigation pills.
- **Surface Glow:** `box-shadow: 0 0 20px -5px rgba(16, 185, 129, 0.15)` — Soft emerald beacon glow applied to active status pods and live radar indicators.

### Named Rules
**The Layered Obsidian Rule.** Depth is created through surface contrast and hairline borders, not blurry drop shadows. Drop shadows are strictly forbidden on base cards.

## Shapes

- **Base Radius:** 8px (`rounded-lg`) for controls, inputs, and list items.
- **Container Radius:** 16px (`rounded-2xl`) for primary cards, filter bars, and modal drawers.
- **Tag / Badge Radius:** 9999px (`rounded-full`) for match score pills and status chips; 4px–6px (`rounded`) for source tags.

## Components

### Buttons
- **Primary:** Background `bg-emerald-600` (`#059669`), text `text-white`, radius `rounded-lg` (8px), padding `8px 16px`. Hover transitions to `bg-emerald-500` with subtle `active:scale-[0.98]`.
- **Secondary / Ghost:** Background `bg-obsidian-950/60` with `border border-white/[0.08]`, text `text-zinc-300`. Hover brings `text-white` and `border-white/[0.18]`.
- **Destructive:** Background `bg-rose-500/10`, border `border-rose-500/20`, text `text-rose-400`. Used for reject, hide, and ban actions.

### Job Item Card
- **Structure:** Rounded container (`rounded-2xl`), border `border-white/[0.08]`, background `bg-obsidian-900/40 hover:bg-obsidian-900/70`.
- **Left Monogram:** 40x40px avatar box (`bg-obsidian-950 border border-white/[0.08]`) with 2-letter uppercase initials.
- **Metadata Line:** Muted 12px text separated by middle dots (`·`) displaying company, location, experience, salary, and age.

### Badges & Chips
- **Freshness Badge:** `bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-mono text-[10px]`.
- **Source Pill:** Monospaced 10px uppercase pill colored by origin platform (LinkedIn: blue, Naukri: indigo, Internshala: sky).
- **Match Score Pill:** Rounded full badge showing `XX% APPLY` or `XX% CONSIDER` with colored dot or border.

### Filter & Search Bar
- Unified dark bar (`bg-obsidian-900/70`) with subtle backdrop blur (`backdrop-blur-md`), embedded search input, and multi-select pill containers.

## Do's and Don'ts

### Do:
- **Do** use `.font-tabular` for all scores, hours, timestamps, and currency amounts.
- **Do** use `border-white/[0.07]` for structural borders across dark surfaces.
- **Do** reserve emerald (`#10b981`) for genuine freshness, success, and high-affinity matches.
- **Do** keep job actions (Details, Save, Reject) accessible directly on the card without hovering.

### Don't:
- **Don't** use heavy dark drop shadows that muddy the dark obsidian background.
- **Don't** use generic saturated blues or purples for primary signals; emerald is the sole system accent.
- **Don't** drop or hide low-matching jobs without clear score transparency and candidate control.
- **Don't** use decorative non-functional icons; every icon must communicate concrete state or action.
