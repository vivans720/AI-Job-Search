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
          950: "#090a0f",
          900: "#0f1118",
          850: "#141722",
          800: "#1a1e2d",
          750: "#22273a",
          700: "#2d344d",
          600: "#444e73",
        },
      },
      boxShadow: {
        "surface-inset": "inset 0 1px 0 0 rgba(255, 255, 255, 0.07)",
        "surface-glow": "0 0 20px -5px rgba(16, 185, 129, 0.15)",
      },
    },
  },
  plugins: [],
} satisfies Config;
