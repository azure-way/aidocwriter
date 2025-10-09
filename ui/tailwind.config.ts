import type { Config } from "tailwindcss";
import scrollbarHide from "tailwind-scrollbar-hide";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        heading: ["Inter", "sans-serif"],
      },
      colors: {
        glass: {
          bg: "rgba(255,255,255,0.12)",
          border: "rgba(255,255,255,0.25)",
        },
      },
      boxShadow: {
        glass: "0 20px 40px rgba(15, 23, 42, 0.25)",
      },
    },
  },
  plugins: [scrollbarHide],
};

export default config;
