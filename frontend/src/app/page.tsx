"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Sparkles, Loader2 } from "lucide-react";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/jobs");
  }, [router]);

  return (
    <div className="min-h-screen bg-obsidian-950 flex flex-col items-center justify-center p-6 text-zinc-300">
      <div className="flex flex-col items-center gap-4 text-center">
        <div className="w-12 h-12 rounded-2xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 animate-pulse">
          <Sparkles className="w-6 h-6" />
        </div>
        <div>
          <h1 className="text-base font-semibold text-zinc-100">AI Job Agent</h1>
          <p className="text-xs text-zinc-500 mt-1">Initializing environment...</p>
        </div>
        <Loader2 className="w-4 h-4 animate-spin text-emerald-400 mt-2" />
      </div>
    </div>
  );
}