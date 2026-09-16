---
name: AI Job Agent India
description: Clean, high-clarity job discovery radar and triage console for early-career Indian tech talent.
colors:
  primary: "#059669"
  primary-hover: "#047857"
  primary-subtle: "#ecfdf5"
  background: "#f8f9fc"
  surface-card: "#ffffff"
  surface-well: "#f1f5f9"
  surface-hover: "#f8fafc"
  border-hairline: "rgba(226, 232, 240, 0.9)"
  border-hairline-strong: "rgba(203, 213, 225, 0.8)"
  text-primary: "#0f172a"
  text-secondary: "#475569"
  text-tertiary: "#94a3b8"
  signal-emerald: "#059669"
  signal-amber: "#b45309"
  signal-rose: "#be123c"
  signal-sky: "#0284c7"
  signal-indigo: "#4338ca"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1.875rem"
    fontWeight: 800
    lineHeight: 1.2
    letterSpacing: "-0.025em"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 700
    lineHeight: 1.3
    letterSpacing: "-0.02em"
  title:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "-0.01em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.011em"
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.025em"
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
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  button-primary-hover:
    backgroundColor: "{colors.primary-hover}"
  button-secondary:
    backgroundColor: "#ffffff"
    textColor: "{colors.text-primary}"
    rounded: "{rounded.lg}"
    padding: "8px 16px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.text-secondary}"
    rounded: "{rounded.lg}"
    padding: "8px 12px"
  card-base:
    backgroundColor: "{colors.surface-card}"
    rounded: "{rounded.xl}"
    padding: "16px sm:20px"
  badge-freshness:
    backgroundColor: "{colors.primary-subtle}"
    textColor: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: "2px 8px"
---

# Design System: AI Job Agent India

## Overview

**Creative North Star: "Precision Daylight Radar"**

AI Job Agent India is an instrument-grade job discovery radar and application triage cockpit designed for early-career tech talent in India. It cuts through noise, ghost jobs, and stale postings with deterministic 24-hour freshness verification and transparent skill-matching breakdown.

The visual system uses a luminous, high-contrast light theme (`#f8f9fc` background with crisp `#ffffff` cards), deep slate typography (`#0f172a`), emerald signal telemetry (`#059669`), and hairline structural borders (`border-slate-200/90`).

## Colors

### Primary & Telemetry
- **Primary Emerald** (`#059669`): Verified freshness badges, primary actions, positive alignment.
- **Deep Emerald Hover** (`#047857`): Interactive button and link hover states.
- **Subtle Emerald Tint** (`#ecfdf5`): Freshness and apply match badge backgrounds.

### Semantic Status
- **Warning Amber** (`#b45309` text, `#fef3c7` bg): Moderate match confidence (`CONSIDER`) and pending review.
- **Destructive Rose** (`#be123c` text, `#ffe4e6` bg): Rejection actions, missing mandatory skills, and exclusions.
- **Platform Sky & Indigo** (`#0284c7`, `#4338ca`): Source tags (LinkedIn, Naukri, Internshala).

### Neutral & Surfaces
- **Canvas Background** (`#f8f9fc`): Base page backdrop.
- **Surface Cards** (`#ffffff`): Elevated content blocks, drawers, and modals.
- **Muted Well** (`#f1f5f9` / `#f8fafc`): Inset toolbars, tab wells, and monogram containers.
- **Structural Borders** (`rgba(226, 232, 240, 0.9)`): Hairline demarcations.

## Typography

- **System Stack:** `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif`
- **Monospace Stack:** `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace`
- **Tabular Numerics:** `.font-tabular` (`font-variant-numeric: tabular-nums`) strictly required for match percentages, salary, counts, and hours.

## Layout & Rhythm

- **Sidebar Navigation:** Fixed desktop sidebar (`w-60`), sticky full viewport height (`100dvh`).
- **Main Container:** `max-w-[1520px] mx-auto` with fluid responsive padding (`p-4 sm:p-5 lg:p-6`).
- **Grid Scale:** 4px geometric intervals (`4px`, `8px`, `12px`, `16px`, `24px`, `32px`).

## Elevation & Depth

- Depth is achieved via hairline border contrast (`border-slate-200/90`) and subtle contact shadows (`shadow-xs`, `shadow-card-subtle`), never murky drop shadows.
- Hover elevation: `shadow-card-hover` with 150ms cubic transition.

## Shapes

- **Inputs & Standard Buttons:** `rounded-xl` (12px)
- **Cards & Filter Bars:** `rounded-2xl` (16px)
- **Chips & Badges:** `rounded-md` (6px) or `rounded-full` for score pills.

## Components

- **Button:** `Button.tsx` supports `primary`, `secondary`, `ghost`, `destructive`, `outline` with loading states.
- **Badge:** `Badge.tsx` supports semantic badges, `FreshnessBadge`, and `MatchBadge`.
- **Card:** `Card.tsx` supports `surface`, `interactive`, and `well` containers.
- **Input:** `Input.tsx` provides accessible, standardized form inputs with icon support.
- **Tabs:** `Tabs.tsx` provides segmented pill controls with tabular counter pills.
- **PageHeader:** `PageHeader.tsx` provides standardized section header hierarchy.

## Do's and Don'ts

### Do:
- Always use `.font-tabular` on scores, percentages, currency, and timestamps.
- Use `Button`, `Badge`, `Card`, `Input`, `Tabs`, and `PageHeader` from `@/components/ui`.
- Keep job actions visible and accessible directly on cards without hiding behind hover.

### Don't:
- Don't use dark obsidian backgrounds; the project is standardized on the high-contrast light theme.
- Don't invent custom ad-hoc button or badge classes when UI primitives exist.
- Don't hide low-matching jobs silently without candidate transparency.
