/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Intel-Terminal palette — driven by CSS variables so the values
        // swap between dark and light themes via the class on <html>.
        // See index.css for the bindings.
        base:        "var(--color-base)",
        surface:     "var(--color-surface)",
        panel:       "var(--color-panel)",
        card:        "var(--color-card)",
        "card-hover":"var(--color-card-hover)",
        rim:         "var(--color-rim)",
        "rim-bright":"var(--color-rim-bright)",
        accent:      "var(--color-accent)",
        "accent-ink":"var(--color-accent-ink)",
        brand:       "rgb(var(--color-brand) / <alpha-value>)",
      },
      fontFamily: {
        sans:     ['"Inter"', "system-ui", "sans-serif"],
        mono:     ['"JetBrains Mono"', "monospace"],
        headline: ['"Newsreader"', "Georgia", "serif"],
      },
      animation: {
        "fade-in":  "fadeIn 0.2s ease-out",
        pulse_slow: "pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        // `animate-blink` is defined in index.css to avoid a tailwind-config
        // restart cycle when iterating on the timing.
      },
      keyframes: {
        fadeIn: {
          "0%":   { opacity: "0", transform: "translateY(4px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
