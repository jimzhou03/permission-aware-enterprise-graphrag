import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Noto Sans SC", "Manrope", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "Consolas", "monospace"]
      },
      colors: {
        accent: {
          50: "#fff6ee",
          100: "#ffe8d5",
          200: "#ffd2ac",
          300: "#ffb680",
          400: "#ff9654",
          500: "#f77b2d",
          600: "#de651d",
          700: "#b74f16",
          800: "#923f17",
          900: "#773618"
        }
      }
    }
  },
  plugins: []
};

export default config;
