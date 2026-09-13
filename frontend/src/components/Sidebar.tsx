"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Compass,
  Bookmark,
  Settings,
  Sparkles,
  ShieldCheck,
  User,
  FileText,
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
      { href: "/resume", label: "Resume", icon: FileText },
      { href: "/ai-provider", label: "AI Provider", icon: Cpu },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-64 border-r border-white/[0.07] bg-obsidian-950/80 backdrop-blur-xl flex flex-col h-[100dvh] sticky top-0 text-zinc-300 z-30">
      {/* Brand Header */}
      <div className="p-5 border-b border-white/[0.07]">
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-9 h-9 rounded-xl bg-gradient-to-br from-emerald-500/20 to-emerald-950/40 border border-emerald-500/30 text-emerald-400 shadow-sm shadow-emerald-950">
            <Sparkles className="w-4 h-4" />
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400 animate-ping opacity-75" />
            <span className="absolute -top-0.5 -right-0.5 w-2 h-2 rounded-full bg-emerald-400" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h1 className="font-semibold text-sm tracking-tight text-zinc-100">AI Job Agent</h1>
              <span className="px-1.5 py-0.5 rounded text-[9px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                IND
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 font-medium">India Tech Radar</p>
          </div>
        </div>
      </div>

      {/* Navigation Groups */}
      <nav className="flex-1 p-3 space-y-6 overflow-y-auto">
        {navGroups.map((group) => (
          <div key={group.title} className="space-y-1">
            <div className="px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-zinc-500">
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
                  className={`group relative flex items-center justify-between px-3 py-2 rounded-lg text-xs font-medium transition-all duration-150 ${
                    isActive
                      ? "bg-white/[0.06] text-zinc-100 shadow-surface-inset border border-white/[0.08]"
                      : "text-zinc-400 hover:text-zinc-200 hover:bg-white/[0.03]"
                  }`}
                >
                  <div className="flex items-center gap-2.5">
                    <Icon
                      className={`w-4 h-4 transition-colors ${
                        isActive
                          ? "text-emerald-400"
                          : "text-zinc-500 group-hover:text-zinc-300"
                      }`}
                    />
                    <span>{item.label}</span>
                  </div>

                  {isActive && (
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400" />
                  )}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer Status Pod */}
      <div className="p-3.5 border-t border-white/[0.07] bg-obsidian-900/40">
        <div className="p-2.5 rounded-lg bg-obsidian-950 border border-white/[0.06] space-y-1.5">
          <div className="flex items-center justify-between text-[11px]">
            <div className="flex items-center gap-1.5 text-zinc-300 font-medium">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>24h Radar Active</span>
            </div>
            <span className="text-[10px] text-zinc-500 font-mono">IST</span>
          </div>

          <div className="flex items-center gap-1.5 text-[10px] text-zinc-400">
            <ShieldCheck className="w-3 h-3 text-emerald-400 shrink-0" />
            <span>Strict manual-apply mode</span>
          </div>
        </div>
      </div>
    </aside>
  );
}
