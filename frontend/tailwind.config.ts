import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f8f6f0",
        ink: "#17201c",
        pine: "#0f5f58",
        brass: "#b8792a",
        mist: "#e7ece8"
      },
      boxShadow: {
        panel: "0 14px 40px rgba(23, 32, 28, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
