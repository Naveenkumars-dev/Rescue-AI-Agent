/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eef6ff", 100: "#d9ebff", 200: "#bcdcff", 300: "#8ec5ff",
          400: "#59a6ff", 500: "#3385f6", 600: "#1f6aeb", 700: "#1954d4",
          800: "#1a45ab", 900: "#1b3c87",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      animation: {
        "bounce-slow": "bounce 1.5s infinite",
      },
    },
  },
  plugins: [],
};
