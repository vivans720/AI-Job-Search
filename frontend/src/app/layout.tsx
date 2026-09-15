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
    <html lang="en">
      <body className="bg-[#f8f9fc] text-slate-900 min-h-[100dvh] flex antialiased selection:bg-blue-500/20 selection:text-blue-700">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:fixed focus:top-4 focus:left-4 z-50 px-4 py-2 bg-blue-600 text-white rounded-lg text-xs font-semibold shadow-lg focus:outline-none"
        >
          Skip to main content
        </a>
        <Sidebar />
        <main
          id="main-content"
          tabIndex={-1}
          className="flex-1 overflow-y-auto min-h-[100dvh] bg-[#f8f9fc] pt-16 lg:pt-6 p-4 sm:p-5 lg:p-6 focus:outline-none"
        >
          <div className="max-w-[1520px] mx-auto w-full">{children}</div>
        </main>
      </body>
    </html>

  );
}
