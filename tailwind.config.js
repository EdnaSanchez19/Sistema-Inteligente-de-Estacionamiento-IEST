module.exports = {
  content: ["./src/**/*.{html,js,ts,jsx,tsx}"],
  corePlugins: { preflight: true },
  theme: {
    extend: {
      colors: { "colors-accents-orange": "var(--colors-accents-orange)" },
    },
  },
  plugins: [],
};
