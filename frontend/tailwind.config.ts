import type { Config } from 'tailwindcss';

const config: Config = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        metro: {
          purple: '#9333ea',
          green: '#10b981',
          yellow: '#facc15',
        },
        bmtc: {
          blue: '#2563eb',
          vajra: '#0284c7',
        },
      },
    },
  },
  plugins: [],
};

export default config;
