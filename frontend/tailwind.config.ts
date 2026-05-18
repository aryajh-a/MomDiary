import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        feed: {
          50: "#fff7ed",
          500: "#f97316",
          700: "#c2410c",
        },
        sleep: {
          50: "#eef2ff",
          500: "#6366f1",
          700: "#4338ca",
        },
        poop: {
          50: "#fefce8",
          500: "#ca8a04",
          700: "#854d0e",
        },
        appointment: {
          50: "#ecfdf5",
          500: "#10b981",
          700: "#047857",
        },
      },
      fontFamily: {
        sans: [
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};

export default config;
