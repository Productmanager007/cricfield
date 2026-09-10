import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0D1117",
        panel: "#161B22",
        panel2: "#1C232C",
        border: "#242C38",
        text: "#E6EDF3",
        muted: "#8B949E",
        faint: "#5A636D",
        amber: "#F0A202",
        positive: "#3FB950",
        negative: "#F85149",
      },
      fontFamily: {
        sans: ['"Inter Variable"', "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
