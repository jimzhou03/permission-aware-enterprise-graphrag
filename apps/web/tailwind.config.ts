import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "sans-serif"],
        mono: ["IBM Plex Mono", "Consolas", "monospace"]
      },
      colors: {
        accent: {
          50: "#eef8f4",
          100: "#d6efe4",
          200: "#abdeca",
          300: "#7ac9ae",
          400: "#4dae91",
          500: "#349377",
          600: "#2d7863",
          700: "#285f50",
          800: "#244d42",
          900: "#203f36"
        }
      }
    }
  },
  plugins: []
};

export default config;

