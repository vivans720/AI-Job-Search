import type { Metadata } from "next";
import "./globals.css";
import { Sidebar } from "@/components/Sidebar";

export const metadata: Metadata = {
  title: "AI Job Agent India",
  description: "Personal AI Job Discovery & Recommendation System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="bg-obsidian-950 text-zinc-100 min-h-[100dvh] flex antialiased selection:bg-emerald-500/20 selection:text-emerald-300">
        <Sidebar />
        <main className="flex-1 overflow-y-auto min-h-[100dvh] bg-gradient-to-b from-obsidian-950 via-obsidian-900/50 to-obsidian-950 p-5 md:p-8">
          <div className="max-w-[1400px] mx-auto w-full">{children}</div>
        </main>
      </body>
    </html>
  );
}
