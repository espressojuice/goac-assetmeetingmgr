import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        goac: {
          blue: "#1e40af",
          dark: "#111827",
        },
      },
    },
  },
  plugins: [],
};

export default config;
