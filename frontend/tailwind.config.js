/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"]
      },
      boxShadow: {
        soft: "0 12px 40px rgba(20, 24, 28, 0.08)"
      }
    }
  },
  plugins: []
};

