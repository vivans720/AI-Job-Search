import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        obsidian: {
          950: "#08090d",
          900: "#0d0f15",
          850: "#12151e",
          800: "#171b26",
          750: "#1e2332",
          700: "#272e42",
          600: "#3d4766",
        },
        signal: {
          emerald: "#10b981",
          amber: "#f59e0b",
          cyan: "#06b6d4",
          rose: "#f43f5e",
        },
      },
      fontFamily: {
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Roboto", "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Monaco", "Consolas", "monospace"],
      },
      boxShadow: {
        "surface-inset": "inset 0 1px 0 0 rgba(255, 255, 255, 0.07)",
        "surface-glow": "0 0 20px -4px rgba(16, 185, 129, 0.15)",
        "card-subtle": "0 2px 10px -2px rgba(0, 0, 0, 0.6)",
        "tactile": "0 1px 2px 0 rgba(0, 0, 0, 0.4), inset 0 1px 0 0 rgba(255, 255, 255, 0.06)",
      },
    },
  },
  plugins: [],
} satisfies Config;
