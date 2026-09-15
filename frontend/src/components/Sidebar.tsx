"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  Bookmark,
  Settings,
  Sparkles,
  ShieldCheck,
  User,
  Cpu,
  Sliders,
} from "lucide-react";

interface NavItem {
  href: string;
  label: string;
  icon: React.ComponentType<{ className?: string }>;
}

interface NavGroup {
  title: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    title: "INTELLIGENCE",
    items: [
      { href: "/jobs", label: "Job Discovery", icon: Compass },
    ],
  },
  {
    title: "APPLICATIONS",
    items: [
      { href: "/saved", label: "Saved Jobs", icon: Bookmark },
    ],
  },
  {
    title: "CANDIDATE & SETUP",
    items: [
      { href: "/profile", label: "Profile", icon: User },
      { href: "/preferences", label: "Preferences", icon: Sliders },
      { href: "/ai-provider", label: "AI Provider", icon: Cpu },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <>
      {/* Mobile Topbar Navigation Trigger */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-40 h-14 bg-white/95 backdrop-blur-xl border-b border-slate-200 flex items-center justify-between px-4">
        <div className="flex items-center gap-2.5">
          <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-emerald-50 border border-emerald-200 text-emerald-600 shadow-xs">
            <Sparkles className="w-4 h-4" />
          </div>
          <span className="font-semibold text-sm text-slate-900">AI Job Agent</span>
          <span className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
            IND
          </span>
        </div>
        <button
          onClick={() => setMobileOpen((prev) => !prev)}
          className="p-2 rounded-lg bg-white border border-slate-200 text-slate-600 hover:text-slate-900 hover:bg-slate-50 shadow-xs"
          aria-label="Toggle navigation menu"
        >
          <Sliders className="w-4 h-4" />
        </button>
      </div>

      {/* Mobile Backdrop Overlay */}
      {mobileOpen && (
        <div
          className="lg:hidden fixed inset-0 z-40 bg-black/60 backdrop-blur-sm"
          onClick={() => setMobileOpen(false)}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed lg:sticky top-0 bottom-0 left-0 z-50 w-60 border-r border-slate-200/80 bg-white flex flex-col h-[100dvh] text-slate-600 transition-transform duration-200 ease-in-out ${
          mobileOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
        }`}
      >
        {/* Brand Header */}
        <div className="p-4 border-b border-slate-100 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="relative flex items-center justify-center w-8 h-8 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 text-white shadow-sm">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h1 className="font-bold text-xs tracking-tight text-slate-900 uppercase">AI Job Agent</h1>
                <span className="px-1.5 py-0.2 rounded-full text-[9px] font-semibold bg-emerald-50 text-emerald-600 border border-emerald-200/60">
                  IND
                </span>
              </div>
              <p className="text-[10px] text-slate-400 font-medium">Tech Radar 24h</p>
            </div>
          </div>
          <button
            onClick={() => setMobileOpen(false)}
            className="lg:hidden p-1.5 text-slate-400 hover:text-slate-700"
          >
            ✕
          </button>
        </div>

        {/* Navigation Groups */}
        <nav className="flex-1 p-3 space-y-5 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.title} className="space-y-1">
              <div className="px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-slate-500">
                {group.title}
              </div>
              {group.items.map((item) => {
                const Icon = item.icon;
                const isActive =
                  pathname === item.href ||
                  (item.href === "/jobs" && pathname === "/");

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={() => setMobileOpen(false)}
                    className={`group relative flex items-center justify-between px-3 py-2.5 rounded-xl text-sm font-medium transition-all duration-150 ${
                      isActive
                        ? "bg-emerald-50 text-emerald-900 font-semibold shadow-xs border border-emerald-200/80"
                        : "text-slate-700 hover:text-slate-900 hover:bg-slate-100/80"
                    }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={`w-4 h-4 transition-colors ${
                          isActive
                            ? "text-emerald-700"
                            : "text-slate-500 group-hover:text-slate-700"
                        }`}
                      />
                      <span>{item.label}</span>
                    </div>

                    {isActive && (
                      <span className="w-1.5 h-1.5 rounded-full bg-emerald-600" />
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        {/* Footer Status Pod & Promo Banner */}
        <div className="p-3 border-t border-slate-200 bg-slate-50/80 space-y-2.5 shrink-0">
          {/* Live Engine Card */}
          <div className="p-2.5 rounded-xl bg-white border border-slate-200 shadow-xs space-y-1.5">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-1.5 text-slate-900 font-bold">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
                </span>
                <span>Live Engine</span>
              </div>
              <span className="text-[11px] text-slate-500 font-mono font-medium">IST / 24h</span>
            </div>

            {/* Subtle waveform graphic */}
            <div className="h-4 flex items-center justify-center gap-0.5 opacity-80">
              <span className="w-0.5 h-1.5 bg-emerald-500 rounded-full animate-pulse" />
              <span className="w-0.5 h-2.5 bg-emerald-600 rounded-full" />
              <span className="w-0.5 h-3.5 bg-emerald-700 rounded-full animate-pulse" />
              <span className="w-0.5 h-2 bg-emerald-600 rounded-full" />
              <span className="w-0.5 h-1 bg-emerald-500 rounded-full" />
              <span className="w-0.5 h-2.5 bg-emerald-600 rounded-full" />
              <span className="text-[10px] text-emerald-800 font-medium ml-1">Strict manual mode</span>
            </div>

            <div className="flex items-center justify-between pt-1.5 border-t border-slate-100 text-[11px] text-slate-500">
              <span className="flex items-center gap-1 text-slate-700 font-medium">
                <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" /> prod
              </span>
              <div className="flex items-center gap-2">
                <Link href="/settings" className="hover:text-slate-900 transition-colors font-medium">Privacy</Link>
                <span>·</span>
                <Link href="/settings" className="hover:text-slate-900 transition-colors font-medium">Docs</Link>
              </div>
            </div>
          </div>

          {/* Let AI find better opportunities promo banner */}
          <div className="p-3 rounded-xl bg-gradient-to-br from-emerald-50/80 via-teal-50/40 to-slate-100 border border-emerald-200/60 text-xs text-slate-800 relative overflow-hidden">
            <p className="font-bold text-slate-900 leading-tight">Precision Radar</p>
            <p className="text-[11px] text-slate-600 mt-0.5">Scoring fresh tech opportunities</p>
          </div>
        </div>
      </aside>


    </>
  );
}
