"use client";

import React from "react";

export type BadgeVariant =
  | "emerald"
  | "sky"
  | "purple"
  | "amber"
  | "rose"
  | "zinc"
  | "indigo"
  | "freshness"
  | "match-apply"
  | "match-consider"
  | "match-skip";

export type BadgeSize = "sm" | "md";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  isTabular?: boolean;
  children: React.ReactNode;
}

const variantStyles: Record<BadgeVariant, string> = {
  emerald: "bg-emerald-50 text-emerald-800 border-emerald-300 font-semibold",
  sky: "bg-sky-50 text-sky-800 border-sky-300 font-semibold",
  purple: "bg-purple-50 text-purple-800 border-purple-300 font-semibold",
  amber: "bg-amber-50 text-amber-900 border-amber-300 font-semibold",
  rose: "bg-rose-50 text-rose-800 border-rose-300 font-semibold",
  zinc: "bg-slate-100 text-slate-800 border-slate-300 font-semibold",
  indigo: "bg-indigo-50 text-indigo-800 border-indigo-300 font-semibold",
  freshness: "bg-emerald-50 text-emerald-800 border-emerald-300 font-mono font-semibold",
  "match-apply": "bg-emerald-50 text-emerald-800 border-emerald-300 font-bold",
  "match-consider": "bg-amber-50 text-amber-900 border-amber-300 font-bold",
  "match-skip": "bg-rose-50 text-rose-800 border-rose-300 font-bold",
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: "px-2 py-0.5 text-[11px] leading-tight",
  md: "px-2.5 py-1 text-xs leading-normal",
};

export function Badge({
  variant = "zinc",
  size = "md",
  isTabular = false,
  className = "",
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={`inline-flex items-center gap-1 font-semibold rounded-md border tracking-tight uppercase ${
        variantStyles[variant]
      } ${sizeStyles[size]} ${isTabular ? "font-tabular" : ""} ${className}`}
      {...props}
    >
      {children}
    </span>
  );
}

export function FreshnessBadge({ hours }: { hours: number | null | undefined }) {
  if (hours === null || hours === undefined) {
    return (
      <Badge variant="freshness" size="sm">
        Fresh
      </Badge>
    );
  }
  return (
    <Badge variant="freshness" size="sm" isTabular>
      {hours === 0 ? "Just Now" : `≤${hours}h Fresh`}
    </Badge>
  );
}

export function MatchBadge({
  score,
  recommendation,
}: {
  score: number;
  recommendation?: string;
}) {
  const rounded = Math.round(score);
  const rec = (recommendation || (score >= 70 ? "APPLY" : score >= 50 ? "CONSIDER" : "SKIP"))
    .toUpperCase()
    .replace("_", " ");

  const variant: BadgeVariant =
    rec.includes("APPLY")
      ? "match-apply"
      : rec.includes("CONSIDER")
      ? "match-consider"
      : "match-skip";

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-bold font-tabular border tracking-tight ${variantStyles[variant]}`}
    >
      <span>{rounded}%</span>
      <span>{rec}</span>
    </span>
  );
}
