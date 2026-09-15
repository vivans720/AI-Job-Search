"use client";

import React from "react";

export interface PageHeaderProps {
  badgeLabel?: string;
  badgeMeta?: string;
  title: string;
  description: string;
  actions?: React.ReactNode;
}

export function PageHeader({
  badgeLabel,
  badgeMeta,
  title,
  description,
  actions,
}: PageHeaderProps) {
  return (
    <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-5 border-b border-slate-200">
      <div className="space-y-1">
        {(badgeLabel || badgeMeta) && (
          <div className="flex items-center gap-2 mb-1.5">
            {badgeLabel && (
              <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-emerald-50 text-emerald-800 border border-emerald-300 font-mono tracking-wider uppercase">
                {badgeLabel}
              </span>
            )}
            {badgeLabel && badgeMeta && <span className="text-xs text-slate-400">/</span>}
            {badgeMeta && <span className="text-xs text-slate-600 font-mono font-medium">{badgeMeta}</span>}
          </div>
        )}
        <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900">{title}</h1>
        <p className="text-sm text-slate-600 max-w-2xl leading-relaxed font-normal">{description}</p>
      </div>

      {actions && <div className="flex items-center gap-2 shrink-0 flex-wrap">{actions}</div>}
    </div>
  );
}
