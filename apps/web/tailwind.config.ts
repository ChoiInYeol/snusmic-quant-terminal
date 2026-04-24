import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        ink: '#18242e',
        panel: '#fbfcfd',
        line: '#d5dee8',
        gain: '#047857',
        loss: '#b91c1c',
        accent: '#2454a6',
      },
      boxShadow: {
        terminal: '0 18px 50px rgba(24, 36, 46, 0.08)',
      },
    },
  },
  plugins: [],
};

export default config;
